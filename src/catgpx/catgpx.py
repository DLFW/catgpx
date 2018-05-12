#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gpxpy
import argparse
import glob
import piexif
from datetime import datetime, timedelta


class CatGPXException(Exception):
    def __init__(self, msg):
        Exception.__init__(self)
        self.message = msg


class CatGPXError(CatGPXException):
    pass


class CatGPXTimeOrderInSegmentError(CatGPXError):
    def __init__(self, track, segment_number, file_name=None):
        CatGPXError.__init__(
            self,
            msg="Points are not in ordered by time in segment {segment} of track \"{track}\"".format(
                segment=str(segment_number),
                track=track.name
            ) +
            "." if file_name == None else " of file {filename}.".format(filename=file_name)
        )


class CatGPXTimeOrderInTrackError(CatGPXError):
    def __init__(self, track, file_name=None):
        CatGPXError.__init__(self,
            msg="Segments are not in ordered by time in track \"{track}\"".format(
                track=track.name
            ) +
            "." if file_name == None else " of file {filename}.".format(filename=file_name)
        )


class CatGPXTimeOffsetError(CatGPXError):
    def __init__(self, offset):
        CatGPXError.__init__(self, msg=
        "Given offset ({value}) is not an integer between -12 and 12".format(value=offset)
                             )


def print_msg(msg):
    print msg


def print_error(msg):
    print msg


def print_detail(msg):
    print msg


def dec2dms(dec):
    is_positive = dec >= 0
    dec = abs(dec)
    minutes, seconds = divmod(dec * 3600, 60)
    degrees, minutes = divmod(minutes, 60)
    # degrees = degrees if is_positive else -degrees
    return (
        int(round(degrees, 0)),
        int(round(minutes, 0)),
        int(round(seconds, 0)),
        is_positive
    )


def get_start_time_of_segment(segment):
    if len(segment.points) == 0:
        return None
    return segment.points[0].time


def get_start_time_of_track(track):
    if len(track.segments) == 0:
        return None
    return get_start_time_of_segment(track.segments[0])


def segment_is_valid(segment):
    last_time = None
    for point in segment.points:
        if last_time is None:
            last_time = point.time
        else:
            if point.time <= last_time:
                return False
            last_time = point.time
    return True


def track_is_valid(track):
    last_time = None
    for segment in track.segments:
        if last_time is None:
            last_time = get_start_time_of_segment(segment)
        else:
            if get_start_time_of_segment(segment) <= last_time:
                return False
            last_time = get_start_time_of_segment(segment)
    return True


def get_gpxs_from_filenames(infiles):
    gpxs = []
    for infile in infiles:
        with open(infile, 'r') as f:
            gpx = gpxpy.parse(f)
            gpxs.append(gpx)
    # validate
    # TODO: make validation an independent method
    i = 0
    for gpx in gpxs:
        i += 1
        for track in gpx.tracks:
            j = 0
            for segment in track.segments:
                j += 1
                if not segment_is_valid(segment):
                    CatGPXTimeOrderInSegmentError(track=track, segment_number=i, file_name=infiles[i - 1])
            if not track_is_valid(track):
                CatGPXTimeOrderInTrackError(track=track, file_name=infiles[i - 1])
    return gpxs


def get_concatenated_gpx(gpxs):
    assert len(gpxs) > 0
    result = None
    for gpx in gpxs:
        if result == None:
            result = gpx
        else:
            result.tracks.extend(gpx.tracks)
            result.routes.extend(gpx.routes)
            result.waypoints.extend(gpx.waypoints)
    result.tracks.sort(key=lambda t: get_start_time_of_track(t))
    return result


def geo_tag(photos, gpx, time_offset):
    for photo in photos:
        print_detail("Tagging image {file}...".format(file=photo))
        try:
            exif_dict = piexif.load(photo)
        except:
            print_error("Image {file} not readable.".format(file=photo))
            continue
        base_time = exif_dict["0th"][306] if 306 in exif_dict["0th"] else None
        original_time = exif_dict["Exif"][36867] if 36867 in exif_dict["Exif"] else None  # digitized time is 36868
        significant_time = None
        if original_time:
            significant_time = original_time
        elif base_time:
            significant_time = base_time
        else:
            print_msg("Image {file} has no original time and no date-time defined.".format(file=photo))
            continue
        assert significant_time != None
        significant_time = datetime.strptime(significant_time, '%Y:%m:%d %H:%M:%S')
        significant_time -= timedelta(hours=time_offset)
        print_detail("Found significant time " + str(significant_time))
        point = gpx.get_location_at(significant_time)
        if point == None or len(point) == 0:
            print_msg("Time of image {file} not present in tracks.".format(file=photo))
        elif len(point) > 1:
            print_error("Multiple points found for given time.")
        else:
            point = point[0]
            print_detail("Found point " + str(point))
            dms_lat = dec2dms(point.latitude)
            dms_long = dec2dms(point.longitude)
            gps_lat = ((dms_lat[0], 1), (dms_lat[1], 1), (dms_lat[2], 1))
            gps_long = ((dms_long[0], 1), (dms_long[1], 1), (dms_long[2], 1))
            exif_dict['GPS'][piexif.GPSIFD.GPSLongitude] = gps_long
            exif_dict['GPS'][piexif.GPSIFD.GPSLongitudeRef] = 'E' if dms_long[3] else 'W'
            exif_dict['GPS'][piexif.GPSIFD.GPSLatitude] = gps_lat
            exif_dict['GPS'][piexif.GPSIFD.GPSLatitudeRef] = 'N' if dms_lat[3] else 'S'
            exif_dict['GPS'][piexif.GPSIFD.GPSTimeStamp] = (
            (point.time.hour, 1), (point.time.minute, 1), (point.time.second, 1))
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, photo)


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('-q', '--quiet', help="No output except for error messages (no output on stdout)")
    parser.add_argument('-v', '--verbose', help="More output on stdout.")
    parser.add_argument('-X', '--no-print', help="Do not print resulting GPX to stdout", default=False, action='store_true')
    parser.add_argument('-T', '--geo-tag', help="JPEG file(s) to geo tag by time stamp")
    parser.add_argument('-O', '--time-offset',
                        help="Time offset for interpretation of track times (format \"[+-]d[d]\") (used for geo-tagging)")
    parser.add_argument('infiles', nargs='*', help="list of gpx input files")
    args = parser.parse_args(args)
    input_file_tokens = args.infiles
    input_files = []
    for token in input_file_tokens:
        input_files.extend(glob.glob(token))
    if len(input_files) == 0:
        print_msg("No input files specified.")
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
                print_msg("No file(s) found for geo tagging")
            else:
                geo_tag(photos, gpx, time_offset)
        if not args.no_print:
            print gpx.to_xml()

if __name__ == '__main__':
    try:
        main()
    except CatGPXError, e:
        print_error(e.message)
