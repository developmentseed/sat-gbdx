# !/usr/bin/env bash
echo "zones, year, id" > error.csv
for zone in ./* ; do
    if [[ -d $zone ]]; then
        zoneID=${zone:2:10}
        for d in $zone/* ; do
            if [[ -d $d ]]; then
                path=${d:2:400}
                echo $path
            fi
        done
    fi
done
