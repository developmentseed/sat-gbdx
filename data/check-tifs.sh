# !/usr/bin/env bash
echo "ZoneId,file" > status.csv
for zone in ./* ; do
    if [[ -d $zone ]]; then
        zoneID=${zone:2:10}
        for d in $zone/* ; do
            if [[ -d $d ]]; then
                year=${d#./$zoneID/}
                TIF="$(find $d -name '*.tif' | xargs -n 1 basename)"
                echo $zoneID, $year, $TIF
            fi
        done
    fi
done