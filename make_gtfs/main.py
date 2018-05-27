import pandas as pd
import numpy as np
import shapely.ops as so
import shapely.geometry as sg
import gtfstk as gt

from . import constants as cs


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

def build_stop_ids(shape_id):
    """
    Create a pair of stop IDs based on the given shape ID.
    """
    return [cs.SEP.join(['stp', shape_id, str(i)]) for i in range(2)]

def build_stop_names(shape_id):
    """
    Create a pair of stop names based on the given shape ID.
    """
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
    f = pfeed.frequencies[['route_short_name', 'route_long_name',
      'route_type', 'shape_id']].drop_duplicates().copy()

    # Create route IDs
    f['route_id'] = 'r' + f['route_short_name'].map(str)

    del f['shape_id']

    return f

def build_shapes(pfeed):
    """
    Given a ProtoFeed, return DataFrame representing ``shapes.txt``.
    Only use shape IDs that occur in both ``pfeed.shapes`` and
    ``pfeed.frequencies``.
    Create reversed shapes where routes traverse shapes in both
    directions.
    """
    rows = []
    for shape, geom in pfeed.shapes[['shape_id',
      'geometry']].itertuples(index=False):
        if shape not in pfeed.shapes_extra:
            continue
        if pfeed.shapes_extra[shape] == 2:
            # Add shape and its reverse
            shid = shape + '-1'
            new_rows = [[shid, i, lon, lat]
              for i, (lon, lat) in enumerate(geom.coords)]
            rows.extend(new_rows)
            shid = shape + '-0'
            new_rows = [[shid, i, lon, lat]
              for i, (lon, lat) in enumerate(reversed(geom.coords))]
            rows.extend(new_rows)
        else:
            # Add shape
            shid = '{}{}{}'.format(shape, cs.SEP, pfeed.shapes_extra[shape])
            new_rows = [[shid, i, lon, lat]
              for i, (lon, lat) in enumerate(geom.coords)]
            rows.extend(new_rows)

    return pd.DataFrame(rows, columns=['shape_id', 'shape_pt_sequence',
      'shape_pt_lon', 'shape_pt_lat'])

def build_stops(pfeed, shapes=None):
    """
    Given a ProtoFeed, return a DataFrame representing ``stops.txt``.
    If ``pfeed.stops`` is not ``None``, then return that.
    Otherwise, require built shapes output by :func:`build_shapes`,
    create one stop at the beginning (the first point) of each shape
    and one at the end (the last point) of each shape,
    and drop stops with duplicate coordinates.
    Note that this will yield one stop for shapes that are loops.
    """
    if pfeed.stops is not None:
        stops = pfeed.stops.copy()
    else:
        if shapes is None:
            raise ValueError('Must input shapes built by build_shapes()')

        geo_shapes = gt.geometrize_shapes(shapes)
        rows = []
        for shape, geom in geo_shapes[['shape_id',
          'geometry']].itertuples(index=False):
            stop_ids = build_stop_ids(shape)
            stop_names = build_stop_names(shape)
            for i in range(2):
                stop_id = stop_ids[i]
                stop_name = stop_names[i]
                stop_lon, stop_lat = geom.interpolate(i,
                  normalized=True).coords[0]
                rows.append([stop_id, stop_name, stop_lon, stop_lat])

        stops = (
            pd.DataFrame(rows, columns=['stop_id', 'stop_name',
              'stop_lon', 'stop_lat'])
            .drop_duplicates(subset=['stop_lon', 'stop_lat'])
        )

    return stops

