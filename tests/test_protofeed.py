import pandas as pd

from .context import make_gtfs, DATA_DIR
from make_gtfs import *


pfeed = read_protofeed(DATA_DIR / "auckland")


def test_copy():
    pfeed1 = pfeed
    pfeed2 = pfeed1.copy()

    # Check attributes
    for key in pfeed1.__dataclass_fields__:
        val = getattr(pfeed2, key)
        expect_val = getattr(pfeed1, key)
        if isinstance(val, (pd.DataFrame, gpd.GeoDataFrame)):
            assert val.equals(expect_val)
        else:
            assert val == expect_val


def test_route_types():
    rt = pfeed.route_types()
    assert isinstance(rt, list)
    assert set(rt) == {2, 3}


def test_read_protofeed():
    pfeed = read_protofeed(DATA_DIR / "auckland")
    assert isinstance(pfeed, ProtoFeed)

    pfeed = read_protofeed(DATA_DIR / "auckland_light")
    assert isinstance(pfeed, ProtoFeed)


def test_pfeed():
    pfeed0 = read_protofeed(DATA_DIR / "auckland")

    # Test init without stops or speed_zones
    pfeed = ProtoFeed(
        meta=pfeed0.meta,
        service_windows=pfeed0.service_windows,
        shapes=pfeed0.shapes,
        frequencies=pfeed0.frequencies,
    )
    assert validate(pfeed)
    # Resulting speed zones should contain one zone per unique route type
    assert pfeed.speed_zones.shape[0] == pfeed.frequencies.route_type.nunique()
    # Speed zone geometries should all be the same
    assert pfeed.speed_zones.geometry.duplicated(keep=False).all()
    # Speed zone speeds should all be infinite
    assert np.equal(pfeed.speed_zones.speed, np.inf).all()

    # Test init without speed_zones
    pfeed = ProtoFeed(
        meta=pfeed0.meta,
        service_windows=pfeed0.service_windows,
        shapes=pfeed0.shapes,
        frequencies=pfeed0.frequencies,
        stops=pfeed0.stops,
    )
    assert validate(pfeed)

    # Test init without stops
    pfeed = ProtoFeed(
        meta=pfeed0.meta,
        service_windows=pfeed0.service_windows,
        shapes=pfeed0.shapes,
        frequencies=pfeed0.frequencies,
        speed_zones=pfeed0.speed_zones,
    )
    assert validate(pfeed)
