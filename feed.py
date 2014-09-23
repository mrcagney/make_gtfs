"""
Todo
-----
- Handle case of more than endpoint stops?
"""
import datetime as dt
import dateutil.relativedelta as rd
import zipfile
import shutil
import json

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
    return ['First stop on route {!s}'.format(route_short_name),
      'Last stop on route {!s}'.format(route_short_name)]

class Feed(object):
    """
    A class to gather all the GTFS files for a feed and store them in memory 
    as Pandas data frames.  
    Make sure you have enough memory!  
    The stop times object can be big.
    """
    def __init__(self, path):
        """
        Read in all the relevant GTFS text files within the directory or 
        ZIP file given by ``path`` and assign them to instance attributes.
        Assume the zip file unzips as a collection of GTFS text files
        rather than as a directory of GTFS text files.
        Set the native distance units of this feed to the given distance
        units.
        Valid options are listed in ``VALID_DISTANCE_UNITS``.
        All distance units will then be converted to kilometers.
        """
        zipped = False
        if zipfile.is_zipfile(path):
            # Extract to temporary location
            zipped = True
            archive = zipfile.ZipFile(path)
            path = path.rstrip('.zip') + '/'
            archive.extractall(path)

        # Import files
        self.config = json.load(open(path + 'config.json', 'r'))
        self.raw_routes = pd.read_csv(path + 'routes.csv', 
          dtype={'route_short_name': str}, sep=';')
        self.raw_shapes = json.load(open(path + 'shapes.geojson', 'r'))        

        if zipped:
            # Remove extracted directory
            shutil.rmtree(path)

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
        f = self.raw_routes[['route_short_name', 'route_desc']].copy()
        cols = self.raw_routes.columns

        # Create route type and fill in missing values with default
        # types from config
        if 'route_type' in self.raw_routes.columns:
            f['route_type'] = self.raw_routes['route_type'].copy()
        else:
            f['route_type'] = np.nan
        f['route_type'].fillna(
          int(self.config['default_route_type']), inplace=True)

        # Create route speeds and fill in missing values with default speeds
        # from config
        if 'speed' in self.raw_routes.columns:
            f['speed'] = self.raw_routes['speed'].copy()
        else:
            f['speed'] = np.nan
        f['speed'].fillna(
          int(self.config['default_speed']), inplace=True)

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

    def get_service_window_duration_by_name(self):
        """
        Return a dictionary of the form
        service window name -> service window duration (minutes).
        """
        sw_by_name = self.config['service_window_by_name']
        return {name: sum(seconds_to_timestr(w[1], inverse=True) -\
          seconds_to_timestr(w[0], inverse=True) for w in window)/60
          for name, window in sw_by_name.items()}

    def add_num_trips_per_direction(self):
        """
        Add the column 'num_trips_per_direction' to ``self.raw_routes``.
        This column is the sum of the number of vehicles
        traveling in one direction on a given route
        over all service windows.
        
        Note that headway and frequency are unidirectional
        (measured in one direction only).
        So the total number of vehicles per hour on a route is
        *double* its frequency.
        """
        f = self.raw_routes.copy()
        duration_by_name = self.get_service_window_duration_by_name()
        f['num_trips_per_direction'] = 0
        for name, duration in duration_by_name.items():
            # Get num vehicles for service window
            n = (duration*60/f[name + '_headway']).fillna(0)
            f['num_trips_per_direction'] += n
        # Double the number to account for vehicles in both directions
        self.raw_routes = f 

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
        sw_by_name = self.config['service_window_by_name']
        for index, row in pd.merge(self.raw_routes, self.routes).iterrows():
            route = row['route_id']
            shape = get_shape_id(route)
            for name, sw in sw_by_name.items():
                headway = row[name + '_headway']
                for i, interval in enumerate(sw):
                    duration = get_duration(*interval)
                    num_trips_per_direction = int(duration/headway)
                    for direction in range(2):
                        for j in range(num_trips_per_direction):
                            F.append([
                              route, 
                              't-{!s}-{!s}-{!s}-{!s}-{!s}'.format(route, 
                               direction, name, i, j), 
                              direction,
                              shape,
                              ])
        f = pd.DataFrame(F, columns=['route_id', 'trip_id', 'direction_id', 
          'shape_id'])

        # Create service IDs
        f['service_id'] = self.calendar['service_id'].iat[0]

        # Save
        self.trips = f

    def create_stops(self):
        """
        Create a Pandas data frame representing ``stops.txt`` and save it to
        ``self.stops``.
        Create one stop at the beginning (the first point) of each shape 
        and one at the end (the last point) of each shape.

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

    def create_stop_times(self):
        """
        Create a Pandas data frame representing ``stop_times.txt`` and save it
        to ``self.stop_times``.

        Assume ``self.stops`` and ``self.trips`` has been created.
        """
        assert hasattr(self, 'stops') and hasattr(self, 'trips'),\
          "You must first create self.stops and self.trips"
        F = []
        sw_by_name = self.config['service_window_by_name']
        for route, group in pd.merge(self.routes, self.trips).groupby(
          'route_id'):
            sids = get_stop_ids(route)
            sids_by_direction = {0: sids, 1: sids[::-1]}
            speed = group['speed']
            for index, row in group.iterrows():
                junk, route, direction, swname, i, j =\
                  row['trip_id'].split('-')
                sids_tmp = sids_by_direction[direction]
                base_time = seconds_to_timestr(sw_by_name[swname][i],
                  inverse=True)
                headway = group[swname + '_headway']
                start_time = base_time + headway*60*j
                # Get end time from route length
                entry = []
                if direction == 0:
                    stop_times = []
        self.stop_times = None