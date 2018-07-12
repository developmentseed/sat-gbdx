#!/usr/bin/env bash
zoneId=$1
date=$2
featuresIds=$3
DIR=$zoneId/$date

# Filter the features which were evaluated as ok
geokit filterbyprop $DIR/scenes.geojson --prop id=$featuresIds > $DIR/scenes-filtered.geojson
sat-gbdx load $DIR/scenes-filtered.geojson --download full