def build_trips(pfeed, routes, service_by_window):
    """
    Given a ProtoFeed and its corresponding routes (DataFrame),
    service-by-window (dictionary), return a DataFrame representing
    ``trips.txt``.
    Trip IDs encode route, direction, and service window information
    to make it easy to compute stop times later.
    """
    # Put together the route and service data
    routes = pd.merge(routes[['route_id', 'route_short_name']],
      pfeed.frequencies)
    routes = pd.merge(routes, pfeed.service_windows)

    # For each row in routes, add trips at the specified frequency in
    # the specified direction
    rows = []
    for index, row in routes.iterrows():
        shape = row['shape_id']
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
            # Warning: this shape-ID-making logic needs to match that
            # in ``build_shapes``
            shid = '{}{}{}'.format(shape, cs.SEP, direction)
            rows.extend([[
              route,
              cs.SEP.join(['t', route, window, start,
              str(direction), str(i)]),
              direction,
              shid,
              service
            ] for i in range(num_trips_per_direction)])

    return pd.DataFrame(rows, columns=['route_id', 'trip_id', 'direction_id',
      'shape_id', 'service_id'])

def buffer_side(linestring, side, buffer):
    """
    Given a Shapely LineString, a side of the LineString
    (string; 'left' = left hand side of LineString,
    'right' = right hand side of LineString, or
    'both' = both sides), and a buffer size in the distance units of
    the LineString, buffer the LineString on the given side by
    the buffer size and return the resulting Shapely polygon.
    """
    b = linestring.buffer(buffer, cap_style=2)
    if side in ['left', 'right'] and buffer > 0:
        # Make a tiny buffer to split the normal-size buffer
        # in half across the linestring
        eps = min(buffer/2, 0.001)
        b0 = linestring.buffer(eps, cap_style=3)
        diff = b.difference(b0)
        polys = so.polygonize(diff)
        # Buffer sides slightly to include original linestring
        if side == 'left':
            b = list(polys)[0].buffer(1.1*eps)
        else:
            b = list(polys)[-1].buffer(1.1*eps)

    return b

def get_nearby_stops(geo_stops, linestring, side, buffer=cs.BUFFER):
    """
    Given a GeoDataFrame of stops, a Shapely LineString in the
    same coordinate system, a side of the LineString
    (string; 'left' = left hand side of LineString,
    'right' = right hand side of LineString, or
    'both' = both sides), and a buffer in the distance units of that
    coordinate system, do the following.
    Return a GeoDataFrame of all the stops that lie within
    ``buffer`` distance units to the ``side`` of the LineString.
    """
    b = buffer_side(linestring, side, buffer)

    # Collect stops
    return geo_stops.loc[geo_stops.intersects(b)].copy()

