# SAT-GBDX

sat-gbdx is a command line utility and Python library built on top of [sat-search](https://github.com/sat-utils/sat-search), that allows for easy searching of the GBDX catalog, ordering of data, and downloading imagery. Under the hood, sat-gbdx interfaces with the GBDX API using [gbdxtools](https://github.com/DigitalGlobe/gbdxtools), but for the user it behaves almsot exactly like sat-search.

The goals of sat-gbdx are:

- Provide a convenient CLI as an interface to an end-user, rather than just developers
- Provide a [STAC](https://github.com/radiantearth/stac-spec) style wrapper to the GBDX API, allowing users to use STAC field names when searching the catalog
- Support all the features of sat-search: saving and loading scenes, downloading scenes, file organization
- Allow users to fetch and clip imagery to just their Area Of Interest


## Installation

Sat-gbdx is a Python 3 library that can be installed locally or the Dockerfile can be used as there are quite a few dependencies that must be installed. But first, sat-gbdx first requires access to GBDX.

##### GBDX Credentials

In order to access GBDX you will need valid credentials specified in one of two ways:

1. A ~/.gbdx-config file, placed in your home directory that has the following format:

```
[gbdx]
user_name = your_user_name
user_password = your_password
```

2. Defining the GBDX_USERNAME and GBDX_PASSWORD environment variables. Create a .env file and put your credentials in it. This can then be use them with Docker (see below) or you can export them to your shell.

```
GBDX_USERNAME=your_user_name
GBDX_PASSWORD=your_password
```
```
# export the .env file to the shell
$ set -o allexport; . .env; set +o allexport
```

##### Installing locally
To install locally you must be using Python 3 (a virtual environment is required), and must have GDAL installed. First clone the repo, then install the requirements, and then finally sat-gbdx.

```
$ git clone git@github.com:developmentseed/sat-gbdx.git
$ cd sat-gbdx
$ pip install -r requirements.txt
$ pip install .
```

##### With Docker
Rather than installing locally Docker can be used. Clone the repository and build the docker image.

```
$ git clone git@github.com:developmentseed/sat-gbdx.git
$ cd sat-gbdx
$ docker-compose build
```

Now the image can be run anywhere on your system, such as if you want to keep all your files in a work directory. Navigate to a work directory (such as one that has GeoJSON files containing Areas of Interest), and create a .env file with your GBDX credentials as given above. Then you can run the Docker image.

```
docker run --env-file .env -v $PWD:/home/geolambda/work -it developmentseed/sat-gbdx:latest /bin/bash
```

This runs the Docker image, adds the environment variables to the running container, mounts the current directory in the container, then provides you with a bash shell. You will initially be in the /home/geolambda directory, with your work directory under /home/geolambda/work

## Using sat-gbdx

Sat-gbdx has all the same functionality as sat-search:

- search catalog
- STAC compliant interface
- save results of a search
- load results of a search
- download assets (e.g. thumbnails, data files) of the results

In addition, sat-gbdx offers a few more features:

- fetch data just the Area of Interest and save as images clipped to the AOI
- ordering of images
- adding [ESRI Worldfiles](http://webhelp.esri.com/arcims/9.3/General/topics/author_world_files.htm) to the downloaded thumbnails so they can be treated as geospatial files (e.g., open in QGIS, use gdal utilities)
- calculation, and filtering, of overlap between the user AOI and the footprint of the data for each scene
- [COMING SOON] Searching of IDAHO catalog and downloading of IDAHO tiles

#### The CLI
The sat-gbdx CLI has an extensive online help that can be printed with the `-h` switch.
```
$ sat-gbdx -h
usage: sat-gbdx [-h] {search,load} ...

GBDX Search

positional arguments:
  {search,load}
    search       Perform new search of scenes
    load         Load scenes from previous search

optional arguments:
  -h, --help     show this help message and exit
```

As can be seen there are two subcommands, each of which has it's own online help (i.e. "sat-gbdx search -h" and "sat-gbdx-load -h") and will be discussed in detail below.

#### Searching

```
$ sat-gbdx search -h
usage: sat-gbdx search [-h] [--version] [-v VERBOSITY]
                       [--print_md [PRINT_MD [PRINT_MD ...]]] [--print_cal]
                       [--save SAVE] [--append] [-c [C:ID [C:ID ...]]]
                       [--intersects INTERSECTS] [--datetime DATETIME]
                       [--eo:cloud_cover EO:CLOUD_COVER]
                       [-p [PARAM [PARAM ...]]] [--url URL]
                       [--overlap OVERLAP]

optional arguments:
  -h, --help            show this help message and exit
  --version             Print version and exit
  -v VERBOSITY, --verbosity VERBOSITY
                        0:quiet, 1:error, 2:warning, 3:info, 4:debug (default:
                        2)

output options:
  --print_md [PRINT_MD [PRINT_MD ...]]
                        Print specified metadata for matched scenes (default:
                        None)
  --print_cal           Print calendar showing dates (default: False)
  --save SAVE           Save results as GeoJSON (default: None)
  --append              Append scenes to GeoJSON file (specified by save)
                        (default: False)

search options:
  -c [C:ID [C:ID ...]], --c:id [C:ID [C:ID ...]]
                        Name(s) of collection (default: None)
  --intersects INTERSECTS
                        GeoJSON Feature (file or string) (default: None)
  --datetime DATETIME   Single date/time or begin and end date/time (e.g.,
                        2017-01-01/2017-02-15 (default: None)
  --eo:cloud_cover EO:CLOUD_COVER
                        Range of acceptable cloud cover (e.g., 0/20) (default:
                        None)
  -p [PARAM [PARAM ...]], --param [PARAM [PARAM ...]]
                        Additional parameters of form KEY=VALUE (default:
                        None)
  --url URL             URL of the API (default: https://sat-
                        api.developmentseed.org)
  --overlap OVERLAP     Minimum % overlap of footprint to AOI (default: None)
```

**Search options**

- **c:id** - A list of names of collections (i.e. sensors). Currently the [collections supported](https://github.com/developmentseed/sat-gbdx/blob/master/satgbdx/collections.json) include: **quickbird-2, geoeye-1, worldview-1, worldview-2, worldview-3, and worldview-3-swir**. If one or more collections are not defined, all collections are searched.
- **intersects** - Provide a GeoJSON Feature string or the name of a GeoJSON file containing a single Feature that is a Polygon of an AOI to be searched.
- **datetime** - Provide a single partial or full datetime (e.g., 2017, 2017-10, 2017-10-11, 2017-10-11T12:00), or two seperated by a slash that defines a range. e.g., 2017-01-01/2017-06-30 will search for scenes acquired in the first 6 months of 2017.
- **eo:cloud_cover** - Provide a single percent cloud cover to match (e.g., 0) or two numbers separated by a slash indicating the range of acceptable cloud cover (e.g., 0/20 searches for scenes with 0% - 20% cloud cover).
- **overlap** - The minimum percent overlap that is acceptable. (e.g., 98 will only return scenes where the scene overlaps at least 98% of the AOI).
- **param** - Allows searching for any other scene properties, currently not supported in sat-gbdx tools
- **url** - Not used in sat-gbdx, the GBDX API is hard-coded

**Output options**
These options control what to do with the search results, multiple switches can be provided.

- **print_md** - Prints a list of specific metadata fields for all the scenes. If given without any arguments it will print a list of the dates and scene IDs. Otherwise it will print a list of fields that are provided. (e.g., --print_md date eo:cloud_cover eo:platform will print a list of date, cloud cover, and the satellite platform such as WORLDVIEW03)
- **print_cal** - Prints a text calendar with specific days colored depending on the platform of the scene (e.g. WORLDVIEW02), along with a legend.
- **save** - Saves results as a FeatureCollection. The FeatureCollection 'properties' contains all of the arguments used in the search and the 'features' contain all of the individual scenes, with individual scene metadata merged with collection level metadata (metadata fields that are the same across all one collection, such as eo:platform)
- **append** - The save option will always create a new file, even overwriting an existing one. If *append* is provided then the scenes will be appended to the FeatureCollection given by the save filename.

#### Loading
Scenes that were previously saved with `sat-gbdx search --save ...` can be loaded with the `load` subcommand.

```
$ sat-gbdx load -h
usage: sat-gbdx load [-h] [--version] [-v VERBOSITY]
                     [--print_md [PRINT_MD [PRINT_MD ...]]] [--print_cal]
                     [--save SAVE] [--append] [--datadir DATADIR]
                     [--filename FILENAME]
                     [--download [DOWNLOAD [DOWNLOAD ...]]] [--pansharp]
                     [--order]
                     scenes

positional arguments:
  scenes                GeoJSON file of scenes

optional arguments:
  -h, --help            show this help message and exit
  --version             Print version and exit
  -v VERBOSITY, --verbosity VERBOSITY
                        0:quiet, 1:error, 2:warning, 3:info, 4:debug (default:
                        2)

output options:
  --print_md [PRINT_MD [PRINT_MD ...]]
                        Print specified metadata for matched scenes (default:
                        None)
  --print_cal           Print calendar showing dates (default: False)
  --save SAVE           Save results as GeoJSON (default: None)
  --append              Append scenes to GeoJSON file (specified by save)
                        (default: False)

download options:
  --datadir DATADIR     Directory pattern to save assets (default: ./)
  --filename FILENAME   Save assets with this filename pattern based on
                        metadata keys (default: ${date}_${c:id}_${id})
  --download [DOWNLOAD [DOWNLOAD ...]]
                        Download assets (default: None)
  --pansharp            Pan-sharpen fetched tiles, if able (default: False)
  --order               Place order for these scenes (default: False)
```

Note that while the search options are gone, output options are still available and can be used with the search results loaded from the file. There is also a new series of options now, for downloading data.

#### Downloading assets
When loading results from a file, the user now has the option to download assets from the scenes.

**Download options**
These control the downloading of assets. Both datadir and filename can include metadata patterns that will be substituted per scene.
- **datadir** - This specifies where downloaded assets will be saved to. It can also be specified by setting the environment variable SATUTILS_DATADIR.
- **filename** - The name of the file to save. It can also be set by setting the environment variable SATUTILS_FILENAME
- **download** - Provide a list of keys to download these assets. For DG currently only **thumbnail** and **full** are supported. More information on downloading data is provided below.
- **order** - Orders the scenes (which go through an activation process before they can be accessed). Everytime --order is called sat-gbdx will print out the status of existing orders for these scenes.
- **parnsharp** - Downloaded full scenes will be pan-sharpened by GBDX.

**Metadata patterns**
Metadata patterns can be within **datadir** and **filename** in order to have custom path and filenames based on the scene metadata. For instance specifying datadir as "./${eo:platform}/${date}" will save assets for each scene under directories of the platform and the date. So a WorldView-3 scene from June 20, 2018 will have it's assets saved in a directory './WORLDVIEW03/2017-06-20'. For filenames these work exactly the same way, except the appropriate extension will be used at the end of the filename, depending on the asset.

**Thumbnails**
The thumbnail for each scene in a *scenes.json* file can be downloaded with
```
    sat-gbdx load scenes.json --download thumbnail
```
The thumbnails will be saved using a directory and filename according to the `datadir` and `filename` options, and will also have a '_thumbnail` suffix. When thumbnails are downloaded an ESRI Worldfile (.wld) file is created, which is a sidecar file that describes the coordinates and resolution of the images. This enables the thumbnails to be viewed in a GIS program like QGIS in their proper geographical location. The world file does not set the spatial reference system used (lat/lon, or WGS-84, or EPSG:4326), so when opened in QGIS it will need to be selected (EPSG:4326).

**Scenes**
Full scenes can be downloaded with
```
    sat-gbdx load scenes.json --download full
```
GBDX data works differently than other types of static data that just need to be downloaded. GBDX assets are downloaded through function calls, and they can sometimes take time to be activated through a process called ordering. If datafiles are requested for download with the *--download* option, the images will be automatically ordered if they've not been already, and their order status will be printed. If an order is not yet ready, download will not download anything and the call should be tried at a later time until all the scenes have been fetched.


## About
sat-gbdx was created by [Development Seed](<http://developmentseed.org>)
