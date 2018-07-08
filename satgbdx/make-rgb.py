#!/usr/bin/env python
import os
import sys
import argparse
import gippy

sensors = {
    'GEOEYE01': [3, 2, 1],
    'QUICKBIRD02': [3, 2, 1],
    'WORLDVIEW02': [5, 3, 2],
    'WORLDVIEW03_VNIR': [4, 3, 2],
}


def main(filenames, path='./'):
    if not os.path.isdir(path):
        os.makedirs(path)
    for f in filenames:
        print(f)
        bname = os.path.basename(os.path.splitext(f)[0])
        parts = bname.split('_')
        date = parts[0]
        if len(parts) == 3:
            sensor = parts[1]
        else:
            sensor = '_'.join(parts[1:3])
        geoimg = gippy.GeoImage(f)
        if sensor == 'GEOEYE01' or sensor == 'QUICKBIRD02':
            geoimg.set_nodata(0)
        geoimg = geoimg.select(sensors[sensor]).autoscale(1, 255, percent=2.0)
        fout = os.path.join(path, bname + '_rgb.tif')
        geoimg.save(fout, nodata=0, dtype='byte', options={'COMPRESS': 'DEFLATE'})


def parse_args(args):
    desc = 'landclass'
    dhf = argparse.ArgumentDefaultsHelpFormatter
    parser0 = argparse.ArgumentParser(description=desc, formatter_class=dhf)
    parser0.add_argument('filenames', help='Filename to multi-band raster', nargs='*')
    parser0.add_argument('--path', help='Path to save output', default='./')
    return vars(parser0.parse_args(args))


def cli():
    args = parse_args(sys.argv[1:])
    main(**args)


if __name__ == "__main__":
    cli()