def build_stop_times(pfeed, routes, shapes, stops, trips, buffer=cs.BUFFER):
    """
    Given a ProtoFeed and its corresponding routes (DataFrame),
    shapes (DataFrame), stops (DataFrame), trips (DataFrame),
    return DataFrame representing ``stop_times.txt``.
    Includes the optional ``shape_dist_traveled`` column.
    Don't make stop times for trips with no nearby stops.
    """
    # Get the table of trips and add frequency and service window details
    routes = (
        routes
        .filter(['route_id', 'route_short_name'])
        .merge(pfeed.frequencies.drop(['shape_id'], axis=1))
    )
    trips = (
        trips
        .assign(service_window_id=lambda x: x.trip_id.map(
          lambda y: y.split(cs.SEP)[2]))
        .merge(routes)
    )

    # Get the geometries of ``shapes`` and not ``pfeed.shapes``
    geometry_by_shape = dict(
        gt.geometrize_shapes(shapes, use_utm=True)
        .filter(['shape_id', 'geometry'])
        .values
    )

    # Save on distance computations by memoizing
    dist_by_stop_by_shape = {shape: {} for shape in geometry_by_shape}

    def compute_stops_dists_times(geo_stops, linestring, shape,
      start_time, end_time):
        """
        Given a GeoDataFrame of stops on one side of a given Shapely
        LineString with given shape ID, compute distances and departure
        times of a trip traversing the LineString from start to end
        at the given start and end times (in seconds past midnight)
        and stopping at the stops encountered along the way.
        Do not assume that the stops are ordered by trip encounter.
        Return three lists of the same length: the stop IDs in order
        that the trip encounters them, the shape distances traveled
        along distances at the stops, and the times the stops are
        encountered, respectively.
        """
        g = geo_stops.copy()
        dists_and_stops = []
        for i, stop in enumerate(g['stop_id'].values):
            if stop in dist_by_stop_by_shape[shape]:
                d = dist_by_stop_by_shape[shape][stop]
            else:
                d = gt.get_segment_length(linestring,
                  g.geometry.iat[i])/1000  # km
                dist_by_stop_by_shape[shape][stop] = d
            dists_and_stops.append((d, stop))
        dists, stops = zip(*sorted(dists_and_stops))
        D = linestring.length/1000
        dists_are_reasonable = all([d < D + 100 for d in dists])
        if not dists_are_reasonable:
            # Assume equal distances between stops :-(
            n = len(stops)
            delta = D/(n - 1)
            dists = [i*delta for i in range(n)]

        # Compute times using distances, start and end stop times,
        # and linear interpolation
        t0, t1 = start_time, end_time
        d0, d1 = dists[0], dists[-1]
        # Interpolate
        times = np.interp(dists, [d0, d1], [t0, t1])
        return stops, dists, times

    # Iterate through trips and set stop times based on stop ID
    # and service window frequency.
    # Remember that every trip has a valid shape ID.
    # Gather stops geographically from ``stops``.
    rows = []
    geo_stops = gt.geometrize_stops(stops, use_utm=True)
    # Look on the side of the traffic side of street for this timezone
    side = cs.traffic_by_timezone[pfeed.meta.agency_timezone.iat[0]]
    for index, row in trips.iterrows():
        shape = row['shape_id']
        geom = geometry_by_shape[shape]
        stops = get_nearby_stops(geo_stops, geom, side, buffer=buffer)
        # Don't make stop times for trips without nearby stops
        if stops.empty:
            continue
        length = geom.length/1000  # km
        speed = row['speed']  # km/h
        duration = int((length/speed)*3600)  # seconds
        frequency = row['frequency']
        if not frequency:
            # No stop times for this trip/frequency combo
            continue
        headway = 3600/frequency  # seconds
        trip = row['trip_id']
        __, route, window, base_timestr, direction, i = (
          trip.split(cs.SEP))
        direction = int(direction)
        base_time = gt.timestr_to_seconds(base_timestr)
        start_time = base_time + headway*int(i)
        end_time = start_time + duration
        stops, dists, times = compute_stops_dists_times(stops, geom, shape,
          start_time, end_time)
        new_rows = [[trip, stop, j, time, time, dist]
          for j, (stop, time, dist) in enumerate(zip(stops, times, dists))]
        rows.extend(new_rows)

    g = pd.DataFrame(rows, columns=['trip_id', 'stop_id', 'stop_sequence',
      'arrival_time', 'departure_time', 'shape_dist_traveled'])

    # Convert seconds back to time strings
    g[['arrival_time', 'departure_time']] =\
      g[['arrival_time', 'departure_time']].applymap(
      lambda x: gt.timestr_to_seconds(x, inverse=True))

    return g

def build_feed(pfeed, buffer=cs.BUFFER):
    # Create Feed tables
    agency = build_agency(pfeed)
    calendar, service_by_window = build_calendar_etc(pfeed)
    routes = build_routes(pfeed)
    shapes = build_shapes(pfeed)
    stops = build_stops(pfeed, shapes)
    trips = build_trips(pfeed, routes, service_by_window)
    stop_times = build_stop_times(pfeed, routes, shapes, stops, trips,
      buffer=buffer)

    # Be tidy and remove unused stops
    stops = stops[stops.stop_id.isin(stop_times.stop_id)].copy()

    # Create Feed
    return gt.Feed(agency=agency, calendar=calendar, routes=routes,
      shapes=shapes, stops=stops, stop_times=stop_times, trips=trips,
      dist_units='km')