import json
import os
import shutil
from pathlib import Path

import pandas as pd
import numpy as np
from shapely.ops import transform
from shapely.geometry import shape as sh_shape
import utm
import gtfstk as gt


# Character to separate different chunks within an ID
SEP = '-'


class ProtoFeed(object):
    """
    An ProtoFeed instance simply holds the source data
    from which to build a GTFS feed.

    Attributes are

    - ``service_windows``: DataFrame
    - ``frequencies``: DataFrame; has speeds filled in
    - ``meta``: DataFrame
    - ``shapes``: dictionary

    These are built from the required source files located at the
    given directory path (string or Path object):

    - ``service_windows.csv``
        This is a CSV file containing service window information.
        A *service window* is a time interval and a set of days of the
        week during which all routes have constant service frequency,
        e.g. Saturday and Sunday 07:00 to 09:00.
        The CSV file contains the columns

        - ``service_window_id`` (required): String. A unique identifier
          for a service window
        - ``start_time``, ``end_time`` (required): Strings. The start
          and end times of the service window in HH:MM:SS format where
          the hour is less than 24
        - ``monday``, ``tuesday``, ``wednesday``, ``thursday``,
          ``friday``, ``saturday``, ``sunday`` (required): Integer 0
          or 1. Indicates whether the service is active on the given day
          (1) or not (0)

    - ``frequencies.csv``
        This is a CSV file containing route frequency information.
        The CSV file contains the columns

        - ``route_short_name`` (required): String. A unique short name
           for the route, e.g. '51X'
        - ``route_desc`` (optional): String. A description of the route
        - ``route_type`` (required): Integer. The
          `GTFS type of the route <https://developers.google.com/transit/gtfs/reference/#routestxt>`_
        - ``service_window_id`` (required): String. A service window ID
          for the route taken from the file ``service_windows.csv``
        - ``direction`` (required): Integer 0, 1, or 2. Indicates
          whether the route travels in GTFS direction 0, GTFS direction
          1, or in both directions.
          In the latter case, trips will be created that travel in both
          directions along the route's path, each direction operating at
          the given frequency.  Otherwise, trips will be created that
          travel in only the given direction.
        - ``frequency`` (required): Integer. The frequency of the route
          during the service window in vehicles per hour.
        - ``speed`` (optional): Float. The speed of the route in
          kilometers per hour
        - ``shape_id`` (required): String. Shape ID in
          ``shapes.geojson`` that corresponds to the linestring of the
          (route, direction, service window) tuple.
          In particular different directions and service windows for the
          same route could have different shapes.

    - ``meta.csv``
        This is a CSV file containing network metadata.
        The CSV file contains the columns

        - ``agency_name`` (required): String. The name of the transport
          agency
        - ``agency_url`` (required): String. A fully qualified URL for
          the transport agency
        - ``agency_timezone`` (required): String. Timezone where the
           transit agency is located. Timezone names never contain the
           space character but may contain an underscore. Refer to
           `http://en.wikipedia.org/wiki/List_of_tz_zones <http://en.wikipedia.org/wiki/List_of_tz_zones>`_ for a list of valid values
        - ``start_date``, ``end_date`` (required): Strings. The start
          and end dates for which all this network information is valid
          formated as YYYYMMDD strings
        - ``default_route_speed`` (required): Float. Default speed in
          kilometers per hour to assign to routes with no ``speed``
          entry in the file ``routes.csv``

    - ``shapes.geojson``
        This is a GeoJSON file containing route shapes.
        The file consists of one feature collection of LineString
        features, where each feature's properties contains at least the
        attribute ``shape_id``, which links the route's shape to the
        route's information in ``routes.csv``.

    """

    def __init__(self, path):
        # Read source files
        self.path = Path(path)
        self.service_windows = pd.read_csv(
          self.path/'service_windows.csv')
        self.meta = pd.read_csv(self.path/'meta.csv',
          dtype={'start_date': str, 'end_date': str})
        with (self.path/'shapes.geojson').open() as src:
            self.proto_shapes = json.load(src)

        # Read and clean frequencies
        frequencies = pd.read_csv(self.path/'frequencies.csv',
          dtype={'route_short_name': str, 'service_window_id': str,
          'shape_id': str, 'direction': int, 'frequency': int})
        cols = frequencies.columns
        if 'route_desc' not in cols:
            frequencies['route_desc'] = np.nan

        # Fill missing route types with 3 (bus)
        frequencies['route_type'].fillna(3, inplace=True)
        frequencies['route_type'] = frequencies['route_type'].astype(int)

        # Create route speeds and fill in missing values with default speeds
        if 'speed' not in cols:
            frequencies['speed'] = np.nan
        frequencies['speed'].fillna(self.meta['default_route_speed'].iat[0],
          inplace=True)
        self.frequencies = frequencies


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

    duration = (
        gt.timestr_to_seconds(timestr2) - gt.timestr_to_seconds(timestr1)
    )

    if units == 's':
        return duration
    elif units == 'min':
        return duration/60
    else:
        return duration/3600

