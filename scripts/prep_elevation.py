"""
prep_elevation.py

One-off data prep script -- NOT part of the live website. Looks up
elevation from the USGS Elevation Point Query Service (EPQS):
https://epqs.nationalmap.gov/v1/docs -- free, no API key, backed by the
3DEP elevation dataset (~0.5m RMSE accuracy). EPQS only covers the
United States, which is fine for an Amtrak route.

Two modes:
  --mode stations  Adds "elevation_ft" to every feature in
                    stations.geojson (one EPQS query per station).
  --mode profile    Samples the route every --interval-miles (handling
                    forked routes the same way prep_mile_markers.py
                    does -- see route_sampling.sample_forked_route) and
                    queries elevation at each sample, writing a profile
                    JSON for the elevation-profile chart.

EPQS has no batch endpoint -- this script queries sequentially with a
short delay between requests as a courtesy to the free public service,
so a full profile run (a few hundred points) can take several minutes.

Requires: only the standard library.

Usage (run from the repo root):
  python3 scripts/prep_elevation.py --mode stations
  python3 scripts/prep_elevation.py --mode profile --interval-miles 5
"""

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from route_sampling import sample_forked_route

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "expeditions" / "empire-builder" / "data"
EPQS_URL = "https://epqs.nationalmap.gov/v1/json"

# Same Empire Builder defaults as prep_mile_markers.py -- the route forks
# at Spokane into Seattle and Portland sections.
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


def fetch_elevation_ft(lon, lat):
    params = urllib.parse.urlencode({"x": lon, "y": lat, "units": "Feet", "wkid": 4326, "includeDate": "false"})
    with urllib.request.urlopen(f"{EPQS_URL}?{params}", timeout=15) as response:
        data = json.loads(response.read())
    return round(data["value"], 1)


def add_station_elevations(stations_path, delay):
    data = json.loads(stations_path.read_text())
    for feature in data["features"]:
        lon, lat = feature["geometry"]["coordinates"]
        elevation = fetch_elevation_ft(lon, lat)
        feature["properties"]["elevation_ft"] = elevation
        print(f"  {feature['properties'].get('amtrak_code')}: {elevation} ft")
        time.sleep(delay)
    stations_path.write_text(json.dumps(data, indent=2))
    print(f"wrote {stations_path} ({len(data['features'])} stations)")


def build_profile(route_source, start, branches, interval_miles, delay):
    source = json.loads(route_source.read_text())
    multiline = source["features"][0]["geometry"]["coordinates"]
    samples, trunk_length = sample_forked_route(multiline, start, branches, interval_miles)

    points = []
    for s in samples:
        elevation = fetch_elevation_ft(s["lon"], s["lat"])
        point = {"mile": s["mile"], "lat": s["lat"], "lon": s["lon"], "elevation_ft": elevation}
        if s["branch"] is not None:
            point["branch"] = s["branch"]
        points.append(point)
        print(f"  mile {s['mile']} ({s['branch'] or 'trunk'}): {elevation} ft")
        time.sleep(delay)

    route_name = source["features"][0]["properties"].get("name")
    return {"route": route_name, "trunk_length_miles": round(trunk_length, 1), "points": points}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["stations", "profile"], required=True)
    parser.add_argument("--stations-path", type=Path, default=DATA_DIR / "stations" / "stations.geojson")
    parser.add_argument("--route-source", type=Path, default=DATA_DIR / "routes" / "empire-builder.geojson")
    parser.add_argument("--profile-out", type=Path, default=DATA_DIR / "elevation" / "empire-builder-profile.json")
    parser.add_argument("--interval-miles", type=float, default=5, help="Distance between profile sample points")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between EPQS requests")
    parser.add_argument("--start", type=parse_lonlat, default=DEFAULT_START, help='"lon,lat" of the route\'s starting endpoint (profile mode only)')
    parser.add_argument(
        "--branch",
        action="append",
        dest="branches",
        type=parse_branch,
        default=None,
        help='"name:lon,lat" of a branch endpoint -- repeatable (profile mode only)',
    )
    args = parser.parse_args()

    if args.mode == "stations":
        add_station_elevations(args.stations_path, args.delay)
    else:
        branches = dict(args.branches) if args.branches else DEFAULT_BRANCHES
        output = build_profile(args.route_source, args.start, branches, args.interval_miles, args.delay)
        args.profile_out.parent.mkdir(parents=True, exist_ok=True)
        args.profile_out.write_text(json.dumps(output, indent=2))
        print(f"wrote {args.profile_out} ({len(output['points'])} points)")


if __name__ == "__main__":
    main()
