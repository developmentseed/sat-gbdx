#!/usr/bin/env bash
zoneId=$1
for d in $zoneId/* ; do
    if [[ -d $d ]]; then
         node index.js $d/scenes-filtered.geojson
    fi
done