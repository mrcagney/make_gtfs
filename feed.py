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
        f = self.raw_routes[['route_short_name', 'route_desc', 
          'route_type']].copy()
        # Fill in missing route types with default route type from config
        f['route_type'].fillna(
          int(self.config['default_route_type']), inplace=True)
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

    def get_shape_by_route(self):
        """
        Return a dictionary of the form route ID -> shape ID.

        Assume ``self.routes`` has been created.
        """
        assert hasattr(self, 'routes'),\
          "You must first create self.routes"

        return {route: 's-{!s}'.format(route) 
          for route in self.routes['route_id'].values}

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
        shape_by_route = self.get_shape_by_route()
        linestring_by_route = self.get_linestring_by_route(use_utm=False)
        for index, row in self.routes.iterrows():
            route = row['route_id']
            linestring = linestring_by_route[route]
            shape = shape_by_route[route]
            rows = [[shape, i, lon, lat] 
              for i, (lon, lat) in enumerate(linestring.coords)]
            F.extend(rows)
        self.shapes = pd.DataFrame(F, columns=['shape_id', 'shape_pt_sequence',
          'shape_pt_lon', 'shape_pt_lat'])

    def get_service_window_duration_by_name(self):
        """
        Return a dictionary of the form
        service window name -> service window duration (hours).
        """
        sw_by_name = self.config['service_window_by_name']
        return {name: sum(w[1] - w[0] for w in window)
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
        Assume ``self.routes`` and ``self.shapes`` have been created.
        """
        assert hasattr(self, 'routes') and hasattr(self, 'shapes'),\
          "You must first create self.routes and self.shapes"

        # Create trip IDs and directions
        self.add_num_trips_per_direction()
        F = []
        shape_by_route = self.get_shape_by_route()
        for index, row in pd.merge(self.raw_routes, self.routes).iterrows():
            route = row['route_id']
            shape = shape_by_route[route]
            ntpd = row['num_trips_per_direction']
            for i in range(int(ntpd)):
                F.append([route, 't-{!s}-{!s}-0'.format(route, i), 0, shape])
                F.append([route, 't-{!s}-{!s}-1'.format(route, i), 1, shape])
        f = pd.DataFrame(F, columns=['route_id', 'trip_id', 'direction_id', 
          'shape_id'])

        # Create service IDs
        f['service_id'] = self.calendar['service_id'].iat[0]

        # Save
        self.trips = f
