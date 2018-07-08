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
from shapely.geometry import shape, Polygon
from pygeotile.tile import Tile
from satsearch.scene import Scene, Scenes
from satsearch.parser import SatUtilsParser
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


"""
e.g.,
./gbdx-search.py --intersects geojsonfile --printmd date scene_id satellite_name --clouds 0,10 --save ${gj%.*}
/scenes-gbdx.geojson --date 2015-01-01,2017-11-01 --datadir ${gj%.*} --nosubdirs --download thumb


Available satellite names
{'GEOEYE01', 'WORLDVIEW03_VNIR', 'LANDSAT08', 'WORLDVIEW01', 'QUICKBIRD02', 'WORLDVIEW02', 'IKONOS', 'WORLDVIEW03_SWIR'}

Available types
{"DigitalGlobeAcquisition", "GBDXCatalogRecord", "IDAHOImage"}

colorInterpretation
BGRN
PAN
WORLDVIEW_8_BAND

"""


class GBDXParser(SatUtilsParser):

    def __init__(self, *args, **kwargs):
        super(GBDXParser, self).__init__(*args, save=False, download=False, output=True, **kwargs)
        group = self.add_argument_group('GBDX parameters')
        # search
        #group.add_argument('--types', nargs='*', default=['DigitalGlobeAcquisition'],
        #                   help='Data types ("DigitalGlobeAcquisition", "GBDXCatalogRecord", "IDAHOImage"')
        #group.add_argument('--overlap', help='Minimum overlap of footprint to AOI', default=1.0, type=float)

        group.add_argument('--load', help='Load search results from file', required=True)

        # downloading
        group.add_argument('--datadir', help='Local directory to save images', default=config.DATADIR)
        group.add_argument('--subdirs', help='Save in subdirs based on these metadata keys', default="")
        group.add_argument('--filename', default="${date}_${satellite_name}_${scene_id}",
                           help='Save files with this filename pattern based on metadata keys')
        group.add_argument('--download', help='Download geotiffs', action='store_true', default=False)

        #group = self.add_argument_group('IDAHO Tiles')
        #group.add_argument('--gettiles', help='Fetch tiles at this zoom level', default=None, type=int)
        group.add_argument('--nocrop', help='Do not crop to AOI', default=False, action='store_true')
        group.add_argument('--pansharp', help='Pan-sharpen fetched images, if able', default=False, action='store_true')
        group.add_argument('--carcount', help='Pan-sharpen fetched images, if able', default=False, action='store_true')


def utm_epsg(latlon):
    zone = utm.from_latlon(latlon[0], latlon[1])
    return ('EPSG:327' if latlon[0] < 0 else 'EPSG:326') + str(zone[2])


def order_scenes(scenes):
    """ Order this scene """
    for scene in scenes:
        scene.metadata['order_id'] = gbdx.ordering.order(scene.scene_id)
        status = gbdx.ordering.status(scene.metadata['order_id'])[0]
        scene.metadata['location'] = status['location']
        print('%s\t%s\t%s\t%s' % (scene.metadata['order_id'], status['acquisition_id'], status['state'], status['location']))


def download_scenes(scenes, nocrop=False, pansharp=False):
    """ Download these scenes """
    with tempfile.NamedTemporaryFile(suffix='.geojson', mode='w', delete=False) as f:
        aoiname = f.name
        aoistr = json.dumps(scenes.metadata['aoi'])
        f.write(aoistr)
    geovec = gippy.GeoVector(aoiname)
    fouts = []
    dirout = tempfile.mkdtemp()
    crop = True if nocrop is False else False
    for scene in scenes:
        if 'location' in scene.metadata:
            path = scene.get_path()
            #dt = dateparser(scene.metadata['timestamp'])
            #bname = '%s_%s' % (dt.strftime('%Y-%m-%d_%H-%M-%S'), scene.metadata['satellite_name'])
            ps = '_pansharp' if pansharp else ''
            fout = os.path.join(path, scene.get_filename(suffix=ps)) + '.tif'
            try:
                img = CatalogImage(scene.scene_id, pansharpen=pansharp, bbox=scenes.bbox(), proj=utm_epsg(scenes.center()))
                if not os.path.exists(fout):
                    tif = img.geotiff(path=fout)
                    geoimg = gippy.GeoImage(tif, True)
                    if scene.metadata['satellite_name'] == 'GEOEYE01' or scene.metadata['satellite_name'] == 'QUICKBIRD02':
                        geoimg.set_nodata(0)
                    else:
                        geoimg.set_nodata(-1e10)
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


def car_count(scene, bbox=None, pansharp=False):
    """ Run workflow """
    # workflows
    if 'location' not in scene.metadata:
        return None

    alg = 'deepcore-singleshot'
    suffix = '_%s' % alg
    suffix = suffix if pansharp is False else '_pansharp' + suffix
    outdir = os.path.join('sez', scene.get_filename(suffix=suffix))

    data = scene.metadata['location']
    if bbox is not None:
        task_crop = gbdx.Task('CropGeotiff', data=data, wkt=shape(bbox).wkt)
        data = task_crop.outputs.data
        workflow = [task_crop]
    else:
        workflow = []

    task_proc = gbdx.Task('AOP_Strip_Processor', data=data,
                          bands='MS', enable_dra=False, enable_acomp=True,
                          enable_pansharpen=pansharp, ortho_epsg='UTM')
    workflow.append(task_proc)

    task_alg = gbdx.Task(alg, data=task_proc.outputs.data.value)
    workflow.append(task_alg)

    workflow = gbdx.Workflow(workflow)
    if bbox is not None:
        workflow.savedata(task_crop.outputs.data, location=outdir)
    #workflow.savedata(task_proc.outputs.data.value, location=outdir)
    workflow.savedata(task_alg.outputs.data, location=outdir)
    workflow.execute()
    workflow.status
    print(workflow.id, workflow.status)

    scene.metadata['workflows'] = scene.metadata.get('workflows', []).append(workflow.id)

    return workflow.id


def main(load=None, download=None, printsearch=False, printmd=None, printcal=False, review=False,
         nocrop=False, pansharp=False, carcount=False, **kwargs):
    """ Create/run GBDX workflow """
    scenes = Scenes.load(load)

    # move to sat-search
    for key, value in kwargs.items():
        scenes.filter(key, value)

    # print summary
    if printmd is not None:
        scenes.print_scenes(printmd)
    # print calendar
    if printcal:
        print(scenes.text_calendar())
    print('%s scenes found' % len(scenes))

    #if order:
    #    order_scenes(scenes)

    if download:
        order_scenes(scenes)
        fouts = download_scenes(scenes, nocrop=nocrop, pansharp=pansharp)

    if carcount:
        for scene in scenes[1:]:
            wid = car_count(scene, pansharp=pansharp) #, bbox=scenes.metadata['aoi'])
            wf = scene.metadata.get('workflows')
            wf = [] if wf is None else wf
            print('Workflow ID', wid)
            scene.metadata['workflows'] = wf + [wid]
            #[car_count(scene, bbox=scenes.bbox()) for scene in scenes]
    # save new metadata back to loaded file
    scenes.save(filename=load)

    return scenes


def cli():
    parser = GBDXParser(description='GBDX Search')
    args = parser.parse_args(sys.argv[1:])

    # enable logging
    logging.basicConfig(stream=sys.stdout, level=args.pop('verbosity') * 10)

    scenes = main(**args)
    return len(scenes)


if __name__ == "__main__":
    cli()
