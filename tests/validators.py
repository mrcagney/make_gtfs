"""
Validators for ProtoFeeds.
Designed along the lines of gtfstk.validators.py.
"""
import numbers

import gtfstk as gt

from . import constants as cs


def valid_speed(x):
    """
    Return ``True`` if ``x`` is a positive number;
    otherwise return ``False``.
    """
    if isinstance(x, numbers.Number) and x > 0:
        return True
    else:
        return False

def check_for_required_columns(problems, table, df):
    """
    Check that the given ProtoFeed table has the required columns.

    Parameters
    ----------
    problems : list
        A four-tuple containing

        1. A problem type (string) equal to ``'error'`` or ``'warning'``;
           ``'error'`` means the ProtoFeed is violated;
           ``'warning'`` means there is a problem but it is not a
           ProtoFeed violation
        2. A message (string) that describes the problem
        3. A ProtoFeed table name, e.g. ``'meta'``, in which the problem
           occurs
        4. A list of rows (integers) of the table's DataFrame where the
           problem occurs

    table : string
        Name of a ProtoFeed table
    df : DataFrame
        The ProtoFeed table corresponding to ``table``

    Returns
    -------
    list
        The ``problems`` list extended as follows.
        Check that the DataFrame contains the colums required by
        the ProtoFeed spec
        and append to the problems list one error for each column
        missing.

    """
    r = cs.PROTOFEED_REF
    req_columns = r.loc[(r['table'] == table) & r['column_required'],
      'column'].values
    for col in req_columns:
        if col not in df.columns:
            problems.append(['error', 'Missing column {!s}'.format(col),
              table, []])

    return problems

def check_for_invalid_columns(problems, table, df):
    """
    Check for invalid columns in the given ProtoFeed DataFrame.

    Parameters
    ----------
    problems : list
        A four-tuple containing

        1. A problem type (string) equal to ``'error'`` or
           ``'warning'``;
           ``'error'`` means the ProtoFeed is violated;
           ``'warning'`` means there is a problem but it is not a
           ProtoFeed violation
        2. A message (string) that describes the problem
        3. A ProtoFeed table name, e.g. ``'meta'``, in which the problem
           occurs
        4. A list of rows (integers) of the table's DataFrame where the
           problem occurs

    table : string
        Name of a ProtoFeed table
    df : DataFrame
        The ProtoFeed table corresponding to ``table``

    Returns
    -------
    list
        The ``problems`` list extended as follows.
        Check whether the DataFrame contains extra columns not in the
        ProtoFeed and append to the problems list one warning for each extra
        column.

    """
    r = cs.PROTOFEED_REF
    valid_columns = r.loc[r['table'] == table, 'column'].values
    for col in df.columns:
        if col not in valid_columns:
            problems.append(['warning',
              'Unrecognized column {!s}'.format(col),
              table, []])

    return problems

def check_frequencies(pfeed, *, as_df=False, include_warnings=False):
    """
    """
    table = 'frequencies'
    problems = []

    # Preliminary checks
    if pfeed.frequencies is None:
        problems.append(['error', 'Missing table', table, []])
    else:
        f = pfeed.frequencies.copy()
        problems = check_for_required_columns(problems, table, f)
    if problems:
        return gt.format_problems(problems, as_df=as_df)

    if include_warnings:
        problems = check_for_invalid_columns(problems, table, f)

    # Check route_short_name and route_long_name
    for column in ['route_short_name', 'route_long_name']:
        problems = gt.check_column(problems, table, f, column, gt.valid_str,
          column_required=False)

    cond = ~(f['route_short_name'].notnull() | f['route_long_name'].notnull())
    problems = gt.check_table(problems, table, f, cond,
      'route_short_name and route_long_name both empty')

    # Check route_type
    v = lambda x: x in range(8)
    problems = gt.check_column(problems, table, f, 'route_type', v)

    # Check service window ID
    problems = gt.check_column_id(problems, table, f, 'service_window_id')

    problems = check_column_linked_id(problems, table, f, 'service_window_id',
      pfeed.service_windows)

    # Check direction
    v = lambda x: x in range(2)
    problems = gt.check_column(problems, table, f, 'direction', v)

    # Check frequency
    v = lambda x: isinstance(x, int)
    problems = gt.check_column(problems, table, f, 'frequency', v)

    # Check speed
    problems = gt.check_column(problems, table, f, 'speed', valid_speed,
      column_required=False)

    # Check shape ID
    problems = gt.check_column_id(problems, table, f, 'shape_id')

    problems = check_column_linked_id(problems, table, f, 'shape_id',
      pfeed.shapes)

    return gt.format_problems(problems, as_df=as_df)

