"""
route_sampling.py

Shared helper used by prep_mile_markers.py and prep_elevation.py: measures
great-circle (haversine) distance along a route's GeoJSON LineString
vertices and interpolates evenly-spaced sample points along it.

Distance is measured along the route's already-simplified line (see
prep_amtrak_route.py's --simplify-tolerance), not actual track mileage --
close enough for placing reference markers/samples, but it won't exactly
match official timetable mileposts.

Requires: only the standard library.
"""

import math


def haversine_miles(lon1, lat1, lon2, lat2):
    """Great-circle distance between two lon/lat points, in miles."""
    earth_radius_miles = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * earth_radius_miles * math.asin(math.sqrt(a))


def sample_route_points(coordinates, interval_miles):
    """
    Walk a LineString's [lon, lat] vertices (in order from one end of the
    route to the other) and return a point every interval_miles, plus the
    route's total length.

    Always includes mile 0 (the first vertex) and the final endpoint, even
    if the endpoint doesn't land exactly on an interval boundary.

    @param coordinates: list of [lon, lat] vertices
    @param interval_miles: distance between samples
    @returns: (samples, total_miles) where samples is a list of
        {"mile": float, "lon": float, "lat": float}, ordered by mile
    """
    samples = [{"mile": 0.0, "lon": coordinates[0][0], "lat": coordinates[0][1]}]
    next_target = interval_miles
    cumulative = 0.0

    for i in range(len(coordinates) - 1):
        lon1, lat1 = coordinates[i]
        lon2, lat2 = coordinates[i + 1]
        seg_len = haversine_miles(lon1, lat1, lon2, lat2)
        seg_start = cumulative
        cumulative += seg_len

        while seg_len > 0 and next_target <= cumulative:
            frac = (next_target - seg_start) / seg_len
            lon = lon1 + frac * (lon2 - lon1)
            lat = lat1 + frac * (lat2 - lat1)
            samples.append({"mile": round(next_target, 1), "lon": lon, "lat": lat})
            next_target += interval_miles

    if samples[-1]["mile"] < cumulative - 0.5:
        samples.append({"mile": round(cumulative, 1), "lon": coordinates[-1][0], "lat": coordinates[-1][1]})

    return samples, cumulative


def _segment_length_miles(coords):
    return sum(haversine_miles(*coords[i], *coords[i + 1]) for i in range(len(coords) - 1))


def build_route_graph(multiline_coords, snap_miles=0.5):
    """
    Reconstruct a route's topology from a GeoJSON MultiLineString's
    sub-lines. Real-world rail GeoJSON exports (e.g. NTAD) often split a
    route into many sub-lines whose order has no meaning, and some routes
    -- like Empire Builder splitting at Spokane into Seattle and Portland
    sections -- genuinely fork, so there's no single "walk the line"
    ordering.

    Endpoints within snap_miles of each other are merged into one node
    (handles small digitization gaps/duplicate stub segments at
    junctions). Self-loop edges (both ends snapping to the same node --
    typically tiny duplicate stub segments) are dropped.

    @param multiline_coords: list of sub-lines, each a list of [lon, lat]
    @param snap_miles: endpoints closer than this are treated as the same junction
    @returns: (node_coords, edges) where node_coords is a list of (lon, lat)
        and edges is a list of {"a": node_idx, "b": node_idx, "coords": [...],
        "length_miles": float} (coords ordered from a to b)
    """
    node_coords = []
    endpoint_to_node = {}

    def node_for(lon, lat):
        for n, (nlon, nlat) in enumerate(node_coords):
            if haversine_miles(lon, lat, nlon, nlat) <= snap_miles:
                return n
        node_coords.append((lon, lat))
        return len(node_coords) - 1

    edges = []
    for coords in multiline_coords:
        a = node_for(*coords[0])
        b = node_for(*coords[-1])
        if a == b:
            continue
        edges.append({"a": a, "b": b, "coords": coords, "length_miles": _segment_length_miles(coords)})

    return node_coords, edges


def nearest_node(node_coords, lon, lat):
    """Index of the node closest to (lon, lat)."""
    return min(range(len(node_coords)), key=lambda n: haversine_miles(lon, lat, *node_coords[n]))


def find_path_segments(edges, num_nodes, start_node, end_node):
    """
    Breadth-first search over `edges` (an undirected multigraph) for a
    path from start_node to end_node. Routes reconstructed by
    build_route_graph are tree-shaped (no alternate routes), so any path
    found is the only path -- this doesn't need shortest-path weighting.

    @returns: ordered list of (edge_index, reversed) -- reversed is True
        when the edge's coords need flipping to run start->end -- or None
        if no path exists.
    """
    adjacency = {n: [] for n in range(num_nodes)}
    for i, edge in enumerate(edges):
        adjacency[edge["a"]].append((edge["b"], i, False))
        adjacency[edge["b"]].append((edge["a"], i, True))

    visited = {start_node}
    queue = [(start_node, [])]
    while queue:
        node, path = queue.pop(0)
        if node == end_node:
            return path
        for neighbor, edge_index, reversed_ in adjacency[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [(edge_index, reversed_)]))
    return None


