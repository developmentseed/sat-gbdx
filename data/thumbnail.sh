#!/usr/bin/env bash
zoneId=$1
dates=$2
IFS=', ' read -r -a listDates <<< "$dates"
for year in "${listDates[@]}"
do
    cd $zoneId/$year/ && sat-gbdx load scenes.geojson --download thumbnail
    cd ../../
done