# File Architecture

## Project shape

Expedition Atlas is a static GitHub Pages site with one landing page and one folder per expedition.

Each expedition is self-contained: it has its own HTML, CSS, JavaScript, and app-ready data. Shared code and styles live at the repository root.

## Top-level structure

```text
expedition-atlas/
├── index.html              # site landing page
├── expeditions/            # one folder per expedition
├── shared/                 # reusable frontend assets
├── raw-data/               # downloaded source data
├── scripts/                # preprocessing scripts
├── project-guidelines/     # project documentation
├── README.md
└── LICENSE
```

## Amtrak Expedition Structure

`expeditions/<expedition-name>/`
├── index.html
├── README.md
├── css/
│   └── style.css
├── js/
│   └── main.js
└── data/
    ├── routes/
    ├── stations/
    ├── pois/
    ├── timetable/
    ├── elevation/
    └── mile-markers/

## Data flow
raw-data/
    ↓
scripts/
    ↓
`expeditions/<expedition-name>/data/`
    ↓
Leaflet site

