// expeditions/empire-builder/js/main.js
//
// Entry point for the Empire Builder expedition page. Loads the route,
// station, and POI GeoJSON layers, wires up the layer control, legend,
// and popups, then fits the map to whatever data actually loaded.
//
// The data files this page reads (see DATA_URLS below) start out as
// empty FeatureCollections -- so this page works before real data is
// dropped in, and once routes/stations/POIs are added to those files,
// they'll show up here with no code changes.

// Path and display info for each GeoJSON file this page loads. Add a
// new entry here when a new route dataset is dropped into data/routes/.
const DATA_URLS = {
  routes: [
    { name: "Empire Builder", url: "data/routes/empire-builder.geojson", color: "#1a4d8f" },
    { name: "Oregon Trail", url: "data/routes/oregon-trail.geojson", color: "#8f5a1a" },
    { name: "Lewis & Clark", url: "data/routes/lewis-clark.geojson", color: "#1a8f4d" },
  ],
  stations: "data/stations/stations.geojson",
  pois: "data/pois/pois.geojson",
  mileMarkers: "data/mile-markers/empire-builder-mile-markers.geojson",
  timetable: {
    westbound: "data/timetable/empire-builder-westbound.json",
    eastbound: "data/timetable/empire-builder-eastbound.json",
  },
};

/**
 * Format a GTFS time string ("HH:MM:SS") as a 12-hour clock time.
 * GTFS allows hours >= 24 to represent times after midnight on a later
 * day of a multi-day trip (Empire Builder takes ~46 hours end to end),
 * so this also appends a "+Nd" suffix when that happens.
 *
 * @param {string} gtfsTime - e.g. "16:05:00" or "62:30:00"
 * @returns {string} e.g. "4:05 PM" or "2:30 PM (+2d)"
 */
function formatGtfsTime(gtfsTime) {
  const [hh, mm] = gtfsTime.split(":").map(Number);
  const dayOffset = Math.floor(hh / 24);
  const hour24 = hh % 24;
  const period = hour24 >= 12 ? "PM" : "AM";
  const hour12 = hour24 % 12 || 12;
  const mmStr = String(mm).padStart(2, "0");
  const suffix = dayOffset > 0 ? ` (+${dayOffset}d)` : "";
  return `${hour12}:${mmStr} ${period}${suffix}`;
}

/**
 * Index a timetable's trips by stop_id, so a station's schedule can be
 * looked up directly by its Amtrak code. A stop_id can map to more than
 * one trip (e.g. shared-corridor stations served by both the Seattle
 * and Portland sections before/after they split at Spokane).
 *
 * @param {{trips: Array}} timetable - parsed timetable JSON
 * @returns {Map<string, Array<{trainNumber, headsign, arrival, departure}>>}
 */
function buildStopIndex(timetable) {
  const index = new Map();
  (timetable.trips || []).forEach((trip) => {
    trip.stops.forEach((stop) => {
      const entries = index.get(stop.stop_id) || [];
      entries.push({
        trainNumber: trip.train_number,
        headsign: trip.headsign,
        arrival: stop.arrival_time,
        departure: stop.departure_time,
      });
      index.set(stop.stop_id, entries);
    });
  });
  return index;
}

/**
 * Fetch both direction timetables and index them by stop_id.
 *
 * @returns {Promise<{westbound: Map, eastbound: Map}>}
 */
async function loadTimetables() {
  const [westbound, eastbound] = await Promise.all([
    fetch(DATA_URLS.timetable.westbound).then((r) => r.json()),
    fetch(DATA_URLS.timetable.eastbound).then((r) => r.json()),
  ]);
  return {
    westbound: buildStopIndex(westbound),
    eastbound: buildStopIndex(eastbound),
  };
}

/**
 * Create the base Leaflet map with a default view and tile layer.
 * Centered on the continental US so the page shows something sensible
 * even before route data is loaded (fitBounds() later narrows this
 * down once real data is present).
 *
 * @returns {L.Map}
 */
function createMap() {
  const map = L.map("map").setView([47, -100], 5);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);
  return map;
}

/**
 * Load one route GeoJSON file as a styled, popup-enabled layer.
 *
 * @param {L.Map} map
 * @param {{name: string, url: string, color: string}} route
 * @returns {Promise<L.GeoJSON>}
 */
function loadRouteLayer(map, route) {
  return loadGeoJsonLayer(map, route.url, {
    style: { color: route.color, weight: 4 },
    onEachFeature: (feature, layer) => {
      const title = (feature.properties && feature.properties.name) || route.name;
      layer.bindPopup(title);
    },
  });
}

