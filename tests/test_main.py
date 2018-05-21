import zipfile
from copy import deepcopy

import pandas as pd
import gtfstk as gt
import shapely.geometry as sg

from .context import make_gtfs, DATA_DIR
from make_gtfs import *


# Load test ProtoFeed
pfeed = ProtoFeed(DATA_DIR/'auckland')

def test_get_duration():
    ts1 = '01:01:01'
    ts2 = '01:05:01'
    get = get_duration(ts1, ts2, units='min')
    expect = 4
    assert get == expect

def test_init():
    assert isinstance(pfeed.frequencies, pd.DataFrame)
    assert isinstance(pfeed.service_windows, pd.DataFrame)
    assert isinstance(pfeed.meta, pd.DataFrame)
    assert isinstance(pfeed.proto_shapes, dict)

def test_build_routes():
    routes = build_routes(pfeed)

    # Should be a data frame
    assert isinstance(routes, pd.DataFrame)

    # Should have correct shape
    expect_nrows = pfeed.frequencies.drop_duplicates(
      'route_short_name').shape[0]
    expect_ncols = 4
    assert routes.shape == (expect_nrows, expect_ncols)

def test_build_linestring_by_shape():
    linestring_by_shape = build_linestring_by_shape(pfeed)

    # Should be a dictionary
    assert isinstance(linestring_by_shape, dict)

    # The elements should be Shapely linestrings
    for x in linestring_by_shape.values():
        assert isinstance(x, sg.LineString)

    # Should contain at most one shape for each route
    nshapes = pfeed.frequencies['shape_id'].unique().shape[0]
    assert len(linestring_by_shape) <= nshapes

def test_build_shapes():
    shapes = build_shapes(pfeed)

    # Should be a data frame
    assert isinstance(shapes, pd.DataFrame)

    # Should have correct shape
    expect_nshapes = len(build_linestring_by_shape(pfeed))
    expect_ncols = 4
    assert shapes.groupby('shape_id').ngroups == expect_nshapes
    assert shapes.shape[1] == expect_ncols

def test_build_stops():
    stops = build_stops(pfeed)
    shapes = build_shapes(pfeed)

    # Should be a data frame
    assert isinstance(stops, pd.DataFrame)

    # Should have correct shape
    nshapes = shapes['shape_id'].unique().shape[0]
    expect_nrows = 2*nshapes
    expect_ncols = 4
    assert stops.shape == (expect_nrows, expect_ncols)

def test_build_trips():
    routes = build_routes(pfeed)
    __, service_by_window = build_calendar_etc(pfeed)
    shapes = build_shapes(pfeed)
    trips = build_trips(pfeed, routes, service_by_window, shapes)

    # Should be a data frame
    assert isinstance(trips, pd.DataFrame)

    # Should have correct shape
    f = pd.merge(routes[['route_id', 'route_short_name']],
      pfeed.frequencies)
    f = pd.merge(f, pfeed.service_windows)
    shapes = set(shapes['shape_id'].unique())
    expect_ntrips = 0
    for index, row in f.iterrows():
        # Get number of trips corresponding to this row
        # and add it to the total
        shape = row['shape_id']
        if shape not in shapes:
            continue
        frequency = row['frequency']
        if not frequency:
            continue
        start, end = row[['start_time', 'end_time']].values
        duration = get_duration(start, end, 'h')
        direction = row['direction']
        if direction == 0:
            trip_mult = 1
        else:
            trip_mult = direction
        expect_ntrips += int(duration*frequency)*trip_mult
    expect_ncols = 5
    assert trips.shape == (expect_ntrips, expect_ncols)

def test_build_stop_times():
    routes = build_routes(pfeed)
    shapes = build_shapes(pfeed)
    stops = build_stops(pfeed)
    __, service_by_window = build_calendar_etc(pfeed)
    trips = build_trips(pfeed, routes, service_by_window, shapes)
    stop_times = build_stop_times(pfeed, routes, shapes, stops, trips)

    # Should be a data frame
    assert isinstance(stop_times, pd.DataFrame)

    # Should have correct shape
    # Number of stop times is twice the number of trips,
    # because each trip has two stops
    expect_nrows = 2*trips.shape[0]
    expect_ncols = 5
    assert stop_times.shape == (expect_nrows, expect_ncols)

def test_build_feed():
    feed = build_feed(DATA_DIR/'auckland')

    # Should be a GTFSTK Feed
    assert isinstance(feed, gt.Feed)

    # Should have correct tables
    names = ['agency', 'calendar', 'routes', 'shapes', 'stops',
      'stop_times', 'trips']
    for name in names:
        assert hasattr(feed, name)