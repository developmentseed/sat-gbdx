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
from pygeotile.tile import Tile
from satsearch.scene import Scene, Scenes
from satsearch.parser import SatUtilsParser
import satsearch.config as config
import gippy
import gippy.algorithms as alg
from gbdxtools import Interface
from pdb import set_trace

logger = logging.getLogger(__name__)
gbdx = Interface()



class GBDXParser(SatUtilsParser):

    def __init__(self, *args, **kwargs):
        super(GBDXParser, self).__init__(*args, **kwargs)
        group = self.add_argument_group('GBDX parameters')
        #group.add_argument('--download', help='Download thumbnails', action='store_true', default=False)
        group.add_argument('--gettiles', help='Fetch tiles at this zoom level', default=None, type=int)
        group.add_argument('--pansharp', help='Pan-sharpen fetched tiles, if able', default=False, action='store_true')
        group.add_argument('--order', action='store_true', default=False, help='Place order')
        #group.add_argument('--datadir', help='Local directory to save images', default=config.DATADIR)
        #group.add_argument('--subdirs', help='Save in subdirs based on these metadata keys', default="${date}_${satellite_name}_${scene_id}")
        #group.add_argument('--filename', help='Save in subdirs based on these metadata keys', default="")
        group.add_argument('--types', nargs='*', default=['DigitalGlobeAcquisition'],
                           help='Data types ("DigitalGlobeAcquisition", "GBDXCatalogRecord", "IDAHOImage"')
        group.add_argument('--overlap', help='Minimum overlap of footprint to AOI', default=0.98, type=float)

    def parse_args(self, *args, **kwargs):
        args = super(GBDXParser, self).parse_args(*args, **kwargs)
        if 'intersects' in args:
            args['geojson'] = args.pop('intersects')
            geovec = gippy.GeoVector(args['geojson'])
            args['searchAreaWkt'] = geovec[0].geometry()
        if 'datetime' in args:
            d1, d2 = args.pop('datetime').split('/')
            args['startDate'] = '%sT00:00:00.00Z'
        #if 'date_to' in args:
        #    args['endDate'] = args.pop('date_to') + 'T23:59:59.59Z'
        return args

    @classmethod
    def new(cls, *args, **kwargs):
        """ Return new parser """
        parser = cls(*args, **kwargs)
        parser.add_search_parser()
        parser.add_load_parser()
        return parser


def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0)/360.0*n)
    ytile = int((1.0 - math.log(math.tan(lat_rad)+(1/math.cos(lat_rad)))/math.pi)/2.0*n)
    return (xtile, ytile)


def get_tiles(scene, aoi, zoom, path='', pansharp=False):
    with open(aoi) as f:
        geom = json.loads(f.read())['geometry']
    lats = [c[1] for c in geom['coordinates'][0]]
    lons = [c[0] for c in geom['coordinates'][0]]
    xmin, ymin = deg2num(max(lats), min(lons), zoom)
    xmax, ymax = deg2num(min(lats), max(lons), zoom)
    xtiles = range(xmin, xmax+1)
    ytiles = range(ymin, ymax+1)
    tiles = []
    url0 = 'https://idaho.geobigdata.io/v1/tile/%s/%s/%s' % (scene.metadata['bucketName'], scene.scene_id, zoom)
    tile_coords = []
    for x in xtiles:
        for y in ytiles:
            tile = Tile.from_google(google_x=x, google_y=y, zoom=zoom)
            p1 = tile.bounds[0]
            p2 = tile.bounds[1]
            pts = [[p1[1], p1[0]], [p2[1], p1[0]], [p2[1], p2[0]], [p1[1], p2[0]]]
            geom0 = Polygon(pts)
            area = shape(geom).intersection(geom0).area
            if area > 0.0:
                tile_coords.append((x, y))
    print('%s total tiles' % (len(tile_coords)))
    tiles = []
    for x, y in tile_coords:
        url = os.path.join(url0, '%s/%s?token=%s') % (x, y, os.environ.get('GBDX_TOKEN'))
        if pansharp and 'PAN_SCENEID' in scene.metadata:
            config.subdirs = config.subdirs + '_pansharp'
            url = url + '&panId=%s' % scene.metadata['PAN_SCENEID']
        path = scene.get_path()
        fout = '%s-%s-%s.png' % (zoom, x, y)
        fout = os.path.join(path, fout)
        if not os.path.exists(fout):
            scene.download_file(url, fout=fout)
        tiles.append(fout)
    print('downloaded tiles')
    return tiles


# IDAHO uses Google tiling system
def open_tile(filename):
    """ Open a tile image and assign projection and geotransform """
    geoimg = gippy.GeoImage(filename, True)
    z, x, y = map(int, geoimg.basename().split('-')[0:4])
    tile = Tile.from_google(google_x=x, google_y=y, zoom=z)
    geoimg.set_srs('EPSG:3857')
    minpt = tile.bounds[0].meters
    maxpt = tile.bounds[1].meters
    affine = np.array(
        [
            minpt[0], (maxpt[0]-minpt[0])/geoimg.xsize(), 0.0,
            maxpt[1], 0.0, -(maxpt[1]-minpt[1])/geoimg.ysize()
        ])
    geoimg.set_affine(affine)
    geoimg.set_nodata(-1)
    return geoimg


