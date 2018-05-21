import click
import gtfstk as gt

import make_gtfs.main as m


@click.command(short_help="Create a GTFS feed from simpler files")
@click.argument('source_path', type=click.Path())
@click.argument('target_path', type=click.Path())
@click.option('-d', '--ndigits', default=6, type=int,
  help="Number of decimal places to round to in output")
def make_gtfs(source_path, target_path, ndigits):
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
    Round all decimals to ndigits decimal places (defaults to 6).
    All distances will be in kilometers.
    """
    feed = m.build_feed(source_path)
    gt.write_gtfs(feed, target_path, ndigits=ndigits)