/**
 * Build the hover tooltip content for a station. Kept short and
 * direction-independent so it doesn't need updating when the
 * eastbound/westbound toggle changes.
 *
 * @param {object} p - station GeoJSON properties
 * @returns {string} HTML
 */
function buildStationTooltipHtml(p) {
  const place = p.city ? `${p.city}, ${p.state || ""}` : "";
  return `<strong>${p.name || "Station"}</strong><br>${p.amtrak_code || ""}${place ? ` &middot; ${place}` : ""}`;
}

/**
 * Build the click popup content for a station: place details plus the
 * schedule for the currently-selected direction. Stations with no
 * schedule entry for that direction (e.g. Browning, MT is missing from
 * the GTFS feed entirely) fall back to a "no data" message instead of
 * erroring or showing nothing.
 *
 * @param {object} p - station GeoJSON properties
 * @param {string} direction - "westbound" or "eastbound"
 * @param {{westbound: Map, eastbound: Map}} stopIndexByDirection
 * @returns {string} HTML
 */
function buildStationPopupHtml(p, direction, stopIndexByDirection) {
  const place = p.city ? `${p.city}, ${p.state || ""}` : "";
  const directionLabel = direction === "eastbound" ? "Eastbound" : "Westbound";
  const entries = (stopIndexByDirection[direction] && stopIndexByDirection[direction].get(p.amtrak_code)) || [];

  const scheduleHtml = entries.length
    ? entries
        .map(
          (e) =>
            `Train ${e.trainNumber} &rarr; ${e.headsign}<br>arr ${formatGtfsTime(e.arrival)} / dep ${formatGtfsTime(e.departure)}`
        )
        .join("<br><br>")
    : `<em>No ${directionLabel.toLowerCase()} schedule data available.</em>`;

  const elevationHtml = p.elevation_ft != null ? `Elevation: ${p.elevation_ft} ft<br>` : "";

  return `
    <strong>${p.name || "Station"}</strong><br>
    ${p.amtrak_code || ""}${place ? ` &middot; ${place}` : ""}<br>
    ${elevationHtml}
    <hr>
    <strong>${directionLabel}</strong><br>
    ${scheduleHtml}
  `;
}

/**
 * Load the station point layer with a hover tooltip (quick info) and a
 * click popup (full info + the selected direction's schedule).
 * Property names match the Station schema in project-guidelines/DATA.md.
 *
 * @param {L.Map} map
 * @param {{westbound: Map, eastbound: Map}} stopIndexByDirection
 * @param {string} initialDirection
 * @returns {Promise<L.GeoJSON>}
 */
function loadStationLayer(map, stopIndexByDirection, initialDirection) {
  return loadGeoJsonLayer(map, DATA_URLS.stations, {
    pointToLayer: (feature, latlng) =>
      L.circleMarker(latlng, { radius: 6, color: "#1a4d8f", fillOpacity: 0.8 }),
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      layer.bindTooltip(buildStationTooltipHtml(p), { direction: "top", sticky: true });
      layer.bindPopup(buildStationPopupHtml(p, initialDirection, stopIndexByDirection));
    },
  });
}

/**
 * Refresh every station marker's popup content for a newly-selected
 * direction. Tooltips don't need updating since they're direction-independent.
 *
 * @param {L.GeoJSON} stationLayer
 * @param {{westbound: Map, eastbound: Map}} stopIndexByDirection
 * @param {string} direction
 */
function updateStationSchedules(stationLayer, stopIndexByDirection, direction) {
  stationLayer.eachLayer((marker) => {
    const p = marker.feature.properties || {};
    marker.setPopupContent(buildStationPopupHtml(p, direction, stopIndexByDirection));
  });
}

/**
 * Add a toggle control for switching the displayed schedule direction.
 *
 * @param {L.Map} map
 * @param {string} initialDirection
 * @param {(direction: string) => void} onChange
 */
function addDirectionToggle(map, initialDirection, onChange) {
  const control = L.control({ position: "topleft" });
  control.onAdd = () => {
    const div = L.DomUtil.create("div", "direction-toggle");
    div.innerHTML = `
      <strong>Schedule direction</strong>
      <label><input type="radio" name="direction" value="westbound" ${initialDirection === "westbound" ? "checked" : ""}> Westbound</label>
      <label><input type="radio" name="direction" value="eastbound" ${initialDirection === "eastbound" ? "checked" : ""}> Eastbound</label>
    `;
    L.DomEvent.disableClickPropagation(div);
    div.querySelectorAll('input[name="direction"]').forEach((input) => {
      input.addEventListener("change", (event) => onChange(event.target.value));
    });
    return div;
  };
  control.addTo(map);
}

