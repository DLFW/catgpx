# -*- coding: utf-8 -*-

import gpxpy
import glob
import piexif
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
logging.basicConfig()

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
    """
    Returns the start time of a track segment.
    
    Precondition: the track segment must be valid (the points must be ordered ascending by time)
    """
    if len(segment.points) == 0:
        return None
    return segment.points[0].time


def get_start_time_of_track(track):
    """
    Returns the start time of a track.
    
    Precondition: the track must be valid (the segments must be ordered ascending by time)
    """
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
    """
    Insert GPS latitude, longitude and time EXIF information for a bunch of photos.
    The information is taken from a GPS track, the EXIF time stamp of the photos and
    the GPS time from the GPX track are used to find the most relevant point of the track 
    for each particular photo.
    
    :param photos: a list of file names of the photos to tag
    :param gpx: the GPX track whose GPS information shall be used for the tagging
    :param time_offset: an integer in [-12 .. 12], added to the GPS time stamps to balance out time zone offsets between the GPX track and the photos
    """
    assert -12 <= time_offset <= 12
    for photo in photos:
        logger.debug("Tagging image {file}...".format(file=photo))
        try:
            exif_dict = piexif.load(photo)
        except:
            logger.error("Image {file} not readable.".format(file=photo))
            continue
        base_time = exif_dict["0th"][306] if 306 in exif_dict["0th"] else None
        original_time = exif_dict["Exif"][36867] if 36867 in exif_dict["Exif"] else None  # digitized time is 36868
        significant_time = None
        if original_time:
            significant_time = original_time
        elif base_time:
            significant_time = base_time
        else:
            logger.info("Image {file} has no original time and no date-time defined.".format(file=photo))
            continue
        assert significant_time != None
        significant_time = datetime.strptime(significant_time, '%Y:%m:%d %H:%M:%S')
        significant_time -= timedelta(hours=time_offset)
        logger.debug("Found significant time " + str(significant_time))
        point = gpx.get_location_at(significant_time)
        if point == None or len(point) == 0:
            logger.info("Time of image {file} not present in tracks.".format(file=photo))
        elif len(point) > 1:
            logger.error("Multiple points found for given time.")
        else:
            point = point[0]
            logger.debug("Found point " + str(point))
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
            
            
