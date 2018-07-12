#!/usr/bin/env python
import os
import sys
import json
import logging
import geojson as geoj
import math
import shapely.wkt
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
        # change defaults from sat-search
        # data directory to store downloaded imagery
        config.DATADIR = os.getenv('SATUTILS_DATADIR', './')
        # filename pattern for saving files
        config.FILENAME = os.getenv('SATUTILS_FILENAME', '${date}_${c:id}_${id}')
        super(GBDXParser, self).__init__(*args, **kwargs)
        self.download_group.add_argument('--pansharp', help='Pan-sharpen fetched tiles, if able', default=False, action='store_true')
        self.download_group.add_argument('--order', action='store_true', default=False, help='Place order for these scenes')

    @classmethod
    def newbie(cls, *args, **kwargs):
        parser = super().newbie(*args, **kwargs)
        #parser.download_group.add_argument('--gettiles', help='Fetch tiles at this zoom level', default=None)
        
        #parser.download_group.add_argument('--order', action='store_true', default=False, help='Place order for these scenes')
        #group.add_argument('--types', nargs='*', default=['DigitalGlobeAcquisition'],
        #                   help='Data types ("DigitalGlobeAcquisition", "GBDXCatalogRecord", "IDAHOImage"')
        parser.search_group.add_argument('--overlap', help='Minimum %% overlap of footprint to AOI', default=1, type=int)        
        return parser


class GBDXScene(Scene):
    """ A GBDX scene """

    def __init__(self, feature):
        """ Transforms a DG record into a STAC item """
        if 'catalogID' in feature:
            # if this is a DG record, transform it
            props = {
                'id': feature['catalogID'],
                'datetime': feature['timestamp'],
                'eo:cloud_cover': feature['cloudCover'],
                'eo:gsd': feature['multiResolution'],
                'eo:sun_azimuth': feature['sunAzimuth'],
                'eo:sun_elevation': feature['sunElevation'],
                'eo:off_nadir': feature['offNadirAngle'],
                'eo:azimuth': feature['targetAzimuth'],
                'dg:image_bands': feature['imageBands']
            }
            geom = shapely.wkt.loads(feature['footprintWkt'])
            item = {
                'properties': props,
                'geometry': geoj.Feature(geometry=geom)['geometry'],
                'assets': {
                    'thumbnail': {'rel': 'thumbnail', 'href': feature['browseURL']}
                }
            }
            feature = dict_merge(item, _COLLECTIONS[feature['platformName']])
        super(GBDXScene, self).__init__(feature)

    def download(self, key, **kwargs):
        """ Download this key from scene assets """
        fname = super().download(key, **kwargs)
        if key == 'thumbnail' and fname is not None:
            geoimg = gippy.GeoImage(fname)
            bname, ext = os.path.splitext(fname)
            wldfile = bname + '.wld'
            coords = self.geometry['coordinates']
            while len(coords) == 1:
                coords = coords[0]
            lats = [c[1] for c in coords]
            lons = [c[0] for c in coords]
            with open(wldfile, 'w') as f:
                f.write('%s\n' % ((max(lons)-min(lons))/geoimg.xsize()))
                f.write('0.0\n0.0\n')
                f.write('%s\n' % (-(max(lats)-min(lats))/geoimg.ysize()))
                f.write('%s\n%s\n' % (min(lons), max(lats)))

            srs = '["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,' + \
                    'AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0],' + \
                    'UNIT["degree",0.0174532925199433],AUTHORITY["EPSG","4326"]]'
        
            #with open(fname+'.aux.xml', 'w') as f:
            #    f.write('<PAMDataset><SRS>PROJCS%s</SRS></PAMDataset>' % srs)
            #geoimg = None
            # convert to GeoTiff
            #geoimg = gippy.GeoImage(fname)
            #geoimg.set_srs('epsg:4326')
            #geoimg.save(bname, format='GTIFF', options={'COMPRESS': 'JPEG'})
            #os.remove(fname)
            #os.remove(wldfile)
            #fname = geoimg.filename()
            return fname


class GBDXScenes(Scenes):

    @classmethod
    def load(cls, filename):
        """ Load a collections class from a GeoJSON file of metadata """
        with open(filename) as f:
            geoj = json.loads(f.read())
        scenes = [GBDXScene(feature) for feature in geoj['features']]
        return cls(scenes, properties=geoj.get('properties', {}))


def query(types=['DigitalGlobeAcquisition'], overlap=None, **kwargs):
    """ Perform a GBDX query by converting from STAC terms to DG terms """
    filters = []  # ["offNadirAngle < 20"
    # build DG search parameters
    if 'c:id' in kwargs:
        _sensors = [COLLECTIONS[c]['properties']['eo:instrument'] for c in kwargs.pop('c:id')]
        filters.append("sensorPlatformName = '%s'" % ','.join(_sensors))
    if 'intersects' in kwargs:
        fc = json.loads(kwargs.pop('intersects'))
        geom = None
        if fc.get('features'):
            geom = shape(fc['features'][0]['geometry'])
        else:
            geom = shape(fc['geometry'])
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
    #with open('results.json', 'w') as f:
    #    f.write(json.dumps(results))
    scenes = [GBDXScene(r['properties']) for r in results]

    # calculate overlap
    scenes = calculate_overlap(scenes, kwargs['searchAreaWkt'])
    if overlap is not None: 
        scenes = list(filter(lambda x: x['overlap'] >= overlap, scenes))

    return scenes


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


def order(scene):
    """ Order this scene """
    if 'dg:order_id' not in scene.keys():
        scene.feature['properties']['dg:order_id'] = gbdx.ordering.order(scene['id'])
    sid = scene.feature['properties']['dg:order_id']
    status = gbdx.ordering.status(sid)[0]
    if status['location'] != 'not_delivered':
        scene['assets']['full'] = {'href': status['location']}
    print('Order %s status for %s: %s, %s' % (sid, status['acquisition_id'], status['state'], status['location']))
    return scene


def download_scenes(scenes, pansharp=False):
    """ Download these scenes """
    with tempfile.NamedTemporaryFile(suffix='.geojson', mode='w', delete=False) as f:
        aoiname = f.name
        aoistr = json.dumps(scenes.properties['intersects'])
        f.write(aoistr)
    geovec = gippy.GeoVector(aoiname)
    fouts = []
    dirout = tempfile.mkdtemp()
    # TODO - wrap this in a try-except-finally to ensure removal of files
    for scene in scenes:
        order(scene)
        if 'full' in scene.assets:
            #dt = dateparser(scene.metadata['timestamp'])
            #bname = '%s_%s' % (dt.strftime('%Y-%m-%d_%H-%M-%S'), scene.metadata['satellite_name'])
            ps = '_pansharp' if pansharp else ''
            fout = os.path.join(scene.get_path(), scene.get_filename(suffix=ps)) + '.tif'
            try:
                # TODO - allow for other projections
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

