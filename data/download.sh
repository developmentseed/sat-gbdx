#!/usr/bin/env bash
zoneId=$1
date=$2
featuresIds=$2
DIR=$zoneId/$date

# Filter the features which were evaluated as ok
geokit filterbyprop $DIR/scene.geojson --prop id=$featuresIds > $DIR/tmp.geojson
rm $DIR/scene.geojson
mv $DIR/tmp.geojson $DIR/scene.geojson
sat-gbdx load $DIR/scene.geojson --download full
