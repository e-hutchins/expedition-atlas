# Amtrak Empire Builder

First expedition in Expedition Atlas: the Amtrak Empire Builder route.

## Data

GeoJSON overlays live in `data/`, one subfolder per layer type:

- `data/routes/` - route line overlays (Empire Builder, Oregon Trail, Lewis & Clark, etc.)
- `data/stations/` - station point markers
- `data/pois/` - points of interest
- `data/timetable/` - per-direction schedule JSON (stops, times) built from Amtrak's GTFS feed
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

