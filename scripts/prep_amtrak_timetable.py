"""
prep_amtrak_timetable.py

One-off data prep script -- NOT part of the live website. Builds
per-direction timetable JSON for an Amtrak route from raw GTFS files
(routes.txt, trips.txt, stop_times.txt, stops.txt) in data/raw/.

GTFS's direction_id is just a 0/1 flag with no fixed real-world
meaning -- it varies by agency/route. For Empire Builder, direction_id
0 trips head to Seattle/Portland (headsign) and direction_id 1 trips
head to Chicago, so 0 = westbound and 1 = eastbound. That mapping is
NOT automatic for other routes (e.g. a north-south route) -- pass
--direction-0/--direction-1 to relabel, and verify against trip
headsigns before trusting the output.

calendar.txt / calendar_dates.txt (service exceptions) are not used
here: as of this writing Empire Builder has a single calendar entry
that runs every day of the week, so there's no exception schedule to
reconcile. A route with seasonal or day-specific trips would need
that logic added.

Requires: only the standard library (csv, json).

Usage (run from the repo root):
  python scripts/prep_amtrak_timetable.py
  python scripts/prep_amtrak_timetable.py --route "Coast Starlight" --direction-0 southbound --direction-1 northbound
"""

import argparse
import csv
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
# This script lives at the repo root (scripts/), one level above the
# expeditions/ folder -- defaults below point at Empire Builder's data,
# but every path is a CLI flag for prepping a different expedition's data.
DATA_DIR = SCRIPT_DIR.parent / "expeditions" / "empire-builder" / "data"
RAW_DATA_DIR = DATA_DIR / "raw"


def slugify(name):
    return name.lower().replace(" ", "-")


def read_csv(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def build_timetables(route_name, raw_dir, direction_labels):
    routes = read_csv(raw_dir / "routes.txt")
    route = next((r for r in routes if r["route_long_name"] == route_name), None)
    if route is None:
        raise SystemExit(f'route "{route_name}" not found in {raw_dir / "routes.txt"}')
    route_id = route["route_id"]

    trips = [t for t in read_csv(raw_dir / "trips.txt") if t["route_id"] == route_id]
    if not trips:
        raise SystemExit(f'no trips found for route_id {route_id} ({route_name})')

    stops_by_id = {s["stop_id"]: s for s in read_csv(raw_dir / "stops.txt")}

    stop_times_by_trip = {}
    for row in read_csv(raw_dir / "stop_times.txt"):
        stop_times_by_trip.setdefault(row["trip_id"], []).append(row)

    by_direction = {"0": [], "1": []}
    for trip in trips:
        trip_id = trip["trip_id"]
        stop_rows = sorted(stop_times_by_trip.get(trip_id, []), key=lambda r: int(r["stop_sequence"]))

        stops = []
        for row in stop_rows:
            stop = stops_by_id.get(row["stop_id"], {})
            stops.append(
                {
                    "stop_id": row["stop_id"],
                    "name": stop.get("stop_name"),
                    "lat": float(stop["stop_lat"]) if stop.get("stop_lat") else None,
                    "lon": float(stop["stop_lon"]) if stop.get("stop_lon") else None,
                    "stop_sequence": int(row["stop_sequence"]),
                    "arrival_time": row["arrival_time"],
                    "departure_time": row["departure_time"],
                }
            )

        by_direction.setdefault(trip["direction_id"], []).append(
            {
                "trip_id": trip_id,
                "train_number": trip.get("trip_short_name"),
                "headsign": trip.get("trip_headsign"),
                "stops": stops,
            }
        )

    return {direction_labels.get(k, k): v for k, v in by_direction.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route", default="Empire Builder", help="Route name as it appears in routes.txt (route_long_name)")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=DATA_DIR / "timetable")
    parser.add_argument("--direction-0", default="westbound", help="Label for GTFS direction_id 0 -- verify against headsigns for a new route")
    parser.add_argument("--direction-1", default="eastbound", help="Label for GTFS direction_id 1 -- verify against headsigns for a new route")
    args = parser.parse_args()

    direction_labels = {"0": args.direction_0, "1": args.direction_1}
    by_direction = build_timetables(args.route, args.raw_dir, direction_labels)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(args.route)
    for label, trips in by_direction.items():
        out_path = args.out_dir / f"{slug}-{label}.json"
        output = {"route": args.route, "direction": label, "trips": trips}
        out_path.write_text(json.dumps(output, indent=2))
        print(f"wrote {out_path} ({len(trips)} trip(s))")
        for t in trips:
            print(f"  - train {t['train_number']} -> {t['headsign']} ({len(t['stops'])} stops)")


if __name__ == "__main__":
    main()
