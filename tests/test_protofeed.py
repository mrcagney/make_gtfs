import numpy as np
import pandas as pd
import geopandas as gpd

from .context import make_gtfs, DATA_DIR
import make_gtfs as mg


pfeed = mg.read_protofeed(DATA_DIR / "auckland")


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
    pfeed = mg.read_protofeed(DATA_DIR / "auckland")
    assert isinstance(pfeed, mg.ProtoFeed)

    pfeed = mg.read_protofeed(DATA_DIR / "auckland_light")
    assert isinstance(pfeed, mg.ProtoFeed)


def test_pfeed():
    pfeed0 = mg.read_protofeed(DATA_DIR / "auckland")

    # Test init without stops or speed_zones
    pfeed = mg.ProtoFeed(
        meta=pfeed0.meta,
        service_windows=pfeed0.service_windows,
        shapes=pfeed0.shapes,
        frequencies=pfeed0.frequencies,
    )
    assert mg.validate(pfeed)
    # Resulting speed zones should contain one zone per unique route type
    assert pfeed.speed_zones.shape[0] == pfeed.frequencies.route_type.nunique()
    # Speed zone geometries should all be the same
    assert pfeed.speed_zones.geometry.duplicated(keep=False).all()
    # Speed zone speeds should all be infinite
    assert np.equal(pfeed.speed_zones.speed, np.inf).all()

    # Test init without speed_zones
    pfeed = mg.ProtoFeed(
        meta=pfeed0.meta,
        service_windows=pfeed0.service_windows,
        shapes=pfeed0.shapes,
        frequencies=pfeed0.frequencies,
        stops=pfeed0.stops,
    )
    assert mg.validate(pfeed)

    # Test init without stops
    pfeed = mg.ProtoFeed(
        meta=pfeed0.meta,
        service_windows=pfeed0.service_windows,
        shapes=pfeed0.shapes,
        frequencies=pfeed0.frequencies,
        speed_zones=pfeed0.speed_zones,
    )
    assert mg.validate(pfeed)
