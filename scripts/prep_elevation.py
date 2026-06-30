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
Individual requests are retried a few times with a short backoff on
timeout/connection errors before giving up, since a transient drop
shouldn't have to kill a multi-minute run.

Requires: only the standard library.

Usage (run from the repo root):
  python3 scripts/prep_elevation.py --mode stations
  python3 scripts/prep_elevation.py --mode profile --interval-miles 5

  # a different, unforked route -- --start/--branch are required for any
  # route other than Empire Builder (no way to derive a route's geography
  # from its name alone)
  python3 scripts/prep_elevation.py --mode profile \
      --route "California Zephyr" \
      --start "-87.6298,41.8786" --branch "emeryville:-122.2885,37.8406"
"""

import argparse
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from config import DEFAULT_ROUTE, EMPIRE_BUILDER_START, EMPIRE_BUILDER_BRANCHES, expedition_data_dir
from helpers import slugify, parse_lonlat, parse_branch
from route_sampling import sample_forked_route, resolve_start_and_branches

EPQS_URL = "https://epqs.nationalmap.gov/v1/json"

EPQS_MAX_RETRIES = 3
EPQS_RETRY_BACKOFF_SECONDS = 5


def fetch_elevation_ft(lon, lat):
    params = urllib.parse.urlencode({"x": lon, "y": lat, "units": "Feet", "wkid": 4326, "includeDate": "false"})
    url = f"{EPQS_URL}?{params}"
    for attempt in range(1, EPQS_MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                data = json.loads(response.read())
            return round(data["value"], 1)
        except (socket.timeout, urllib.error.URLError) as e:
            if attempt == EPQS_MAX_RETRIES:
                raise
            print(f"    EPQS request failed ({e}), retrying in {EPQS_RETRY_BACKOFF_SECONDS}s ({attempt}/{EPQS_MAX_RETRIES})...")
            time.sleep(EPQS_RETRY_BACKOFF_SECONDS)


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
    parser.add_argument("--route", default=DEFAULT_ROUTE, help="Route name, used to derive default --expedition/--route-source/--profile-out paths (profile mode only)")
    parser.add_argument("--expedition", default=None, help="Expedition folder name under expeditions/ -- defaults to the slugified --route name")
    parser.add_argument("--stations-path", type=Path, default=None, help="Defaults to <expedition>/data/stations/stations.geojson")
    parser.add_argument("--route-source", type=Path, default=None, help="Defaults to <expedition>/data/routes/<slugified-route>.geojson (profile mode only)")
    parser.add_argument("--profile-out", type=Path, default=None, help="Defaults to <expedition>/data/elevation/<slugified-route>-profile.json (profile mode only)")
    parser.add_argument("--interval-miles", type=float, default=5, help="Distance between profile sample points")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between EPQS requests")
    parser.add_argument("--start", type=parse_lonlat, default=None, help='"lon,lat" of the route\'s starting endpoint -- required for any route other than Empire Builder (profile mode only)')
    parser.add_argument(
        "--branch",
        action="append",
        dest="branches",
        type=parse_branch,
        default=None,
        help='"name:lon,lat" of a branch endpoint -- repeatable. Required (with --start) for any route other than Empire Builder (profile mode only).',
    )
    args = parser.parse_args()

    data_dir = expedition_data_dir(args.expedition or slugify(args.route))
    stations_path = args.stations_path or (data_dir / "stations" / "stations.geojson")

    if args.mode == "stations":
        add_station_elevations(stations_path, args.delay)
    else:
        route_source = args.route_source or (data_dir / "routes" / f"{slugify(args.route)}.geojson")
        profile_out = args.profile_out or (data_dir / "elevation" / f"{slugify(args.route)}-profile.json")
        start, branches = resolve_start_and_branches(
            args.route, args.start, args.branches, DEFAULT_ROUTE, EMPIRE_BUILDER_START, EMPIRE_BUILDER_BRANCHES
        )
        output = build_profile(route_source, start, branches, args.interval_miles, args.delay)
        profile_out.parent.mkdir(parents=True, exist_ok=True)
        profile_out.write_text(json.dumps(output, indent=2))
        print(f"wrote {profile_out} ({len(output['points'])} points)")


if __name__ == "__main__":
    main()
