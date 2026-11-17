#!/usr/bin/env python3
"""Build the normalised Tawnawilly files from the raw files (stage 2).

Usage (from the repo root):
    python data/source/nli_parish/tawnawilly/normalised/build_normalised.py
    python data/source/nli_parish/tawnawilly/normalised/build_normalised.py --check

Inputs:  ../raw/*.csv, rules.csv, overrides.csv
Outputs: tawnawilly_baptisms_normalised.csv, tawnawilly_marriages_normalised.csv

Deterministic: the same inputs always give the same output. Never edit the
outputs by hand; change the raw files, rules.csv or overrides.csv and rebuild.
--check rebuilds in memory and fails if the committed outputs differ.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "raw"
MONTHS = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
BAPTISM_COLS = ["row_id", "page", "record_no", "date_iso", "child_forename", "father_forename",
                "father_surname", "mother_forename", "mother_surname", "townland", "townland_status",
                "sponsor1", "sponsor2", "sponsor3", "sponsor4", "priest", "raw_status", "confidence",
                "rules_applied"]
MARRIAGE_COLS = ["row_id", "page", "record_no", "date_iso", "groom_forename", "groom_surname",
                 "bride_forename", "bride_surname", "witness1", "witness2", "priest", "raw_status",
                 "confidence", "rules_applied"]
CONF_ORDER = {"certain": 3, "probable": 2, "possible": 1}


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def render_csv(cols: list[str], rows: list[dict]) -> str:
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=cols, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def split_name(text: str) -> tuple[str, str]:
    """Forename(s) and surname from a name as written. The surname is the last word,
    or the word before a trailing bracket and everything after it."""
    text = text.strip()
    if not text:
        return "", ""
    words = text.split()
    if len(words) == 1:
        return text, ""
    if "(" in text:
        idx = next(i for i, w in enumerate(words) if "(" in w)
        if idx >= 1:
            return " ".join(words[: idx - 1]), " ".join(words[idx - 1:])
    return " ".join(words[:-1]), words[-1]


def parse_date(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    m = re.fullmatch(r"(\d{1,2}) ([A-Z][a-z]{2}) (\d{4})", text)
    if m:
        return f"{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"
    m = re.fullmatch(r"([A-Z][a-z]{2}) (\d{4})", text)
    if m:
        return f"{m.group(2)}-{MONTHS[m.group(1)]:02d}"
    raise ValueError(f"Unrecognised date: {text!r}")


class Rules:
    def __init__(self, rows: list[dict]):
        self.maps: dict[str, dict[str, dict]] = {"forename": {}, "surname": {}, "townland": {}}
        for r in rows:
            self.maps[r["kind"]][r["as_written"]] = r

    def forename(self, text: str, used: list[str], field: str) -> str:
        if not text:
            return ""
        table = self.maps["forename"]
        if text in table:
            new = table[text]["normalised"]
        else:
            new = " ".join(table[w]["normalised"] if w in table else w for w in text.split())
        if new != text:
            used.append(f"{field}: {text} > {new}")
        return new

    def surname(self, text: str, used: list[str], field: str) -> str:
        row = self.maps["surname"].get(text)
        new = row["normalised"] if row else text
        if new != text:
            used.append(f"{field}: {text} > {new}")
        return new

    def townland(self, text: str, used: list[str]) -> tuple[str, str]:
        row = self.maps["townland"].get(text)
        if row is None:
            return text, ("" if not text else "unmapped")
        if row["normalised"] != text:
            used.append(f"townland: {text} > {row['normalised']}")
        return row["normalised"], row["status"]


def full_name(rules: Rules, text: str, used: list[str], field: str) -> str:
    fore, sur = split_name(text)
    fore = rules.forename(fore, used, field)
    sur = rules.surname(sur, used, field)
    return " ".join(x for x in (fore, sur) if x)


def build_baptism(raw: dict, rules: Rules) -> tuple[dict, dict]:
    text = raw["resolved_reading"] or raw["reading_1"]
    parts = [p.strip() for p in text.split(" | ")]
    if len(parts) != 7:
        raise ValueError(f"{raw['row_id']}: expected 7 parts, found {len(parts)}")
    date, child, father, mother, town, sponsors, priest = parts
    father = re.sub(r"^F:\s*", "", father)
    mother = re.sub(r"^M:\s*", "", mother)
    sponsors = [s.strip() for s in re.sub(r"^S:\s*", "", sponsors).split(";")]
    used: list[str] = []
    ff, fs = split_name(father)
    mf, ms = split_name(mother)
    townland, tstatus = rules.townland(town.strip(), used)
    out = {
        "row_id": raw["row_id"], "page": raw["page"], "record_no": raw["record_no"],
        "date_iso": parse_date(date),
        "child_forename": rules.forename(child, used, "child_forename"),
        "father_forename": rules.forename(ff, used, "father_forename"),
        "father_surname": rules.surname(fs, used, "father_surname"),
        "mother_forename": rules.forename(mf, used, "mother_forename"),
        "mother_surname": rules.surname(ms, used, "mother_surname"),
        "townland": townland, "townland_status": tstatus,
        "priest": priest, "raw_status": raw["status"], "confidence": "",
    }
    for i in range(4):
        out[f"sponsor{i + 1}"] = full_name(rules, sponsors[i], used, f"sponsor{i + 1}") if i < len(sponsors) else ""
    return out, {"used": used}


def build_marriage(raw: dict, rules: Rules) -> tuple[dict, dict]:
    text = raw["resolved_reading"] or raw["reading_1"]
    parts = [p.strip() for p in text.split(" | ")]
    if len(parts) != 4:
        raise ValueError(f"{raw['row_id']}: expected 4 parts, found {len(parts)}")
    date, couple, witnesses, priest = parts
    groom, _, bride = couple.partition(" x ")
    witnesses = [w.strip() for w in re.sub(r"^W:\s*", "", witnesses).split(";")]
    used: list[str] = []
    gf, gs = split_name(groom)
    bf, bs = split_name(bride)
    out = {
        "row_id": raw["row_id"], "page": raw["page"], "record_no": raw["record_no"],
        "date_iso": parse_date(date),
        "groom_forename": rules.forename(gf, used, "groom_forename"),
        "groom_surname": rules.surname(gs, used, "groom_surname"),
        "bride_forename": rules.forename(bf, used, "bride_forename"),
        "bride_surname": rules.surname(bs, used, "bride_surname"),
        "priest": priest, "raw_status": raw["status"], "confidence": "",
    }
    for i in range(2):
        out[f"witness{i + 1}"] = full_name(rules, witnesses[i], used, f"witness{i + 1}") if i < len(witnesses) else ""
    return out, {"used": used}


def apply_overrides(row: dict, meta: dict, overrides: list[dict]) -> None:
    conf = []
    for o in overrides:
        if o["row_id"] != row["row_id"]:
            continue
        field = o["field"]
        if field not in row:
            raise ValueError(f"Override for unknown field {field} on {row['row_id']}")
        meta["used"].append(f"override {field}: {row[field]} > {o['value']}")
        row[field] = o["value"]
        if o["confidence"]:
            conf.append(o["confidence"])
    if conf:
        row["confidence"] = min(conf, key=lambda c: CONF_ORDER[c])


def build(kind: str) -> str:
    rules = Rules(read_csv(HERE / "rules.csv"))
    overrides = read_csv(HERE / "overrides.csv")
    by_row: dict[str, list[dict]] = {}
    for o in overrides:
        by_row.setdefault(o["row_id"], []).append(o)
    raws = read_csv(RAW / f"tawnawilly_{kind}_raw.csv")
    cols = BAPTISM_COLS if kind == "baptisms" else MARRIAGE_COLS
    builder = build_baptism if kind == "baptisms" else build_marriage
    rows = []
    for raw in raws:
        row, meta = builder(raw, rules)
        apply_overrides(row, meta, by_row.get(raw["row_id"], []))
        row["rules_applied"] = "; ".join(meta["used"])
        rows.append(row)
    return render_csv(cols, rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if committed outputs differ from a rebuild")
    args = parser.parse_args()
    status = 0
    for kind in ("baptisms", "marriages"):
        target = HERE / f"tawnawilly_{kind}_normalised.csv"
        text = build(kind)
        if args.check:
            if not target.is_file() or target.read_text(encoding="utf-8") != text:
                print(f"OUT OF DATE: {target.name} (run build_normalised.py)", file=sys.stderr)
                status = 1
        else:
            target.write_text(text, encoding="utf-8", newline="")
            print(f"wrote {target.name}: {text.count(chr(10)) - 1} rows")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