def check_meta(pfeed, *, as_df=False, include_warnings=False):
    """
    Check that ``pfeed.meta`` is valid.
    Return a list of problems of the form described in
    :func:`check_table`;
    the list will be empty if no problems are found.
    """
    table = 'meta'
    problems = []

    # Preliminary checks
    if pfeed.meta is None:
        problems.append(['error', 'Missing table', table, []])
    else:
        f = pfeed.meta.copy()
        problems = check_for_required_columns(problems, table, f)
    if problems:
        return gt.format_problems(problems, as_df=as_df)

    if include_warnings:
        problems = check_for_invalid_columns(problems, table, f)

    # Check agency_name
    problems = gt.check_column(problems, table, f, 'agency_name', gt.valid_str)

    # Check agency_url
    problems = gt.check_column(problems, table, f, 'agency_url', gt.valid_url)

    # Check agency_timezone
    problems = gt.check_column(problems, table, f, 'agency_timezone',
      gt.valid_timezone)

    # Check start_date and end_date
    for col in ['start_date', 'end_date']:
        problems = gt.check_column(problems, table, f, col, gt.valid_date)

    # Check default_route_speed
    problems = gt.check_column(problems, table, f, 'default_route_speed',
      valid_speed)

    return gt.format_problems(problems, as_df=as_df)

def check_shapes(pfeed, *, as_df=False, include_warnings=False):
    """
    Analog of :func:`check_agency` for ``pfeed.shapes``.
    """
    table = 'shapes'
    problems = []

    # Preliminary checks
    if pfeed.shapes is None:
        return problems

    f = pfeed.shapes.copy()
    problems = check_for_required_columns(problems, table, f)
    if problems:
        return gt.format_problems(problems, as_df=as_df)

    if include_warnings:
        problems = check_for_invalid_columns(problems, table, f)

    # Check shape_id
    problems = gt.check_column(problems, table, f, 'shape_id', valid_str)

    # Check shape_pt_lon and shape_pt_lat
    for column, bound in [('shape_pt_lon', 180), ('shape_pt_lat', 90)]:
        v = lambda x: pd.notnull(x) and -bound <= x <= bound
        cond = ~f[column].map(v)
        problems = check_table(problems, table, f, cond,
          '{!s} out of bounds {!s}'.format(column, [-bound, bound]))

    # Check for duplicated (shape_id, shape_pt_sequence) pairs
    cond = f[['shape_id', 'shape_pt_sequence']].duplicated()
    problems = check_table(problems, table, f, cond,
      'Repeated pair (shape_id, shape_pt_sequence)')

    # Check if shape_dist_traveled does decreases on a trip
    if 'shape_dist_traveled' in f.columns:
        g = f.dropna(subset=['shape_dist_traveled'])
        indices = []
        prev_sid = None
        prev_dist = -1
        cols = ['shape_id', 'shape_dist_traveled']
        for i, sid, dist in g[cols].itertuples():
            if sid == prev_sid and dist < prev_dist:
                indices.append(i)

            prev_sid = sid
            prev_dist = dist

        if indices:
            problems.append(['error',
              'shape_dist_traveled decreases on a trip', table, indices])

    return gt.format_problems(problems, as_df=as_df)

