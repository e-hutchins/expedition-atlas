# Amtrak Empire Builder

First expedition in Expedition Atlas: the Amtrak Empire Builder route.

## Data

GeoJSON overlays live in `data/`, one subfolder per layer type:

- `data/routes/` - route line overlays (Empire Builder, Oregon Trail, Lewis & Clark, etc.)
- `data/stations/` - station point markers
- `data/pois/` - points of interest
- `data/timetable/` - per-direction schedule JSON (stops, times) built from Amtrak's GTFS feed
- `data/mile-markers/` - mile-marker point overlay, placed every N miles along a route
- `data/elevation/` - elevation profile JSON (mile vs. elevation_ft), used by the elevation-profile chart
- `data/raw/` - raw NTAD/BTS/GTFS downloads (gitignored, not site assets)
- `data/station_list.md` - authoritative Empire Builder stop list, used to cross-reference the spatial-join station output; copied from Amtrak website

See [../../project-guidelines/DATA.md](../../project-guidelines/DATA.md) for the Route, Station, and POI schemas.

## Data sources

 - [USDOT BTS Amtrak routes](https://data-usdot.opendata.arcgis.com/datasets/usdot::amtrak-routes/about) | download NTAD_Amtrak_Routes_5503594535609073988.geojson and put in [data/raw](data/raw) |
 - [USDOT BTS Amtrak stations](https://geodata.bts.gov/datasets/usdot::amtrak-stations/about) | download NTAD_Amtrak_Stations_8364964222168212810.geojson and put in [data/raw](data/raw) |
 - [Empire Builder station list](https://www.amtrak.com/empire-builder-train)
 - [Timetables](https://content.amtrak.com/content/gtfs/GTFS.zip)

## Data download

### Timetables

```
cd expeditions/empire-builder/data/raw
wget https://content.amtrak.com/content/gtfs/GTFS.zip
unzip GTFS.zip
```

## Data prep scripts

The Amtrak data prep scripts live in the repo's top-level [`/scripts/`](../../scripts/) folder (not under this expedition folder) since they're written to prep any Amtrak route, not just Empire Builder. Run both from the **repo root**.

`scripts/prep_amtrak_route.py` regenerates the route and station GeoJSON from the raw NTAD files in `data/raw/`. It pulls one named route out of the nationwide NTAD routes export, simplifies its geometry, and spatial-joins nationwide stations against it -- then drops any match not on `data/station_list.md` (catches shared-corridor false positives like a station on a connecting service's track).

Requires `shapely` (`pip install shapely`).

Run with no arguments to regenerate the Empire Builder files (the defaults):

```
python3 scripts/prep_amtrak_route.py
```

This overwrites `expeditions/empire-builder/data/routes/empire-builder.geojson` and `expeditions/empire-builder/data/stations/stations.geojson`. Run it again whenever the raw NTAD files in `data/raw/` change.

To prep a different Amtrak route, pass `--route` and `--route-out` (otherwise it'll look for a route named "Empire Builder" and overwrite the Empire Builder route file):

```
python3 scripts/prep_amtrak_route.py \
  --route "California Zephyr" \
  --route-out expeditions/empire-builder/data/routes/california-zephyr.geojson
```

A station list for that route isn't required -- if `--station-list` points to a file that doesn't exist, the script skips cross-referencing and falls back to the spatial join alone (with no false-positive filtering). All other tuning (`--simplify-tolerance`, `--station-buffer`, source/output paths) is also exposed as flags; run `python3 scripts/prep_amtrak_route.py --help` for the full list.

`scripts/prep_amtrak_timetable.py` builds `data/timetable/<route>-<direction>.json` from the GTFS files in `data/raw/` (routes.txt, trips.txt, stop_times.txt, stops.txt). Each output file lists every trip running in that direction, with its ordered stops, lat/lon, and arrival/departure times.

Requires only the Python standard library.

```
python3 scripts/prep_amtrak_timetable.py
```

This writes `expeditions/empire-builder/data/timetable/empire-builder-westbound.json` and `empire-builder-eastbound.json`. GTFS's `direction_id` (0/1) has no fixed real-world meaning -- for Empire Builder, 0 happens to be westbound and 1 eastbound (confirmed against trip headsigns), which is the script's default. For a different or non-east/west route, pass `--route`, `--direction-0`, and `--direction-1`, and verify the mapping yourself:

```
python3 scripts/prep_amtrak_timetable.py --route "Coast Starlight" --direction-0 southbound --direction-1 northbound
```

`scripts/prep_mile_markers.py` places a marker every N miles along a route, for the mile-marker map overlay. Distance is great-circle (haversine), not actual track mileage -- a visual reference, not an exact match to official timetable mileposts. Empire Builder forks at Spokane into a Seattle and a Portland section; the script reconstructs that topology from the route's GeoJSON and walks each branch separately (see `scripts/route_sampling.py`), tagging markers past the fork with which branch they're on.

Requires only the Python standard library.

```
python3 scripts/prep_mile_markers.py
python3 scripts/prep_mile_markers.py --interval-miles 50
```

This writes `expeditions/empire-builder/data/mile-markers/empire-builder-mile-markers.geojson`. For a different, unforked route, pass `--route-source`, `--out`, `--start`, and a single `--branch` (that route's far end):

```
python3 scripts/prep_mile_markers.py \
  --route-source expeditions/empire-builder/data/routes/california-zephyr.geojson \
  --out expeditions/empire-builder/data/mile-markers/california-zephyr-mile-markers.geojson \
  --start "-87.6298,41.8786" --branch "emeryville:-122.2885,37.8406"
```

`scripts/prep_elevation.py` looks up elevation from the [USGS Elevation Point Query Service](https://epqs.nationalmap.gov/v1/docs) (free, no API key, backed by the 3DEP dataset, ~0.5m RMSE accuracy, US-only -- fine for an Amtrak route). It has two modes: `stations` adds `elevation_ft` to every feature in `stations.geojson`, and `profile` samples the route (same fork-handling as `prep_mile_markers.py`) and writes an elevation-profile JSON for the chart on the map page.

EPQS has no batch endpoint, so this queries one point at a time with a short delay between requests as a courtesy to the free service -- a full profile run (a few hundred points) can take several minutes. **This script needs outbound network access to `epqs.nationalmap.gov`; run it from your own machine, not a network-restricted environment.**

Requires only the Python standard library.

```
python3 scripts/prep_elevation.py --mode stations
python3 scripts/prep_elevation.py --mode profile --interval-miles 5
```

This overwrites `expeditions/empire-builder/data/stations/stations.geojson` (adding `elevation_ft`) and writes `expeditions/empire-builder/data/elevation/empire-builder-profile.json`. Until you run the `profile` mode, that file stays at its placeholder `"points": []` state and the elevation-profile chart on the page just stays hidden.

