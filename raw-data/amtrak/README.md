## Data sources

 - [USDOT BTS Amtrak routes](https://data-usdot.opendata.arcgis.com/datasets/usdot::amtrak-routes/about) | download NTAD_Amtrak_Routes_5503594535609073988.geojson and put in [`ntad`](ntad/) |
 - [USDOT BTS Amtrak stations](https://geodata.bts.gov/datasets/usdot::amtrak-stations/about) | download NTAD_Amtrak_Stations_8364964222168212810.geojson and put in [`ntad`](ntad/) |
 - [Timetables](https://content.amtrak.com/content/gtfs/GTFS.zip) | can wget or download and put in [`gtfs`](gtfs/); see below |

## Data download

### Timetables

```
cd raw-data/amtrak/gtfs
wget https://content.amtrak.com/content/gtfs/GTFS.zip
unzip GTFS.zip
rm GTFS.zip
```

## Data prep scripts

The Amtrak data prep scripts live in the repo's top-level [`/scripts/`](../../scripts/) folder (not under this expedition folder) since they're written to prep any Amtrak route, not just Empire Builder. See [`scripts/README.md`](../../scripts/README.md) for what each one does and how to run it.

