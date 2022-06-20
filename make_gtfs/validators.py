"""
ProtoFeed validation.
TODO: checked some linked ID columns
"""
import re
import pytz

import pandas as pd
import pandera as pa
import geopandas as gpd


URL_PATTERN = re.compile(
    r'^(?:http)s?://(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::\d+)?(?:/?|[/?]\S+)$',
    re.IGNORECASE|re.UNICODE
)
DATE_PATTERN = r"\d\d\d\d\d\d\d\d"
TIME_PATTERN = r"([01][0-9]|2[0-3]):([0-5][0-9]):([0-5][0-9])"
TIMEZONES = set(pytz.all_timezones)
NONBLANK_PATTERN = r"(?!\s*$).+"

# ProtoFeed schemas
SCHEMA_META = pa.DataFrameSchema(
    {
        "agency_name": pa.Column(str, pa.Check.str_matches(NONBLANK_PATTERN)),
        "agency_url": pa.Column(str, pa.Check.str_matches(URL_PATTERN)),
        "agency_timezone": pa.Column(str, pa.Check.isin(TIMEZONES)),
        "start_date": pa.Column(
            str,
            checks=[
                pa.Check.str_matches(DATE_PATTERN),
                pa.Check(lambda x:
                    pd.to_datetime(x) > pd.to_datetime("1900-01-01", yearfirst=True)
                ),
            ]
        ),
        "end_date": pa.Column(
            str,
            checks=[
                pa.Check.str_matches(DATE_PATTERN),
                pa.Check(lambda x:
                    pd.to_datetime(x) > pd.to_datetime("1900-01-01", yearfirst=True)
                ),
            ]
        ),
        "speed_route_type_0": pa.Column(float, pa.Check.gt(0), required=False),
        "speed_route_type_1": pa.Column(float, pa.Check.gt(0), required=False),
        "speed_route_type_2": pa.Column(float, pa.Check.gt(0), required=False),
        "speed_route_type_3": pa.Column(float, pa.Check.gt(0), required=False),
        "speed_route_type_4": pa.Column(float, pa.Check.gt(0), required=False),
        "speed_route_type_5": pa.Column(float, pa.Check.gt(0), required=False),
        "speed_route_type_6": pa.Column(float, pa.Check.gt(0), required=False),
        "speed_route_type_7": pa.Column(float, pa.Check.gt(0), required=False),
        "speed_route_type_11": pa.Column(float, pa.Check.gt(0), required=False),
        "speed_route_type_12": pa.Column(float, pa.Check.gt(0), required=False),
    },
    checks=pa.Check(lambda x: x.shape[0] == 1),  # Should have exactly 1 row
    index=pa.Index(int),
    strict="filter",  # Drop columns not specified above
    coerce=True,
)
SCHEMA_SHAPES = pa.DataFrameSchema(
    {
        "shape_id": pa.Column(
            str,
            pa.Check.str_matches(NONBLANK_PATTERN),
            unique=True,
        ),
        "geometry": pa.Column(
            checks=[
                pa.Check(lambda x: x.geom_type == "LineString"),
                pa.Check(lambda x: x.is_valid),
                pa.Check(lambda x: x.length > 0),
            ]
        ),
    },
    checks=pa.Check(lambda x: x.shape[0] >= 1),  # Should have at least 1 row
    index=pa.Index(int),
    strict="filter",  # Drop columns not specified above
    coerce=True,
)
SCHEMA_SERVICE_WINDOWS = pa.DataFrameSchema(
    {
        "service_window_id": pa.Column(
            str,
            pa.Check.str_matches(NONBLANK_PATTERN),
            unique=True,
        ),
        "start_time": pa.Column(str, pa.Check.str_matches(TIME_PATTERN)),
        "end_time": pa.Column(str, pa.Check.str_matches(TIME_PATTERN)),
        "monday": pa.Column(int, pa.Check.isin(range(2))),
        "tuesday": pa.Column(int, pa.Check.isin(range(2))),
        "wednesday": pa.Column(int, pa.Check.isin(range(2))),
        "thursday": pa.Column(int, pa.Check.isin(range(2))),
        "friday": pa.Column(int, pa.Check.isin(range(2))),
        "saturday": pa.Column(int, pa.Check.isin(range(2))),
        "sunday": pa.Column(int, pa.Check.isin(range(2))),
    },
    checks=pa.Check(lambda x: x.shape[0] >= 1),  # Should have at least 1 row
    index=pa.Index(int),
    strict="filter",  # Drop columns not specified above
    coerce=True,
)
SCHEMA_FREQUENCIES = pa.DataFrameSchema(
    {
        "route_short_name": pa.Column(str, pa.Check.str_matches(NONBLANK_PATTERN)),
        "route_long_name": pa.Column(str, pa.Check.str_matches(NONBLANK_PATTERN)),
        "route_type": pa.Column(int, pa.Check.isin(list(range(8)) + [11, 12])),
        "service_window_id": pa.Column(str, pa.Check.str_matches(NONBLANK_PATTERN)),
        "shape_id": pa.Column(str, pa.Check.str_matches(NONBLANK_PATTERN)),
        "direction": pa.Column(int, pa.Check.isin(range(3))),
        "frequency": pa.Column(int, pa.Check.gt(0)),
        "speed": pa.Column(float, pa.Check.gt(0), required=False),
    },
    checks=pa.Check(lambda x: x.shape[0] >= 1),  # Should have at least 1 row
    index=pa.Index(int),
    strict="filter",  # Drop columns not specified above
    coerce=True,
)
SCHEMA_STOPS = pa.DataFrameSchema(
    {
        "stop_id": pa.Column(str, pa.Check.str_matches(NONBLANK_PATTERN), unique=True),
        "stop_code": pa.Column(str, nullable=True, required=False),
        "stop_name": pa.Column(str, pa.Check.str_matches(NONBLANK_PATTERN)),
        "stop_desc": pa.Column(str, nullable=True, required=False),
        "stop_lat": pa.Column(float),
        "stop_lon": pa.Column(float),
        "zone_id": pa.Column(str, nullable=True, required=False),
        "stop_url": pa.Column(str, pa.Check.str_matches(URL_PATTERN), nullable=True, required=False),
        "location_type": pa.Column(int, pa.Check.isin(range(5)), nullable=True, required=False),
        "parent_station": pa.Column(str, nullable=True, required=False),
        "stop_timezone": pa.Column(str, pa.Check.isin(TIMEZONES), nullable=True, required=False),
        "wheelchair_boarding": pa.Column(int, pa.Check.isin(range(3)), nullable=True, required=False),
    },
    checks=pa.Check(lambda x: x.shape[0] >= 1),  # Should have at least 1 row
    index=pa.Index(int),
    strict="filter",  # Drop columns not specified above
    coerce=True,
)

