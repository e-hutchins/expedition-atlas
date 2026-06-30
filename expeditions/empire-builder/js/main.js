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
 * GTFS times in Amtrak's feed are all written in one reference
 * timezone, regardless of which station they belong to -- confirmed by
 * checking that travel speed between consecutive stops stays smooth
 * straight through every real timezone boundary on the route
 * (Central/Mountain at Williston, Mountain/Pacific near Sandpoint), with
 * no artificial jump, which there would be if times were already each
 * station's local time.
 *
 * That check alone can't tell you *which* zone is the reference, though
 * -- only that there is one. That's agency.txt's agency_timezone for
 * Amtrak's main agency (id 51, which owns the Empire Builder route in
 * routes.txt): America/New_York, i.e. Eastern, not Chicago/Central
 * despite Chicago being the route's hub. Each station's actual
 * timezone (stops.txt's stop_timezone field, carried into the timetable
 * JSON by prep_amtrak_timetable.py) is used below to shift the
 * displayed time to that station's local time.
 */
const REFERENCE_TIMEZONE = "America/New_York";

// Standard (non-DST) UTC offset in hours for each timezone this feed
// uses. Only the *difference* between two zones is used below, and that
// difference is the same with or without DST -- the contiguous-US zones
// here all observe DST on the same dates, so the table doesn't need to
// track DST itself, just each zone's relative position.
const ZONE_UTC_OFFSET_HOURS = {
  "America/New_York": -5,
  "America/Chicago": -6,
  "America/Denver": -7,
  "America/Los_Angeles": -8,
};

/**
 * Current timezone abbreviation (e.g. "CDT", "MST") for an IANA zone,
 * via the browser's Intl API against today's date. This is what makes
 * the label DST-aware without a DST rules table of our own -- the
 * browser already knows whether daylight time is in effect today.
 *
 * @param {string} timezone - IANA zone name, e.g. "America/Denver"
 * @returns {string} e.g. "MDT", or "" if the zone isn't recognized
 */
function getZoneAbbreviation(timezone) {
  try {
    const parts = new Intl.DateTimeFormat("en-US", { timeZone: timezone, timeZoneName: "short" }).formatToParts(new Date());
    return (parts.find((part) => part.type === "timeZoneName") || {}).value || "";
  } catch (e) {
    return "";
  }
}

/**
 * Format a GTFS time string ("HH:MM:SS"), written in REFERENCE_TIMEZONE,
 * as a 12-hour clock time in a specific station's local timezone, with
 * that timezone's abbreviation appended. GTFS allows hours >= 24 to
 * represent times after midnight on a later day of a multi-day trip
 * (Empire Builder takes ~46 hours end to end); shifting timezones can
 * itself cross a day boundary, so the day-offset is recomputed after
 * applying the shift rather than carried over from the raw GTFS hour.
 *
 * @param {string} gtfsTime - e.g. "16:05:00" or "62:30:00"
 * @param {string} [stopTimezone] - the station's IANA timezone (from
 *   stop_timezone); falls back to no shift/label if missing
 * @returns {string} e.g. "5:35 PM CDT" or "12:17 PM PDT (+2d)"
 */
function formatGtfsTime(gtfsTime, stopTimezone) {
  const [hh, mm] = gtfsTime.split(":").map(Number);
  const referenceOffset = ZONE_UTC_OFFSET_HOURS[REFERENCE_TIMEZONE];
  const targetOffset = (stopTimezone && ZONE_UTC_OFFSET_HOURS[stopTimezone]) ?? referenceOffset;
  const shiftMinutes = (targetOffset - referenceOffset) * 60;

  const totalMinutes = hh * 60 + mm + shiftMinutes;
  const dayOffset = Math.floor(totalMinutes / (24 * 60));
  const hour24 = ((Math.floor(totalMinutes / 60) % 24) + 24) % 24;
  const minute = ((totalMinutes % 60) + 60) % 60;

  const period = hour24 >= 12 ? "PM" : "AM";
  const hour12 = hour24 % 12 || 12;
  const mmStr = String(minute).padStart(2, "0");
  const zoneLabel = stopTimezone ? getZoneAbbreviation(stopTimezone) : "";
  const suffix = dayOffset > 0 ? ` (+${dayOffset}d)` : "";
  return `${hour12}:${mmStr} ${period}${zoneLabel ? ` ${zoneLabel}` : ""}${suffix}`;
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
        timezone: stop.stop_timezone,
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
            `Train ${e.trainNumber} &rarr; ${e.headsign}<br>arr ${formatGtfsTime(e.arrival, e.timezone)} / dep ${formatGtfsTime(e.departure, e.timezone)}`
        )
        .join("<br><br>")
    : `<em>No ${directionLabel.toLowerCase()} schedule data available.</em>`;

  const elevationHtml = p.elevation_ft != null ? `Elevation: ${p.elevation_ft} ft<br>` : "";
  const mileageHtml = p.mile != null ? `Mile ${p.mile}${p.branch ? ` (${p.branch} branch)` : ""}<br>` : "";

  return `
    <strong>${p.name || "Station"}</strong><br>
    ${p.amtrak_code || ""}${place ? ` &middot; ${place}` : ""}<br>
    ${mileageHtml}
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
