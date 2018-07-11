#!/usr/bin/env bash
pathGeojson=$1
DIR=$(dirname "${pathGeojson}")
featuresIds=$2

# Filter the features which were evaluated as ok
geokit filterbyprop $pathGeojson --prop id=$featuresIds > $DIR/tmp.geojson
# mv $DIR/tmp.geojson > $pathGeojson
# rm $DIR/tmp.geojson
# sat-gbdx load $pathGeojson --download full

