# !/usr/bin/env bash
echo "zones, year, id" > error.csv
for zone in ./* ; do
    if [[ -d $zone ]]; then
        zoneID=${zone:2:10}
        echo "=============================: " $zoneID
        for d in $zone/* ; do
            if [[ -d $d ]]; then
                echo $d
                OUTPUT="$(node index.js $d/scenes-filtered.geojson)";
                echo $OUTPUT
                cd $d/
                echo sat-gbdx load scenes-filtered.geojson --download full
                sat-gbdx load scenes-filtered.geojson --download full
                if [ $? -eq 0 ]; then
                    echo OK
                else
                    echo $d, $OUTPUT >> ../../error.csv
                fi
                cd ../../
            fi
        done
     echo aws s3 sync $zoneID/  s3://sez-u/phase2/data/search-gbdx/$zoneID
    fi
done
