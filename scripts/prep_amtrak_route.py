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

Each station also gets a "mile" property (distance along the route
from --start, in the same units/method as prep_mile_markers.py) and,
past a fork, a "branch" property -- computed by projecting the
station onto the route line (see route_sampling.project_station_onto_route).
--start/--branch are optional only for Empire Builder; required
together for any other route, since there's no way to derive a
route's geography from its name alone.

Requires: shapely (pip install shapely)

Usage (run from the repo root):
  python scripts/prep_amtrak_route.py
  python scripts/prep_amtrak_route.py \
      --route "California Zephyr" --expedition california-zephyr \
      --start "-87.6298,41.8786" --branch "emeryville:-122.2885,37.8406"
"""

import argparse
import json
import re
from pathlib import Path

from shapely.geometry import Point, shape, mapping

from config import NTAD_DIR, DEFAULT_ROUTE, EMPIRE_BUILDER_START, EMPIRE_BUILDER_BRANCHES, expedition_data_dir
from helpers import slugify, parse_lonlat, parse_branch
from route_sampling import resolve_start_and_branches, project_station_onto_route


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


def prep_stations(route_geom, stations_source, out_path, buffer_deg, station_list_path, route_multiline, start, branches):
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

        lon, lat = feat["geometry"]["coordinates"]
        mile, branch = project_station_onto_route(route_multiline, start, branches, lon, lat)

        properties = {
            "name": name,
            "amtrak_code": code,
            "city": p.get("City"),
            "state": p.get("State"),
            "mile": round(mile, 1),
            # arrival, departure, elevation_ft from the
            # project-guidelines/DATA.md schema are NOT present
            # in this source -- they need a timetable / DEM
            # source and are intentionally left out rather than
            # invented.
        }
        if branch is not None:
            properties["branch"] = branch

        matches.append({"type": "Feature", "geometry": feat["geometry"], "properties": properties})

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
    parser.add_argument("--route", default=DEFAULT_ROUTE, help="Route name as it appears in the NTAD routes file")
    parser.add_argument("--expedition", default=None, help="Expedition folder name under expeditions/ -- defaults to the slugified --route name")
    parser.add_argument("--routes-source", type=Path, default=NTAD_DIR / "NTAD_Amtrak_Routes_5503594535609073988.geojson")
    parser.add_argument("--stations-source", type=Path, default=NTAD_DIR / "NTAD_Amtrak_Stations_8364964222168212810.geojson")
    parser.add_argument("--route-out", type=Path, default=None, help="Defaults to <expedition>/data/routes/<slugified-route-name>.geojson")
    parser.add_argument("--stations-out", type=Path, default=None, help="Defaults to <expedition>/data/stations/stations.geojson")
    parser.add_argument("--station-list", type=Path, default=None, help="Optional markdown file of official stops, one per line ending in (CODE), used to filter out shared-corridor false positives. Defaults to <expedition>/data/station_list.md")
    parser.add_argument("--simplify-tolerance", type=float, default=0.0005, help="Degrees; ~50m, cuts ~45k points down to ~2.4k")
    parser.add_argument("--station-buffer", type=float, default=0.02, help="Degrees; ~2km, stable result across 0.01-0.05 in testing")
    parser.add_argument("--start", type=parse_lonlat, default=None, help='"lon,lat" of the route\'s starting endpoint, used to compute each station\'s mileage -- required for any route other than Empire Builder')
    parser.add_argument(
        "--branch",
        action="append",
        dest="branches",
        type=parse_branch,
        default=None,
        help='"name:lon,lat" of a branch endpoint -- repeatable. A route with no fork just needs one. Required (with --start) for any route other than Empire Builder.',
    )
    args = parser.parse_args()

    data_dir = expedition_data_dir(args.expedition or slugify(args.route))
    route_out = args.route_out or (data_dir / "routes" / f"{slugify(args.route)}.geojson")
    stations_out = args.stations_out or (data_dir / "stations" / "stations.geojson")
    station_list = args.station_list or (data_dir / "station_list.md")
    start, branches = resolve_start_and_branches(
        args.route, args.start, args.branches, DEFAULT_ROUTE, EMPIRE_BUILDER_START, EMPIRE_BUILDER_BRANCHES
    )

    route_geom = prep_route(args.route, args.routes_source, route_out, args.simplify_tolerance)
    route_multiline = (
        [list(line.coords) for line in route_geom.geoms]
        if route_geom.geom_type == "MultiLineString"
        else [list(route_geom.coords)]
    )
    prep_stations(route_geom, args.stations_source, stations_out, args.station_buffer, station_list, route_multiline, start, branches)


if __name__ == "__main__":
    main()
