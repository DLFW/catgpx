#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import logging
import glob
from pycatgpx import (
    get_concatenated_gpx,
    get_gpxs_from_filenames,
    geo_tag,
    CatGPXError
    )

logger = logging.getLogger("pycatgpx")
logging.basicConfig()

class CatGPXTimeOffsetError(CatGPXError):
    def __init__(self, offset):
        CatGPXError.__init__(self, msg=
        "Given offset ({value}) is not an integer between -12 and 12".format(value=offset)
                             )

def start(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', help="Print additional information to stderr", action='store_true')
    parser.add_argument('-V', '--extra-verbose', help="Print additional information and debug messages to stderr", action='store_true')
    parser.add_argument('-X', '--no-print', help="Do not print resulting GPX to stdout", default=False, action='store_true')
    parser.add_argument('-T', '--geo-tag', help="JPEG file(s) to geo tag by time stamp")
    parser.add_argument('-O', '--time-offset',
                        help="Time offset for interpretation of track times (format \"[+-]d[d]\") (used for geo-tagging)")
    parser.add_argument('infiles', nargs='*', help="list of gpx input files")
    args = parser.parse_args(args)
    
    if args.verbose:
        logger.setLevel(logging.INFO)
    if args.extra_verbose:
        logger.setLevel(logging.DEBUG)
    
    input_file_tokens = args.infiles
    input_files = []
    for token in input_file_tokens:
        input_files.extend(glob.glob(token))
    if len(input_files) == 0:
        logger.error("No input files specified.")
    else:
        gpx = get_concatenated_gpx(get_gpxs_from_filenames(input_files))
        time_offset = 0
        if args.time_offset:
            try:
                time_offset = int(args.time_offset)
                assert -12 <= time_offset <= 12
            except:
                raise CatGPXTimeOffsetError(args.time_offset)
        if args.geo_tag:
            photos = glob.glob(args.geo_tag)
            if len(photos) == 0:
                logger.error("No file(s) found for geo tagging")
            else:
                geo_tag(photos, gpx, time_offset)
        if not args.no_print:
            print gpx.to_xml()

if __name__ == '__main__':
    try:
        start()
    except CatGPXError, e:
        logger.error(e.message)
