#!/usr/bin/env python
import os
import sys
import json
import logging
import geojson as geoj
import math
import shapely.wkt
import numpy as np
from dateutil.parser import parse as dateparser
from shapely.geometry import shape, Polygon

from satsearch.scene import Scene, Scenes
from satsearch.parser import SatUtilsParser
import satsearch.config as config
import gippy
import gippy.algorithms as alg

import satgbdx
import satgbdx.utils as utils


logger = logging.getLogger(__name__)


def main(scenes=None, review=False, print_md=None, print_cal=False,
         save=None, append=False, download=None, 
         order=False, gettiles=None, geojson=None, pansharp=False, **kwargs):

    if scenes is None:
        scenes = Scenes(satgbdx.query(**kwargs), properties=kwargs)
    else:
        scenes = Scenes.load(scenes)
        # hack
        #for s in scenes.scenes:
        #    s.source = ''
        #if 'scene_id' in kwargs:
        #    scenes.filter('scene_id', kwargs.pop('scene_id'))
        #if 'satellite_name' in kwargs:
        #    scenes.filter('satellite_name', kwargs.pop('satellite_name'))

    if review:
        if not os.getenv('IMGCAT', None):
            raise ValueError('Set IMGCAT envvar to terminal image display program to use review feature')
        scenes.review_thumbnails()

    # print metadata
    if print_md is not None:
        scenes.print_scenes(print_md)

    # print calendar
    if print_cal:
        print(scenes.text_calendar())

    if order:
        scenes = satgbdx.order_scenes(scenes, pansharp=pansharp)
        #for scene in scenes:
        #    scene.metadata['order_id'] = 'test'  # gbdx.ordering.order(scene.scene_id)
        #    status = gbdx.ordering.status(scene.metadata['order_id'])[0]
        #    print('%s\t%s\t%s\t%s' % (scene.metadata['order_id'], status['acquisition_id'], status['state'], status['location']))

    # save all metadata in JSON file
    if save is not None:
        scenes.save(filename=save, append=append)

    print('%s scenes found' % len(scenes))

    # download files given keys
    if download is not None:
        if 'thumbnail' in download:
            scenes.download(key=download.pop('thumbnail'))
        if len(download) > 0:
            satgbdx.download_scenes(scenes)
        #for key in download:
        #    scenes.download(key=key)
    """
    if download:
        for scene in scenes:
            fout = scene.get_path(no_create=True) + '.jpg'
            fname = scene.download_file(scene.metadata['browseURL'], fout=fout)
            wldfile = os.path.splitext(os.path.basename(fname))[0] + '.wld'
            fout = os.path.join(os.path.dirname(fout), wldfile)
            coords = scene.geometry['coordinates'][0][0]
            lats = [c[1] for c in coords]
            lons = [c[0] for c in coords]
            timg = gippy.GeoImage(fname)
            with open(fout, 'w') as f:
                f.write('%s\n' % ((max(lons)-min(lons))/timg.xsize()))
                f.write('0.0\n0.0\n')
                f.write('%s\n' % (-(max(lats)-min(lats))/timg.ysize()))
                f.write('%s\n%s\n' % (min(lons), max(lats)))
    """

    if gettiles is not None:
        zoom = gettiles
        # find matching MS/PAN scenes
        pan_scenes = [scene for scene in scenes if scene.metadata['colorInterpretation'] == 'PAN']
        other_scenes = [scene for scene in scenes if scene.metadata['colorInterpretation'] != 'PAN']
        for scene in pan_scenes:
            for sc in other_scenes:
                if scene.metadata['catalogID'] == sc.metadata['catalogID']:
                    sc.metadata['PAN_SCENEID'] = scene.scene_id
        opts = {}
        for scene in other_scenes:
            filenames = satgbdx.get_tiles(scene, geojson, zoom, path=config.DATADIR, pansharp=pansharp)
            tiles = [utils.open_tile(filename) for filename in filenames]
            if geojson is not None:
                geovec = gippy.GeoVector(geojson)
                res = tiles[0].resolution()
                # put these in the top level
                pattern = config.SUBDIRS + '_z%s.tif' % zoom
                fout = os.path.join(scene.get_path(subdirs=''), scene.get_filename(pattern))
                if pansharp:
                    fout = fout + '_pansharp'
                geoimg = alg.cookie_cutter(tiles, fout, geovec[0], xres=res.x(), yres=res.y(), proj='EPSG:3857', options=opts)

    #if download:
    #    order_scenes(scenes)
    #    fouts = download_scenes(scenes, nocrop=nocrop, pansharp=pansharp)

    # save all metadata in JSON file
    if save is not None:
        scenes.save(filename=save, append=append)

    return scenes


def cli():
    parser = satgbdx.GBDXParser.newbie(description='GBDX Search')
    args = parser.parse_args(sys.argv[1:])

    # read the GeoJSON file
    if 'intersects' in args:
        if os.path.exists(args['intersects']):
            with open(args['intersects']) as f:
                args['intersects'] = json.dumps(json.loads(f.read()))

    cmd = args.pop('command', None)
    if cmd is not None:
        main(**args)


if __name__ == "__main__":
    cli()