def check_meta(pfeed):
    """
    """
    return SCHEMA_META.validate(pfeed.meta)

def check_shapes(pfeed):
    """
    """
    if not isinstance(pfeed.shapes, gpd.GeoDataFrame):
        raise ValueError("Shapes must be a GeoDataFrame")

    return SCHEMA_SHAPES.validate(pfeed.shapes)

def check_service_windows(pfeed):
    """
    """
    return SCHEMA_SERVICE_WINDOWS.validate(pfeed.service_windows)


def check_frequencies(pfeed):
    """
    """
    return SCHEMA_FREQUENCIES.validate(pfeed.frequencies)

    # Check service window ID
    # problems = gk.check_column_linked_id(
    #     problems, table, f, "service_window_id", pfeed.service_windows
    # )

def check_stops(pfeed):
    """
    """
    return SCHEMA_STOPS.validate(pfeed.stops)


def validate(pfeed):
    """
    Return the given ProtoFeed if it is valid.
    Otherwise, raise a ValueError or a Pandera SchemaError.
    """
    # Check for invalid columns and check the required tables
    checkers = [
        "check_meta",
        "check_service_windows",
        "check_shapes",
        "check_frequencies",
        "check_stops",
    ]
    for checker in checkers:
        globals()[checker](pfeed)

    # TODO: checked some linked ID columns

    return pfeed
