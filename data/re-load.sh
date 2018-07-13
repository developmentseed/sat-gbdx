# !/usr/bin/env bash
zoneId=$1
for d in $zoneId/* ; do
    if [[ -d $d ]]; then
        cd $d/
        sat-gbdx load scenes-filtered.geojson --download full
        cd ../../
    fi
done