#!/usr/bin/env python
import os
import logging

import satgbdx
import satsearch.config as config


logger = logging.getLogger(__name__)


def main(scenes=None, review=False, print_md=None, print_cal=False,
         save=None, append=False, download=None, 
         order=False, gettiles=None, geojson=None, **kwargs):

    if scenes is None:
        scenes = satgbdx.GBDXScenes(satgbdx.query(**kwargs), properties=kwargs)
    else:
        # ensure we update the results file every time (could have ordering information)
        if save is None:
            save = scenes
        scenes = satgbdx.GBDXScenes.load(scenes)

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
        scenes = [s.order for s in scenes]

    print('%s scenes found' % len(scenes))

    # download files given keys
    if download is not None:
        for key in download:
            if key not in ['thumbnail', 'default', 'rgb', 'visual', 'analytic']:
                logger.warning('Download keys not recognized (%s)' % ','.join(download))
            if key == 'thumbnail':
                scenes.download(key='thumbnail')
            else:
                scenes.fetch(key)

    # save all metadata in JSON file
    if save is not None:
        scenes.save(filename=save)

    return scenes
