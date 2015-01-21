import json
import os
import shutil

import pandas as pd
import numpy as np
from shapely.ops import transform
from shapely.geometry import shape, mapping
import utm

# Program description
DESC = """
  This is a Python 3.4 command line program that makes a GTFS Feed
  from a few CSV files of route information ('service_windows.csv', 'routes.csv', 'meta.csv') and a GeoJSON file of route shapes ('shapes.geojson').
  """

# Character to separate different chunks within an ID
SEP = '#'

def timestr_to_seconds(x, inverse=False, mod24=False):
    """
    Given a time string of the form '%H:%M:%S', return the number of seconds
    past midnight that it represents.
    In keeping with GTFS standards, the hours entry may be greater than 23.
    If ``mod24 == True``, then return the number of seconds modulo ``24*3600``.
    If ``inverse == True``, then do the inverse operation.
    In this case, if ``mod24 == True`` also, then first take the number of 
    seconds modulo ``24*3600``.
    """
    if not inverse:
        try:
            hours, mins, seconds = x.split(':')
            result = int(hours)*3600 + int(mins)*60 + int(seconds)
            if mod24:
                result %= 24*3600
        except:
            result = None
    else:
        try:
            seconds = int(x)
            if mod24:
                seconds %= 24*3600
            hours, remainder = divmod(seconds, 3600)
            mins, secs = divmod(remainder, 60)
            result = '{:02d}:{:02d}:{:02d}'.format(hours, mins, secs)
        except:
            result = None
    return result

def get_duration(timestr1, timestr2, units='s'):
    """
    Return the duration of the time period between the first and second 
    time string in the given units.
    Allowable units are 's' (seconds), 'min' (minutes), 'h' (hours).    
    Assume ``timestr1 < timestr2``.
    """
    valid_units = ['s', 'min', 'h']
    assert units in valid_units,\
      "Units must be one of {!s}".format(valid_units)

    duration = timestr_to_seconds(timestr2) - timestr_to_seconds(timestr1)

    if units == 's':
        return duration
    elif units == 'min':
        return duration/60
    else:
        return duration/3600

def get_stop_ids(route_id):
    return [SEP.join(['stp', route_id, str(i)]) for i in range(2)]

def get_stop_names(route_short_name):
    return ['Route {!s} stop {!s}'.format(route_short_name, i)
      for i in range(2)]

def parse_args():
    """
    Parse command line options and return an object with two attributes:
    `input_dir`, a list of one input directory path, and `output_file`, 
    a list of one output file path.
    """
    import argparse
    import textwrap

    parser = argparse.ArgumentParser(
      formatter_class=argparse.RawDescriptionHelpFormatter, 
      description=textwrap.dedent(DESC))
    parser.add_argument('input_dir', nargs='?', type=str, default='.',
      help='path to a directory containing the input files '\
      '(default: current directory)')
    parser.add_argument('-o', dest='output_dir', 
      help="path to the output directory (default: input_dir)")
    parser.add_argument('-z', dest='as_zip', action='store_true', 
      default=False,
      help='Write the output as a zip file instead of a collection of text files (default: False')
    return parser.parse_args()

def main():
    """
    Get command line arguments, create feed, and export feed.
    """
    # Read command line arguments
    args = parse_args()

    # Create and export feed
    feed = Feed(args.input_dir)
    feed.create_all()
    feed.export(args.output_dir, as_zip=args.as_zip)


