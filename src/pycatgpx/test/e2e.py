'''
Created on 20.06.2016

@author: DLF
'''
import unittest
import os
import gpxpy.gpx
from datetime import datetime, timedelta
from catgpx.catgpx import (
	get_start_time_of_track,
	get_gpxs_from_filenames,
	get_concatenated_gpx
)
path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)

def get_test_segment_by_point_list(point_list):
	segment = gpxpy.gpx.GPXTrackSegment()
	for point in point_list:
		p = gpxpy.gpx.GPXTrackPoint(latitude = point[0], longitude = point[1], time = point[2])
		segment.points.append(p)
	return segment

def get_test_gpx_with_track_by_start_time(start_time, number_of_points = 2):
	segment = get_test_segment_by_point_list(
		[ [50, 8 + 0.01 * i, start_time + timedelta(minutes=1)] for i in range(number_of_points) ]
	)
	track = gpxpy.gpx.GPXTrack()
	track.segments.append(segment)
	gpx = gpxpy.gpx.GPX()
	gpx.tracks.append(track)
	return gpx


class FileTest(unittest.TestCase):

	def test_load_file(self):
		file_path = os.path.join(dir_path,"track.gpx")
		gpx = get_concatenated_gpx(get_gpxs_from_filenames([file_path]))
		self.assertTrue(gpx != None)
		
class ConcatenationTest(unittest.TestCase):
		
	def test_if_two_gpxs_with_one_track_each_are_concatenated_then_the_tracks_are_sorted_by_start_time__earlier_given_first(self):
		gpx_1 = get_test_gpx_with_track_by_start_time(datetime(2016,6,1))
		gpx_2 = get_test_gpx_with_track_by_start_time(datetime(2016,6,2))
		gpx = get_concatenated_gpx([gpx_1, gpx_2])
		self.assertEqual(len(gpx.tracks), 2)
		self.assertTrue(
			get_start_time_of_track(gpx.tracks[0]) < get_start_time_of_track(gpx.tracks[1]) 
		)
		
	def test_if_two_gpxs_with_one_track_each_are_concatenated_then_the_tracks_are_sorted_by_start_time__later_given_first(self):
		gpx_1 = get_test_gpx_with_track_by_start_time(datetime(2016,6,1))
		gpx_2 = get_test_gpx_with_track_by_start_time(datetime(2016,6,2))
		gpx = get_concatenated_gpx([gpx_2, gpx_1])
		self.assertEqual(len(gpx.tracks), 2)
		self.assertTrue(
			get_start_time_of_track(gpx.tracks[0]) < get_start_time_of_track(gpx.tracks[1]) 
		)
		
	#TODO test concatenation of waypoints and routes

if __name__ == "__main__":
	#import sys;sys.argv = ['', 'Test.testName']
	unittest.main()