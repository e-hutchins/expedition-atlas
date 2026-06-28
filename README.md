# expedition-atlas
interactive travel atlas(es) that combine maps, history, train routes, and points of interest

## Structure

- `index.html` - landing page, links to each expedition
- `shared/` - CSS/JS used by more than one expedition (keep this minimal)
- `expeditions/<name>/` - one self-contained folder per expedition (its own HTML, CSS, JS, and GeoJSON data). Adding a new expedition means adding one new folder here.
- `project-guidelines/DATA.md` - GeoJSON schemas (POI, Station)

Plain static HTML/CSS/JS + Leaflet, served via GitHub Pages. No build step.
