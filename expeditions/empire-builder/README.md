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
- `data/station_list.md` - authoritative Empire Builder stop list, used to cross-reference the spatial-join station output; [copied from Amtrak website]((https://www.amtrak.com/empire-builder-train)

See [../../project-guidelines/DATA.md](../../project-guidelines/DATA.md) for the Route, Station, and POI schemas.