def check_stops(pfeed, *, as_df=False, include_warnings=False):
    """
    Analog of :func:`check_agency` for ``pfeed.stops``.
    """
    table = 'stops'
    problems = []

    # Preliminary checks
    if pfeed.stops is None:
        problems.append(['error', 'Missing table', table, []])
    else:
        f = pfeed.stops.copy()
        problems = check_for_required_columns(problems, table, f)
    if problems:
        return gt.format_problems(problems, as_df=as_df)

    if include_warnings:
        problems = check_for_invalid_columns(problems, table, f)

    # Check stop_id
    problems = gt.check_column_id(problems, table, f, 'stop_id')

    # Check stop_code, stop_desc, zone_id, parent_station
    for column in ['stop_code', 'stop_desc', 'zone_id', 'parent_station']:
        problems = gt.check_column(problems, table, f, column, valid_str,
          column_required=False)

    # Check stop_name
    problems = gt.check_column(problems, table, f, 'stop_name', valid_str)

    # Check stop_lon and stop_lat
    for column, bound in [('stop_lon', 180), ('stop_lat', 90)]:
        v = lambda x: pd.notnull(x) and -bound <= x <= bound
        cond = ~f[column].map(v)
        problems = check_table(problems, table, f, cond,
          '{!s} out of bounds {!s}'.format(column, [-bound, bound]))

    # Check stop_url
    problems = gt.check_column(problems, table, f, 'stop_url', valid_url,
      column_required=False)

    # Check location_type
    v = lambda x: x in range(2)
    problems = gt.check_column(problems, table, f, 'location_type', v,
      column_required=False)

    # Check stop_timezone
    problems = gt.check_column(problems, table, f, 'stop_timezone',
      valid_timezone, column_required=False)

    # Check wheelchair_boarding
    v = lambda x: x in range(3)
    problems = gt.check_column(problems, table, f, 'wheelchair_boarding', v,
      column_required=False)

    # Check further location_type and parent_station
    if 'parent_station' in f.columns:
        if 'location_type' not in f.columns:
            problems.append(['error',
              'parent_station column present but location_type column missing',
              table, []])
        else:
            # Stations must have location type 1
            station_ids = f.loc[f['parent_station'].notnull(),
              'parent_station']
            cond = f['stop_id'].isin(station_ids) & (f['location_type'] != 1)
            problems = check_table(problems, table, f, cond,
              'A station must have location_type 1')

            # Stations must not lie in stations
            cond = (f['location_type'] == 1) & f['parent_station'].notnull()
            problems = check_table(problems, table, f, cond,
              'A station must not lie in another station')

    if include_warnings:
        # Check for stops without trips
        s = pfeed.stop_times['stop_id']
        cond = ~pfeed.stops['stop_id'].isin(s)
        problems = check_table(problems, table, f, cond,
          'Stop has no stop times', 'warning')

    return gt.format_problems(problems, as_df=as_df)

