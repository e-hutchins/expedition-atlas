"""
prep_amtrak_route.py

One-off data prep script -- NOT part of the live website. Run manually
whenever the raw NTAD (National Transportation Atlas Database) BTS
exports change, or to pull a new Amtrak route into this expedition.

What it does:
  1. Routes: pulls a single named route's feature out of the nationwide
     NTAD Amtrak Routes file (which has all 49 Amtrak routes),
     simplifies its geometry (the source is track-centerline
     resolution -- ~45k points -- far more than a web map needs), and
     writes it out with minimal properties.
  2. Stations: the nationwide NTAD Amtrak Stations file has no field
     linking a station to a route, so this does a spatial join --
     buffers the route line and keeps TRAIN stations that fall within
     it -- then remaps properties to the project schema.
  3. Optional cross-reference: where a route shares a corridor with
     another Amtrak service (e.g. Empire Builder's Chicago-Milwaukee
     segment, also used by the Hiawatha), the spatial join alone can
     pull in stations the route doesn't actually stop at. If a
     station-list markdown file (one official stop per line, ending
     in "(CODE)") is supplied, any spatially-matched station whose
     code isn't on that list is dropped and reported.

Modular by design: defaults below reproduce the original Empire
Builder run, but every input/output path and the route name are CLI
flags so this script can prep additional Amtrak routes later.

Requires: shapely (pip install shapely)

Usage (run from the repo root):
  python scripts/prep_amtrak_route.py
  python scripts/prep_amtrak_route.py --route "California Zephyr" --route-out expeditions/empire-builder/data/routes/california-zephyr.geojson
"""

import argparse
import json
import re
from pathlib import Path

from shapely.geometry import Point, shape, mapping

SCRIPT_DIR = Path(__file__).parent
# This script lives at the repo root (scripts/), one level above the
# expeditions/ folder -- defaults below point at Empire Builder's data,
# but every path is a CLI flag for prepping a different expedition's data.
DATA_DIR = SCRIPT_DIR.parent / "expeditions" / "empire-builder" / "data"
RAW_DATA_DIR = DATA_DIR / "raw"


def slugify(name):
    return name.lower().replace(" ", "-")


def parse_station_list(path):
    """Pull official station codes (e.g. "(SEA)") out of a markdown list."""
    codes = set()
    for line in path.read_text().splitlines():
        m = re.search(r"\(([A-Z]{3})\)", line)
        if m:
            codes.add(m.group(1))
    return codes


def prep_route(route_name, routes_source, out_path, simplify_tolerance):
    source = json.loads(routes_source.read_text())
    feature = next(
        (f for f in source["features"] if f["properties"].get("name") == route_name),
        None,
    )
    if feature is None:
        raise SystemExit(f'route "{route_name}" not found in {routes_source}')

    geom = shape(feature["geometry"]).simplify(simplify_tolerance, preserve_topology=False)

    output = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": mapping(geom),
                "properties": {
                    "name": route_name,
                    "source_url": feature["properties"].get("ROUTE_URL"),
                },
            }
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")
    return geom


def prep_stations(route_geom, stations_source, out_path, buffer_deg, station_list_path):
    region = route_geom.buffer(buffer_deg)
    source = json.loads(stations_source.read_text())

    official_codes = None
    if station_list_path is not None and station_list_path.exists():
        official_codes = parse_station_list(station_list_path)

    matches = []
    dropped = []
    for feat in source["features"]:
        if feat["properties"].get("StnType") != "TRAIN":
            continue
        if not region.contains(Point(feat["geometry"]["coordinates"])):
            continue
        p = feat["properties"]
        code = p.get("Code")
        name = p.get("StationName")

        if official_codes is not None and code not in official_codes:
            dropped.append((code, name))
            continue

        matches.append(
            {
                "type": "Feature",
                "geometry": feat["geometry"],
                "properties": {
                    "name": name,
                    "amtrak_code": code,
                    "city": p.get("City"),
                    "state": p.get("State"),
                    # arrival, departure, elevation_ft from the
                    # project-guidelines/DATA.md schema are NOT present
                    # in this source -- they need a timetable / DEM
                    # source and are intentionally left out rather than
                    # invented.
                },
            }
        )

    output = {"type": "FeatureCollection", "features": matches}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    print(f"wrote {out_path} ({len(matches)} stations, {out_path.stat().st_size} bytes)")
    for f in sorted(matches, key=lambda f: f["properties"]["name"]):
        print(" -", f["properties"]["amtrak_code"], f["properties"]["name"])

    if dropped:
        print(f"\ndropped {len(dropped)} station(s) not on {station_list_path.name} (shared-corridor false positives):")
        for code, name in dropped:
            print(" -", code, name)

    if official_codes is not None:
        missing = official_codes - {f["properties"]["amtrak_code"] for f in matches}
        if missing:
            print(f"\nWARNING: {len(missing)} code(s) on {station_list_path.name} had no spatial-join match: {sorted(missing)}")

    return matches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route", default="Empire Builder", help="Route name as it appears in the NTAD routes file")
    parser.add_argument("--routes-source", type=Path, default=RAW_DATA_DIR / "NTAD_Amtrak_Routes_5503594535609073988.geojson")
    parser.add_argument("--stations-source", type=Path, default=RAW_DATA_DIR / "NTAD_Amtrak_Stations_8364964222168212810.geojson")
    parser.add_argument("--route-out", type=Path, default=None, help="Defaults to data/routes/<slugified-route-name>.geojson")
    parser.add_argument("--stations-out", type=Path, default=DATA_DIR / "stations" / "stations.geojson")
    parser.add_argument("--station-list", type=Path, default=DATA_DIR / "station_list.md", help="Optional markdown file of official stops, one per line ending in (CODE), used to filter out shared-corridor false positives")
    parser.add_argument("--simplify-tolerance", type=float, default=0.0005, help="Degrees; ~50m, cuts ~45k points down to ~2.4k")
    parser.add_argument("--station-buffer", type=float, default=0.02, help="Degrees; ~2km, stable result across 0.01-0.05 in testing")
    args = parser.parse_args()

    route_out = args.route_out or (DATA_DIR / "routes" / f"{slugify(args.route)}.geojson")

    route_geom = prep_route(args.route, args.routes_source, route_out, args.simplify_tolerance)
    prep_stations(route_geom, args.stations_source, args.stations_out, args.station_buffer, args.station_list)


if __name__ == "__main__":
    main()
