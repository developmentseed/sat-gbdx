# !/usr/bin/env bash
for zone in ./* ; do
    if [[ -d $zone ]]; then
        zoneID=${zone:2:10}
        echo "=============================: " $zoneID
        for d in $zone/* ; do
            if [[ -d $d ]]; then
                echo $d
                cd $d/
                sat-gbdx load scenes-filtered.geojson --download full
                cd ../../
            fi
        done
     echo aws s3 sync $zoneID/  s3://sez-u/phase2/data/search-gbdx/$zoneID
    fi
done
