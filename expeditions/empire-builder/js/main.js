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
};

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
 * Load the station point layer with popups showing station details.
 * Property names match the Station schema in project-guidelines/DATA.md.
 *
 * @param {L.Map} map
 * @returns {Promise<L.GeoJSON>}
 */
function loadStationLayer(map) {
  return loadGeoJsonLayer(map, DATA_URLS.stations, {
    pointToLayer: (feature, latlng) =>
      L.circleMarker(latlng, { radius: 6, color: "#1a4d8f", fillOpacity: 0.8 }),
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      layer.bindPopup(`<strong>${p.name || "Station"}</strong><br>${p.amtrak_code || ""}`);
    },
  });
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

  const routeLayers = await Promise.all(DATA_URLS.routes.map((route) => loadRouteLayer(map, route)));
  const stationLayer = await loadStationLayer(map);
  const poiLayer = await loadPoiLayer(map);

  const overlays = {};
  DATA_URLS.routes.forEach((route, i) => {
    overlays[route.name] = routeLayers[i];
  });
  overlays["Stations"] = stationLayer;
  overlays["Points of Interest"] = poiLayer;
  L.control.layers(null, overlays).addTo(map);

  fitToLoadedLayers(map, [...routeLayers, stationLayer, poiLayer]);
}

document.addEventListener("DOMContentLoaded", initEmpireBuilderMap);
