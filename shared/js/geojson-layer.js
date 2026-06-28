// shared/js/geojson-layer.js
//
// Shared helper for loading a GeoJSON file and adding it to a Leaflet
// map as a layer. Lives here (rather than in an expedition's own js/)
// because more than one expedition will need this same logic.

/**
 * Fetch a GeoJSON file and add it to a Leaflet map as a layer.
 *
 * @param {L.Map} map - the Leaflet map instance to add the layer to.
 * @param {string} url - path to the GeoJSON file to load.
 * @param {Object} [options] - Leaflet GeoJSON layer options (style,
 *   pointToLayer, onEachFeature for popups, etc.), passed through to
 *   L.geoJSON().
 * @returns {Promise<L.GeoJSON>} resolves with the layer once it has
 *   been added to the map.
 */
async function loadGeoJsonLayer(map, url, options = {}) {
  const response = await fetch(url);
  const data = await response.json();
  const layer = L.geoJSON(data, options);
  layer.addTo(map);
  return layer;
}
