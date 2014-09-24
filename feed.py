"""
"""
import json
import os
import shutil

import pandas as pd
import numpy as np
from shapely.ops import transform
from shapely.geometry import shape, mapping
import utm

def seconds_to_timestr(seconds, inverse=False):
    """
    Return the given number of integer seconds as the time string '%H:%M:%S'.
    If ``inverse == True``, then do the inverse operation.
    In keeping with GTFS standards, the hours entry may be greater than 23.
    """
    if not inverse:
        try:
            seconds = int(seconds)
            hours, remainder = divmod(seconds, 3600)
            mins, secs = divmod(remainder, 60)
            result = '{:02d}:{:02d}:{:02d}'.format(hours, mins, secs)
        except:
            result = None
    else:
        try:
            hours, mins, seconds = seconds.split(':')
            result = int(hours)*3600 + int(mins)*60 + int(seconds)
        except:
            result = None
    return result

def timestr_mod_24(timestr):
    """
    Given a GTFS time string in the format %H:%M:%S, return a timestring
    in the same format but with the hours taken modulo 24.
    """
    try:
        hours, mins, seconds = [int(x) for x in timestr.split(':')]
        hours %= 24
        result = '{:02d}:{:02d}:{:02d}'.format(hours, mins, seconds)
    except:
        result = None
    return result

def get_duration(timestr_a, timestr_b):
    """
    Return the number of minutes in the time interval 
    [``timestr_a``, ``timestr_b``].
    """
    a = seconds_to_timestr(timestr_a, inverse=True)
    b = seconds_to_timestr(timestr_b, inverse=True)
    return (b - a)/60

def get_shape_id(route_id):
    return 's-{!s}'.format(route_id)

def get_stop_ids(route_id):
    return ['st-{!s}-{!s}'.format(route_id, i) for i in range(2)]

def get_stop_names(route_short_name):
    return ['Route {!s} stop {!s}'.format(route_short_name, i)
      for i in range(2)]


