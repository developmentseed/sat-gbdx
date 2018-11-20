#!/usr/bin/env python
import os
import sys
import shutil
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
    return {c['id']:c for c in cols['collections']}


COLLECTIONS = load_collections()
_COLLECTIONS = {c['properties']['eo:instrument']:c for c in COLLECTIONS.values()}

COG_OPTS = {'COMPRESS': 'DEFLATE', 'PREDICTOR': '2', 'INTERLEAVE': 'BAND',
        'TILED': 'YES', 'BLOCKXSIZE': '512', 'BLOCKYSIZE': '512'}


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
    if 'id' in kwargs:
        results = [gbdx.catalog.get(kwargs['id'])]
    else:
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
    if 'searchAreaWkt' in kwargs:
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
    print('%s (Order %s): %s' % (status['acquisition_id'], sid, status['state']))
    return False if status['location'] == 'not_delivered' else True


def download_scenes(scenes, spec='', pansharpen=False, acomp=False, dra=False):
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
        fulfilled = order(scene)
        if fulfilled:
            #dt = dateparser(scene.metadata['timestamp'])
            #bname = '%s_%s' % (dt.strftime('%Y-%m-%d_%H-%M-%S'), scene.metadata['satellite_name'])
            suffix = '_pansharp' if pansharpen else ''
            if spec == 'rgb':
                suffix += '_rgb'
            fout = os.path.join(os.getcwd(), scene.get_filename(suffix=suffix)) + '.tif'
            try:
                # TODO - allow for other projections
                img = CatalogImage(scene['id'], pansharpen=pansharpen, acomp=acomp, dra=dra,
                                   bbox=scenes.bbox()) #, proj=utm_epsg(scenes.center()))
                if not os.path.exists(fout):
                    tif = img.geotiff(path=fout, proj='EPSG:4326', spec=spec)
                    geoimg = gippy.GeoImage(tif, True)
                    if scene['eo:platform'] == 'GEOEYE01' or scene['eo:platform'] == 'QUICKBIRD02':
                        geoimg.set_nodata(0)
                    else:
                        geoimg.set_nodata(-1e10)
                    # this clips the image to the AOI
                    res = geoimg.resolution()
                    fout2 = os.path.join(dirout, os.path.basename(fout))
                    imgout = alg.cookie_cutter([geoimg], fout2, geovec[0], xres=res.x(), yres=res.y(), proj=geoimg.srs(), options=COG_OPTS)
                    imgout = None
                    os.remove(fout)
                    shutil.move(fout2, fout)
                fouts.append(fout)
            except Exception as e:
                print(e)
    os.remove(aoiname)
    return fouts
