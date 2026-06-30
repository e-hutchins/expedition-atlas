# Data

## GeoJSON Schemas

### POI 
{
  "name": "...",
  "category": "...",
  "description": "...",
  "sources": [],
  "image": "...",
  "expedition": "empire-builder"
}

### Route
{
  "name": "...",
  "source_url": "..."
}

### Station 
{
  "name": "...",
  "amtrak_code": "...",
  "city": "...",
  "state": "...",
  "mile": 0,
  "branch": "...",
  "elevation_ft": 0
}

`mile` is the station's distance along the route from its starting endpoint, and `branch` follows the same convention as Mile Marker below (only present past a route's fork point) -- both computed by `scripts/prep_amtrak_route.py` via `route_sampling.project_station_onto_route`.

`elevation_ft` is optional -- it's added to stations.geojson by `scripts/prep_elevation.py --mode apply-stations`, which merges a cached station-elevations file (`data/elevation/<route>-station-elevations.json`, written once by `--mode fetch-stations` from the USGS Elevation Point Query Service) by `amtrak_code`. The fetch/apply split means a stations.geojson rebuild (e.g. via `prep_amtrak_route.py`) only needs the network-free apply step, not a fresh EPQS query per station.

### Mile Marker
{
  "mile": 0,
  "branch": "..."
}

Built by `scripts/prep_mile_markers.py`. `branch` is only present on markers past a route's fork point (e.g. Empire Builder splits at Spokane into "seattle" and "portland") -- markers on the shared trunk have no `branch` property.

### Elevation Profile Point
{
  "mile": 0,
  "lat": 0,
  "lon": 0,
  "elevation_ft": 0,
  "branch": "..."
}

Built by `scripts/prep_elevation.py --mode profile`, one file per route with `{"route": "...", "trunk_length_miles": 0, "points": [...]}`. Same `branch` convention as Mile Marker.