def get_stop_ids(shape_id):
    return [SEP.join(['stp', shape_id, str(i)]) for i in range(2)]

def get_stop_names(shape_id):
    return ['Stop {!s} on shape {!s} '.format(i, shape_id)
      for i in range(2)]

def build_agency(pfeed):
    """
    Given a ProtoFeed, return a DataFrame representing ``agency.txt``
    """
    return pd.DataFrame({
      'agency_name': pfeed.meta['agency_name'].iat[0],
      'agency_url': pfeed.meta['agency_url'].iat[0],
      'agency_timezone': pfeed.meta['agency_timezone'].iat[0],
    }, index=[0])

def build_calendar_etc(pfeed):
    """
    Given a ProtoFeed, return a DataFrame representing ``calendar.txt``
    and a dictionary of the form <service window ID> -> <service ID>,
    respectively.
    """
    windows = pfeed.service_windows.copy()

    # Create a service ID for each distinct days_active field and map the
    # service windows to those service IDs
    def get_sid(bitlist):
        return 'srv' + ''.join([str(b) for b in bitlist])

    weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday',
      'saturday', 'sunday']
    bitlists = set()

    # Create a dictionary <service window ID> -> <service ID>
    d = dict()
    for index, window in windows.iterrows():
        bitlist = window[weekdays].tolist()
        d[window['service_window_id']] = get_sid(bitlist)
        bitlists.add(tuple(bitlist))
    service_by_window = d

    # Create calendar
    start_date = pfeed.meta['start_date'].iat[0]
    end_date = pfeed.meta['end_date'].iat[0]
    F = []
    for bitlist in bitlists:
        F.append([get_sid(bitlist)] + list(bitlist) +
          [start_date, end_date])
    calendar = pd.DataFrame(F, columns=(
      ['service_id'] + weekdays + ['start_date', 'end_date']))

    return calendar, service_by_window

def build_routes(pfeed):
    """
    Given a ProtoFeed, return a DataFrame representing ``routes.txt``.
    """
    f = pfeed.frequencies[['route_short_name', 'route_desc',
      'route_type', 'shape_id']].drop_duplicates().copy()

    # Create route IDs
    f['route_id'] = 'r' + f['route_short_name'].map(str)

    del f['shape_id']

    return f

def build_linestring_by_shape(pfeed, *, use_utm=False):
    """
    Given a ProtoFeed, return a dictionary of the form
    <shape ID> -> <Shapely linestring of shape>.
    Only include shape IDs that occur in both ``pfeed.frequencies``
    and ``pfeed.proto_shapes``.

    If ``use_utm``, then return each linestring in in UTM coordinates.
    Otherwise, return each linestring in WGS84 longitude-latitude
    coordinates.
    """
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

    return {f['properties']['shape_id']:
      transform(proj, sh_shape(f['geometry']))
      for f in pfeed.proto_shapes['features']}

def build_shapes(pfeed):
    """
    Given a ProtoFeed, return DataFrame representing ``shapes.txt``.
    Only include shape IDs that occur in both ``pfeed.frequencies``
    and ``pfeed.proto_shapes``.
    """
    F = []
    linestring_by_shape = build_linestring_by_shape(pfeed)
    for shape, linestring in linestring_by_shape.items():
        rows = [[shape, i, lon, lat]
          for i, (lon, lat) in enumerate(linestring.coords)]
        F.extend(rows)

    return pd.DataFrame(F, columns=['shape_id', 'shape_pt_sequence',
      'shape_pt_lon', 'shape_pt_lat'])

def build_stops(pfeed):
    """
    Given a ProtoFeed, return a DataFrame representing ``stops.txt``.
    Create one stop at the beginning (the first point) of each shape
    and one at the end (the last point) of each shape.

    Only create stops for shape IDs that are listed in both
    ``frequencies.csv`` and ``shapes.geojson``.
    """
    linestring_by_shape = build_linestring_by_shape(pfeed)
    F = []
    for shape, linestring in linestring_by_shape.items():
        stop_ids = get_stop_ids(shape)
        stop_names = get_stop_names(shape)
        for i in range(2):
            stop_id = stop_ids[i]
            stop_name = stop_names[i]
            stop_lon, stop_lat = linestring.interpolate(i,
              normalized=True).coords[0]
            F.append([stop_id, stop_name, stop_lon, stop_lat])

    return pd.DataFrame(F, columns=['stop_id', 'stop_name',
      'stop_lon', 'stop_lat'])