def check_stop_times(pfeed, *, as_df=False, include_warnings=False):
    """
    Analog of :func:`check_agency` for ``pfeed.stop_times``.
    """
    table = 'stop_times'
    problems = []

    # Preliminary checks
    if pfeed.stop_times is None:
        problems.append(['error', 'Missing table', table, []])
    else:
        f = pfeed.stop_times.copy().sort_values(['trip_id', 'stop_sequence'])
        problems = check_for_required_columns(problems, table, f)
    if problems:
        return gt.format_problems(problems, as_df=as_df)

    if include_warnings:
        problems = check_for_invalid_columns(problems, table, f)

    # Check trip_id
    problems = check_column_linked_id(problems, table, f, 'trip_id',
      pfeed.trips)

    # Check arrival_time and departure_time
    v = lambda x: pd.isnull(x) or valid_time(x)
    for col in ['arrival_time', 'departure_time']:
        problems = gt.check_column(problems, table, f, col, v)

    # Check that arrival and departure times exist for the first and last
    # stop of each trip and for each timepoint.
    # For pfeeds with many trips, iterating through the stop time rows is
    # faster than uisg groupby.
    if 'timepoint' not in f.columns:
        f['timepoint'] = np.nan  # This will not mess up later timepoint check

    indices = []
    prev_tid = None
    prev_atime = 1
    prev_dtime = 1
    for i, tid, atime, dtime, tp in f[['trip_id', 'arrival_time',
      'departure_time', 'timepoint']].itertuples():
        if tid != prev_tid:
            # Check last stop of previous trip
            if pd.isnull(prev_atime) or pd.isnull(prev_dtime):
                indices.append(i - 1)
            # Check first stop of current trip
            if pd.isnull(atime) or pd.isnull(dtime):
                indices.append(i)
        elif tp == 1 and (pd.isnull(atime) or pd.isnull(dtime)):
            # Failure at timepoint
            indices.append(i)

        prev_tid = tid
        prev_atime = atime
        prev_dtime = dtime

    if indices:
        problems.append(['error',
          'First/last/time point arrival/departure time missing',
          table, indices])

    # Check stop_id
    problems = check_column_linked_id(problems, table, f, 'stop_id',
      pfeed.stops)

    # Check for duplicated (trip_id, stop_sequence) pairs
    cond = f[['trip_id', 'stop_sequence']].dropna().duplicated()
    problems = check_table(problems, table, f, cond,
      'Repeated pair (trip_id, stop_sequence)')

    # Check stop_headsign
    problems = gt.check_column(problems, table, f, 'stop_headsign',
      valid_str, column_required=False)

    # Check pickup_type and drop_off_type
    for col in ['pickup_type', 'drop_off_type']:
        v = lambda x: x in range(4)
        problems = gt.check_column(problems, table, f, col, v,
          column_required=False)

    # Check if shape_dist_traveled decreases on a trip
    if 'shape_dist_traveled' in f.columns:
        g = f.dropna(subset=['shape_dist_traveled'])
        indices = []
        prev_tid = None
        prev_dist = -1
        for i, tid, dist in g[['trip_id', 'shape_dist_traveled']].itertuples():
            if tid == prev_tid and dist < prev_dist:
                indices.append(i)

            prev_tid = tid
            prev_dist = dist

        if indices:
            problems.append(['error',
              'shape_dist_traveled decreases on a trip', table, indices])

    # Check timepoint
    v = lambda x: x in range(2)
    problems = gt.check_column(problems, table, f, 'timepoint', v,
      column_required=False)

    if include_warnings:
        # Check for duplicated (trip_id, departure_time) pairs
        cond = f[['trip_id', 'departure_time']].duplicated()
        problems = check_table(problems, table, f, cond,
          'Repeated pair (trip_id, departure_time)', 'warning')

    return gt.format_problems(problems, as_df=as_df)

def check_transfers(pfeed, *, as_df=False, include_warnings=False):
    """
    Analog of :func:`check_agency` for ``pfeed.transfers``.
    """
    table = 'transfers'
    problems = []

    # Preliminary checks
    if pfeed.transfers is None:
        return problems

    f = pfeed.transfers.copy()
    problems = check_for_required_columns(problems, table, f)
    if problems:
        return gt.format_problems(problems, as_df=as_df)

    if include_warnings:
        problems = check_for_invalid_columns(problems, table, f)

    # Check from_stop_id and to_stop_id
    for col in ['from_stop_id', 'to_stop_id']:
        problems = check_column_linked_id(problems, table, f, col,
          pfeed.stops, 'stop_id')

    # Check transfer_type
    v = lambda x: pd.isnull(x) or x in range(5)
    problems = gt.check_column(problems, table, f, 'transfer_type', v,
      column_required=False)

    # Check min_transfer_time
    v = lambda x: x >= 0
    problems = gt.check_column(problems, table, f, 'min_transfer_time', v,
      column_required=False)

    return gt.format_problems(problems, as_df=as_df)

