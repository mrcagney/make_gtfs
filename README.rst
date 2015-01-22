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
- ``routes.csv``
- ``meta.csv``
- ``shapes.geojson``


service_windows.csv
--------------------
This is a CSV file containing service window information.
A *service window* is a time interval and a set of days of the week during which all routes have constant service frequency, e.g. Saturday and Sunday 07:00 to 09:00.
The CSV file contains the columns

- ``service_window_id`` (required): a unique identifier for a service window
- ``start_time``, ``end_time`` (required): the start and end times of the service window in HH:MM:SS format where the hour is less than 24
- ``monday``, ``tuesday``, ``wednesday``, ``thursday`` ``friday``, ``saturday``, ``sunday`` (required): 0 or 1, indicating whether the service is active on the given day (1) or not (0) 


routes.csv
-----------
This is a CSV file containing route information.
The CSV file contains the columns

- ``route_short_name`` (required): a unique short name for the route, e.g. '51X'
- ``route_desc`` (optional): a description of the route
- ``route_type`` (required): the `GTFS type of the route <https://developers.google.com/transit/gtfs/reference#routes_fields>`
- ``shape_id`` (required): unique shape ID of the route that links to ``shapes.geojson``
- ``service_window_id`` (required): a service window ID for the route taken from the file ``service_windows.csv`` 
- ``frequency`` (required): the frequency of the route during the service window in vehicles per hour
- ``is_bidirectional`` (required): 0 or 1 indicating whether the route travels in both directions along its shape (1) or not (0). If this field is 1, then trips will be created that travel in both directions along the route's path, each direction operating at the given frequency.  Otherwise, trips will be created that travel in only one direction, the direction of the route's path, operating at the given frequency. 
- ``speed`` (optional): the speed of the route in kilometers per hour


shapes.geojson
---------------
This is a GeoJSON file containing route shapes.
The file consists of one feature collection of LineString features, where each feature's properties contains at least the attribute ``shape_id``, which links the route's shape to the route's information in ``routes.csv``.

meta.csv
------------
This is a CSV file containing network metadata.
The CSV file contains the columns

- ``agency_name`` (required): the name of the transport agency
- ``agency_url`` (required): a fully qualified URL for the transport agency
- ``agency_timezone`` (required): timezone where the transit agency is located. Timezone names never contain the space character but may contain an underscore. Refer to `http://en.wikipedia.org/wiki/List_of_tz_zones <http://en.wikipedia.org/wiki/List_of_tz_zones>`_ for a list of valid values
- ``start_date``, ``end_date`` (required): the start and end dates for which all this network information is valid formated as YYYYMMDD strings
- ``default_route_speed`` (required): a default speed in kilometers per hour to assign to routes with no ``speed`` entry in the file ``routes.csv``


Algorithm
=========
Basically, 

- ``routes.txt`` is created from ``routes.csv``
- ``shapes.txt`` is created from ``shapes.geojson``
- ``agency.txt`` is created from ``meta.csv``
- ``calendar.txt`` is created in a dumb way with exactly one all-week service that applies to all trips
- ``stops.txt`` is created by making a pair of stops for each shape which lie on the shape's endpoints.  This will lead to duplicate stops in case shapes share endpoints.
- ``trips.txt`` and ``stop_times.txt`` are created by taking each route, each service window, and running a set of trips starting on the hour and operating at the route's speed and frequency specified for that service window.  If the route is bidirectional then two sets of trips in opposing directions will be created, each operating at the route's frequency. 

Examples
=========
Play with ``examples/examples.ipynb`` in an iPython notebook or view the notebook as HTML `here <https://rawgit.com/araichev/make_gtfs/master/examples/examples.html>`_.


Documentation
===============
Under ``docs/`` or view it as HTML `here <https://rawgit.com/araichev/make_gtfs/master/docs/_build/html/index.html>`_.

Todo
=====
- Allow for route shape variations by using MultiLineString features instead of LineStrings
