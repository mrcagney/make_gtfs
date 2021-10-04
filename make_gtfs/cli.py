"""
The command-line-interface module.
"""
import click
import gtfs_kit as gk

from . import protofeed as pf
from . import constants as cs
from . import main as m


@click.command(short_help="Create a GTFS feed from simpler files")
@click.argument("source_path", type=click.Path())
@click.argument("target_path", type=click.Path())
@click.option(
    "-b",
    "--buffer",
    default=cs.BUFFER,
    type=float,
    show_default=True,
    help="Meters to buffer trip paths to find stops",
)
@click.option(
    "-n",
    "--ndigits",
    default=6,
    type=int,
    show_default=True,
    help="Number of decimal places to round float values in the output " "GTFS feed",
)
def make_gtfs(source_path, target_path, buffer, ndigits):
    """
    Create a GTFS feed from the files in the directory SOURCE_PATH.
    See the project README for a description of the required source
    files.
    Save the feed to the file or directory TARGET_PATH.
    If the target path ends in '.zip', then write the feed as a zip
    archive.
    Otherwise assume the path is a directory, and write the feed as a
    collection of CSV files to that directory, creating the directory
    if it does not exist.

    If a stops file is present, then search within ``buffer`` meters
    on the traffic side of trip paths for stops.
    Round all decimals to ndigits decimal places.
    All distances in the resulting GTFS feed will be in kilometers.
    """
    pfeed = pf.read_protofeed(source_path)
    feed = m.build_feed(pfeed, buffer=buffer)
    feed.write(target_path, ndigits=ndigits)
