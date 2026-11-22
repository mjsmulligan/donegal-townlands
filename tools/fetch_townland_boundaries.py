#!/usr/bin/env python3
"""Fetch townland outlines from Tailte Eireann and write one GeoJSON for the site.

Reads the townlands in data/processed/places/places.csv, asks Tailte Eireann's
public map service for only those polygons (matched on LOGAINM_ID, so Lower,
Middle and Upper townlands cannot be confused), and writes:

  data/processed/places/townland_boundaries.geojson
  data/processed/places/townland_boundaries_review.csv

Every place gets one row in the review file. Checks per place:
  ok               polygon found, Logainm point sits inside it, names agree
  name_differs     polygon found and point inside, but the names differ
  point_outside    polygon found but the Logainm point is outside it
  id_not_found     no polygon came back for that LOGAINM_ID

Standard library only. Needs internet access to services-eu1.arcgis.com.

Usage (from the repo root):
  python tools/fetch_townland_boundaries.py
  python tools/fetch_townland_boundaries.py --input path/to/downloaded.geojson

--input is the fallback: if you download Tailte's national GeoJSON yourself
(WGS84 version), point this at it and the same filtering and checks run.

Source data: (c) Tailte Eireann. The data.gov.ie listing for the townland
boundary datasets gives the licence as CC BY 4.0. Keep the attribution on the
site. Confirm the licence on the dataset page you download from, because the
newer 2026 listing did not state one when checked.
"""
import argparse
import csv
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Generalised 20 m townlands, national statutory boundaries (2019 release).
# Light enough for a web map. Swap for a newer or ungeneralised service with --service.
DEFAULT_SERVICE = (
    "https://services-eu1.arcgis.com/FH5XCsx8rYXqnjF5/arcgis/rest/services/"
    "Townlands_OSi_National_Statutory_Boundaries___Generalised_20m/FeatureServer/0"
)
ATTRIBUTION = "Townland boundaries (c) Tailte Eireann, CC BY 4.0"
CHUNK = 40


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def read_places(path):
    places = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("place_type") != "townland":
                continue
            try:
                lat = float(row["latitude"])
                lng = float(row["longitude"])
            except (TypeError, ValueError):
                lat = lng = None
            places.append({
                "logainm_id": str(row["logainm_id"]).strip(),
                "name_en": row["name_en"].strip(),
                "name_ga": (row.get("name_ga") or "").strip(),
                "lat": lat,
                "lng": lng,
            })
    return places


def query_service(service, ids):
    """Ask the map service for the given LOGAINM_IDs, in chunks. Returns features."""
    features = []
    for i in range(0, len(ids), CHUNK):
        chunk = ids[i:i + CHUNK]
        where = "LOGAINM_ID IN (%s)" % ",".join("'%s'" % x for x in chunk)
        data = urllib.parse.urlencode({
            "where": where,
            "outFields": "TD_ID,ENGLISH,GAEILGE,LOGAINM_ID,COUNTY",
            "returnGeometry": "true",
            "outSR": "4326",
            "geometryPrecision": "5",
            "f": "geojson",
        }).encode()
        body = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(service + "/query", data=data)
                with urllib.request.urlopen(req, timeout=90) as r:
                    body = json.load(r)
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                print("  attempt %d failed: %s" % (attempt + 1, e), file=sys.stderr)
                time.sleep(2 * (attempt + 1))
        if body is None:
            sys.exit("Could not reach the map service. Try --input with a downloaded file.")
        if "error" in body:
            sys.exit("Map service error: %s" % body["error"])
        got = body.get("features", [])
        if body.get("exceededTransferLimit"):
            print("  warning: transfer limit hit for a chunk", file=sys.stderr)
        features.extend(got)
        print("  fetched %d polygons for ids %d-%d" % (len(got), i + 1, i + len(chunk)))
    return features


def read_input(path, wanted):
    with open(path, encoding="utf-8") as f:
        gj = json.load(f)
    feats = []
    for ft in gj["features"]:
        lid = str((ft.get("properties") or {}).get("LOGAINM_ID", "")).strip()
        if lid in wanted:
            feats.append(ft)
    if feats:
        g = feats[0]["geometry"]
        c = g["coordinates"]
        while isinstance(c[0], list):
            c = c[0]
        if abs(c[0]) > 180:
            sys.exit("This file is in Irish Transverse Mercator, not WGS84. "
                     "Download the GeoJSON version, or reproject it first.")
    return feats


