import unittest
import zipfile

import pandas as pd 
from pandas.util.testing import assert_frame_equal, assert_series_equal
from shapely.geometry import Point, LineString, mapping

from make_gtfs.make_gtfs import *

# Load test feeds
akl = Feed('data/auckland_snippet/')

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
        expect = 4
        self.assertEqual(get, expect)

    def test_init(self):
        feed = akl
        self.assertIsInstance(feed.raw_routes, pd.core.frame.DataFrame)
        self.assertIsInstance(feed.config, dict)
        self.assertIsInstance(feed.raw_shapes, dict)

    def test_get_window_duration(self):
        feed = akl
        get = feed.get_window_duration('weekday_peak', units='h')
        expect = 4
        self.assertEqual(get, expect)

    def test_create_routes(self):
        feed = akl
        feed.create_routes()      
        routes = feed.routes 
        # Should be a data frame
        self.assertIsInstance(routes, pd.core.frame.DataFrame)
        # Should have correct shape
        expect_nrows = feed.raw_routes.shape[0]
        expect_ncols = 4
        self.assertEqual(routes.shape, (expect_nrows, expect_ncols))

    def test_create_linestring_by_route(self):
        feed = akl
        linestring_by_route = feed.get_linestring_by_route(use_utm=False)
        # Should be a dictionary
        self.assertIsInstance(linestring_by_route, dict)
        # The first element should be a Shapely linestring
        self.assertIsInstance(list(linestring_by_route.values())[0], 
          LineString)
        # Should contain one shape for each route
        self.assertEqual(len(linestring_by_route), feed.raw_routes.shape[0])

    def test_create_shapes(self):
        feed = akl
        feed.create_shapes()
        shapes = feed.shapes
        # Should be a data frame
        self.assertIsInstance(shapes, pd.core.frame.DataFrame)
        # Should have correct shape
        expect_nshapes = feed.raw_routes.shape[0]
        expect_ncols = 4
        self.assertEqual(shapes.groupby('shape_id').ngroups, expect_nshapes)
        self.assertEqual(shapes.shape[1], expect_ncols)

    def test_create_stops(self):
        feed = akl
        feed.create_stops()
        stops = feed.stops
        # Should be a data frame
        self.assertIsInstance(stops, pd.core.frame.DataFrame)
        # Should have correct shape
        expect_nrows = 2*feed.raw_routes.shape[0]
        expect_ncols = 4
        self.assertEqual(stops.shape, (expect_nrows, expect_ncols))

    def test_create_trips(self):
        feed = akl
        feed.create_trips()
        trips = feed.trips
        # Should be a data frame
        self.assertIsInstance(trips, pd.core.frame.DataFrame)
        # Should have correct shape
        windows = feed.get_service_windows()
        expect_nrows = 0
        for index, row in feed.raw_routes.iterrows():
            # Number of trips for this route is the sum over each service
            # window of twice the window duration divided by the headway. 
            # Twice because have a trip running in both directions 
            # simulateously
            expect_nrows += 2*sum(
              feed.get_window_duration(wname, units='min')//\
              row[wname + '_headway'] for wname in windows)
        expect_ncols = 5
        self.assertEqual(trips.shape, (expect_nrows, expect_ncols))

    def test_create_stop_times(self):
        feed = akl
        feed.create_stop_times()
        stop_times = feed.stop_times
        # Should be a data frame
        self.assertIsInstance(stop_times, pd.core.frame.DataFrame)
        # Should have correct shape
        windows = feed.get_service_windows()
        expect_nrows = 0
        for index, row in feed.raw_routes.iterrows():
            # Number of trips for this route is the sum over each service
            # window of twice the window duration divided by the headway. 
            # Twice because have a trip running in both directions 
            # simulateously.
            # Number of stop times is twice the number of trips,
            # because each trip has two stops.
            expect_nrows += 4*sum(
              feed.get_window_duration(wname, units='min')//\
              row[wname + '_headway'] for wname in windows)
        expect_ncols = 5
        self.assertEqual(stop_times.shape, (expect_nrows, expect_ncols))

    def test_create_all(self):
        feed = akl
        feed.create_all()
        names = ['agency', 'calendar', 'routes', 'stops', 'trips',
          'stop_times']
        for name in names:
            self.assertTrue(hasattr(feed, name))

    def test_export(self):
        feed = akl
        
        # Should raise an error if try to export before create files
        self.assertRaises(AssertionError, feed.export())
        
        # Should create the necessary files. 
        # Already know they're CSV because rely on Pandas for CSV export.
        feed.create_all()
        odir = 'tests/'
        feed.export(odir)
        names = ['agency', 'calendar', 'routes', 'stops', 'trips',
          'stop_times']
        for name in names:
            path = os.path.join(odir, name + '.txt')
            self.assertTrue(os.path.exists(path))
            os.remove(path) # Clean up

        # Should create a zip archive this time
        feed.export(odir, as_zip=True)
        zip_path = os.path.join(odir, 'gtfs.zip')
        self.assertTrue(zipfile.is_zipfile(zip_path))
    
        # Zip archive should contain all the necessary files
        expect_nameset = set(name + '.txt' for name in names)
        get_nameset = set(zipfile.ZipFile(zip_path, 'r').namelist())
        self.assertEqual(get_nameset, expect_nameset)

        os.remove(zip_path) # Remove zip file


if __name__ == '__main__':
    unittest.main()