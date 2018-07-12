#!/usr/bin/env bash
zoneId=$1
startDate=$2
mkdir $zoneId

# Download the zone polygon
wget https://s3.amazonaws.com/ds-data-projects/SEZ/sez-zone/$zoneId.geojson -O $zoneId/$zoneId.geojson

# Searching the images
YEARS=( $(seq $startDate 2018 ) )
for year in "${YEARS[@]}"; do
     mkdir $zoneId/$year
     echo RANGE: $year-01-01/$year-12-31 
     OUTPUT="$(sat-gbdx search \
         --datetime $year-01-01/$year-12-31 \
         --intersects $zoneId/$zoneId.geojson  \
         --eo:cloud_cover 0/20 \
         --overlap 98 \
         --save $zoneId/$year/scenes.geojson)"
     echo $OUTPUT
     numScenes=$(echo $OUTPUT | sed 's/[^0-9]*//g')
     mv results.json $zoneId/$year
     if (( $numScenes == 0 )); then
         rm -rf $zoneId/$year/
     fi
done
tar czf $zoneId-search-gbdx.tar.gz $zoneId/
mv $zoneId-search-gbdx.tar.gz $zoneId/