def build_trips(pfeed, routes, service_by_window, shapes):
    """
    Given a ProtoFeed and its corresponding routes (DataFrame),
    service-by-window (dictionary), and shapes (DataFrame),
    return a DataFrame representing ``trips.txt``.
    Trip IDs encode route, direction, and service window information
    to make it easy to compute stop times later.

    Will create ``calendar``, ``routes``, and ``shapes``
    if they don't already exist.

    Will not create trips for routes with null linestrings.
    """
    # Put together the route and service data
    routes = pd.merge(routes[['route_id', 'route_short_name']],
      pfeed.frequencies)
    routes = pd.merge(routes, pfeed.service_windows)

    # For each row in routes, add trips at the specified frequency in
    # the specified direction
    F = []
    shapes = set(shapes['shape_id'].unique())
    for index, row in routes.iterrows():
        shape = row['shape_id']
        # Don't create trips for shapes that don't exist
        if shape not in shapes:
            continue
        route = row['route_id']
        window = row['service_window_id']
        start, end = row[['start_time', 'end_time']].values
        duration = get_duration(start, end, 'h')
        frequency = row['frequency']
        if not frequency:
            # No trips during this service window
            continue
        # Rounding down occurs here if the duration isn't integral
        # (bad input)
        num_trips_per_direction = int(frequency*duration)
        service = service_by_window[window]
        direction = row['direction']
        if direction == 2:
            directions = [0, 1]
        else:
            directions = [direction]
        for direction in directions:
            F.extend([[
              route,
              SEP.join(['t', route, window, start,
              str(direction), str(i)]),
              direction,
              shape,
              service
            ] for i in range(num_trips_per_direction)])

    return pd.DataFrame(F, columns=['route_id', 'trip_id', 'direction_id',
      'shape_id', 'service_id'])

def build_stop_times(pfeed, routes, shapes, stops, trips):
    """
    Given a ProtoFeed and its corresponding routes (DataFrame),
    shapes (DataFrame), stops (DataFrame), trips (DataFrame),
    return DataFrame representing ``stop_times.txt``.
    """
    # Get the table of trips and add frequency and service window details
    routes = pd.merge(routes[['route_id', 'route_short_name']],
      pfeed.frequencies)
    trips = trips.copy()
    trips['service_window_id'] = trips['trip_id'].map(
      lambda x: x.split(SEP)[2])
    trips = pd.merge(routes, trips)

    linestring_by_shape = build_linestring_by_shape(pfeed, use_utm=True)

    # Iterate through trips and set stop times based on stop ID
    # and service window frequency.
    # Remember that every trip has a valid shape ID.
    F = []
    for index, row in trips.iterrows():
        shape = row['shape_id']
        length = linestring_by_shape[shape].length/1000  # kilometers
        speed = row['speed']  # kph
        duration = int((length/speed)*3600)  # seconds
        frequency = row['frequency']
        if not frequency:
            # No stop times for this trip/frequency combo
            continue
        headway = 3600/frequency  # seconds
        trip = row['trip_id']
        junk, route, window, base_timestr, direction, i =\
          trip.split(SEP)
        direction = int(direction)
        stops = get_stop_ids(shape)
        if direction == 1:
            stops.reverse()
        base_time = gt.timestr_to_seconds(base_timestr)
        start_time = base_time + headway*int(i)
        end_time = start_time + duration
        # Get end time from route length
        entry0 = [trip, stops[0], 0, start_time, start_time]
        entry1 = [trip, stops[1], 1, end_time, end_time]
        F.extend([entry0, entry1])

    g = pd.DataFrame(F, columns=['trip_id', 'stop_id', 'stop_sequence',
      'arrival_time', 'departure_time'])

    # Convert seconds back to time strings
    g[['arrival_time', 'departure_time']] =\
      g[['arrival_time', 'departure_time']].applymap(
      lambda x: gt.timestr_to_seconds(x, inverse=True))

    return g

def build_feed(path):
    """
    Given a path (string or Path object) to a directory of source files
    from which to build a ProtoFeed, build and return the corresponding
    GTFSTK Feed.
    Distance units are kilometers.
    """
    # Create ProtoFeed
    pfeed = ProtoFeed(path)

    # Create Feed tables
    agency = build_agency(pfeed)
    calendar, service_by_window = build_calendar_etc(pfeed)
    routes = build_routes(pfeed)
    shapes = build_shapes(pfeed)
    stops = build_stops(pfeed)
    trips = build_trips(pfeed, routes, service_by_window, shapes)
    stop_times = build_stop_times(pfeed, routes, shapes, stops, trips)

    # Create Feed
    return gt.Feed(agency=agency, calendar=calendar, routes=routes,
      shapes=shapes, stops=stops, stop_times=stop_times, trips=trips,
      dist_units='km')
