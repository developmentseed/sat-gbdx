#!/usr/bin/env python
import os
import sys
import json
import logging
import geojson as geoj
import math
import shapely.wkt
import numpy as np
import tempfile
import json
from shapely.geometry import shape, Polygon
from pygeotile.tile import Tile
from satsearch.scene import Scene, Scenes
from satsearch.parser import SatUtilsParser
from satsearch.utils import dict_merge
import satsearch.config as config
from dateutil.parser import parse as dateparser
import gippy
import gippy.algorithms as alg
from gbdxtools import Interface
from gbdxtools import CatalogImage
import utm
from pdb import set_trace

logger = logging.getLogger(__name__)
logging.getLogger('requests').setLevel(logging.CRITICAL)
gbdx = Interface()


def load_collections():
    """ Load DG collections from included JSON file """
    path = os.path.dirname(__file__)
    with open(os.path.join(path, 'collections.json')) as f:
        cols = json.loads(f.read())
    return {c['properties']['c:id']:c for c in cols['features']}


COLLECTIONS = load_collections()
_COLLECTIONS = {c['properties']['eo:instrument']:c for c in COLLECTIONS.values()}


class GBDXParser(SatUtilsParser):

    def __init__(self, *args, **kwargs):
        super(GBDXParser, self).__init__(*args, **kwargs)
        group = self.add_argument_group('GBDX parameters')
        #group.add_argument('--gettiles', help='Fetch tiles at this zoom level', default=None)
        #group.add_argument('--pansharp', help='Pan-sharpen fetched tiles, if able', default=False, action='store_true')
        self.download_group.add_argument('--order', action='store_true', default=False, help='Place order for these scenes')
        #group.add_argument('--types', nargs='*', default=['DigitalGlobeAcquisition'],
        #                   help='Data types ("DigitalGlobeAcquisition", "GBDXCatalogRecord", "IDAHOImage"')
        self.output_group.add_argument('--overlap', help='Minimum %% overlap of footprint to AOI', default=None, type=int)


def query(types=['DigitalGlobeAcquisition'], overlap=None, **kwargs):
    """ Perform a GBDX query by converting from STAC terms to DG terms """
    filters = []  # ["offNadirAngle < 20"
    # build DG search parameters
    if 'c:id' in kwargs:
        _sensors = [COLLECTIONS[c]['properties']['eo:instrument'] for c in kwargs.pop('c:id')]
        filters.append("sensorPlatformName = '%s'" % ','.join(_sensors))
    if 'intersects' in kwargs:
        geom = shape(json.loads(kwargs.pop('intersects'))['geometry'])
        kwargs['searchAreaWkt'] = geom.wkt
    if 'datetime' in kwargs:
        dt = kwargs.pop('datetime').split('/')
        kwargs['startDate'] = dateparser(dt[0]).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        if len(dt) > 1:
            kwargs['endDate'] = dateparser(dt[1]).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    if 'eo:cloud_cover' in kwargs:
        cc = kwargs.pop('eo:cloud_cover').split('/')
        if len(cc) == 2:
            filters.append("cloudCover >= %s" % cc[0])
            filters.append("cloudCover <= %s" % cc[1])
        else:
            filters.append("cloudCover <= %s" % cc[0])
    results = gbdx.catalog.search(filters=filters, types=types, **kwargs)
    with open('results.json', 'w') as f:
        f.write(json.dumps(results))
    scenes = [Scene(dg_to_stac(r['properties'])) for r in results]

    # calculate overlap
    scenes = calculate_overlap(scenes, kwargs['searchAreaWkt'])
    if overlap is not None: 
        scenes = list(filter(lambda x: x['overlap'] >= overlap, scenes))

    return scenes


