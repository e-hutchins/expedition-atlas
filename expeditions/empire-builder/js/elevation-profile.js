// expeditions/empire-builder/js/elevation-profile.js
//
// Renders the elevation-profile chart from data/elevation/empire-builder-profile.json
// (built by scripts/prep_elevation.py --mode profile). Separate from
// main.js/Leaflet since this is a Chart.js chart, not a map layer.

const PROFILE_URL = "data/elevation/empire-builder-profile.json";

// Empire Builder forks at Spokane into a Seattle and a Portland section
// (see route_sampling.sample_forked_route) -- one color per branch.
const BRANCH_COLORS = {
  seattle: "#1a4d8f",
  portland: "#8f5a1a",
};

/**
 * Build one Chart.js line dataset per branch, each made up of the shared
 * trunk points plus that branch's own points, sorted by mile so the line
 * draws continuously from the start of the route.
 *
 * @param {Array<{mile: number, elevation_ft: number, branch?: string}>} points
 * @returns {Array} Chart.js dataset objects
 */
function buildDatasets(points) {
  const trunkPoints = points.filter((p) => !p.branch);
  const branchNames = [...new Set(points.filter((p) => p.branch).map((p) => p.branch))];

  if (branchNames.length === 0) {
    return [
      {
        label: "Elevation",
        data: trunkPoints.map((p) => ({ x: p.mile, y: p.elevation_ft })),
        borderColor: "#1a4d8f",
        fill: false,
        pointRadius: 2,
      },
    ];
  }

  return branchNames.map((name) => {
    const combined = [...trunkPoints, ...points.filter((p) => p.branch === name)].sort(
      (a, b) => a.mile - b.mile
    );
    return {
      label: name.charAt(0).toUpperCase() + name.slice(1),
      data: combined.map((p) => ({ x: p.mile, y: p.elevation_ft })),
      borderColor: BRANCH_COLORS[name] || "#666",
      fill: false,
      pointRadius: 2,
    };
  });
}

/**
 * Fetch the elevation profile and render it as a Chart.js line chart. If
 * no points have been generated yet (the placeholder file's empty
 * "points": [] state, before someone runs prep_elevation.py with live
 * network access), hides the chart container instead of showing an
 * empty/broken chart.
 *
 * @returns {Promise<void>}
 */
async function initElevationProfile() {
  const container = document.getElementById("elevation-profile-container");
  const response = await fetch(PROFILE_URL);
  const data = await response.json();

  if (!data.points || data.points.length === 0) {
    container.style.display = "none";
    return;
  }

  new Chart(document.getElementById("elevation-profile-chart"), {
    type: "line",
    data: { datasets: buildDatasets(data.points) },
    options: {
      parsing: false,
      scales: {
        x: { type: "linear", title: { display: true, text: "Mile" } },
        y: { title: { display: true, text: "Elevation (ft)" } },
      },
    },
  });
}

document.addEventListener("DOMContentLoaded", initElevationProfile);
