#!/usr/bin/env bash
id=$1
startDate=$2
mkdir $id

# Download the zone polygon
wget https://s3.amazonaws.com/ds-data-projects/SEZ/sez-zone/$id.geojson -O $id/$id.geojson

# Searching the images
cids=('quickbird-2' 'geoeye-1' 'worldview-1' 'worldview-2' 'worldview-3' 'worldview-3-swir')
YEARS=( $(seq $startDate 2018 ) )
for year in "${YEARS[@]}";
do
   for cid in "${cids[@]}"  
        do
            mkdir $id/$year-$cid
            echo CID: $cid  RANGE: $year-01-01/$year-12-31 
            OUTPUT="$(sat-gbdx search \
                --datetime $year-01-01/$year-12-31 \
                --c:id $cid \
                --intersects $id/$id.geojson  \
                --eo:cloud_cover 0/20 \
                --overlap 98 \
                --save $id/$year-$cid/$year-$cid.geojson)"
            echo $OUTPUT
            numScenes=$(echo $OUTPUT | sed 's/[^0-9]*//g')
            mv results.json $id/$year-$cid
            if (( $numScenes == 0 )); then
                rm -rf $id/$year-$cid/
            fi
    done
done
tar czf $id.tar.gz $id/
mv $id.tar.gz $id/