def path_to_coords(edges, path_segments):
    """Concatenate a find_path_segments() result into one ordered
    [lon, lat] coordinate list, deduplicating shared junction points."""
    coords = []
    for edge_index, reversed_ in path_segments:
        segment_coords = edges[edge_index]["coords"]
        if reversed_:
            segment_coords = list(reversed(segment_coords))
        if coords and coords[-1] == segment_coords[0]:
            coords.extend(segment_coords[1:])
        else:
            coords.extend(segment_coords)
    return coords


def resolve_start_and_branches(route, start, branches, default_route, default_start, default_branches):
    """
    Resolve which --start/--branch endpoints a prep script should use.
    --start and --branch are optional only for `default_route` (the route
    a script's built-in defaults describe) -- there's no way to derive a
    different route's start/fork geography from its name alone, so any
    other route must supply both explicitly.

    @param route: the --route value the user passed (or its default)
    @param start: the parsed --start value, or None if omitted
    @param branches: the parsed --branch values (list of (name, (lon, lat))), or None if omitted
    @param default_route: the route name --start/--branch are allowed to be omitted for
    @param default_start: (lon, lat) to use when they're omitted for default_route
    @param default_branches: dict of {name: (lon, lat)} to use when omitted for default_route
    @returns: (start, branches) -- branches as a dict of {name: (lon, lat)}
    """
    if start is None and branches is None:
        if route != default_route:
            raise SystemExit(f'--start and --branch are required for any route other than "{default_route}"')
        return default_start, default_branches
    if start is not None and branches is not None:
        return start, dict(branches)
    raise SystemExit("--start and --branch must be provided together")


def sample_forked_route(multiline_coords, start_lonlat, branches, interval_miles):
    """
    Sample a route every interval_miles, handling routes that fork into
    more than one branch (e.g. Empire Builder splitting at Spokane into
    Seattle and Portland sections). Each named branch endpoint gets its
    own path from start_lonlat; the longest shared prefix of those paths
    is the trunk (mileage measured from start_lonlat), and samples past
    that point are tagged with which branch they're on. A route with a
    single branch (no fork) just gets every sample tagged branch=None.

    @param multiline_coords: the route's GeoJSON MultiLineString sub-lines
    @param start_lonlat: (lon, lat) of the route's starting endpoint
    @param branches: dict of {branch_name: (lon, lat)} endpoint per branch
    @param interval_miles: distance between samples
    @returns: (samples, trunk_length_miles) where samples is a list of
        {"mile": float, "lon": float, "lat": float, "branch": str or None},
        trunk samples first (sorted by mile), then each branch's samples
        in `branches` order (sorted by mile)
    """
    node_coords, edges = build_route_graph(multiline_coords)
    start_node = nearest_node(node_coords, *start_lonlat)

    path_segments_by_branch = {}
    path_coords_by_branch = {}
    for name, (lon, lat) in branches.items():
        end_node = nearest_node(node_coords, lon, lat)
        segments = find_path_segments(edges, len(node_coords), start_node, end_node)
        if segments is None:
            raise ValueError(f"no path found from the start point to branch endpoint '{name}'")
        path_segments_by_branch[name] = segments
        path_coords_by_branch[name] = path_to_coords(edges, segments)

    all_segment_lists = list(path_segments_by_branch.values())
    common_len = 0
    while common_len < len(all_segment_lists[0]) and all(
        common_len < len(segs) and segs[common_len] == all_segment_lists[0][common_len]
        for segs in all_segment_lists
    ):
        common_len += 1
    trunk_length_miles = sum(edges[i]["length_miles"] for i, _ in all_segment_lists[0][:common_len])

    trunk_samples = {}
    branch_samples_by_name = {name: [] for name in branches}
    for name, coords in path_coords_by_branch.items():
        points, _ = sample_route_points(coords, interval_miles)
        for point in points:
            if point["mile"] <= trunk_length_miles + 1e-6:
                trunk_samples[point["mile"]] = point
            else:
                branch_samples_by_name[name].append(point)

    samples = [{**point, "branch": None} for point in sorted(trunk_samples.values(), key=lambda p: p["mile"])]
    for name in branches:
        ordered = sorted(branch_samples_by_name[name], key=lambda p: p["mile"])
        samples.extend({**point, "branch": name} for point in ordered)

    return samples, trunk_length_miles
