# !/usr/bin/env bash
echo "ZoneId,year,file" > status.csv
for zone in ./* ; do
    if [[ -d $zone ]]; then
        zoneID=${zone:2:10}
        for d in $zone/* ; do
            if [[ -d $d ]]; then
                # year=${d#./$zoneID/}
                TIF="$(find $d -name '*0.tif' | xargs -n 1 basename)"
                NEW_TIF=$(echo "$TIF" | cut -f 1 -d '.')_rgb.tif
                sensors="$(echo "$TIF" | awk -F[__] '{print $2}')"
                cd $d
                #echo $TIF, $sensors
                # Convert to RGB
                # quickbird-2
                #     1:blue
                #     2:green
                #     3:red
                # ============
                # geoeye-1
                #     1: blue
                #     2: green
                #     3: red
                #==============
                # worldview-4
                #     1: blue
                #     2: green
                #     3: red
                if [ "$sensors" == "quickbird-2" ] || [ "$sensors" == "geoeye-1" ] || [ "$sensors" == "worldview-4" ]; then
                   echo gdal_translate -ot Byte -scale -b 3 -b 2 -b 1 $TIF $NEW_TIF -exponent 0.5 -co COMPRESS=DEFLATE -co PHOTOMETRIC=RGB
                fi
                # worldview-2
                #     2: blue
                #     3: green
                #     5: red
                #=============
                # worldview-3
                #     2: blue
                #     3: green
                #     5: red
                if [ "$sensors" == "worldview-2" ]; then
                  echo gdal_translate -ot Byte -scale -b 5 -b 3 -b 2 $TIF $NEW_TIF -exponent 0.5 -co COMPRESS=DEFLATE -co PHOTOMETRIC=RGB
                fi

                if [ "$sensors" == "worldview-3" ]; then
                #   echo rm $NEW_TIF
                 #  echo  $TIF --> $NEW_TIF
	          # rm $NEW_TIF
	           #rm tmp.tif
                  echo gdal_translate -ot Byte -scale -b 5 -b 3 -b 2 $TIF tmp.tif -exponent 0.5 -co COMPRESS=DEFLATE -co PHOTOMETRIC=RGB
                   echo gdal_translate tmp.tif $NEW_TIF -co COMPRESS=JPEG -co TILED=YES
                   echo  rm tmp.tif
                fi
                # ============
                # worldview-1
                # 1 : pan
                if [ "$sensors" == "worldview-1" ]; then
                   gdal_translate -ot Byte -scale -b 1 -b 1 -b 1 $TIF $NEW_TIF -exponent 0.5 -co COMPRESS=DEFLATE -co PHOTOMETRIC=RGB
                fi
                cd ../../
            fi
        done
    fi
done