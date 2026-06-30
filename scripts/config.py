"""
config.py

Shared repo-path constants and Empire-Builder-specific defaults used
across the data prep scripts.

Each expedition's prepped data lives at expeditions/<expedition>/data/
-- use expedition_data_dir() to get that path. Every script's
--expedition flag defaults to the slugified --route name, since today
each Amtrak route gets its own same-named expedition folder; pass
--expedition explicitly if an expedition's folder name doesn't match
its route's slug.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
EXPEDITIONS_DIR = REPO_ROOT / "expeditions"

# Raw NTAD/GTFS downloads live outside any expedition folder, in the
# repo-root raw-data/ tree -- see raw-data/amtrak/README.md for what
# goes here and how to fetch it.
NTAD_DIR = REPO_ROOT / "raw-data" / "amtrak" / "ntad"
GTFS_DIR = REPO_ROOT / "raw-data" / "amtrak" / "gtfs"

DEFAULT_ROUTE = "Empire Builder"

# Only used as the zero-argument default for --route "Empire Builder" in
# prep_mile_markers.py and prep_elevation.py (it forks at Spokane into
# Seattle and Portland sections) -- any other route needs --start/--branch
# supplied explicitly; see route_sampling.resolve_start_and_branches.
EMPIRE_BUILDER_START = (-87.6386255917863, 41.8786208960517)  # Chicago
EMPIRE_BUILDER_BRANCHES = {
    "seattle": (-122.329440335734, 47.5963013692978),
    "portland": (-122.673348451259, 45.5274512051907),
}


def expedition_data_dir(expedition):
    """expeditions/<expedition>/data, e.g. expedition_data_dir("empire-builder")."""
    return EXPEDITIONS_DIR / expedition / "data"
