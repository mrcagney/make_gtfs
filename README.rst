Make GTFS
***********
This is a Python 3.4 command line program that makes a GTFS feed
from a few simple CSV files of route information and a GeoJSON file of route shapes.
It's inspired by Conveyal's `geom2gtfs <https://github.com/conveyal/geom2gtfs>`_.

Experimental. 
Needs more testing.
Use at your own risk.


Installation
=============
``pip install make_gtfs``


Usage
=====
``python make_gtfs.py [-h] [-o OUTPUT_FILE] [input_dir]``

The input directory must contain the following three files

- ``service_windows.csv``
- ``frequencies.csv``
- ``meta.csv``
- ``shapes.geojson``


service_windows.csv
--------------------
This is a CSV file containing service window information.
A *service window* is a time interval and a set of days of the week during which all routes have constant service frequency, e.g. Saturday and Sunday 07:00 to 09:00.
The CSV file contains the columns

- ``service_window_id`` (required): String. A unique identifier for a service window
- ``start_time``, ``end_time`` (required): Strings. The start and end times of the service window in HH:MM:SS format where the hour is less than 24
- ``monday``, ``tuesday``, ``wednesday``, ``thursday`` ``friday``, ``saturday``, ``sunday`` (required): Integer 0 or 1. Indicates whether the service is active on the given day (1) or not (0) 


frequencies.csv
-----------
This is a CSV file containing route frequency information.
The CSV file contains the columns

- ``route_short_name`` (required): String. A unique short name for the route, e.g. '51X'
- ``route_desc`` (optional): String. A description of the route
- ``route_type`` (required): Integer. The `GTFS type of the route <https://developers.google.com/transit/gtfs/reference#routes_fields>`_
- ``service_window_id`` (required): String. A service window ID for the route taken from the file ``service_windows.csv`` 
- ``direction`` (required): Integer 0, 1, or 2. Indicates whether the route travels in GTFS direction 0, GTFS direction 1, or in both directions.
In the latter case, trips will be created that travel in both directions along the route's path, each direction operating at the given frequency.  Otherwise, trips will be created that travel in only the given direction.
- ``frequency`` (required): Integer. The frequency of the route during the service window in vehicles per hour. 
- ``speed`` (optional): Float. The speed of the route in kilometers per hour
- ``shape_id`` (required): String. Shape ID in ``shapes.geojson`` that corresponds to the linestring of the (route, direction, service window) tuple. In particular different directions and service windows for the same route could have different shapes.


shapes.geojson
---------------
This is a GeoJSON file containing route shapes.
The file consists of one feature collection of LineString features, where each feature's properties contains at least the attribute ``shape_id``, which links the route's shape to the route's information in ``routes.csv``.

meta.csv
------------
This is a CSV file containing network metadata.
The CSV file contains the columns

- ``agency_name`` (required): String. The name of the transport agency
- ``agency_url`` (required): String. A fully qualified URL for the transport agency
- ``agency_timezone`` (required): String. Timezone where the transit agency is located. Timezone names never contain the space character but may contain an underscore. Refer to `http://en.wikipedia.org/wiki/List_of_tz_zones <http://en.wikipedia.org/wiki/List_of_tz_zones>`_ for a list of valid values
- ``start_date``, ``end_date`` (required): Strings. The start and end dates for which all this network information is valid formated as YYYYMMDD strings
- ``default_route_speed`` (required): Float. Default speed in kilometers per hour to assign to routes with no ``speed`` entry in the file ``routes.csv``


Algorithm
=========
Basically, 

- ``routes.txt`` is created from ``routes.csv``
- ``shapes.txt`` is created from ``shapes.geojson``
- ``agency.txt`` is created from ``meta.csv``
- ``calendar.txt`` is created in a dumb way with exactly one all-week service that applies to all trips
- ``stops.txt`` is created by making a pair of stops for each shape which lie on the shape's endpoints.  This will lead to duplicate stops in case shapes share endpoints.
- ``trips.txt`` and ``stop_times.txt`` are created by taking each route, service window, and direction, and running a set of trips starting on the hour and operating at the route's speed and frequency specified for that service window.  If the route direction is 2, then two sets of trips in opposing directions will be created, each operating at the route's frequency. 


Examples
=========
See ``data/auckland`` for example files.
You can also play with ``examples/examples.ipynb`` in an iPython notebook or view the notebook as HTML `here <https://rawgit.com/araichev/make_gtfs/master/examples/examples.html>`_.


Documentation
===============
Under ``docs/`` or view it as HTML `here <https://rawgit.com/araichev/make_gtfs/master/docs/_build/html/index.html>`_.

