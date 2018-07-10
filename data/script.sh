#!/usr/bin/env bash
id=$1
startDate=$2
mkdir $id

# Download the zone polygon
wget https://s3.amazonaws.com/ds-data-projects/SEZ/sez-zone/$id.geojson -O $id/$id.geojson

# Searching the images
cids=('quickbird-2' 'geoeye-1' 'worldview-1' 'worldview-2' 'worldview-3' 'worldview-3-swir')  
for cid in "${cids[@]}"  
do
   sat-gbdx search \
    --datetime $startDate-01-01/2018-12-31 \
    --c:id $cid \
    --intersects $id/$id.geojson  \
    --eo:cloud_cover 0/20 \
    --overlap 98 \
    --save $id/$id-$cid.geojson
    geokit splitbyprop $id/$id-$cid.geojson --prop=datetime
    # let's just keep the important files
    rm $id/$id-$cid.geojson
done
    rm $id/$id.geojson