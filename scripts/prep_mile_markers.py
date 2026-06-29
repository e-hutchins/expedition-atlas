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

  # a different, unforked route -- one --branch is just that route's far end
  python3 scripts/prep_mile_markers.py \
      --route-source expeditions/empire-builder/data/routes/california-zephyr.geojson \
      --out expeditions/empire-builder/data/mile-markers/california-zephyr-mile-markers.geojson \
      --start "-87.6298,41.8786" --branch "emeryville:-122.2885,37.8406"
"""

import argparse
import json
from pathlib import Path

from route_sampling import sample_forked_route

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "expeditions" / "empire-builder" / "data"

# Empire Builder forks at Spokane -- defaults below cover both sections.
DEFAULT_START = (-87.6386255917863, 41.8786208960517)  # Chicago
DEFAULT_BRANCHES = {
    "seattle": (-122.329440335734, 47.5963013692978),
    "portland": (-122.673348451259, 45.5274512051907),
}


def parse_lonlat(s):
    lon, lat = s.split(",")
    return (float(lon), float(lat))


def parse_branch(s):
    name, coords = s.split(":", 1)
    return name, parse_lonlat(coords)


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
    parser.add_argument("--route-source", type=Path, default=DATA_DIR / "routes" / "empire-builder.geojson")
    parser.add_argument("--out", type=Path, default=DATA_DIR / "mile-markers" / "empire-builder-mile-markers.geojson")
    parser.add_argument("--interval-miles", type=float, default=100, help="Distance between markers")
    parser.add_argument("--start", type=parse_lonlat, default=DEFAULT_START, help='"lon,lat" of the route\'s starting endpoint')
    parser.add_argument(
        "--branch",
        action="append",
        dest="branches",
        type=parse_branch,
        default=None,
        help='"name:lon,lat" of a branch endpoint -- repeatable. A route with no fork just needs one.',
    )
    args = parser.parse_args()

    branches = dict(args.branches) if args.branches else DEFAULT_BRANCHES

    output, trunk_length = build_mile_markers(args.route_source, args.start, branches, args.interval_miles)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2))
    print(f"wrote {args.out} ({len(output['features'])} markers)")
    print(f"trunk length (shared by all branches): ~{trunk_length:.0f} miles")


if __name__ == "__main__":
    main()
