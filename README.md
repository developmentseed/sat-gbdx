# gbdx-search

GBDX search is a command line utility built on top of [sat-search](https://github.com/sat-utils/sat-search). It allows for easy searching of the GBDX catalog API using gbdxtools, downloading of thumbnails, and ordering of data.

All of the options for saving search results, controlling save directories, and output options like calendars in sat-search are supported.

When thumbnails are downloaded a world (.wld) file is created, which is a sidecar file that describes the coordinates and resolution of the images. This enables the thumbnails to be viewed in a GIS program like QGIS in their proper geographical location. The world file does not set the spatial reference system used (lat/lon, or WGS-84, or EPSG:4326), so when opened in QGIS it will need to be selected.

See the command line help for all the available options.

In GBDX the available satellite names are:

	- GEOEYE01
	- WORLDVIEW03_VNIR
	- LANDSAT08
	- WORLDVIEW01
	- QUICKBIRD02
	- WORLDVIEW02
	- IKONOS
	- WORLDVIEW03_SWIR

"""
e.g.,
./gbdx-search.py --intersects geojsonfile --printmd date scene_id satellite_name --clouds 0,10 --save ${gj%.*}
/scenes-gbdx.geojson --date 2015-01-01,2017-11-01 --datadir ${gj%.*} --nosubdirs --download thumb

Available satellite names
{'GEOEYE01', 'WORLDVIEW03_VNIR', 'LANDSAT08', 'WORLDVIEW01', 'QUICKBIRD02', 'WORLDVIEW02', 'IKONOS', 'WORLDVIEW03_SWIR'}

Available types
{"DigitalGlobeAcquisition", "GBDXCatalogRecord", "IDAHOImage"}

colorInterpretation
BGRN
PAN
WORLDVIEW_8_BAND

"""
```
usage: gbdx-search.py [-h] [--satellite_name SATELLITE_NAME]
                      [--scene_id [SCENE_ID [SCENE_ID ...]]]
                      [--intersects INTERSECTS] [--contains CONTAINS]
                      [--date DATE] [--clouds CLOUDS]
                      [--param [PARAM [PARAM ...]]] [--load LOAD]
                      [--save SAVE] [--append] [--printsearch]
                      [--printmd [PRINTMD [PRINTMD ...]]] [--printcal]
                      [--review] [--verbosity VERBOSITY] [--download]
                      [--order] [--datadir DATADIR]

GBDX Search

optional arguments:
  -h, --help            show this help message and exit
  --verbosity VERBOSITY
                        0:all, 1:debug, 2:info, 3:warning, 4:error, 5:critical
                        (default: 2)

search parameters:
  --satellite_name SATELLITE_NAME
                        Name of satellite (default: None)
  --scene_id [SCENE_ID [SCENE_ID ...]]
                        One or more scene IDs (default: None)
  --intersects INTERSECTS
                        GeoJSON Feature (file or string) (default: None)
  --contains CONTAINS   lon,lat points (default: None)
  --date DATE           Single date or begin and end date (e.g.,
                        2017-01-01,2017-02-15 (default: None)
  --clouds CLOUDS       Range of acceptable cloud cover (e.g., 0,20) (default:
                        None)
  --param [PARAM [PARAM ...]]
                        Additional parameters of form KEY=VALUE (default:
                        None)

saving/loading parameters:
  --load LOAD           Load search results from file (ignores other search
                        parameters) (default: None)
  --save SAVE           Save scenes metadata as GeoJSON (default: None)
  --append              Append scenes to GeoJSON file (specified by save)
                        (default: False)

search output:
  --printsearch         Print search parameters (default: False)
  --printmd [PRINTMD [PRINTMD ...]]
                        Print specified metadata for matched scenes (default:
                        None)
  --printcal            Print calendar showing dates (default: False)
  --review              Interactive review of thumbnails (default: False)

GBDX parameters:
  --download            Downlaod thumbnails (default: False)
  --order               Place order (default: False)
  --datadir DATADIR     Local directory to save images (default:
                        /home/mhanson/satutils-data)
```

## About
python-seed was created by [Development Seed](<http://developmentseed.org>)
