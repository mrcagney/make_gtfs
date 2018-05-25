import pandas as pd
import gtfstk as gt

from .context import make_gtfs, DATA_DIR
from make_gtfs import *


# Load test ProtoFeed
pfeed = read_protofeed(DATA_DIR/'auckland')

def test_get_duration():
    ts1 = '01:01:01'
    ts2 = '01:05:01'
    get = get_duration(ts1, ts2, units='min')
    expect = 4
    assert get == expect

def test_build_routes():
    routes = build_routes(pfeed)

    # Should be a data frame
    assert isinstance(routes, pd.DataFrame)

    # Should have correct shape
    expect_nrows = pfeed.frequencies.drop_duplicates(
      'route_short_name').shape[0]
    expect_ncols = 4
    assert routes.shape == (expect_nrows, expect_ncols)

def test_build_shapes():
    shapes = build_shapes(pfeed)

    # Should be a data frame
    assert isinstance(shapes, pd.DataFrame)

    # Should have correct shape
    count = 0
    for direction in pfeed.shapes_extra.values():
        if direction == 0:
            count += 1
        else:
            count += direction
    expect_nshapes = count
    expect_ncols = 4
    assert shapes.groupby('shape_id').ngroups == expect_nshapes
    assert shapes.shape[1] == expect_ncols

def test_build_stops():
    # Test with null ``pfeed.stops``
    pfeed_stopless = pfeed.copy()
    pfeed_stopless.stops = None
    shapes = build_shapes(pfeed_stopless)
    stops = build_stops(pfeed_stopless, shapes)

    # Should be a data frame
    assert isinstance(stops, pd.DataFrame)

    # Should have correct shape
    nshapes = shapes.shape_id.nunique()
    assert stops.shape[0] <= 2*nshapes
    assert stops.shape[1] == 4

    # Test with non-null ``pfeed.stops``
    stops = build_stops(pfeed)

    # Should be a data frame
    assert isinstance(stops, pd.DataFrame)

    # Should have correct shape
    assert stops.shape == pfeed.stops.shape

def test_build_trips():
    routes = build_routes(pfeed)
    __, service_by_window = build_calendar_etc(pfeed)
    shapes = build_shapes(pfeed)
    trips = build_trips(pfeed, routes, service_by_window)

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
    # Test stopless version first
    pfeed_stopless = pfeed.copy()
    pfeed_stopless.stops = None
    routes = build_routes(pfeed_stopless)
    shapes = build_shapes(pfeed_stopless)
    __, service_by_window = build_calendar_etc(pfeed_stopless)
    stops = build_stops(pfeed_stopless, shapes)
    trips = build_trips(pfeed_stopless, routes, service_by_window)
    stop_times = build_stop_times(pfeed_stopless, routes, shapes, stops, trips)

    # Should be a data frame
    assert isinstance(stop_times, pd.DataFrame)

    # Should have correct shape.
    # Number of stop times is at most twice the number of trips,
    # because each trip has at most two stops
    assert stop_times.shape[0] <= 2*trips.shape[0]
    assert stop_times.shape[1] == 6

    # Test with stops
    routes = build_routes(pfeed)
    shapes = build_shapes(pfeed)
    stops = build_stops(pfeed)
    __, service_by_window = build_calendar_etc(pfeed)
    trips = build_trips(pfeed, routes, service_by_window)
    stop_times = build_stop_times(pfeed, routes, shapes, stops, trips)

    # Should be a data frame
    assert isinstance(stop_times, pd.DataFrame)

    # Should have correct shape.
    # Number of stop times is at least twice the number of trips,
    # because each trip has two stops
    assert stop_times.shape[0] >= 2*trips.shape[0]
    assert stop_times.shape[1] == 6

    # Test with stops and tiny buffer so that no stop times are built
    stop_times = build_stop_times(pfeed, routes, shapes, stops, trips,
      buffer=0)

    # Should be a data frame
    assert isinstance(stop_times, pd.DataFrame)

    # Should be empty
    assert stop_times.empty

def test_build_feed():
    feed = build_feed(pfeed)

    # Should be a GTFSTK Feed
    assert isinstance(feed, gt.Feed)

    # Should have correct tables
    names = ['agency', 'calendar', 'routes', 'shapes', 'stops',
      'stop_times', 'trips']
    for name in names:
        assert hasattr(feed, name)

    # Should be a valid feed
    v = feed.validate()
    assert 'error' not in v.type.values