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
  "elevation_ft": 0
}

`elevation_ft` is optional -- it's filled in by `scripts/prep_elevation.py --mode stations` from the USGS Elevation Point Query Service. It was deliberately left out of this schema earlier because we had no real source for it; now that we do, it's back, sourced rather than invented.

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