def check_trips(pfeed, *, as_df=False, include_warnings=False):
    """
    Analog of :func:`check_agency` for ``pfeed.trips``.
    """
    table = 'trips'
    problems = []

    # Preliminary checks
    if pfeed.trips is None:
        problems.append(['error', 'Missing table', table, []])
    else:
        f = pfeed.trips.copy()
        problems = check_for_required_columns(problems, table, f)
    if problems:
        return gt.format_problems(problems, as_df=as_df)

    if include_warnings:
        problems = check_for_invalid_columns(problems, table, f)

    # Check trip_id
    problems = gt.check_column_id(problems, table, f, 'trip_id')

    # Check route_id
    problems = check_column_linked_id(problems, table, f, 'route_id',
      pfeed.routes)

    # Check service_id
    g = pd.DataFrame()
    if pfeed.calendar is not None:
        g = pd.concat([g, pfeed.calendar])
    if pfeed.calendar_dates is not None:
        g = pd.concat([g, pfeed.calendar_dates])
    problems = check_column_linked_id(problems, table, f, 'service_id', g)

    # Check direction_id
    v = lambda x: x in range(2)
    problems = gt.check_column(problems, table, f, 'direction_id', v,
      column_required=False)

    # Check block_id
    if 'block_id' in f.columns:
        v = lambda x: pd.isnull(x) or valid_str(x)
        cond = ~f['block_id'].map(v)
        problems = check_table(problems, table, f, cond, 'Blank block_id')

        g = f.dropna(subset=['block_id'])
        cond = ~g['block_id'].duplicated(keep=False)
        problems = check_table(problems, table, g, cond, 'Unrepeated block_id')

    # Check shape_id
    problems = check_column_linked_id(problems, table, f, 'shape_id',
      pfeed.shapes, column_required=False)

    # Check wheelchair_accessible and bikes_allowed
    v = lambda x: x in range(3)
    for column in ['wheelchair_accessible', 'bikes_allowed']:
        problems = gt.check_column(problems, table, f, column, v,
          column_required=False)

    # Check for trips with no stop times
    if include_warnings:
        s = pfeed.stop_times['trip_id']
        cond = ~f['trip_id'].isin(s)
        problems = check_table(problems, table, f, cond,
          'Trip has no stop times', 'warning')

    return gt.format_problems(problems, as_df=as_df)

def validate(ppfeed, *, as_df=True, include_warnings=True):
    """
    Check whether the given pfeed satisfies the ProtoFeed.

    Parameters
    ----------
    pfeed : Feed
    as_df : boolean
        If ``True``, then return the resulting report as a DataFrame;
        otherwise return the result as a list
    include_warnings : boolean
        If ``True``, then include problems of types ``'error'`` and
        ``'warning'``; otherwise, only return problems of type
        ``'error'``

    Returns
    -------
    list or DataFrame
        Run all the table-checking functions: :func:`check_agency`,
        :func:`check_calendar`, etc.
        This yields a possibly empty list of items
        [problem type, message, table, rows].
        If ``as_df``, then format the error list as a DataFrame with the
        columns

        - ``'type'``: 'error' or 'warning'; 'error' means the ProtoFeed is
          violated; 'warning' means there is a problem but it's not a
          ProtoFeed violation
        - ``'message'``: description of the problem
        - ``'table'``: table in which problem occurs, e.g. 'routes'
        - ``'rows'``: rows of the table's DataFrame where problem occurs

        Return early if the pfeed is missing required tables or required
        columns.

    Notes
    -----
    - This function interprets the ProtoFeed liberally, classifying problems
      as warnings rather than errors where the ProtoFeed is unclear.
      For example if a trip_id listed in the trips table is not listed
      in the stop times table (a trip with no stop times),
      then that's a warning and not an error.
    - Timing benchmark: on a 2.80 GHz processor machine with 16 GB of
      memory, this function checks `this 31 MB Southeast Queensland pfeed
      <http://transitpfeeds.com/p/translink/21/20170310>`_
      in 22 seconds, including warnings.

    """
    problems = []

    # Check for invalid columns and check the required tables
    checkers = [
      'check_frequencies',
      'check_meta',
      'check_service_windows',
      'check_shapes',
      'check_stops',
    ]
    for checker in checkers:
        problems.extend(globals()[checker](pfeed,
          include_warnings=include_warnings))

    return gt.gt.format_problems(problems, as_df=as_df)
