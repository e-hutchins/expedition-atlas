# Data prep scripts

One-off scripts that turn raw Amtrak/NTAD/GTFS/USGS source data into the
GeoJSON/JSON files an expedition's page actually loads. None of these
are part of the live website -- run them manually, from the **repo
root**, whenever a source file changes or a new route is added.

They're written to prep any Amtrak route, not just Empire Builder, which
is why they live here rather than under an expedition's own folder (see
project principle: shared code only lives outside an expedition folder
when more than one expedition needs it). Every script defaults to
Empire Builder's data when run with no arguments; pass `--route` (and,
for the two scripts that need geographic endpoints, `--start`/`--branch`)
to prep a different route instead. All four scripts also take
`--expedition`, which controls which `expeditions/<expedition>/data/`
folder output is written to/read from -- it defaults to the slugified
`--route` name, so it only needs to be passed explicitly if an
expedition's folder name doesn't match its route's slug.

`config.py`, `helpers.py`, and `route_sampling.py` are shared modules,
not scripts you run directly. `config.py` holds the repo-path
constants (`NTAD_DIR`, `GTFS_DIR`), the `expedition_data_dir()` helper
used to resolve `--expedition` into a path, and Empire Builder's
default route name/start/branch coordinates, all four scripts import
from it. `helpers.py` holds `slugify()` (all four scripts) and the
`--start`/`--branch` CLI parsers (`prep_mile_markers.py` and
`prep_elevation.py`). `route_sampling.py` is used by
`prep_mile_markers.py` and `prep_elevation.py` for great-circle
distance/interpolation and for reconstructing a route's topology when
it forks (see below).

## prep_amtrak_route.py

Regenerates the route and station GeoJSON from the raw NTAD files in
[`raw-data/amtrak/ntad/`](../raw-data/amtrak/) (see that folder's
README for what to download and where). Pulls one named route out of
the nationwide NTAD routes export, simplifies its geometry, and
spatial-joins nationwide stations against it -- then drops any match
not on `data/station_list.md` (catches shared-corridor false positives
like a station on a connecting service's track).

Requires `shapely` (`pip install shapely`).

Run with no arguments to regenerate the Empire Builder files (the
defaults):

```
python3 scripts/prep_amtrak_route.py
```

This overwrites `expeditions/empire-builder/data/routes/empire-builder.geojson`
and `expeditions/empire-builder/data/stations/stations.geojson`. Run it
again whenever the raw NTAD files change.

To prep a different Amtrak route into its own expedition folder, pass
`--route` and `--expedition` (otherwise it'll look for a route named
"Empire Builder" and overwrite the Empire Builder route file):

```
python3 scripts/prep_amtrak_route.py \
  --route "California Zephyr" --expedition california-zephyr
```

A station list for that route isn't required -- if `--station-list`
points to a file that doesn't exist, the script skips cross-referencing
and falls back to the spatial join alone (with no false-positive
filtering). All other tuning (`--simplify-tolerance`, `--station-buffer`,
source/output paths) is also exposed as flags; run
`python3 scripts/prep_amtrak_route.py --help` for the full list.

## prep_amtrak_timetable.py

Builds `data/timetable/<route>-<direction>.json` from the GTFS files in
[`raw-data/amtrak/gtfs/`](../raw-data/amtrak/) (routes.txt, trips.txt,
stop_times.txt, stops.txt). Each output file lists every trip running
in that direction, with its ordered stops, lat/lon, and
arrival/departure times.

Requires only the Python standard library.

```
python3 scripts/prep_amtrak_timetable.py
```

This writes `expeditions/empire-builder/data/timetable/empire-builder-westbound.json`
and `empire-builder-eastbound.json`. GTFS's `direction_id` (0/1) has no
fixed real-world meaning -- for Empire Builder, 0 happens to be
westbound and 1 eastbound (confirmed against trip headsigns), which is
the script's default. For a different or non-east/west route, pass
`--route`, `--direction-0`, and `--direction-1`, and verify the mapping
yourself:

```
python3 scripts/prep_amtrak_timetable.py --route "Coast Starlight" --direction-0 southbound --direction-1 northbound
```

## prep_mile_markers.py

Places a marker every N miles along a route, for the mile-marker map
overlay. Distance is great-circle (haversine) distance along the
route's simplified line, not actual track mileage -- a visual
reference, not an exact match to official timetable mileposts.

Some routes (Empire Builder among them) aren't a single line -- they
fork partway through (Empire Builder splits at Spokane into a Seattle
section and a Portland section). `route_sampling.sample_forked_route()`
reconstructs the route's actual topology from its GeoJSON
MultiLineString sub-lines and walks each branch separately, sharing
mileage on the common trunk. A route with only one branch (no fork)
works the same way with every marker simply tagged `branch=None`.

Requires only the Python standard library.

Run with no arguments to regenerate Empire Builder's mile markers (the
default):

```
python3 scripts/prep_mile_markers.py
python3 scripts/prep_mile_markers.py --interval-miles 50
```

This writes `expeditions/empire-builder/data/mile-markers/empire-builder-mile-markers.geojson`.

For a different route, pass `--route` (used to derive default
`--route-source`/`--out` paths via the route's slugified name) plus
`--start` and `--branch` -- both are **required together** for any
route other than Empire Builder, since there's no way to derive a
route's start/fork geography from its name alone. A route with no fork
just needs one `--branch` (that route's far end):

```
python3 scripts/prep_mile_markers.py \
  --route "California Zephyr" \
  --start "-87.6298,41.8786" --branch "emeryville:-122.2885,37.8406"
```

## prep_elevation.py

Looks up elevation from the [USGS Elevation Point Query Service](https://epqs.nationalmap.gov/v1/docs)
(free, no API key, backed by the 3DEP dataset, ~0.5m RMSE accuracy,
US-only -- fine for an Amtrak route). It has two modes: `stations` adds
`elevation_ft` to every feature in `stations.geojson`, and `profile`
samples the route (same fork-handling as `prep_mile_markers.py`) and
writes an elevation-profile JSON for the chart on the map page.

EPQS has no batch endpoint, so this queries one point at a time with a
short delay between requests as a courtesy to the free service -- a
full profile run (a few hundred points) can take several minutes. Each
request retries a few times with a short backoff on timeout/connection
errors before giving up, so a transient drop doesn't kill the whole
run. **This script needs outbound network access to
`epqs.nationalmap.gov`; run it from your own machine, not a
network-restricted environment.**

Requires only the Python standard library.

```
python3 scripts/prep_elevation.py --mode stations
python3 scripts/prep_elevation.py --mode profile --interval-miles 5
```

This overwrites `expeditions/empire-builder/data/stations/stations.geojson`
(adding `elevation_ft`) and writes
`expeditions/empire-builder/data/elevation/empire-builder-profile.json`.
Until you run `profile` mode, that file stays at its placeholder
`"points": []` state and the elevation-profile chart on the page just
stays hidden.

`--mode profile` takes the same `--route`/`--start`/`--branch` flags as
`prep_mile_markers.py`, with the same rule: required together for any
route other than Empire Builder.

```
python3 scripts/prep_elevation.py --mode profile \
  --route "California Zephyr" \
  --start "-87.6298,41.8786" --branch "emeryville:-122.2885,37.8406"
```
