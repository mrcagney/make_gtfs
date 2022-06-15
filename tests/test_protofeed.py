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

def test_read_protofeed():
    pfeed = read_protofeed(DATA_DIR / "auckland")
    assert isinstance(pfeed, ProtoFeed)
