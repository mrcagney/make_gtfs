import unittest

import pandas as pd 
import numpy as np
from pandas.util.testing import assert_frame_equal, assert_series_equal
from shapely.geometry import Point, LineString, mapping

from make_gtfs import *

# Load test feeds
akl = Feed('tests/auckland_snippet/')

class TestFeed(unittest.TestCase):
    def test_seconds_to_timestr(self):
        seconds = 3600 + 60 + 1
        timestr = '01:01:01'
        self.assertEqual(seconds_to_timestr(seconds), timestr)
        self.assertEqual(seconds_to_timestr(timestr, inverse=True), seconds)
        self.assertIsNone(seconds_to_timestr(timestr))
        self.assertIsNone(seconds_to_timestr(seconds, inverse=True))
        self.assertIsNone(seconds_to_timestr('01:01', inverse=True))

    def test_timestr_mod_24(self):
        timestr1 = '01:01:01'
        self.assertEqual(timestr_mod_24(timestr1), timestr1)
        timestr2 = '25:01:01'
        self.assertEqual(timestr_mod_24(timestr2), timestr1)
        
    def test_get_duration(self):
        ts1 = '01:01:01'
        ts2 = '01:05:01'
        get = get_duration(ts1, ts2, units='min')
        self.assertEqual(get, 4)


    def test_init(self):
        feed = akl
        self.assertIsInstance(feed.raw_routes, pd.core.frame.DataFrame)
        self.assertIsInstance(feed.config, dict)
        self.assertIsInstance(feed.raw_shapes, dict)


    # def test_get_trips_stats(self):
    #     feed = cairns
    #     trips_stats = feed.get_trips_stats()
    #     # Should be a data frame with the correct number of rows
    #     self.assertIsInstance(trips_stats, pd.core.frame.DataFrame)
    #     self.assertEqual(trips_stats.shape[0], feed.trips.shape[0])
    #     # Shapeless feeds should have null entries for distance column
    #     feed2 = cairns_shapeless
    #     trips_stats = feed2.get_trips_stats()
    #     self.assertEqual(len(trips_stats['distance'].unique()), 1)
    #     self.assertTrue(np.isnan(trips_stats['distance'].unique()[0]))   
    #     # Should contain the correct trips
    #     get_trips = set(trips_stats['trip_id'].values)
    #     expect_trips = set(feed.trips['trip_id'].values)
    #     self.assertEqual(get_trips, expect_trips)

    # def test_get_linestring_by_shape(self):
    #     feed = cairns
    #     linestring_by_shape = feed.get_linestring_by_shape()
    #     # Should be a dictionary
    #     self.assertIsInstance(linestring_by_shape, dict)
    #     # The first element should be a Shapely linestring
    #     self.assertIsInstance(list(linestring_by_shape.values())[0], 
    #       LineString)
    #     # Should contain all shapes
    #     self.assertEqual(len(linestring_by_shape), 
    #       feed.shapes.groupby('shape_id').first().shape[0])
    #     # Should be None if feed.shapes is None
    #     feed2 = cairns_shapeless
    #     self.assertIsNone(feed2.get_linestring_by_shape())


if __name__ == '__main__':
    unittest.main()