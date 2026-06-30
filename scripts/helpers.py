"""
helpers.py

Small utility functions shared across the data prep scripts: slugifying
a route name for use in a filename, and parsing the "lon,lat" /
"name:lon,lat" CLI argument formats used by prep_mile_markers.py and
prep_elevation.py.
"""


def slugify(name):
    return name.lower().replace(" ", "-")


def parse_lonlat(s):
    lon, lat = s.split(",")
    return (float(lon), float(lat))


def parse_branch(s):
    name, coords = s.split(":", 1)
    return name, parse_lonlat(coords)
