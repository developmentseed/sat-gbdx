import json
import logging
import os
import sys

import satsearch.config as config
from satsearch.parser import SatUtilsParser
from .main import main


logger = logging.getLogger(__name__)


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
        #group.add_argument('--types', nargs='*', default=['DigitalGlobeAcquisition'],
        #                   help='Data types ("DigitalGlobeAcquisition", "GBDXCatalogRecord", "IDAHOImage"')
        parser.search_group.add_argument('--overlap', help='Minimum %% overlap of footprint to AOI', default=1, type=int)        
        return parser


def cli():
    parser = GBDXParser.newbie(description='GBDX Search')
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