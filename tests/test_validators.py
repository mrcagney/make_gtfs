import geopandas as gpd

from .context import make_gtfs, DATA_DIR
from make_gtfs import *


# Load test ProtoFeed
sample = read_protofeed(DATA_DIR/'auckland')

def test_check_frequencies():
    assert not check_frequencies(sample)

    pfeed = sample.copy()
    pfeed.frequencies = None
    assert check_frequencies(pfeed)

    pfeed = sample.copy()
    del pfeed.frequencies['route_short_name']
    assert check_frequencies(pfeed)

    pfeed = sample.copy()
    pfeed.frequencies['b'] = 3
    assert check_frequencies(pfeed, include_warnings=True)

    pfeed = sample.copy()
    pfeed.frequencies['route_long_name'] = ''
    assert check_frequencies(pfeed)

    pfeed = sample.copy()
    pfeed.frequencies['service_window_id'] = 'Hubba hubba'
    assert check_frequencies(pfeed)

    for col in ['direction', 'frequency', 'speed']:
        pfeed = sample.copy()
        pfeed.frequencies[col] = 'bingo'
        assert check_frequencies(pfeed)

def test_check_meta():
    assert not check_meta(sample)

    pfeed = sample.copy()
    pfeed.meta = None
    assert check_meta(pfeed)

    pfeed = sample.copy()
    del pfeed.meta['agency_name']
    assert check_meta(pfeed)

    pfeed = sample.copy()
    pfeed.meta['b'] = 3
    assert check_meta(pfeed, include_warnings=True)

    pfeed = sample.copy()
    pfeed.meta = pd.concat([pfeed.meta, pfeed.meta.iloc[:1]])
    assert check_meta(pfeed)

    pfeed = sample.copy()
    pfeed.meta['agency_name'] = ''
    assert check_meta(pfeed)

    for col in ['agency_timezone', 'agency_url', 'start_date', 'end_date',
      'default_route_speed']:
        pfeed = sample.copy()
        pfeed.meta[col] = 'bingo'
        assert check_meta(pfeed)

def test_check_service_windows():
    assert not check_service_windows(sample)

    pfeed = sample.copy()
    pfeed.service_windows = None
    assert check_service_windows(pfeed)

    pfeed = sample.copy()
    del pfeed.service_windows['service_window_id']
    assert check_service_windows(pfeed)

    pfeed = sample.copy()
    pfeed.service_windows['b'] = 3
    assert check_service_windows(pfeed, include_warnings=True)

    pfeed = sample.copy()
    pfeed.service_windows = pd.concat(
        [pfeed.service_windows, pfeed.service_windows.iloc[:1]]
    )
    assert check_service_windows(pfeed)

    for col in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday',
      'saturday', 'sunday', 'start_time', 'end_time']:
        pfeed = sample.copy()
        pfeed.service_windows[col].iat[0] = '5'
        assert check_service_windows(pfeed)

def test_check_shapes():
    assert not check_shapes(sample)

    # Make a nonempty shapes table to check
    pfeed = sample.copy()
    rows = [
        ['1100015', sg.LineString([[0, 0], [1, 1]])],
        ['1100015', sg.LineString([[0, 0], [1, 1]])],
    ]
    columns = ['shape_id', 'geometry']
    pfeed.shapes = gpd.GeoDataFrame(rows, columns=columns)
    assert not check_shapes(pfeed)

    pfeed = sample.copy()
    del pfeed.shapes['shape_id']
    assert check_shapes(pfeed)

    pfeed = sample.copy()
    pfeed.shapes['yo'] = 3
    assert not check_shapes(pfeed)
    assert check_shapes(pfeed, include_warnings=True)

    pfeed = sample.copy()
    pfeed.shapes['shape_id'].iat[0] = ''
    assert check_shapes(pfeed)

def test_check_stops():
    assert not check_stops(sample)

    pfeed = sample.copy()
    pfeed.stops = None
    assert not check_stops(pfeed)

    # Don't need to test much else, because GTFSTK does the work here
    pfeed = sample.copy()
    pfeed.stops.stop_id.iat[0] = ''
    assert check_stops(pfeed)

def test_validate():
    assert not validate(sample, as_df=False, include_warnings=False)