def transform(record):
    """ Transforms a DG record into a STAC item """
    props = {
        'id': record['catalogID'],
        'datetime': record['timestamp'],
        'eo:platform': record['platformName'],
        'eo:instrument': record['sensorPlatformName'],
    }
    geom = shapely.wkt.loads(record['footprintWkt'])
    item = {
        'properties': props,
        'geometry': geoj.Feature(geometry=geom)['geometry'],
        'assets': {
            'thumbnail': {'rel': 'thumbnail', 'href': record['browseURL']}
        }
    }
    return item


def calculate_overlap(scenes, geometry):
    geom0 = shapely.wkt.loads(geometry)
    # calculate overlap
    for s in scenes:
        geom = shapely.wkt.loads(s.geometry)
        s.feature['properties']['overlap'] = geom.intersection(geom0).area / geom0.area
    return scenes


def query(types=['DigitalGlobeAcquisition'], overlap=None, **kwargs):
    """ Perform a GBDX query """
    filters = []  # ["offNadirAngle < 20"]
    # get scenes from search
    if 'satellite_name' in kwargs:
        filters.append("sensorPlatformName = '%s'" % kwargs.pop('satellite_name'))
    if 'cloud_from' in kwargs:
        filters.append("cloudCover >= %s" % kwargs.pop('cloud_from'))
    if 'cloud_to' in kwargs:
        filters.append("cloudCover <= %s" % kwargs.pop('cloud_to'))
    #import pdb; pdb.set_trace()
    results = gbdx.catalog.search(filters=filters, types=types, **kwargs)
    if 'searchAreaWkt' in kwargs:
        geom0 = shapely.wkt.loads(kwargs['searchAreaWkt'])
    else:
        geom0 = None

    scenes = Scenes([Scene(transform(r['properties'])) for r in results])
    # calculate overlap
    if False: #'searchAreaWkt' in kwargs and overlap is not None:
        scenes = calculate_overlap(scenes, kwargs['searchAreaWkt'])
        scenes.scenes = list(filter(lambda x: x['overlap'] >= overlap, scenes.scenes))

    return scenes


def main(scenes=None, review=False, print_md=None, print_cal=False,
         save=None, append=False, download=None, 
         order=False, gettiles=None, geojson=None, pansharp=False, **kwargs):

    if scenes is None:
        scenes = query(**kwargs)
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

    # save all metadata in JSON file
    if save is not None:
        scenes.save(filename=save, append=append)

    print('%s scenes found' % len(scenes))

    # download thumbnail
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

    if gettiles is not None:
        zoom = gettiles
        # find matching MS/PAN scenes
        #set_trace()
        pan_scenes = [scene for scene in scenes if scene.metadata['colorInterpretation'] == 'PAN']
        other_scenes = [scene for scene in scenes if scene.metadata['colorInterpretation'] != 'PAN']
        for scene in pan_scenes:
            for sc in other_scenes:
                if scene.metadata['catalogID'] == sc.metadata['catalogID']:
                    sc.metadata['PAN_SCENEID'] = scene.scene_id
        opts = {}
        for scene in other_scenes:
            filenames = get_tiles(scene, geojson, zoom, path=config.DATADIR, pansharp=pansharp)
            tiles = [open_tile(filename) for filename in filenames]
            if geojson is not None:
                geovec = gippy.GeoVector(geojson)
                res = tiles[0].resolution()
                # put these in the top level
                pattern = config.SUBDIRS + '_z%s.tif' % zoom
                fout = os.path.join(scene.get_path(subdirs=''), scene.get_filename(pattern))
                if pansharp:
                    fout = fout + '_pansharp'
                geoimg = alg.cookie_cutter(tiles, fout, geovec[0], xres=res.x(), yres=res.y(), proj='EPSG:3857', options=opts)

    if order:
        for scene in scenes:
            scene.metadata['order_id'] = 'test'  # gbdx.ordering.order(scene.scene_id)
            status = gbdx.ordering.status(scene.metadata['order_id'])[0]
            print('%s\t%s\t%s\t%s' % (scene.metadata['order_id'], status['acquisition_id'], status['state'], status['location']))

    # save all metadata in JSON file
    if save is not None:
        scenes.save(filename=save, append=append)

    return scenes


def cli():
    parser = GBDXParser.new(description='GBDX Search')
    args = parser.parse_args(sys.argv[1:])

    # enable logging
    #logging.basicConfig(stream=sys.stdout, level=args.pop('verbosity') * 10)

    cmd = args.pop('command', None)
    if cmd is not None:
        return main(**args)


if __name__ == "__main__":
    cli()
