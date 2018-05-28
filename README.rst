Make GTFS
***********
.. image:: https://travis-ci.org/mrcagney/make_gtfs.svg?branch=master
    :target: https://travis-ci.org/mrcagney/make_gtfs

A Python 3.5+ library to build GTFS feeds from basic route information.
Inspired by Conveyal's `geom2gtfs <https://github.com/conveyal/geom2gtfs>`_.
Makes naive timetables, but they are often good enough for preliminary work.


Installation
=============
``pipenv install make_gtfs``


Usage
=====
Use as a library, or use from the command line by typing ``make_gtfs --help`` and following the instructions.

Make GTFS uses the following files to build a GTFS feed.

- ``frequencies.csv``: (required) A CSV file containing route frequency
  information. The CSV file contains the columns

  - ``route_short_name``: (required) String. A unique short name
    for the route, e.g. '51X'
  - ``route_long_name``: (required) String. Full name of the route
    that is more descriptive than ``route_short_name``
  - ``route_type``: (required) Integer. The
    `GTFS type of the route <https://developers.google.com/transit/gtfs/reference/#routestxt>`_
  - ``service_window_id`` (required): String. A service window ID
    for the route taken from the file ``service_windows.csv``
  - ``direction``: (required) Integer 0, 1, or 2. Indicates
    whether the route travels in GTFS direction 0, GTFS direction
    1, or in both directions.
    In the latter case, trips will be created that travel in both
    directions along the route's path, each direction operating at
    the given frequency.  Otherwise, trips will be created that
    travel in only the given direction.
  - ``frequency`` (required): Integer. The frequency of the route
    during the service window in vehicles per hour.
  - ``speed``:  (optional) Float. The speed of the route in
    kilometers per hour
  - ``shape_id``: (required) String. A shape ID that is listed in
    ``shapes.geojson`` and corresponds to the linestring of the
    (route, direction, service window) tuple.

- ``meta.csv``: (required) A CSV file containing network metadata.
  The CSV file contains the columns

  - ``agency_name``: (required) String. The name of the transport
    agency
  - ``agency_url``: (required) String. A fully qualified URL for
    the transport agency
  - ``agency_timezone``: (required) String. Timezone where the
    transit agency is located. Timezone names never contain the
    space character but may contain an underscore. Refer to
    `http://en.wikipedia.org/wiki/List_of_tz_zones <http://en.wikipedia.org/wiki/List_of_tz_zones>`_ for a list of valid values
  - ``start_date``, ``end_date`` (required): Strings. The start
    and end dates for which all this network information is valid
    formated as YYYYMMDD strings
  - ``default_route_speed``: (required) Float. Default speed in
    kilometers per hour to assign to routes with no ``speed``
    entry in the file ``routes.csv``

- ``service_windows.csv``: (required) A CSV file containing service window
  information.
  A *service window* is a time interval and a set of days of the
  week during which all routes have constant service frequency,
  e.g. Saturday and Sunday 07:00 to 09:00.
  The CSV file contains the columns

  - ``service_window_id``: (required) String. A unique identifier
    for a service window
  - ``start_time``, ``end_time``: (required) Strings. The start
    and end times of the service window in HH:MM:SS format where
    the hour is less than 24
  - ``monday``, ``tuesday``, ``wednesday``, ``thursday``,
    ``friday``, ``saturday``, ``sunday`` (required): Integer 0
    or 1. Indicates whether the service is active on the given day
    (1) or not (0)

- ``shapes.geojson``: (required) A GeoJSON file containing route shapes.
  The file consists of one feature collection of LineString
  features, where each feature's properties contains at least the
  attribute ``shape_id``, which links the route's shape to the
  route's information in ``routes.csv``.

- ``stops.csv``: (optional) A CSV file containing all the required
  and optional fields of ``stops.txt`` in
  `the GTFS <https://developers.google.com/transit/gtfs/reference/#stopstxt>`_



Algorithm
=========
Basically,

- ``routes.txt`` is created from ``frequencies.csv``
- ``agency.txt`` is created from ``meta.csv``
- ``calendar.txt`` is created in a dumb way with exactly one all-week service that applies to all trips
- ``shapes.txt`` is created from ``shapes.geojson``
- ``stops.txt`` is created from ``stops.csv`` if given.
  Otherwise it is created by making a pair of stops for each shape, one stop at each endpoint of the shape and then deleting stops with duplicate coordinates. Note that this yields only one stop for each shape that is a loop.
- ``trips.txt`` and ``stop_times.txt`` are created by taking each route, service window, and direction, and running a set of trips starting on the hour and operating at the route's speed and frequency specified for that service window.
  If the route direction is 2, then two sets of trips in opposing directions will be created, each operating at the route's frequency.
  Assign stops to each trip as follows.
  Collect all stops in the built file ``stops.txt`` that are within a fixed distance of the traffic side (e.g. the right hand side for USA agency timezones and the left hand side for New Zealand agency timezones) of the trip shape.
  If the trip has no nearby stops, then do not make stop times for that trip.


Examples
=========
See ``data/auckland`` for example files and play with the Jupyter notebook at ``ipynb/examples.ipynb``.


Documentation
===============
Under ``docs/`` or view it as HTML `here <https://rawgit.com/araichev/make_gtfs/master/docs/_build/singlehtml/index.html>`_.


Authors
========
- Alex Raichev, 2014-09


Notes
======
- Development status is Alpha
- Uses semantic versioning
- Thanks to `MRCagney <https://mrcagney.com>`_ for funding this project


Changes
========

2.0.0, 2018-05-28
------------------
- Extended to handle optional input stops
- Wrote ProtoFeed validation
- Modularized code more


1.0.0, 2018-05-22
------------------
- Restructured code and used GTFSTK, Click, Pytest, Pipenv


0.6.1, 2015-03-05
-------------------
- Fixed a bug in ``create_stop_times()`` that crashed when given a zero frequency.


0.6, 2015-01-29
-------------------
- Added direction field and renamed ``routes.csv`` to ``frequencies.csv``.
- Simplified the code some too.


0.5.1, 2015-01-28
-------------------
- Eliminated stops and trips for routes that have no linestrings


0.5, 2015-01-27
-----------------
- Changed from headways to frequencies and replaced ``config.json`` with CSV files


0.4, 2014-10-09
------------------
- Changed ``config.json`` spec to account for active days


0.3, 2014-09-29
-----------------
- Finished writing first set of tests and packaged



