import pandas as pd
import gtfs_kit as gk

from .context import make_gtfs, DATA_DIR
from make_gtfs import *


# Load test ProtoFeed
pfeed = read_protofeed(DATA_DIR / "auckland")


def test_init():
    pfeed = ProtoFeed()
    for key in PROTOFEED_ATTRS:
        assert hasattr(pfeed, key)


def test_copy():
    pfeed1 = pfeed
    pfeed2 = pfeed1.copy()

    # Check attributes
    for key in cs.PROTOFEED_ATTRS:
        val = getattr(pfeed2, key)
        expect_val = getattr(pfeed1, key)
        if isinstance(val, pd.DataFrame):
            assert val.equals(expect_val)
        else:
            assert val == expect_val


def test_read_protofeed():
    pfeed = read_protofeed(DATA_DIR / "auckland")
    assert isinstance(pfeed, ProtoFeed)