def polygons_of(geom):
    """Return a list of polygons; each polygon is a list of rings of [lng, lat]."""
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def ring_contains(ring, x, y):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def polys_contain(polys, x, y):
    for poly in polys:
        if ring_contains(poly[0], x, y) and not any(ring_contains(h, x, y) for h in poly[1:]):
            return True
    return False


def nearest_vertex_m(polys, lng, lat):
    best = None
    k = math.cos(math.radians(lat))
    for poly in polys:
        for ring in poly:
            for x, y in ring:
                d = math.hypot((x - lng) * k, y - lat) * 111320
                if best is None or d < best:
                    best = d
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--places", default="data/processed/places/places.csv")
    ap.add_argument("--out", default="data/processed/places/townland_boundaries.geojson")
    ap.add_argument("--review", default="data/processed/places/townland_boundaries_review.csv")
    ap.add_argument("--service", default=DEFAULT_SERVICE)
    ap.add_argument("--input", help="a downloaded WGS84 GeoJSON, used instead of the map service")
    args = ap.parse_args()

    places = read_places(args.places)
    ids = sorted({p["logainm_id"] for p in places}, key=int)
    print("%d townlands in %s" % (len(places), args.places))

    feats = read_input(args.input, set(ids)) if args.input else query_service(args.service, ids)

    # Group polygons by LOGAINM_ID. A townland in several detached parts becomes one MultiPolygon.
    by_id = {}
    for ft in feats:
        props = ft.get("properties") or {}
        lid = str(props.get("LOGAINM_ID", "")).strip()
        rec = by_id.setdefault(lid, {"polys": [], "props": props})
        rec["polys"].extend(polygons_of(ft["geometry"]))

    out_features, review = [], []
    for p in places:
        rec = by_id.get(p["logainm_id"])
        row = {"logainm_id": p["logainm_id"], "name_en": p["name_en"], "osi_name": "",
               "status": "", "detail": ""}
        if not rec or not rec["polys"]:
            row["status"] = "id_not_found"
            row["detail"] = "No polygon with this LOGAINM_ID. May not be a townland in the boundary data."
            review.append(row)
            continue
        polys = rec["polys"]
        osi_name = (rec["props"].get("ENGLISH") or "").strip()
        row["osi_name"] = osi_name
        inside = None
        if p["lat"] is not None:
            inside = polys_contain(polys, p["lng"], p["lat"])
        names_agree = norm(osi_name) == norm(p["name_en"])
        if inside is False:
            row["status"] = "point_outside"
            row["detail"] = "Logainm point is %d m from the nearest boundary vertex." % round(
                nearest_vertex_m(polys, p["lng"], p["lat"]))
            others = [o["props"].get("ENGLISH") for lid, o in by_id.items()
                      if lid != p["logainm_id"] and polys_contain(o["polys"], p["lng"], p["lat"])]
            if others:
                row["detail"] += " It falls inside: %s." % ", ".join(others)
        elif not names_agree:
            row["status"] = "name_differs"
            row["detail"] = "Logainm name '%s' vs Tailte name '%s'." % (p["name_en"], osi_name)
        else:
            row["status"] = "ok"
        review.append(row)

        geom = ({"type": "Polygon", "coordinates": polys[0]} if len(polys) == 1
                else {"type": "MultiPolygon", "coordinates": polys})
        out_features.append({
            "type": "Feature",
            "properties": {"logainm_id": p["logainm_id"], "name_en": p["name_en"],
                           "name_ga": p["name_ga"] or (rec["props"].get("GAEILGE") or "")},
            "geometry": geom,
        })

    out = {"type": "FeatureCollection", "attribution": ATTRIBUTION, "features": out_features}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    with open(args.review, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["logainm_id", "name_en", "osi_name", "status", "detail"])
        w.writeheader()
        w.writerows(review)

    counts = {}
    for r in review:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    size_kb = Path(args.out).stat().st_size / 1024
    print("\nWrote %d outlines to %s (%.0f KB)" % (len(out_features), args.out, size_kb))
    print("Review file: %s" % args.review)
    for k in ("ok", "name_differs", "point_outside", "id_not_found"):
        print("  %-14s %d" % (k, counts.get(k, 0)))


if __name__ == "__main__":
    main()
