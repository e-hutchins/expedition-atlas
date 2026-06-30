"""
prep_mile_markers.py

One-off data prep script -- NOT part of the live website. Places a marker
every N miles along a route, for the mile-marker overlay on the map.

Distance is great-circle (haversine) distance along the route's
simplified line, not actual track mileage -- a visual reference, not an
exact match to official Amtrak timetable mileposts.

Some routes (Empire Builder among them) aren't a single line -- they
fork partway through (Empire Builder splits at Spokane into a Seattle
section and a Portland section). route_sampling.sample_forked_route()
reconstructs the route's actual topology from its GeoJSON
MultiLineString sub-lines and walks each branch separately, sharing
mileage on the common trunk. A route with only one branch (no fork)
works the same way with every marker simply tagged branch=None.

Requires: only the standard library.

Usage (run from the repo root):
  python3 scripts/prep_mile_markers.py
  python3 scripts/prep_mile_markers.py --interval-miles 50

  # a different, unforked route -- one --branch is just that route's far end.
  # --start/--branch are required for any route other than Empire Builder,
  # since there's no way to derive a route's geography from its name alone.
  python3 scripts/prep_mile_markers.py \
      --route "California Zephyr" \
      --start "-87.6298,41.8786" --branch "emeryville:-122.2885,37.8406"
"""

import argparse
import json
from pathlib import Path

from config import DEFAULT_ROUTE, EMPIRE_BUILDER_START, EMPIRE_BUILDER_BRANCHES, expedition_data_dir
from helpers import slugify, parse_lonlat, parse_branch
from route_sampling import sample_forked_route, resolve_start_and_branches


def build_mile_markers(route_source, start, branches, interval_miles):
    source = json.loads(route_source.read_text())
    multiline = source["features"][0]["geometry"]["coordinates"]
    samples, trunk_length = sample_forked_route(multiline, start, branches, interval_miles)

    features = []
    for s in samples:
        properties = {"mile": s["mile"]}
        if s["branch"] is not None:
            properties["branch"] = s["branch"]
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
                "properties": properties,
            }
        )
    return {"type": "FeatureCollection", "features": features}, trunk_length


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--route", default=DEFAULT_ROUTE, help="Route name, used to derive default --expedition/--route-source/--out paths")
    parser.add_argument("--expedition", default=None, help="Expedition folder name under expeditions/ -- defaults to the slugified --route name")
    parser.add_argument("--route-source", type=Path, default=None, help="Defaults to <expedition>/data/routes/<slugified-route>.geojson")
    parser.add_argument("--out", type=Path, default=None, help="Defaults to <expedition>/data/mile-markers/<slugified-route>-mile-markers.geojson")
    parser.add_argument("--interval-miles", type=float, default=100, help="Distance between markers")
    parser.add_argument("--start", type=parse_lonlat, default=None, help='"lon,lat" of the route\'s starting endpoint -- required for any route other than Empire Builder')
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
    route_source = args.route_source or (data_dir / "routes" / f"{slugify(args.route)}.geojson")
    out = args.out or (data_dir / "mile-markers" / f"{slugify(args.route)}-mile-markers.geojson")
    start, branches = resolve_start_and_branches(
        args.route, args.start, args.branches, DEFAULT_ROUTE, EMPIRE_BUILDER_START, EMPIRE_BUILDER_BRANCHES
    )

    output, trunk_length = build_mile_markers(route_source, start, branches, args.interval_miles)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2))
    print(f"wrote {out} ({len(output['features'])} markers)")
    print(f"trunk length (shared by all branches): ~{trunk_length:.0f} miles")


if __name__ == "__main__":
    main()
