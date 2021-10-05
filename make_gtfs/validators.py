"""
Validators for ProtoFeeds.
Designed along the lines of gtfs_kit.validators.py.
"""
import numbers

import pandas as pd
import shapely.geometry as sg
import gtfs_kit as gk

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
    req_columns = r.loc[(r["table"] == table) & r["column_required"], "column"].values
    for col in req_columns:
        if col not in df.columns:
            problems.append(["error", "Missing column {!s}".format(col), table, []])

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
    valid_columns = r.loc[r["table"] == table, "column"].values
    for col in df.columns:
        if col not in valid_columns:
            problems.append(
                ["warning", "Unrecognized column {!s}".format(col), table, []]
            )

    return problems


def check_frequencies(pfeed, *, as_df=False, include_warnings=False):
    """
    Check that ``pfeed.frequency`` follows the ProtoFeed spec.
    Return a list of problems of the form described in
    :func:`gk.check_table`;
    the list will be empty if no problems are found.
    """
    table = "frequencies"
    problems = []

    # Preliminary checks
    if pfeed.frequencies is None:
        problems.append(["error", "Missing table", table, []])
    else:
        f = pfeed.frequencies.copy()
        problems = check_for_required_columns(problems, table, f)
    if problems:
        return gk.format_problems(problems, as_df=as_df)

    if include_warnings:
        problems = check_for_invalid_columns(problems, table, f)

    # Check route_short_name and route_long_name
    for column in ["route_short_name", "route_long_name"]:
        problems = gk.check_column(
            problems, table, f, column, gk.valid_str, column_required=False
        )

    cond = ~(f["route_short_name"].notnull() | f["route_long_name"].notnull())
    problems = gk.check_table(
        problems, table, f, cond, "route_short_name and route_long_name both empty"
    )

    # Check route_type
    v = lambda x: x in range(8)
    problems = gk.check_column(problems, table, f, "route_type", v)

    # Check service window ID
    problems = gk.check_column_linked_id(
        problems, table, f, "service_window_id", pfeed.service_windows
    )

    # Check direction
    v = lambda x: x in range(3)
    problems = gk.check_column(problems, table, f, "direction", v)

    # Check frequency
    v = lambda x: isinstance(x, int)
    problems = gk.check_column(problems, table, f, "frequency", v)

    # Check speed
    problems = gk.check_column(
        problems, table, f, "speed", valid_speed, column_required=False
    )

    # Check shape ID
    problems = gk.check_column_linked_id(problems, table, f, "shape_id", pfeed.shapes)

    return gk.format_problems(problems, as_df=as_df)


def check_meta(pfeed, *, as_df=False, include_warnings=False):
    """
    Analog of :func:`check_frequencies` for ``pfeed.meta``
    """
    table = "meta"
    problems = []

    # Preliminary checks
    if pfeed.meta is None:
        problems.append(["error", "Missing table", table, []])
    else:
        f = pfeed.meta.copy()
        problems = check_for_required_columns(problems, table, f)
    if problems:
        return gk.format_problems(problems, as_df=as_df)

    if include_warnings:
        problems = check_for_invalid_columns(problems, table, f)

    if f.shape[0] > 1:
        problems.append(
            ["error", "Meta must have only one row", table, list(range(1, f.shape[0]))]
        )

    # Check agency_name
    problems = gk.check_column(problems, table, f, "agency_name", gk.valid_str)

    # Check agency_url
    problems = gk.check_column(problems, table, f, "agency_url", gk.valid_url)

    # Check agency_timezone
    problems = gk.check_column(problems, table, f, "agency_timezone", gk.valid_timezone)

    # Check start_date and end_date
    for col in ["start_date", "end_date"]:
        problems = gk.check_column(problems, table, f, col, gk.valid_date)

    # Check default_route_speed
    problems = gk.check_column(problems, table, f, "default_route_speed", valid_speed)

    return gk.format_problems(problems, as_df=as_df)


def check_service_windows(pfeed, *, as_df=False, include_warnings=False):
    """
    Analog of :func:`check_frequencies` for ``pfeed.service_windows``
    """
    table = "service_windows"
    problems = []

    # Preliminary checks
    if pfeed.service_windows is None:
        problems.append(["error", "Missing table", table, []])
    else:
        f = pfeed.service_windows.copy()
        problems = check_for_required_columns(problems, table, f)
    if problems:
        return gk.format_problems(problems, as_df=as_df)

    if include_warnings:
        problems = check_for_invalid_columns(problems, table, f)

    # Check service window ID
    problems = gk.check_column_id(problems, table, f, "service_window_id")

    # Check start_time and end_time
    for column in ["start_time", "end_time"]:
        problems = gk.check_column(problems, table, f, column, gk.valid_time)

    # Check weekday columns
    v = lambda x: x in range(2)
    for col in [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]:
        #
        problems = gk.check_column(problems, table, f, col, v)

    return gk.format_problems(problems, as_df=as_df)


def check_shapes(pfeed, *, as_df=False, include_warnings=False):
    """
    Analog of :func:`check_frequencies` for ``pfeed.shapes``
    """
    table = "shapes"
    problems = []

    # Preliminary checks
    if pfeed.shapes is None:
        return problems

    f = pfeed.shapes.copy()
    problems = check_for_required_columns(problems, table, f)
    if problems:
        return gk.format_problems(problems, as_df=as_df)

    if include_warnings:
        problems = check_for_invalid_columns(problems, table, f)

    # Check shape_id
    problems = gk.check_column(problems, table, f, "shape_id", gk.valid_str)

    # Check geometry
    v = lambda x: isinstance(x, sg.LineString) and not x.is_empty
    problems = gk.check_column(problems, table, f, "geometry", v)

    return gk.format_problems(problems, as_df=as_df)


def check_stops(pfeed, *, as_df=False, include_warnings=False):
    """
    Analog of :func:`check_frequencies` for ``pfeed.stops``
    """
    # Use GTFS Kit's stop validator
    if pfeed.stops is not None:
        stop_times = pd.DataFrame(columns=["stop_id"])
        feed = gk.Feed(stops=pfeed.stops, stop_times=stop_times, dist_units="km")
        return gk.check_stops(feed, as_df=as_df, include_warnings=False)


def validate(pfeed, *, as_df=True, include_warnings=True):
    """
    Check whether the given pfeed satisfies the ProtoFeed spec.

    Parameters
    ----------
    pfeed : ProtoFeed
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

        - ``'type'``: 'error' or 'warning'; 'error' means the ProtoFeed
          spec is violated; 'warning' means there is a problem but it's
          not a ProtoFeed spec violation
        - ``'message'``: description of the problem
        - ``'table'``: table in which problem occurs, e.g. 'routes'
        - ``'rows'``: rows of the table's DataFrame where problem occurs

        Return early if the pfeed is missing required tables or required
        columns.

    """
    problems = []

    # Check for invalid columns and check the required tables
    checkers = [
        "check_frequencies",
        "check_meta",
        "check_service_windows",
        "check_shapes",
        "check_stops",
    ]
    for checker in checkers:
        problems.extend(globals()[checker](pfeed, include_warnings=include_warnings))

    return gk.format_problems(problems, as_df=as_df)
