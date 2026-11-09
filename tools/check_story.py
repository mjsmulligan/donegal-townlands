#!/usr/bin/env python3
"""Story check (WP21): fail any name, place, date, age or relationship in a family story that is
not in the family's fact sheet.

    python tools/check_story.py cullionboy Kelly
    python tools/check_story.py --text story.txt --facts townlands/cullionboy/records/facts/kelly.json

Only usable facts count (tree, census as recorded, Griffith's, accepted links, derived, media). A
proposed link is never usable, so a story cannot rest on it. Exit code 1 if anything fails.

What it checks (FAIL):
  names and places  every capitalised word is in the fact sheet
  dates             full dates, day and month, month and year, years and decades
  numbers           every number or number word is a figure in the sheet (an age, a count, an acre)
  ages              "Name was thirty-four", "Name, thirteen," match an age held for that person
  relationships     "his brother John", "daughter of X and Y", "married Z" match a relation held
  privacy           a tree person not cleared by 100/75/50 is named
  death causes      "died of X" uses words the sheet holds
What it does NOT check: whether a sentence is true in sense, whether the order of events is
right, or whether an unaccepted link is implied in prose. Mike's read of the story stays the
last check. Items marked WARN need a look but do not fail.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
MONTH_RE = "(?:January|February|March|April|May|June|July|August|September|October|November|December)"
ONES = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
ORD_UNITS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9}
ORD_TEENS = {"tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15,
             "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19}
ORD_TENS = {"twentieth": 20, "thirtieth": 30, "fortieth": 40, "fiftieth": 50, "sixtieth": 60}
STARTERS = set("""A After All Although An And As At Before But By During Each For From He Her His However If In
It Its Neither Nor Not Of On Only Once One Or Over Rose She Since So Some Still That The Their Then There
These They This Three Two Four Five Six Seven Eight Nine Ten Until What When Where Which While With
Later Soon Today Both Many Most Another Every Nobody Nothing Meanwhile Within Throughout Between Among Beyond Years Months Days""".split())
STARTERS.discard("Rose")   # a name; must be in the fact sheet
RELATIONS = ["grandfather", "grandmother", "brother", "sister", "mother", "father", "son", "daughter", "wife",
             "husband", "nephew", "niece", "uncle", "aunt", "cousin", "grandson", "granddaughter"]
REL_RE = "(?:%s)s?" % "|".join(RELATIONS)
WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
NUM_WORD = "(?:%s)" % "|".join(sorted(list(ONES) + list(TENS) + list(ORD_UNITS) + list(ORD_TEENS) + list(ORD_TENS), key=len, reverse=True))
NUM_PHRASE = re.compile(r"\b(%s(?:[- ](?:%s))?)\b" % (NUM_WORD, NUM_WORD), re.I)


def strip_poss(w: str) -> str:
    return re.sub(r"['’]s$", "", w)


def words(text: str) -> set[str]:
    return {strip_poss(w).lower() for w in WORD.findall(text or "")}


def to_number(phrase: str):
    p = phrase.lower().replace(" ", "-")
    parts = p.split("-")
    try:
        if len(parts) == 1:
            w = parts[0]
            for table in (ONES, TENS, ORD_TEENS, ORD_TENS):
                if w in table:
                    return table[w]
            return ORD_UNITS.get(w)
        if parts[0] in TENS:
            u = ONES.get(parts[1]) or ORD_UNITS.get(parts[1])
            return TENS[parts[0]] + u if u else None
    except KeyError:
        return None
    return None


def parse_date(s: str):
    m = re.match(r"^\s*(?:(\d{1,2})\s+)?([A-Za-z]{3})[a-z]*\.?\s+(\d{4})\s*$", s or "")
    if m and m[2].lower() in MONTHS:
        return (int(m[1]) if m[1] else None, MONTHS.index(m[2].lower()) + 1, int(m[3]))
    return None


class Vocab:
    """What the usable facts allow."""

    def __init__(self, sheet: dict):
        self.sheet = sheet
        self.words, self.numbers, self.years = set(), set(), set()
        self.dates, self.day_months, self.month_years = set(), set(), set()
        self.ages: dict[str, dict[int, str]] = {}      # lower first or full name -> {age: tier}
        self.rel: dict[tuple, str] = {}                # (relation, lower name) -> tier
        self.spouses: dict[str, str] = {}
        self.persons = []
        self.uncleared = []
        for f in sheet["facts"]:
            if not f["usable"]:
                continue
            tier = f["tier"]
            blob = " ".join(str(f.get(k, "")) for k in ("text", "who", "place", "born_place", "died_place",
                                                          "recorded_name", "lessor", "caption", "of"))
            self.words |= words(blob)
            for dstr in re.findall(r"\b\d{1,2} [A-Za-z]{3,9} \d{4}\b", blob):
                d = parse_date(dstr)
                if d:
                    self.dates.add(d)
            for m in re.finditer(r"\b(\d{1,2}) (%s) (\d{4})" % MONTH_RE, blob):
                self.dates.add((int(m[1]), MONTHS.index(m[2][:3].lower()) + 1, int(m[3])))
            for d in list(self.dates):
                if d[0]:
                    self.day_months.add((d[0], d[1]))
                self.month_years.add((d[1], d[2]))
            for n in re.findall(r"\b\d+\b", blob):
                v = int(n)
                (self.years if 1500 <= v <= 2100 else self.numbers).add(v)
            for k in ("age", "count", "year"):
                v = f.get(k)
                if isinstance(v, int):
                    (self.years if k == "year" else self.numbers).add(v)
            for v in f.get("counts", []) or []:
                self.numbers.add(v)
            if f.get("acres") is not None:
                self.numbers.add(int(f["acres"]))
            if f["kind"] == "person":
                self.persons.append(f)
                if f.get("cleared") is False:
                    self.uncleared.append(f)
            if f["kind"] == "relation":
                self.rel[(f["relation"], f["who"].lower())] = tier
                self.rel[(f["relation"], f["who"].split()[0].lower())] = tier
            if f["kind"] == "marriage":
                a, b = f["who"]
                self.spouses[a.lower()] = self.spouses[b.lower()] = tier
                self.spouses[a.split()[0].lower()] = self.spouses[b.split()[0].lower()] = tier
            if f["kind"] in ("age", "anchor", "census") and isinstance(f.get("age"), int):
                nm = f["who"].lower()
                for key in {nm, nm.split()[0]}:
                    self.ages.setdefault(key, {}).setdefault(f["age"], tier)
                    if f["kind"] in ("anchor",) and f.get("recorded_name"):
                        rn = f["recorded_name"].lower()
                        for k2 in {rn, rn.split()[0]}:
                            self.ages.setdefault(k2, {}).setdefault(f["age"], tier)
        for f in sheet["facts"]:   # an age is also held under a person's nickname and tree given name
            if f["kind"] == "person" and f.get("nick"):
                self.ages.setdefault(f["nick"].lower(), {})
        for y in list(self.years):
            pass
        for f in sheet["facts"]:
            if f["usable"] and f["kind"] in ("person", "marriage", "note"):
                for s in re.findall(r"\b(\d{4})s?\b", f["text"]):
                    self.years.add(int(s))
        for d in self.dates:
            self.years.add(d[2])


def sentences(text: str):
    for m in re.finditer(r"[^.!?]+[.!?]?", text):
        s = m.group(0)
        if s.strip():
            yield m.start(), s


class Finding:
    def __init__(self, level, rule, snippet, message):
        self.level, self.rule, self.snippet, self.message = level, rule, snippet, message

    def __str__(self):
        return "%-4s %-13s %s: %s" % (self.level, self.rule, self.snippet, self.message)


def check_text(text: str, sheet: dict) -> tuple[list[Finding], dict]:
    v = Vocab(sheet)
    out: list[Finding] = []
    support = {}

    def note(tier):
        support[tier] = support.get(tier, 0) + 1

    # names and places
    for pos, s in sentences(text):
        toks = [(m.start(), m.group(0)) for m in WORD.finditer(s)]
        for i, (p, tok) in enumerate(toks):
            if not tok[0].isupper():
                continue
            low = strip_poss(tok).lower()
            if low in v.words or (low.endswith("s") and low[:-1] in v.words) or low in ("january february march april may june july august september october november december "
                                         "monday tuesday wednesday thursday friday saturday sunday").split():
                continue
            if low in ONES or low in TENS:
                continue
            first = s[:p].strip() == "" or i == 0
            nxt = toks[i + 1][1] if i + 1 < len(toks) else ""
            if first and strip_poss(tok) in STARTERS:
                continue
            if first and not nxt[:1].isupper() and re.search(r"(?<![.!?]\s)\b%s\b" % re.escape(tok.lower()), text):
                continue   # the same word appears in lower case elsewhere, so it is an ordinary word
            out.append(Finding("FAIL", "name", tok, "not in the fact sheet" + (
                " (if it is an ordinary word that starts a sentence, add it to STARTERS in check_story.py)" if first else "")))
    # dates
    claimed = []
    for m in re.finditer(r"\b(\d{1,2})(?:st|nd|rd|th)? (%s)(?: (\d{4}))?" % MONTH_RE, text):
        d, mo, y = int(m[1]), MONTHS.index(m[2][:3].lower()) + 1, int(m[3]) if m[3] else None
        claimed.append(m.span())
        if y and (d, mo, y) not in v.dates:
            out.append(Finding("FAIL", "date", m[0], "date is not in the fact sheet"))
        elif not y and (d, mo) not in v.day_months:
            out.append(Finding("FAIL", "date", m[0], "day and month are not in the fact sheet"))
        else:
            note("dates")
    for m in re.finditer(r"\b(%s) (\d{4})\b" % MONTH_RE, text):
        if any(a <= m.start() < b for a, b in claimed):
            continue
        if (MONTHS.index(m[1][:3].lower()) + 1, int(m[2])) not in v.month_years:
            out.append(Finding("FAIL", "date", m[0], "month and year are not in the fact sheet"))
        else:
            note("dates")
    for m in re.finditer(r"\b(1[5-9]\d\d|20\d\d)(s?)\b", text):
        y = int(m[1])
        ok = any(y <= x < y + 10 for x in v.years) if m[2] else y in v.years
        if not ok:
            out.append(Finding("FAIL", "year", m[0], "year is not in the fact sheet"))
    # numbers
    spans = [m.span() for m in re.finditer(r"\b\d{1,2}(?:st|nd|rd|th)? %s(?: \d{4})?|\b%s \d{4}|\b\d{4}s?\b" % (MONTH_RE, MONTH_RE), text)]
    for m in NUM_PHRASE.finditer(text):
        if any(a <= m.start() < b for a, b in spans):
            continue
        n = to_number(m[1])
        w = m[1].lower()
        if n is None or w in ("one", "first", "second"):
            continue
        if n not in v.numbers:
            out.append(Finding("FAIL", "number", m[0], "%d is not a figure in the fact sheet" % n))
    for m in re.finditer(r"(?<![\d/])\b(\d{1,3})\b(?!\d|\s*(?:%s))" % MONTH_RE, text):
        if any(a <= m.start() < b for a, b in spans):
            continue
        if int(m[1]) not in v.numbers:
            out.append(Finding("FAIL", "number", m[0], "not a figure in the fact sheet"))
    # ages for a named person
    pat = re.compile(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)?)(?:,| was| were| is| aged|, aged| \() ?(?:then )?(%s(?:[- ]%s)?|\d{1,3})\b" % (NUM_WORD, NUM_WORD), re.I)
    for m in pat.finditer(text):
        name = m[1].lower()
        val = int(m[2]) if m[2].isdigit() else to_number(m[2])
        if val is None or m[2].lower() in ("one", "first", "second"):
            continue
        known = v.ages.get(name) or v.ages.get(name.split()[0])
        if known is None:
            continue
        if val in known:
            note("ages:" + known[val])
        elif not any(abs(val - k) <= 0 for k in known):
            out.append(Finding("FAIL", "age", m[0].strip(), "no age of %d is held for %s (held: %s)" % (
                val, m[1], ", ".join(str(k) for k in sorted(known)))))
    # relationships
    for m in re.finditer(r"\b(%s) ([A-Z][a-z]+(?: [A-Z][a-zA-Z]+)?)" % REL_RE, text):
        r = m[1].lower().rstrip("s") if m[1].lower() not in ("husbands",) else "husband"
        first = m[2].split()[0].lower()
        key_full, key_first = (r, m[2].lower()), (r, first)
        hit = v.rel.get(key_full) or v.rel.get(key_first)
        if not hit and r in ("grandfather", "grandmother"):
            hit = v.rel.get(("grandparent", m[2].lower())) or v.rel.get(("grandparent", first))
        if r in ("son", "daughter") and re.search(r"%s of\b" % m[1], text[max(0, m.start() - 0):m.end() + 4]):
            continue
        if first in ("of", "and", "in", "who", "was", "were") or not hit:
            if not hit:
                out.append(Finding("FAIL", "relationship", m[0], "no %s named %s in the fact sheet" % (r, m[2])))
        else:
            note("relations:" + hit)
    for m in re.finditer(r"\b(?:son|daughter|sons|daughters) of ([A-Z][a-z]+(?: [A-Z][a-zA-Z]+)?)(?: and ([A-Z][a-z]+(?: [A-Z][a-zA-Z]+)?))?", text):
        for nm, rels in ((m[1], ("father", "mother", "parent")), (m[2], ("father", "mother", "parent"))):
            if nm and not any((r, nm.lower()) in v.rel or (r, nm.split()[0].lower()) in v.rel for r in rels):
                out.append(Finding("FAIL", "relationship", m[0], "%s is not a parent in the fact sheet" % nm))
    for m in re.finditer(r"\bmarried ([A-Z][a-z]+(?: [A-Z][a-zA-Z]+)?)", text):
        nm = m[1].lower()
        if nm in v.spouses or nm.split()[0] in v.spouses:
            note("marriages:" + (v.spouses.get(nm) or v.spouses[nm.split()[0]]))
        else:
            out.append(Finding("FAIL", "relationship", m[0], "no marriage to %s in the fact sheet" % m[1]))
    # privacy
    for p in v.uncleared:
        for nm in {p["who"], p["who"].split()[0]} if p["who"].count(" ") == 0 else {p["who"]}:
            if re.search(r"\b%s\b" % re.escape(nm), text):
                out.append(Finding("FAIL", "privacy", nm, "named in the story but not cleared by 100/75/50"))
    # causes of death
    for m in re.finditer(r"\bdied of ((?:[a-z]+ ){0,2}[a-z]+)", text):
        for w in m[1].split():
            if w not in ("and", "the", "a", "on", "in", "at", "when") and w not in v.words:
                out.append(Finding("FAIL", "cause", m[0], "'%s' is not in the fact sheet" % w))
                break
    # an unusable fact cannot support a story
    return out, support


def story_text(case_dir: Path, family: str) -> str:
    c = json.loads((case_dir / "content.json").read_text(encoding="utf-8"))
    for f in c.get("families", []):
        if family.lower() in [k.lower() for k in f.get("keys", [])] or family.lower() == f.get("tab", "").lower():
            return "\n\n".join([f.get("story", "")] + f.get("paras", []))
    raise SystemExit("No family story for %s in %s" % (family, case_dir.name))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("townland", nargs="?")
    ap.add_argument("family", nargs="?")
    ap.add_argument("--text", type=Path, help="check this file instead of the story in content.json")
    ap.add_argument("--facts", type=Path)
    a = ap.parse_args(argv)
    if a.text:
        text = a.text.read_text(encoding="utf-8")
        facts = a.facts
    else:
        if not (a.townland and a.family):
            ap.error("give a townland and family, or --text and --facts")
        case = ROOT / "townlands" / a.townland
        text = story_text(case, a.family)
        facts = a.facts or case / "records" / "facts" / ("%s.json" % re.sub(r"[^a-z0-9]+", "_", a.family.lower()))
    if not facts or not Path(facts).is_file():
        print("No fact sheet. Run: python tools/family_facts.py %s %s" % (a.townland, a.family))
        return 1
    sheet = json.loads(Path(facts).read_text(encoding="utf-8"))
    findings, support = check_text(text, sheet)
    fails = [f for f in findings if f.level == "FAIL"]
    for f in findings:
        print(f)
    t = sheet["tiers"]
    print("Fact sheet: " + ", ".join("%s %d" % (k, n) for k, n in t.items()) +
          ". Accepted census links %d, proposed (not usable) %d." % (sheet["accepted_census_links"], sheet["proposed_census_links"]))
    if support:
        print("Checked claims rest on: " + ", ".join("%s %d" % kv for kv in sorted(support.items())))
    print("%d failed, %d to look at." % (len(fails), len(findings) - len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
