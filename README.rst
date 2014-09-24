Make GTFS
==========
This is a Python 3.4 command line program that makes a GTFS feed
from a GeoJSON file of route shapes, a CSV file of route headways, and a configuration file.
It's inspired by Conveyal's `geom2gtfs <https://github.com/conveyal/geom2gtfs>`_.

Experimental. 
Needs more testing.
Use at your own risk.

Installation
-------------

Usage
-------
``python make_gtfs.py [-h] [-o OUTPUT_FILE] [input_dir]``

The input directory must contain the following three files

- ``routes.csv``: A CSV file with a header column containing...
- ``shapes.geojson``: A GeoJSON file containing one feature collection with...
- ``config.json``: A JSON file containing...


Examples
---------

Documentation
--------------
