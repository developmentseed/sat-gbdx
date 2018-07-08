import numpy as np
from pygeotile.tile import Tile
import gippy


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