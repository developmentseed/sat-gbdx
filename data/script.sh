#!/usr/bin/env bash
id=$1
startDate=$2
mkdir $id

# Download the zone polygon
wget https://s3.amazonaws.com/ds-data-projects/SEZ/sez-zone/$id.geojson -O $id/$id.geojson

# Searching the images
YEARS=( $(seq $startDate 2018 ) )
for year in "${YEARS[@]}"; do
     mkdir $id/$year
     echo RANGE: $year-01-01/$year-12-31 
     OUTPUT="$(sat-gbdx search \
         --datetime $year-01-01/$year-12-31 \
         --intersects $id/$id.geojson  \
         --eo:cloud_cover 0/20 \
         --overlap 98 \
         --save $id/$year/scenes.geojson)"
     echo $OUTPUT
     numScenes=$(echo $OUTPUT | sed 's/[^0-9]*//g')
     mv results.json $id/$year
     if (( $numScenes == 0 )); then
         rm -rf $id/$year/
     fi
done
tar czf $id.tar.gz $id/
mv $id.tar.gz $id/