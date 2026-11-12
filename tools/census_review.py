"""Build a single-file review page for one townland's proposed census links (WP18).

    python tools/census_review.py cullionboy [--include-proposed-given-names] [--out PATH]

Runs the linker for the townland and writes an HTML page with accept and reject buttons.
The page does not change the project. It produces a list of decisions that Mike downloads (or
copies) and sends back, and `census_links.py accept` records them. Output goes to
data/processed/census_links/ (not committed).

Every link is in one of three queues (WP23):
  clean   high confidence and not ambiguous: needs only the audit sample
  review  everything else Mike should look at
  hidden  low confidence, across townlands, no household support, no surname change. These are
          the likeliest coincidences of a name and an age elsewhere in the DED. They are shown as
          a count and in their own tab. Nothing is rejected or recorded for them.
`--show-all` puts the hidden links into the review queue instead.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import census_links as cl  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent / "census_review_template.html"
AUDIT_SIZE = 20
HIDE_FLAGS = ("moved townland", "no household continuity")
BLOCK_FLAGS = ("surname change",)


def queue_of(conf: str, flags: list[str], hide: bool = True) -> str:
    """clean, review or hidden. A link is hidden only when all of these hold: low confidence, it
    moves townland, nothing else in its household corroborates it, and it is not a surname change
    (a woman who married is a real possibility and always stays in review)."""
    if conf == "high" and "ambiguous" not in flags:
        return "clean"
    if (hide and conf == "low" and all(f in flags for f in HIDE_FLAGS)
            and not any(f in flags for f in BLOCK_FLAGS)):
        return "hidden"
    return "review"


def build_rows(csv_files: list[Path], hide: bool = True) -> list[dict]:
    rows, seen = [], set()
    for f in csv_files:
        with open(f, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                k = r["from_obs"] + ">" + r["to_obs"]
                if k in seen:
                    continue
                seen.add(k)
                rows.append({
                    "k": k, "conf": r["confidence"], "group": r["group"], "years": r["years"],
                    "from": {"obs": r["from_obs"], "name": r["from_name"], "age": r["from_age"],
                             "rel": r["from_relation"], "town": ""},
                    "to": {"obs": r["to_obs"], "name": r["to_name"], "age": r["to_age"],
                           "rel": r["to_relation"], "town": ""},
                    "method": r["method"], "flags": [x for x in r["flags"].split("; ") if x],
                    "audit": False, "prior": r["status"],
                    "queue": queue_of(r["confidence"], [x for x in r["flags"].split("; ") if x], hide),
                    "_ft": r["from_townland"], "_tt": r["to_townland"],
                })
    for r in rows:
        if r["_ft"] != r["_tt"]:
            r["from"]["town"], r["to"]["town"] = r["_ft"], r["_tt"]
        del r["_ft"], r["_tt"]
    highs = sorted((r for r in rows if r["conf"] == "high"),
                   key=lambda r: hashlib.sha1(r["k"].encode()).hexdigest())
    for r in highs[:AUDIT_SIZE]:
        r["audit"] = True
    return rows


CENSUS_URLS = {  # National Archives viewer patterns, as in tools/build.py CENSUS_URLS
    1901: "https://nationalarchives.ie/collections/search-the-census/view-pdf/?doc=%s",
    1911: "https://nationalarchives.ie/collections/search-the-census/view-pdf/?doc=%s",
    1926: "https://nationalarchives.ie/collections/search-the-1926-census/view-1926-pdf/?doc=%s",
}


def _member(c: dict) -> dict:
    marital = c["marital_raw"]
    extra = []
    if c["marr_years"] is not None:
        extra.append("%s yrs" % c["marr_years"])
    if c["born"] is not None:
        extra.append("%s born" % c["born"])
    if extra:
        marital = (marital + ", " if marital else "") + ", ".join(extra)
    return {"obs": c["obs"], "name": cl._name(c), "age": c["age"] if c["age"] is not None else "",
            "sex": c["sex"], "rel": c["rel"], "marital": marital, "occ": c["occ"], "birth": c["birth"],
            "url": CENSUS_URLS[c["year"]] % c["ref"] if c["ref"] else ""}


def household_heads(census_dir: Path, rows: list[dict]) -> dict:
    """Every household a proposed link touches, with its head and members, and the household id on each row."""
    census = cl.load_census(census_dir)
    obs = {r["obs"]: r for r in census}
    members = {}
    for r in census:
        members.setdefault(r["hh"], []).append(r)
    heads = {}
    for row in rows:
        for side in ("from", "to"):
            c = obs[row[side]["obs"]]
            hid = "%d|%s" % (c["year"], c["form"] or ("%s|%s" % (c["tkey"], c["house"] or c["loc"])))
            row[side]["hh"] = hid
            if hid not in heads:
                group = members[c["hh"]]
                head = next((m for m in group if m["relc"] == "head"), None)
                heads[hid] = {"y": c["year"], "label": cl._hh_label(c), "town": c["townland"],
                              "head": cl._name(head) if head else "", "age": head["age"] if head else "",
                              "size": len(group), "members": [_member(m) for m in group]}
    return heads


def build_page(townland: str, rows: list[dict], heads: dict) -> str:
    groups = []
    for r in rows:
        if r["group"] not in groups:
            groups.append(r["group"])
    data = {"townland": townland, "rows": rows, "groups": groups, "hh": heads}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", payload)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("townland")
    ap.add_argument("--census-dir", type=Path, default=cl.CENSUS_DIR)
    ap.add_argument("--config", type=Path, default=cl.CONFIG)
    ap.add_argument("--include-proposed-given-names", action="store_true")
    ap.add_argument("--show-all", action="store_true",
                    help="do not hide low links across townlands with no household support")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    out = args.out or cl.OUT_DIR / ("review_%s.html" % args.townland.lower().replace(" ", "_"))
    with tempfile.TemporaryDirectory() as tmp:
        cl.run_propose(args.census_dir, Path(tmp), cl.load_config(args.config), townland=args.townland,
                       include_proposed=args.include_proposed_given_names)
        rows = build_rows(sorted(Path(tmp).glob("*_links.csv")), hide=not args.show_all)
    if not rows:
        print("No proposed links involve %s." % args.townland)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_page(args.townland.title(), rows, household_heads(args.census_dir, rows)), encoding="utf-8")
    n = {c: sum(1 for r in rows if r["conf"] == c) for c in ("high", "medium", "low")}
    q = {k: sum(1 for r in rows if r["queue"] == k) for k in ("clean", "review", "hidden")}
    print("%d links (high %d, medium %d, low %d). Queues: clean %d, review %d, hidden %d. Review page: %s"
          % (len(rows), n["high"], n["medium"], n["low"], q["clean"], q["review"], q["hidden"], out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
