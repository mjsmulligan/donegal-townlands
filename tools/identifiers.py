"""Generate and validate permanent Donegal Townlands identifiers.

The registry is append-only. Its committed Git version is the baseline:
existing rows may not be changed or removed. Add new rows only with this tool.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import pathlib
import re
import subprocess
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTRY_RELATIVE = pathlib.Path("data/research/identifier_registry.csv")
FIELDS = ["id", "type", "status", "successor", "date", "reason"]
KINDS = {"person", "family", "property", "place", "source-record", "assertion"}
STATUSES = {"active", "merged", "split", "retired"}
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def new_identifier(kind: str, manual_place: bool = False) -> str:
    """Return a UUID v4, optionally in the manual-place namespace."""
    if kind not in KINDS:
        raise ValueError(f"unknown identifier type: {kind}")
    value = str(uuid.uuid4())
    return f"dt-place:{value}" if manual_place else value


def is_valid_identifier(value: str, kind: str) -> bool:
    if kind == "place" and value.startswith("dt-place:"):
        return bool(UUID_RE.fullmatch(value.removeprefix("dt-place:")))
    return bool(UUID_RE.fullmatch(value))


def parse_registry(text: str) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    try:
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames != FIELDS:
            return [], [f"registry header must be: {','.join(FIELDS)}"]
        rows = list(reader)
    except (csv.Error, UnicodeError) as exc:
        return [], [f"cannot parse registry CSV: {exc}"]

    seen: set[str] = set()
    for line_no, row in enumerate(rows, start=2):
        if None in row or any(row.get(field) is None for field in FIELDS):
            errors.append(f"registry line {line_no}: malformed row")
            continue
        value = row["id"].strip()
        kind = row["type"].strip()
        status = row["status"].strip()
        if not value:
            errors.append(f"registry line {line_no}: empty id")
        seen.add(value)

        if kind not in KINDS:
            errors.append(f"registry line {line_no}: invalid type {kind!r}")
        elif not is_valid_identifier(value, kind):
            errors.append(f"registry line {line_no}: invalid UUID v4 identifier {value!r}")

        if status not in STATUSES:
            errors.append(f"registry line {line_no}: invalid status {status!r}")
        if not row["date"].strip():
            errors.append(f"registry line {line_no}: date is required")

    # Repeated IDs are permitted only as appended lifecycle events. UUIDs
    # themselves remain unique: a repeated ID is never a new identifier.
    histories: dict[str, list[tuple[int, dict[str, str]]]] = {}
    for line_no, row in enumerate(rows, start=2):
        histories.setdefault(row.get("id", "").strip(), []).append((line_no, row))

    for value, history in histories.items():
        previous_status = None
        previous_type = None
        previous_date = None
        for line_no, row in history:
            kind = row.get("type", "").strip()
            status = row.get("status", "").strip()
            date_value = row.get("date", "").strip()
            if previous_type is not None and kind != previous_type:
                errors.append(f"registry line {line_no}: type cannot change for {value}")
            if previous_status is None and status != "active":
                errors.append(f"registry line {line_no}: first entry for {value} must be active")
            elif previous_status is not None:
                if previous_status != "active":
                    errors.append(f"registry line {line_no}: terminal status cannot be changed")
                if status == "active":
                    errors.append(f"registry line {line_no}: lifecycle entry must change status")
                if previous_date and date_value < previous_date:
                    errors.append(f"registry line {line_no}: lifecycle date moves backwards")
            previous_type = kind
            previous_status = status
            previous_date = date_value

            successors = [
                item.strip() for item in row.get("successor", "").split(";") if item.strip()
            ]
            if value in successors:
                errors.append(f"registry line {line_no}: an id cannot succeed itself")
            if status == "active" and successors:
                errors.append(f"registry line {line_no}: active id cannot have a successor")
            if status in {"merged", "split", "retired"}:
                if not successors:
                    errors.append(f"registry line {line_no}: {status} id requires a successor")
                if "DECISIONS.md" not in row.get("reason", ""):
                    errors.append(
                        f"registry line {line_no}: {status} id reason must point to DECISIONS.md"
                    )

    ids = set(histories)
    for line_no, row in enumerate(rows, start=2):
        for successor in (x.strip() for x in row.get("successor", "").split(";")):
            if successor and successor not in ids:
                errors.append(
                    f"registry line {line_no}: successor {successor!r} is not registered"
                )
    return rows, errors


def validate_append_only(current: bytes, baseline: bytes) -> list[str]:
    """Require the committed baseline to remain an exact byte prefix."""
    if not baseline:
        return ["committed registry baseline is empty or unavailable"]
    if not baseline.endswith(b"\n"):
        return ["committed registry baseline does not end with a newline"]
    if not current.startswith(baseline):
        return ["registry is not append-only: a committed line was changed or removed"]
    return []


def committed_registry(root: pathlib.Path = ROOT) -> tuple[bytes | None, str | None]:
    """Read the registry from HEAD. The initial header must be committed first."""
    relative = REGISTRY_RELATIVE.as_posix()
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "show", f"HEAD:{relative}"],
            check=True, capture_output=True,
        )
        return result.stdout, None
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return None, (
            "no committed registry baseline found. Commit the header-only "
            f"{relative} before registering the first entity."
        )


def validate_registry_file(root: pathlib.Path = ROOT) -> list[str]:
    path = root / REGISTRY_RELATIVE
    if not path.exists():
        return [f"missing registry: {REGISTRY_RELATIVE.as_posix()}"]
    current = path.read_bytes()
    try:
        text = current.decode("utf-8-sig")
    except UnicodeDecodeError:
        return ["registry is not valid UTF-8"]
    _, errors = parse_registry(text)
    baseline, baseline_error = committed_registry(root)
    if baseline_error:
        errors.append(baseline_error)
    else:
        errors.extend(validate_append_only(current, baseline))
    return errors


def append_identifier(
    kind: str, reason: str, root: pathlib.Path = ROOT, manual_place: bool = False
) -> str:
    if not reason.strip():
        raise ValueError("a reason is required")
    if manual_place and kind != "place":
        raise ValueError("--manual-place is valid only with --type place")
    errors = validate_registry_file(root)
    if errors:
        raise ValueError("registry validation failed:\n" + "\n".join(errors))
    value = new_identifier(kind, manual_place)
    path = root / REGISTRY_RELATIVE
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writerow({
            "id": value,
            "type": kind,
            "status": "active",
            "successor": "",
            "date": dt.date.today().isoformat(),
            "reason": reason.strip(),
        })
    return value


def append_transition(
    identifier: str, status: str, successor: str, reason: str,
    root: pathlib.Path = ROOT
) -> None:
    if status not in {"merged", "split", "retired"}:
        raise ValueError("transition status must be merged, split or retired")
    if not successor.strip():
        raise ValueError("at least one successor is required")
    if "DECISIONS.md" not in reason:
        raise ValueError("reason must point to the relevant entry in DECISIONS.md")
    errors = validate_registry_file(root)
    if errors:
        raise ValueError("registry validation failed:\\n" + "\\n".join(errors))

    path = root / REGISTRY_RELATIVE
    rows, parse_errors = parse_registry(path.read_text(encoding="utf-8-sig"))
    if parse_errors:
        raise ValueError("registry validation failed:\\n" + "\\n".join(parse_errors))
    history = [row for row in rows if row["id"] == identifier]
    if not history:
        raise ValueError(f"identifier is not registered: {identifier}")
    if history[-1]["status"] != "active":
        raise ValueError("only an active identifier can be transitioned")
    kind = history[-1]["type"]
    successors = [item.strip() for item in successor.split(";") if item.strip()]
    registered = {row["id"] for row in rows}
    missing = [item for item in successors if item not in registered]
    if missing:
        raise ValueError("successor identifiers are not registered: " + ", ".join(missing))
    if identifier in successors:
        raise ValueError("an identifier cannot succeed itself")

    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\\n")
        writer.writerow({
            "id": identifier,
            "type": kind,
            "status": status,
            "successor": ";".join(successors),
            "date": dt.date.today().isoformat(),
            "reason": reason.strip(),
        })


def generator_self_test(count: int = 10000, root: pathlib.Path = ROOT) -> list[str]:
    if count < 1:
        return ["test count must be positive"]
    path = root / REGISTRY_RELATIVE
    existing: set[str] = set()
    if path.exists():
        rows, errors = parse_registry(path.read_text(encoding="utf-8-sig"))
        if errors:
            return errors
        existing = {row["id"] for row in rows}
    generated = [str(uuid.uuid4()) for _ in range(count)]
    errors = []
    if len(set(generated)) != count:
        errors.append(f"UUID generator produced duplicates in {count} IDs")
    reused = existing.intersection(generated)
    if reused:
        errors.append(f"UUID generator reused registered IDs: {sorted(reused)[:5]}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Donegal Townlands identifier registry")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("new", help="generate and register a new UUID v4")
    create.add_argument("--type", required=True, choices=sorted(KINDS))
    create.add_argument("--reason", required=True)
    create.add_argument("--manual-place", action="store_true",
                        help="use dt-place:<uuid> for a place absent from Logainm")

    transition = sub.add_parser("transition", help="append a merge, split or retirement event")
    transition.add_argument("--id", required=True)
    transition.add_argument("--status", required=True, choices=["merged", "split", "retired"])
    transition.add_argument("--successor", required=True,
                            help="registered successor ID or IDs separated by semicolons")
    transition.add_argument("--reason", required=True,
                            help="include a pointer to DECISIONS.md")

    check = sub.add_parser("validate", help="validate registry and Git append-only history")
    test = sub.add_parser("self-test", help="test generation of 10,000 unique UUIDs")
    test.add_argument("--count", type=int, default=10000)

    args = parser.parse_args()
    try:
        if args.command == "new":
            value = append_identifier(args.type, args.reason, manual_place=args.manual_place)
            print(value)
            return 0
        if args.command == "transition":
            append_transition(args.id, args.status, args.successor, args.reason)
            print(f"appended {args.status} event for {args.id}")
            return 0
        if args.command == "validate":
            errors = validate_registry_file()
        else:
            errors = generator_self_test(args.count)
        print("\n".join(errors) if errors else "identifiers: ok")
        return 1 if errors else 0
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
