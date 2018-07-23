# !/usr/bin/env bash
for zone in ./* ; do
    if [[ -d $zone ]]; then
        zoneID=${zone:2:10}
        for d in $zone/* ; do
            if [[ -d $d ]]; then
                cd $d
                echo "================================= $d"
                geo="$(find . -name '*0.geojson' | xargs -n 1 basename)"
                geokit filterbyprop $geo --prop=highway=* > ways.geojson
                geokit filterbyprop $geo --prop=building=* > buildings.geojson
                roads="$(geokit distance ways.geojson)"
                if [ $? -eq 1 ]; then
                    roads=0
                fi
                buildings="$(geokit area buildings.geojson)"
                if [ $? -eq 1 ]; then
                    buildings=0
                fi
                echo "{roads:$roads,buildings:$buildings }" > result.json
                rm ways.geojson
                rm buildings.geojson
		        cd ../../
            fi
        done
    fi
done