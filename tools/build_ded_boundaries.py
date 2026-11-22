#!/usr/bin/env python3
"""Build DED outlines by dissolving the townland outlines.

Each townland in data/processed/places/places.csv carries the Logainm ID of its DED. This joins the townland
outlines in data/processed/places/townland_boundaries.geojson by that ID and merges the townlands of each DED
into one shape. Edges that two neighbouring townlands share cancel out, and what is left is the DED's outer
edge (and the edge of any hole). Nothing is fetched, so the DED outlines come from the same Tailte Eireann data
and match the townland edges exactly.

Writes data/processed/places/ded_boundaries.geojson. Standard library only.

Checks: every DED must come out as closed rings, and the area of the result must match the sum of its townland
areas to within 0.5 percent. The tool stops with a message if either fails, so a gap or an overlap in the
townland data is reported and not drawn. A townland with no outline (the lake islands) is simply absent from
its DED and is counted in the summary.

Usage (from the repo root):
  python tools/build_ded_boundaries.py
"""
import argparse
import collections
import csv
import json
import math
import sys
from pathlib import Path

ATTRIBUTION = "Townland boundaries (c) Tailte Eireann, CC BY 4.0"
TOLERANCE = 0.005


def polygons_of(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def ring_area(ring):
    """Signed area of a ring in lng/lat degrees squared (positive when counter-clockwise)."""
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:])) / 2


def hectares(ring, lat):
    kx, ky = 111320 * math.cos(math.radians(lat)), 110574
    return abs(ring_area(ring)) * kx * ky / 1e4


def contains(ring, x, y):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi, xj, yj = ring[i][0], ring[i][1], ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def dissolve(polygons):
    """Merge polygons that share edges. Returns a list of polygons (each a list of rings), outer ring first,
    outer rings counter-clockwise, holes clockwise. Raises ValueError if the edges do not close into rings."""
    count = collections.Counter()
    for poly in polygons:
        for ring in poly:
            for a, b in zip(ring, ring[1:]):
                a, b = tuple(a), tuple(b)
                if a != b:
                    count[(a, b) if a < b else (b, a)] += 1
    boundary = sorted(e for e, n in count.items() if n % 2 == 1)
    adjacent = collections.defaultdict(list)
    for a, b in boundary:
        adjacent[a].append(b)
        adjacent[b].append(a)
    for v in adjacent.values():
        v.sort()
    used = set()
    rings = []
    for a, b in boundary:
        if (a, b) in used:
            continue
        used.add((a, b))
        ring, here = [a, b], b
        while here != a:
            step = None
            for n in adjacent[here]:
                key = (here, n) if here < n else (n, here)
                if key not in used:
                    step = (n, key)
                    break
            if step is None:
                raise ValueError("edges do not close into a ring near %s" % (here,))
            used.add(step[1])
            ring.append(step[0])
            here = step[0]
        rings.append(ring)
    rings.sort(key=lambda r: -abs(ring_area(r)))
    outers = []                      # [outer ring, [holes]]
    for ring in rings:
        x, y = ring[0]
        parent = None
        for o in reversed(outers):   # the smallest outer ring that holds it
            if contains(o[0], x, y):
                parent = o
                break
        if parent is not None and len([1 for o in outers if contains(o[0], x, y)]) % 2 == 1:
            parent[1].append(ring)
        else:
            outers.append([ring, []])
    result = []
    for outer, holes in outers:
        if ring_area(outer) < 0:
            outer = outer[::-1]
        result.append([outer] + [h[::-1] if ring_area(h) > 0 else h for h in holes])
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--places", default="data/processed/places/places.csv")
    ap.add_argument("--townlands", default="data/processed/places/townland_boundaries.geojson")
    ap.add_argument("--out", default="data/processed/places/ded_boundaries.geojson")
    args = ap.parse_args()

    with open(args.places, newline="", encoding="utf-8") as f:
        places = list(csv.DictReader(f))
    deds = {p["logainm_id"]: p for p in places if p["place_type"] == "ded"}
    members = collections.defaultdict(list)
    for p in places:
        if p["place_type"] == "townland" and p["ded_id"]:
            members[p["ded_id"]].append(p["logainm_id"])
    with open(args.townlands, encoding="utf-8") as f:
        outlines = {str(ft["properties"]["logainm_id"]): ft["geometry"] for ft in json.load(f)["features"]}

    features, problems = [], []
    for ded_id in sorted(members, key=lambda d: deds.get(d, {}).get("name_en", d)):
        ded = deds.get(ded_id)
        if ded is None:
            problems.append("DED %s has townlands but no DED row in %s" % (ded_id, args.places))
            continue
        ids = members[ded_id]
        have = [i for i in ids if i in outlines]
        polys = [p for i in have for p in polygons_of(outlines[i])]
        try:
            merged = dissolve(polys)
        except ValueError as e:
            problems.append("%s: %s" % (ded["name_en"], e))
            continue
        lat = polys[0][0][0][1]
        before = sum(hectares(p[0], lat) - sum(hectares(h, lat) for h in p[1:]) for p in polys)
        after = sum(hectares(p[0], lat) - sum(hectares(h, lat) for h in p[1:]) for p in merged)
        if abs(after - before) > TOLERANCE * before:
            problems.append("%s: merged area %.0f ha but townlands add up to %.0f ha" % (ded["name_en"], after, before))
            continue
        geom = ({"type": "Polygon", "coordinates": merged[0]} if len(merged) == 1
                else {"type": "MultiPolygon", "coordinates": merged})
        features.append({"type": "Feature",
                         "properties": {"ded_id": ded_id, "name_en": ded["name_en"], "name_ga": ded.get("name_ga", ""),
                                        "townlands": len(ids), "with_outline": len(have)},
                         "geometry": geom})
        print("%-12s %2d townlands, %2d with outlines, %d ring(s), %.0f ha" % (
            ded["name_en"], len(ids), len(have), sum(len(p) for p in merged), after))
    if problems:
        sys.exit("Not written:\n  " + "\n  ".join(problems))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "attribution": ATTRIBUTION, "features": features}, f, separators=(",", ":"))
    print("Wrote %d DED outlines to %s (%.0f KB)" % (len(features), args.out, Path(args.out).stat().st_size / 1024))


if __name__ == "__main__":
    main()
