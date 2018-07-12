#!/usr/bin/env bash
zoneId=$1
date=$2
featuresIds=$2
DIR=$zoneId/$date

# Filter the features which were evaluated as ok
geokit filterbyprop $DIR/scenes.geojson --prop id=$featuresIds > $DIR/tmp.geojson
rm $DIR/scenes.geojson
mv $DIR/tmp.geojson $DIR/scenes.geojson
sat-gbdx load $DIR/scenes.geojson --download full
