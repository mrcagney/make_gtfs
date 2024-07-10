import os
import sys
import pathlib as pl

sys.path.insert(0, os.path.abspath(".."))

import make_gtfs
import pytest

DATA_DIR = pl.Path("data")
