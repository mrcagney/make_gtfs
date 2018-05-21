import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath('..'))

import make_gtfs
import pytest

DATA_DIR = Path('data')