/**
 * Load the points-of-interest layer with popups showing POI details.
 * Property names match the POI schema in project-guidelines/DATA.md.
 *
 * @param {L.Map} map
 * @returns {Promise<L.GeoJSON>}
 */
function loadPoiLayer(map) {
  return loadGeoJsonLayer(map, DATA_URLS.pois, {
    pointToLayer: (feature, latlng) => L.marker(latlng),
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      layer.bindPopup(`<strong>${p.name || "Point of interest"}</strong><br>${p.description || ""}`);
    },
  });
}

/**
 * Load the mile-marker point layer: small reference dots every N miles
 * along the route (see scripts/prep_mile_markers.py), each with a
 * tooltip showing its mile number and, past the Spokane fork, which
 * branch it's on. Decorative/reference layer, so it's added to the
 * layer control but switched off by default (see initEmpireBuilderMap).
 *
 * @param {L.Map} map
 * @returns {Promise<L.GeoJSON>}
 */
function loadMileMarkerLayer(map) {
  return loadGeoJsonLayer(map, DATA_URLS.mileMarkers, {
    pointToLayer: (feature, latlng) =>
      L.circleMarker(latlng, { radius: 3, color: "#666", weight: 1, fillOpacity: 0.6 }),
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      const branchSuffix = p.branch ? ` (${p.branch})` : "";
      layer.bindTooltip(`Mile ${p.mile}${branchSuffix}`, { direction: "top" });
    },
  });
}

/**
 * Add a legend control listing each route's color.
 *
 * @param {L.Map} map
 */
function addLegend(map) {
  const legend = L.control({ position: "bottomright" });
  legend.onAdd = () => {
    const div = L.DomUtil.create("div", "legend");
    const rows = DATA_URLS.routes
      .map(
        (route) =>
          `<div><span class="legend-swatch" style="background:${route.color}"></span>${route.name}</div>`
      )
      .join("");
    div.innerHTML = `<strong>Routes</strong>${rows}`;
    return div;
  };
  legend.addTo(map);
}

/**
 * Fit the map to the combined bounds of whichever layers actually have
 * data. Layers loaded from still-empty GeoJSON files have no bounds,
 * so they're skipped -- this keeps the default view from breaking
 * before real data is dropped in.
 *
 * @param {L.Map} map
 * @param {L.GeoJSON[]} layers
 */
function fitToLoadedLayers(map, layers) {
  let bounds = null;
  layers.forEach((layer) => {
    const layerBounds = layer.getBounds();
    if (layerBounds.isValid()) {
      bounds = bounds ? bounds.extend(layerBounds) : layerBounds;
    }
  });
  if (bounds && bounds.isValid()) {
    map.fitBounds(bounds);
  }
}

/**
 * Initialize the Empire Builder map: create it, load every GeoJSON
 * layer, wire up the layer control and legend, then fit the view to
 * whatever data is actually present.
 *
 * @returns {Promise<void>}
 */
async function initEmpireBuilderMap() {
  const map = createMap();
  addLegend(map);

  let currentDirection = "westbound";
  const [routeLayers, stopIndexByDirection] = await Promise.all([
    Promise.all(DATA_URLS.routes.map((route) => loadRouteLayer(map, route))),
    loadTimetables(),
  ]);
  const stationLayer = await loadStationLayer(map, stopIndexByDirection, currentDirection);
  const poiLayer = await loadPoiLayer(map);
  const mileMarkerLayer = await loadMileMarkerLayer(map);
  map.removeLayer(mileMarkerLayer); // decorative layer, off by default

  addDirectionToggle(map, currentDirection, (direction) => {
    currentDirection = direction;
    updateStationSchedules(stationLayer, stopIndexByDirection, currentDirection);
  });

  const overlays = {};
  DATA_URLS.routes.forEach((route, i) => {
    overlays[route.name] = routeLayers[i];
  });
  overlays["Stations"] = stationLayer;
  overlays["Points of Interest"] = poiLayer;
  overlays["Mile Markers"] = mileMarkerLayer;
  L.control.layers(null, overlays).addTo(map);

  fitToLoadedLayers(map, [...routeLayers, stationLayer, poiLayer]);
}

document.addEventListener("DOMContentLoaded", initEmpireBuilderMap);
