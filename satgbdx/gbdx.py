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
import traceback
from tempfile import TemporaryDirectory

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

COG = {'COMPRESS': 'DEFLATE', 'PREDICTOR': '2', 'INTERLEAVE': 'BAND',
        'TILED': 'YES', 'BLOCKXSIZE': '256', 'BLOCKYSIZE': '256'}

JPEG_COG = {'COMPRESS': 'JPEG', 'PHOTOMETRIC': 'YCBCR',
        'TILED': 'YES', 'BLOCKXSIZE': '256', 'BLOCKYSIZE': '256'}


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

    #def utm_epsg(self, latlon):
    #    """ Get UTM zone for this scene """
    #    zone = utm.from_latlon(latlon[0], latlon[1])
    #    return ('EPSG:327' if latlon[0] < 0 else 'EPSG:326') + str(zone[2])

    def order(self):
        """ Order this scene """
        if 'dg:order_id' not in self.keys():
            self.feature['properties']['dg:order_id'] = gbdx.ordering.order(self['id'])
        sid = self.feature['properties']['dg:order_id']
        status = gbdx.ordering.status(sid)[0]
        if status['location'] == 'not_delivered':
            logger.info('%s (Order %s): %s' % (status['acquisition_id'], sid, status['state']))
        return False if status['location'] == 'not_delivered' else True

    def download(self, key, **kwargs):
        """ Download this key from scene assets """
        if key != 'thumbnail':
            logger.warn('Downloading non-thumbnail images not supported')
        fname = super().download(key, **kwargs)
        if fname is not None:
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

    def fetch(self, key, aoi, pansharpen=False, acomp=False, dra=False, **kwargs):
        if self.order():
            # create tempfile for AOI
            with tempfile.NamedTemporaryFile(suffix='.geojson', mode='w', delete=False) as f:
                aoiname = f.name
                aoistr = json.dumps(aoi)
                f.write(aoistr)
            geovec = gippy.GeoVector(aoiname)
            ext = geovec.extent()
            bbox = [ext.x0(), ext.y0(), ext.x1(), ext.y1()]

            # determine name
            #dt = dateparser(scene.metadata['timestamp'])
            #bname = '%s_%s' % (dt.strftime('%Y-%m-%d_%H-%M-%S'), scene.metadata['satellite_name'])
            # defaults
            spec = ''
            pansharpen = False
            acomp = False
            dra = False
            nodata = 0 if self['eo:platform'] in ['GEOEYE01', 'QUICKBIRD02'] else -1e10
            opts = COG

            # set options
            if key == 'rgb':
                pansharpen = True
                spec = 'rgb'
                nodata = 0
                #opts = JPEG_COG
            elif key == 'visual':
                pansharpen = True
                dra = True
                nodata = 0
                #opts = JPEG_COG
            elif key == 'analytic':
                acomp = True

            fout = os.path.join(self.get_path(), self.get_filename(suffix='_%s' % key)) + '.tif'

            with TemporaryDirectory() as temp_dir:
                try:
                    if not os.path.exists(fout):
                        logger.info('Fetching %s: %s' % (key, fout))
                        # TODO - allow for other projections
                        img = CatalogImage(self['id'], pansharpen=pansharpen, acomp=acomp, dra=dra, bbox=bbox) #, proj=utm_epsg(scenes.center()))
                        tmp_fout1 = os.path.join(temp_dir, '%s_%s_1.tif' % (self['id'], key))
                        tmp_fout2 = os.path.join(temp_dir, '%s_%s_2.tif' % (self['id'], key))
                        tif = img.geotiff(path=tmp_fout1, proj='EPSG:4326', spec=spec)
                        # clip and save
                        geoimg = gippy.GeoImage(tif, True)
                        # workaround for gbdxtools scaling
                        if key in ['rgb', 'visual']:
                            geoimg = geoimg.autoscale(1, 255).save(tmp_fout2)
                        geoimg.set_nodata(0)
                        # this clips the image to the AOI
                        res = geoimg.resolution()
                        imgout = alg.cookie_cutter([geoimg], fout, geovec[0], xres=res.x(), yres=res.y(), proj=geoimg.srs(), options=opts)
                        imgout.add_overviews([2,4,8,16], resampler='average')
                        imgout = None
                except Exception as e:
                    logger.warning('Error fetching: %s' % str(e))
                    #logger.warning('Traceback: %s', traceback.format_exc())

            os.remove(aoiname)
            return fout


class GBDXScenes(Scenes):

    @classmethod
    def load(cls, filename):
        """ Load a collections class from a GeoJSON file of metadata """
        with open(filename) as f:
            geoj = json.loads(f.read())
        scenes = [GBDXScene(feature) for feature in geoj['features']]
        return cls(scenes, properties=geoj.get('properties', {}))

    def fetch(self, key, **kwargs):
        dls = []
        for s in self.scenes:
            fname = s.fetch(key, aoi=self.properties['intersects'], **kwargs)
            if fname is not None:
                dls.append(fname)
        return dls


def query(types=['DigitalGlobeAcquisition'], overlap=None, **kwargs):
    """ Perform a GBDX query by converting from STAC terms to DG terms """
    filters = []  # ["offNadirAngle < 20"
    if 'id' in kwargs:
        results = [gbdx.catalog.get(i) for i in kwargs['id'].split(',')]
    else:
        # build DG search parameters
        if 'c:id' in kwargs:
            _sensors = [COLLECTIONS[c]['properties']['eo:instrument'] for c in kwargs.pop('c:id')]
            filters.append("sensorPlatformName = '%s'" % ','.join(_sensors))
        if 'intersects' in kwargs:
            fc = json.loads(kwargs.pop('intersects'))
            geom = None
            if fc.get('features'):
                # if FeatureCollection
                geom = shape(fc['features'][0]['geometry'])
            elif fc.get('geometry'):
                # if Feature
                geom = shape(fc['geometry'])
            else:
                # if direct geometry
                geom = shape(fc)
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
