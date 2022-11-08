import geopandas as gpd
import pandera as pa

from .context import make_gtfs, DATA_DIR, pytest
from make_gtfs import *


# Load test ProtoFeed
sample = read_protofeed(DATA_DIR / "auckland")


def test_check_meta():
    assert check_meta(sample).shape[0]

    pfeed = sample.copy()
    pfeed.meta = None
    with pytest.raises(TypeError):
        check_meta(pfeed)

    pfeed = sample.copy()
    del pfeed.meta["agency_name"]
    with pytest.raises(pa.errors.SchemaError):
        check_meta(pfeed)

    pfeed = sample.copy()
    pfeed.meta = pd.concat([pfeed.meta, pfeed.meta.iloc[:1]])
    with pytest.raises(pa.errors.SchemaError):
        check_meta(pfeed)

    for col in [
        "agency_timezone",
        "agency_url",
        "start_date",
        "end_date",
    ]:
        pfeed = sample.copy()
        pfeed.meta[col] = "bingo"
        print(col)
        with pytest.raises(pa.errors.SchemaError):
            check_meta(pfeed)


def test_check_shapes():
    assert check_shapes(sample).shape[0]

    pfeed = sample.copy()
    del pfeed.shapes["shape_id"]
    with pytest.raises(pa.errors.SchemaError):
        check_shapes(pfeed)

    pfeed = sample.copy()
    pfeed.shapes["yo"] = 3
    assert check_shapes(pfeed).shape[0]

    pfeed = sample.copy()
    pfeed.shapes.geometry.iat[0] = None
    with pytest.raises(pa.errors.SchemaError):
        check_shapes(pfeed)


def test_check_service_windows():
    assert check_service_windows(sample).shape[0]

    pfeed = sample.copy()
    pfeed.service_windows = pd.DataFrame()
    with pytest.raises(pa.errors.SchemaError):
        check_service_windows(pfeed)

    pfeed = sample.copy()
    del pfeed.service_windows["service_window_id"]
    with pytest.raises(pa.errors.SchemaError):
        check_service_windows(pfeed)

    pfeed = sample.copy()
    pfeed.service_windows = pd.concat(
        [pfeed.service_windows, pfeed.service_windows.iloc[:1]]
    )
    with pytest.raises(pa.errors.SchemaError):
        check_service_windows(pfeed)

    for col in [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "start_time",
        "end_time",
    ]:
        pfeed = sample.copy()
        pfeed.service_windows[col].iat[0] = "5"
        with pytest.raises(pa.errors.SchemaError):
            check_service_windows(pfeed)


def test_check_frequencies():
    assert check_frequencies(sample).shape[0]

    pfeed = sample.copy()
    pfeed.frequencies = pd.DataFrame()
    with pytest.raises(pa.errors.SchemaError):
        check_frequencies(pfeed)

    pfeed = sample.copy()
    del pfeed.frequencies["route_short_name"]
    with pytest.raises(pa.errors.SchemaError):
        check_frequencies(pfeed)

    pfeed = sample.copy()
    pfeed.frequencies["route_long_name"] = ""
    with pytest.raises(pa.errors.SchemaError):
        check_frequencies(pfeed)

    for col in ["direction", "frequency", "speed"]:
        pfeed = sample.copy()
        pfeed.frequencies[col] = "bingo"
        with pytest.raises(pa.errors.SchemaError):
            check_frequencies(pfeed)


def test_check_stops():
    assert check_stops(sample).shape[0]

    pfeed = sample.copy()
    pfeed.stops = None
    assert check_stops(pfeed) is None

    pfeed = sample.copy()
    pfeed.stops = pd.DataFrame()
    with pytest.raises(pa.errors.SchemaError):
        check_stops(pfeed)

    pfeed = sample.copy()
    pfeed.stops.stop_id.iat[0] = ""
    with pytest.raises(pa.errors.SchemaError):
        check_stops(pfeed)


def test_check_speed_zones():
    assert check_speed_zones(sample).shape[0]

    # Delete zone ID
    pfeed = sample.copy()
    del pfeed.speed_zones["speed_zone_id"]
    with pytest.raises(pa.errors.SchemaError):
        check_speed_zones(pfeed)

    # Set bad route type
    pfeed = sample.copy()
    pfeed.speed_zones["route_type"].iat[0] = "3"
    with pytest.raises(pa.errors.SchemaError):
        check_speed_zones(pfeed)

    # Make speed zones IDs collide within a route type
    pfeed = sample.copy()
    pfeed.speed_zones["speed_zone_id"] = "a"
    with pytest.raises(ValueError):
        check_speed_zones(pfeed)

    # Make speed zones overlap within a route type
    pfeed = sample.copy()
    pfeed.speed_zones["route_type"] = 3
    pfeed.speed_zones["speed_zone_id"] = [
        str(i) for i in range(pfeed.speed_zones.shape[0])
    ]
    with pytest.raises(ValueError):
        check_speed_zones(pfeed)


def test_crosscheck_ids():
    pfeed = sample.copy()
    pfeed.frequencies["shape_id"] = "Hubba hubba"
    with pytest.raises(ValueError):
        crosscheck_ids(
            "shape_id", pfeed.frequencies, "frequencies", pfeed.shapes, "shapes"
        )


def test_validate():
    assert isinstance(validate(sample), ProtoFeed)

    pfeed = sample.copy()
    pfeed.frequencies["service_window_id"] = "Hubba hubba"
    with pytest.raises(ValueError):
        validate(pfeed)
