#!/usr/bin/env bash
pathGeojson=$1
DIR=$(dirname "${pathGeojson}")
featuresIds=$2

# Filter the features which were evaluated as ok
geokit filterbyprop $pathGeojson --prop id=$featuresIds > $DIR/tmp.geojson
rm $pathGeojson
mv $DIR/tmp.geojson $pathGeojson
sat-gbdx load $pathGeojson --download full