class Feed(object):
    """
    A class to gather all the GTFS files for a feed and store them in memory 
    as Pandas data frames.  
    Make sure you have enough memory!  
    The stop times object can be big.
    """
    def __init__(self, home_path):
        """
        Import the data files located in the directory at the given path,
        and assign them to attributes of a new Feed object.
        """
        self.home_path = home_path

        # Import files
        self.config = json.load(open(
          os.path.join(home_path, 'config.json'), 'r'))
        self.raw_shapes = json.load(open(
          os.path.join(home_path,'shapes.geojson'), 'r'))        

        raw_routes = pd.read_csv(
          os.path.join(home_path, 'routes.csv'), 
          dtype={'route_short_name': str})
        cols = raw_routes.columns
        # Create route type and fill in missing values with default
        # types from config
        if 'route_type' not in cols:
            raw_routes['route_type'] = np.nan
        raw_routes['route_type'].fillna(
          int(self.config['default_route_type']), inplace=True)
        raw_routes['route_type'] = raw_routes['route_type'].astype(int)
        # Create route speeds and fill in missing values with default speeds
        # from config
        if 'speed' not in cols:
            raw_routes['speed'] = np.nan
        raw_routes['speed'].fillna(
          int(self.config['default_speed']), inplace=True)
        # Save
        self.raw_routes = raw_routes

    def create_agency(self):
        """
        Create a Pandas data frame representing ``agency.txt``.
        """
        self.agency = pd.DataFrame({
          'agency_name': self.config['agency_name'], 
          'agency_url': self.config['agency_url'],
          'agency_timezone': self.config['agency_timezone']
          }, index=[0])

    def create_calendar(self):
        """
        Create a Pandas data frame representing ``calendar.txt``.
        It is a dumb calendar with one service that operates
        on every day of the week.
        """
        self.calendar = pd.DataFrame({
          'service_id': 'c0', 
          'monday': 1,
          'tuesday': 1, 
          'wednesday': 1,
          'thursday': 1, 
          'friday': 1, 
          'saturday': 1, 
          'sunday': 1, 
          'start_date': self.config['start_date'], 
          'end_date': self.config['end_date'],
          }, index=[0])

    def create_routes(self):
        """
        Create a Pandas data frame representing ``routes.txt``.
        """
        f = self.raw_routes[['route_short_name', 'route_desc', 
          'route_type']].copy()

        # Create route IDs
        f['route_id'] = ['r' + str(i) for i in range(f.shape[0])]
        
        # Save
        self.routes = f 

    def get_linestring_by_route(self, use_utm=False):
        """
        Given a GeoJSON feature collection of linestrings tagged with 
        route short names, return a dictionary with structure
        route ID -> Shapely linestring of shape.
        If ``use_utm == True``, then return each linestring in
        in UTM coordinates.
        Otherwise, return each linestring in WGS84 longitude-latitude
        coordinates.

        Assume ``self.routes`` has been created.
        """
        assert hasattr(self, 'routes'),\
          "You must first create self.routes"

        # Note the output for conversion to UTM with the utm package:
        # >>> u = utm.from_latlon(47.9941214, 7.8509671)
        # >>> print u
        # (414278, 5316285, 32, 'T')
        d = {}
        if use_utm:
            def proj(lon, lat):
                return utm.from_latlon(lat, lon)[:2] 
        else:
            def proj(lon, lat):
                return lon, lat
            
        rid_by_rsn = dict(self.routes[['route_short_name', 'route_id']].values)
        return {rid_by_rsn[f['properties']['route_short_name']]: 
          transform(proj, shape(f['geometry'])) 
          for f in self.raw_shapes['features']}

    def create_shapes(self):
        """
        Create a Pandas data frame representing ``shapes.txt`` and save it 
        to ``self.shapes``.
        Each route has one shape that is used for both directions of travel. 
        
        Assume ``self.routes`` has been created.
        """
        assert hasattr(self, 'routes'),\
          "You must first create self.routes"

        F = []
        linestring_by_route = self.get_linestring_by_route(use_utm=False)
        for index, row in self.routes.iterrows():
            route = row['route_id']
            linestring = linestring_by_route[route]
            shape = get_shape_id(route)
            rows = [[shape, i, lon, lat] 
              for i, (lon, lat) in enumerate(linestring.coords)]
            F.extend(rows)
        self.shapes = pd.DataFrame(F, columns=['shape_id', 'shape_pt_sequence',
          'shape_pt_lon', 'shape_pt_lat'])

    def create_stops(self):
        """
        Create a Pandas data frame representing ``stops.txt`` and save it to
        ``self.stops``.
        Create one stop at the beginning (the first point) of each shape 
        and one at the end (the last point) of each shape.
        This will create duplicate stops in case shapes share endpoints.

        Assume ``self.routes`` has been created.
        """
        assert hasattr(self, 'routes'),\
          "You must first create self.routes"

        linestring_by_route = self.get_linestring_by_route(use_utm=False)
        rsn_by_rid = dict(self.routes[['route_id', 'route_short_name']].values)
        F = []
        for rid, linestring in linestring_by_route.items():
            rsn = rsn_by_rid[rid] 
            stop_ids = get_stop_ids(rid)
            stop_names = get_stop_names(rsn)
            for i in range(2):
                stop_id = stop_ids[i]
                stop_name = stop_names[i]
                stop_lon, stop_lat = linestring.interpolate(i, 
                  normalized=True).coords[0]
                F.append([stop_id, stop_name, stop_lon, stop_lat])
        self.stops = pd.DataFrame(F, columns=['stop_id', 'stop_name', 
          'stop_lon', 'stop_lat'])

    def get_service_windows(self):
        """
        Return a list of tuples of the form 
        (service window name string, 
         service window start time string, service window duration in minutes)
        Service window names can be repeated in case the service is not a 
        contiguous block of time, e.g. "offpeak" from 06:00:00 to 08:00:00 and
        from 09:00:00 to 19:00:00.
        """
        sw_by_name = self.config['service_window_by_name']
        result = []
        for name, window in sw_by_name.items():
            for interval in window:
                duration = (seconds_to_timestr(interval[1], inverse=True) -\
                  seconds_to_timestr(interval[0], inverse=True))/60
                result.append((name, interval[0], duration))
        return result

    def create_trips(self):
        """
        Create a Pandas data frame representing ``trips.txt`` and save it to
        ``self.trips``.
        Trip IDs encode direction, service window, and trip number within that
        direction and service window to make it easy to compute stop times.

        Assume ``self.routes`` and ``self.shapes`` have been created.
        """
        assert hasattr(self, 'routes') and hasattr(self, 'shapes'),\
          "You must first create self.routes and self.shapes"

        # Create trip IDs and directions
        #self.add_num_trips_per_direction()
        F = []
        windows = self.get_service_windows()
        for index, row in pd.merge(self.raw_routes, self.routes).iterrows():
            route = row['route_id']
            shape = get_shape_id(route)
            for name, start, duration in windows:
                headway = row[name + '_headway']
                num_trips_per_direction = int(duration/headway)
                for direction in range(2):
                    for i in range(num_trips_per_direction):
                        F.append([
                          route, 
                          't-{!s}-{!s}-{!s}-{!s}-{!s}'.format(
                          route, name, start, direction, i), 
                          direction,
                          shape,
                          ])
        f = pd.DataFrame(F, columns=['route_id', 'trip_id', 'direction_id', 
          'shape_id'])

        # Create service IDs
        f['service_id'] = self.calendar['service_id'].iat[0]

        # Save
        self.trips = f

    def create_stop_times(self):
        """
        Create a Pandas data frame representing ``stop_times.txt`` and save it
        to ``self.stop_times``.

        Assume ``self.stops`` and ``self.trips`` has been created.
        """
        assert hasattr(self, 'stops') and hasattr(self, 'trips'),\
          "You must first create self.stops and self.trips"

        F = []
        windows = self.get_service_windows()
        linestring_by_route = self.get_linestring_by_route(use_utm=True)
        # Store arrival and departure times as seconds past midnight and
        # convert to strings at the end
        f = pd.merge(self.raw_routes, 
          self.routes[['route_id', 'route_short_name']])
        for route, group in pd.merge(f, self.trips).groupby(
          'route_id'):
            length = linestring_by_route[route].length/1000  # kilometers
            speed = group['speed'].iat[0]  # kph
            duration = int((length/speed)*3600)  # seconds
            sids = get_stop_ids(route)
            sids_by_direction = {0: sids, 1: sids[::-1]}
            for index, row in group.iterrows():
                trip = row['trip_id']
                junk, route, swname, base_timestr, direction, i =\
                  trip.split('-')
                direction = int(direction)
                i = int(i)
                sids_tmp = sids_by_direction[direction]
                base_time = seconds_to_timestr(base_timestr,
                  inverse=True)
                headway = row[swname + '_headway']
                start_time = base_time + headway*60*i
                end_time = start_time + duration
                # Get end time from route length
                entry0 = [trip, sids_tmp[0], 0, start_time, start_time]
                entry1 = [trip, sids_tmp[1], 1, end_time, end_time]
                F.extend([entry0, entry1])
        g = pd.DataFrame(F, columns=['trip_id', 'stop_id', 'stop_sequence',
          'arrival_time', 'departure_time'])
        g[['arrival_time', 'departure_time']] =\
          g[['arrival_time', 'departure_time']].applymap(
          lambda x: seconds_to_timestr(x))
        self.stop_times = g

    def create_all(self):
        self.create_agency()
        self.create_calendar()
        self.create_routes()
        self.create_shapes()
        self.create_stops()
        self.create_trips()
        self.create_stop_times()

    def export(self, zip_path=None):
        """
        Assuming all the necessary data frames have been created
        (as in create_all()), export them to CSV files and zip to the given
        path.
        If ``zip_path is None``, then write to ``self.home_path + 'gtfs.zip'``.
        """
        names = ['agency', 'calendar', 'routes', 'stops', 'trips',
          'stop_times']
        for name in names:
            assert hasattr(self, name),\
              "You must create {!s}".format(name)
        
        # Write files to a temporary directory 
        tmp_dir = os.path.join(self.home_path, 'hello-tmp-dir')
        if not os.path.exists(tmp_dir):
            os.mkdir(tmp_dir)
        for name in names:
            path = os.path.join(tmp_dir, name + '.txt')
            getattr(self, name).to_csv(path, index=False)

        # Zip files 
        if zip_path is None:
            zip_path = os.path.join(self.home_path, 'gtfs')
        shutil.make_archive(zip_path, format="zip", root_dir=tmp_dir)    

        # Delete temporary directory
        shutil.rmtree(tmp_dir)