def dg_to_stac(record):
    """ Transforms a DG record into a STAC item """
    props = {
        'id': record['catalogID'],
        'datetime': record['timestamp'],
        'eo:cloud_cover': record['cloudCover'],
        'eo:gsd': record['multiResolution'],
        'eo:sun_azimuth': record['sunAzimuth'],
        'eo:sun_elevation': record['sunElevation'],
        'eo:off_nadir': record['offNadirAngle'],
        'eo:azimuth': record['targetAzimuth'],
        'dg:image_bands': record['imageBands']
    }
    geom = shapely.wkt.loads(record['footprintWkt'])
    item = {
        'properties': props,
        'geometry': geoj.Feature(geometry=geom)['geometry'],
        'assets': {
            'thumbnail': {'rel': 'thumbnail', 'href': record['browseURL']}
        }
    }
    return dict_merge(item, _COLLECTIONS[record['platformName']])


def calculate_overlap(scenes, geometry):
    geom0 = shapely.wkt.loads(geometry)
    # calculate overlap
    for s in scenes:
        geom = shape(s.geometry)
        s.feature['properties']['overlap'] = int(geom.intersection(geom0).area / geom0.area * 100)
    return scenes


def utm_epsg(latlon):
    zone = utm.from_latlon(latlon[0], latlon[1])
    return ('EPSG:327' if latlon[0] < 0 else 'EPSG:326') + str(zone[2])


def order(scene, pansharp=False):
    """ Order this scene """
    if 'dg:order_id' not in scene.keys():
        scene.feature['properties']['dg:order_id'] = gbdx.ordering.order(scene['id'])
    sid = scene.feature['properties']['dg:order_id']
    status = gbdx.ordering.status(sid)[0]
    key = 'ordered_pansharp' if pansharp else 'ordered'
    if status['location'] != 'not_delivered':
        scene['assets'][key] = {'href': status['location']}
    #scene.feature['properties']['location'] = status['location']
    print('%s\t%s\t%s\t%s' % (sid, status['acquisition_id'], status['state'], status['location']))
    return scene


def order_scenes(scenes, pansharp=False):
    """ Order this scene """
    [order(s, pansharp=pansharp) for s in scenes]
    return scenes


def download_scenes(scenes, pansharp=False):
    """ Download these scenes """
    with tempfile.NamedTemporaryFile(suffix='.geojson', mode='w', delete=False) as f:
        aoiname = f.name
        aoistr = json.dumps(scenes.properties['intersects'])
        f.write(aoistr)
    geovec = gippy.GeoVector(aoiname)
    fouts = []
    dirout = tempfile.mkdtemp()
    key = 'ordered_pansharp' if pansharp else 'ordered'
    # TODO - wrap this in a try-except-finally to ensure removal of files
    for scene in scenes:
        order(scene, pansharp=pansharp)
        if key in scene.assets:
            #dt = dateparser(scene.metadata['timestamp'])
            #bname = '%s_%s' % (dt.strftime('%Y-%m-%d_%H-%M-%S'), scene.metadata['satellite_name'])
            ps = '_pansharp' if pansharp else ''
            fout = os.path.join(scene.get_path(), scene.get_filename(suffix=ps)) + '.tif'
            try:
                # TODO - allow for other projections
                import pdb; pdb.set_trace()
                img = CatalogImage(scene['id'], pansharpen=pansharp, bbox=scenes.bbox(), proj=utm_epsg(scenes.center()))
                if not os.path.exists(fout):
                    tif = img.geotiff(path=fout)
                    geoimg = gippy.GeoImage(tif, True)
                    if scene['eo:platform'] == 'GEOEYE01' or scene['eo:platform'] == 'QUICKBIRD02':
                        geoimg.set_nodata(0)
                    else:
                        geoimg.set_nodata(-1e10)
                    # this clips the image to the AOI
                    res = geoimg.resolution()
                    fout2 = os.path.join(dirout, os.path.basename(fout))
                    imgout = alg.cookie_cutter([geoimg], fout2, geovec[0], xres=res.x(), yres=res.y(), proj=geoimg.srs())
                    imgout = None
                    os.remove(fout)
                    os.rename(fout2, fout)
                fouts.append(fout)
            except Exception as e:
                print(e)
    os.remove(aoiname)
    return fouts


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

