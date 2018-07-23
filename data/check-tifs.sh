# !/usr/bin/env bash
for zone in ./* ; do
    if [[ -d $zone ]]; then
        zoneID=${zone:2:10}
        for d in $zone/* ; do
            if [[ -d $d ]]; then
                #echo $d
                for file in $d/*; do
                echo $file
                filename="$(echo ${file##*/})"
                echo $filename
                done
            fi
        done
    fi
done