class Feed(object):
    """
    A class to gather all the GTFS files for a feed and store them in memory 
    as Pandas data frames.  
    Make sure you have enough memory!  
    The stop times object can be big.
    """
    def __init__(self, input_dir):
        """
        Import the data files located in the given directory path,
        and assign them to attributes of a new Feed object.
        """
        self.input_dir = input_dir

        # Import files
        service_windows = pd.read_csv(
          os.path.join(input_dir, 'service_windows.csv'))
        proto_routes = pd.read_csv(
          os.path.join(input_dir, 'routes.csv'), 
          dtype={'route_short_name': str, 'service_window_id': str, 
          'shape_id': str})
        meta = pd.read_csv(
          os.path.join(input_dir, 'meta.csv'),
          dtype={'start_date': str, 'end_date': str})
        proto_shapes = json.load(open(
          os.path.join(input_dir, 'shapes.geojson'), 'r'))        

        # Clean up raw routes
        cols = proto_routes.columns
        if 'route_desc' not in cols:
            proto_routes['route_desc'] = np.nan

        # Fill missing route types with 3 (bus)
        proto_routes['route_type'].fillna(3, inplace=True)
        proto_routes['route_type'] = proto_routes['route_type'].astype(int)
        
        # Create route speeds and fill in missing values with default speeds
        if 'speed' not in cols:
            proto_routes['speed'] = np.nan
        proto_routes['speed'].fillna(meta['default_route_speed'].iat[0], 
          inplace=True)
        
        # Save
        self.proto_routes = proto_routes
        self.service_windows = service_windows
        self.meta = meta
        self.proto_shapes = proto_shapes

    def create_agency(self):
        """
        Create a Pandas data frame representing ``agency.txt`` and save it to
        ``self.agency``.
        """
        self.agency = pd.DataFrame({
          'agency_name': self.meta['agency_name'].iat[0], 
          'agency_url': self.meta['agency_url'].iat[0],
          'agency_timezone': self.meta['agency_timezone'].iat[0],
          }, index=[0])

    def create_calendar(self):
        """
        Create a Pandas data frame representing ``calendar.txt`` and save it to
        ``self.calendar``.
        Create the service IDs from the distinct weekly activities of the 
        service windows.
        Also save the dictionary service window ID -> service ID to
        ``self.service_by_service_window``.
        """
        windows = self.service_windows
        # Create a service ID for each distinct days_active field and map the
        # service windows to those service IDs
        def get_sid(bitlist):
            return 'srv' + ''.join([str(b) for b in bitlist])

        weekdays = ['monday', 'tuesday', 'wednesday', 'thursday','friday',
          'saturday', 'sunday']
        bitlists = set()

        # Create a dictionary service window ID -> service ID
        d = dict()
        for index, window in windows.iterrows():
            bitlist = window[weekdays].tolist()
            d[window['service_window_id']] = get_sid(bitlist)
            bitlists.add(tuple(bitlist))
        self.service_by_service_window = d

        # Create calendar
        start_date =  self.meta['start_date'].iat[0]
        end_date = self.meta['end_date'].iat[0]
        F = []
        for bitlist in bitlists: 
            F.append([get_sid(bitlist)] + list(bitlist) +\
              [start_date, end_date])
        self.calendar = pd.DataFrame(F, columns=
          ['service_id'] + weekdays + ['start_date', 'end_date'])

    def create_routes(self):
        """
        Create a Pandas data frame representing ``routes.txt`` and save it
        to ``self.routes``.
        Also create a dictionary with structure route ID -> shape ID and
        save it to ``self.shape_by_route``.
        """
        f = self.proto_routes[['route_short_name', 'route_desc', 
          'route_type', 'shape_id']].drop_duplicates().copy()

        # Create route IDs
        f['route_id'] = ['r' + str(i) for i in range(f.shape[0])]
        
        # Save
        self.shape_by_route = dict(f[['route_id', 'shape_id']].values)
        del f['shape_id']
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

        Will create ``self.routes`` if it does not already exist.

        The route IDs of routes without shapes (routes in ``routes.csv`` but 
        not in ``shapes.geojson``) will not appear in the resulting dictionary.
        """
        if not hasattr(self, 'routes'):
            self.create_routes()

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
            
        linestring_by_shape = {f['properties']['shape_id']: 
          transform(proj, shape(f['geometry'])) 
          for f in self.proto_shapes['features']}
        shape_by_route = self.shape_by_route
        return {route: linestring_by_shape[shape_by_route[route]] 
          for route in self.routes['route_id'].values}

    def create_shapes(self):
        """
        Create a Pandas data frame representing ``shapes.txt`` and save it 
        to ``self.shapes``.
        Each route has one shape that is used for both directions of travel. 
        
        Will create ``self.routes`` if it does not already exist.
        """
        if not hasattr(self, 'routes'):
            self.create_routes()

        F = []
        linestring_by_route = self.get_linestring_by_route(use_utm=False)
        shape_by_route = self.shape_by_route
        for index, row in self.routes.iterrows():
            route = row['route_id']
            if route not in linestring_by_route:
                continue
            linestring = linestring_by_route[route]
            shape = shape_by_route[route]
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

        Will create ``self.routes`` if it does not already exist.
        """
        if not hasattr(self, 'routes'):
            self.create_routes()

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

    def create_trips(self):
        """
        Create a Pandas data frame representing ``trips.txt`` and save it to
        ``self.trips``.
        Trip IDs encode direction, service window, and trip number within that
        direction and service window to make it easy to compute stop times.

        Will create ``self.calendar``, ``self.routes``, and ``self.shapes`` 
        if they don't already exist.
        """
        if not hasattr(self, 'calendar'):
            self.create_calendar()
        if not hasattr(self, 'routes'):
            self.create_routes()
        if not hasattr(self, 'shapes'):
            self.create_shapes()

        # Create trip IDs and directions
        F = []
        shape_by_route = self.shape_by_route
        for index, row in pd.merge(self.proto_routes, self.routes).iterrows():
            route = row['route_id']
            shape = shape_by_route[route]
            for sw in self.service_windows:
                swname = sw['name']
                headway = row[swname + '_headway']
                service = self.service_by_service_window[swname]
                for subwindow in sw['subwindows']:
                    start = subwindow[0]
                    duration = get_duration(*subwindow, units='s') 
                    try:
                        num_trips_per_direction = int(duration/(headway*60))
                    except ValueError:
                        num_trips_per_direction = 0
                    for direction in range(2):
                        for i in range(num_trips_per_direction):
                            F.append([
                              route, 
                              SEP.join(['t', route, swname, start, 
                              str(direction), str(i)]), 
                              direction,
                              shape,
                              service,
                              ])
        f = pd.DataFrame(F, columns=['route_id', 'trip_id', 'direction_id', 
          'shape_id', 'service_id'])

        # Save
        self.trips = f

    def create_stop_times(self):
        """
        Create a Pandas data frame representing ``stop_times.txt`` and save it
        to ``self.stop_times``.

        Will create ``self.stops`` and ``self.trips`` if they don't already 
        exist.
        """
        if not hasattr(self, 'stops'):
            self.create_stops()
        if not hasattr(self, 'trips'):
            self.create_trips()

        F = []
        linestring_by_route = self.get_linestring_by_route(use_utm=True)
        # Store arrival and departure times as seconds past midnight and
        # convert to strings at the end
        f = pd.merge(self.proto_routes, 
          self.routes[['route_id', 'route_short_name']])
        for route, group in pd.merge(f, self.trips).groupby(
          'route_id'):
            if route not in linestring_by_route:
                continue
            length = linestring_by_route[route].length/1000  # kilometers
            speed = group['speed'].iat[0]  # kph
            duration = int((length/speed)*3600)  # seconds
            sids_tmp = get_stop_ids(route)
            sids_by_direction = {0: sids_tmp, 1: sids_tmp[::-1]}
            for index, row in group.iterrows():
                trip = row['trip_id']
                junk, route, swname, base_timestr, direction, i =\
                  trip.split(SEP)
                direction = int(direction)
                i = int(i)
                sids = sids_by_direction[direction]
                base_time = timestr_to_seconds(base_timestr)
                headway = row[swname + '_headway']
                start_time = base_time + headway*60*i
                end_time = start_time + duration
                # Get end time from route length
                entry0 = [trip, sids[0], 0, start_time, start_time]
                entry1 = [trip, sids[1], 1, end_time, end_time]
                F.extend([entry0, entry1])
        g = pd.DataFrame(F, columns=['trip_id', 'stop_id', 'stop_sequence',
          'arrival_time', 'departure_time'])
        g[['arrival_time', 'departure_time']] =\
          g[['arrival_time', 'departure_time']].applymap(
          lambda x: timestr_to_seconds(x, inverse=True))
        self.stop_times = g

    def create_all(self):
        """
        Create all Pandas data frames necessary for a GTFS feed.
        """
        self.create_agency()
        self.create_calendar()
        self.create_routes()
        self.create_shapes()
        self.create_stops()
        self.create_trips()
        self.create_stop_times()

    def export(self, output_dir=None, as_zip=False):
        """
        Assuming all the necessary data frames have been created
        (as in create_all()), export them to CSV files to the given output
        directory.
        If ``as_zip`` is True, then instead write the files to a 
        zip archive called ``gtfs.zip`` in the given output directory.
        If ``output_dir is None``, then write to ``self.input_dir``.
        """
        names = ['agency', 'calendar', 'routes', 'stops', 'shapes', 'trips',
          'stop_times']
        for name in names:
            assert hasattr(self, name),\
              "You must create {!s}".format(name)
        
        # Write files 
        if output_dir is None:
            output_dir = self.input_dir
        if not os.path.exists(output_dir):
            os.mkdir(output_dir)
        for name in names:
            path = os.path.join(output_dir, name + '.txt')
            getattr(self, name).to_csv(path, index=False)

        # If requested, zip files and then delete files 
        if as_zip:
            # Create a temporary directory and move CSV files there
            tmp_dir = os.path.join(output_dir, 'hello-tmp-dir')
            if not os.path.exists(tmp_dir):
                os.mkdir(tmp_dir)
            for name in names:
                old_path = os.path.join(output_dir, name + '.txt')
                new_path = os.path.join(tmp_dir, name + '.txt')
                shutil.move(old_path, new_path)
            
            # Create zip archive
            zip_path = os.path.join(output_dir, 'gtfs')
            shutil.make_archive(zip_path, format="zip", root_dir=tmp_dir)    

            # Delete temporary directory
            shutil.rmtree(tmp_dir)


if __name__ == '__main__':
    main()