import shutil

import click.testing
from click.testing import CliRunner

from .context import make_gtfs, DATA_DIR
from make_gtfs import *
from make_gtfs.cli import *


runner = CliRunner()

def rm_paths(*paths):
    """
    Delete the given file paths/directory paths, if they exists.
    """
    for p in paths:
        p = Path(p)
        if p.exists():
            if p.is_file():
                p.unlink()
            else:
                shutil.rmtree(str(p))

def test_make_gtfs():
    s_path = DATA_DIR/'auckland'
    t_path = DATA_DIR/'auckland_gtfs.zip'
    rm_paths(t_path)

    result = runner.invoke(make_gtfs, [str(s_path), str(t_path)])
    assert result.exit_code == 0

    rm_paths(t_path)