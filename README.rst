Make GTFS
***********
This is a Python 3.4 command line program that makes a GTFS feed
from a CSV file of route headways, a GeoJSON file of route shapes, and a configuration file of metadata.
It's inspired by Conveyal's `geom2gtfs <https://github.com/conveyal/geom2gtfs>`_.

Experimental. 
Needs more testing.
Use at your own risk.

Installation
=============
``pip install git+https://github.com/araichev/make_gtfs.git``

Usage
=====
``python make_gtfs.py [-h] [-o OUTPUT_FILE] [input_dir]``

The input directory must contain the following three files

- ``routes.csv``
- ``shapes.geojson``
- ``config.json``

More specifically...

routes.csv
-----------
This is a CSV file of route names and headways.
It must contain a header row with at least the columns ``route_short_name``
and one column of the form ``<service window name>_headway`` for every service window. 
Route short names must be unique and headways are specified in minutes.

A *service window* is a (not necessarily contiguous) time period of the week during which a route headways are constant, e.g. Saturday 6:00 to 7:00 and 9:00 to 15:00.

Here's an example ``routes.csv`` file::

    route_short_name,route_desc,weekday_peak_headway,weekday_offpeak_headway,weekday_eve_headway,saturday_day_headway,saturday_eve_headway,sunday_day_headway,sunday_eve_headway
    010,"City Link, Wynyard Quarter to Karangahape Rd via Queen St",5,7.5,10,7.5,10,7.5,10
    020,"Inner Link. Britomart, Three Lamps, Ponsonby, Grafton, Newmarket, Parnell and to Britomart",10,15,15,15,15,15,15

You can also specify the columns

- ``route_desc``: (optional; default='') `GTFS route description <https://developers.google.com/transit/gtfs/reference#routes_fields>`_
- ``speed``: (optional; default specified in ``config.json``) speed measured in kilometers per hour 
- ``route_type``: (optional; default specified in ``config.json``) `GTFS route type <https://developers.google.com/transit/gtfs/reference#routes_fields>`_


shapes.geojson
---------------
This is a GeoJSON file containing route shapes.
The file consists of one feature collection of LineString features, where each feature's properties contains at least the attribute ``route_short_name``, which links the route's shape to its headway information in ``routes.csv``.

Here's an example of ``shapes.geojson``::

    {"type": "FeatureCollection", "features": [{"geometry": {"coordinates": [[174.767029,-36.84444], [174.767401,-36.843364], [174.768695,-36.843668], [174.768113,-36.845003], [174.767631,-36.844886], [174.766853,-36.844619], [174.765414,-36.849031], [174.763086,-36.854224], [174.762292,-36.853955], [174.761962,-36.853794], [174.758882,-36.856034], [174.759072,-36.857619], [174.760359,-36.857912], [174.76158,-36.857914], [174.765362,-36.848887], [174.767029,-36.84444]], "type": "LineString"}, "properties": {"route_short_name": "010"}, "type": "Feature"}, {"geometry": {"coordinates": [[174.744138,-36.847422], [174.743802,-36.848536], [174.744437,-36.850401], [174.744949,-36.85224], [174.745351,-36.853356], [174.746586,-36.856383], [174.749513,-36.857891], [174.75102,-36.858745], [174.7528,-36.859625], [174.754449,-36.858743], [174.758345,-36.857714], [174.759975,-36.857934], [174.762143,-36.857998], [174.762377,-36.857951], [174.763637,-36.858627], [174.767094,-36.860498], [174.770286,-36.861276], [174.771142,-36.863454], [174.771209,-36.864033], [174.770684,-36.866002], [174.775142,-36.866991], [174.777979,-36.86755], [174.778222,-36.867546], [174.77908,-36.864907], [174.779162,-36.864662], [174.781841,-36.86199], [174.782643,-36.860773], [174.782887,-36.858941], [174.781213,-36.856564], [174.778722,-36.852603], [174.778063,-36.851994], [174.775938,-36.851178], [174.774518,-36.850486], [174.774569,-36.849787], [174.774394,-36.848658], [174.773665,-36.847417], [174.77268,-36.84645], [174.77176,-36.845896], [174.77093,-36.845632], [174.769794,-36.84549], [174.767472,-36.844944], [174.765344,-36.84428], [174.764025,-36.844294], [174.76239,-36.844776], [174.761424,-36.845411], [174.759115,-36.845826], [174.756675,-36.846161], [174.752991,-36.845157], [174.751725,-36.8471], [174.751048,-36.84825], [174.749652,-36.848449], [174.7479,-36.848519], [174.746635,-36.847883], [174.745532,-36.847517], [174.744298,-36.847422]], "type": "LineString"}, "properties": {"route_short_name": "020"}, "type": "Feature"},

config.json
------------
This is a JSON file of configuration variables.
It contains network metadata.
The required fields and format are most easily illustrated by example::

    {
      "agency_name":"Auckland Transport",
      "agency_url":"https://at.govt.nz/",
      "agency_timezone":"Pacific/Auckland",
      "start_date":"20140101",
      "end_date":"20150101",
      "service_windows":{
        "weekday_peak": [["07:00:00", "09:00:00"], ["16:00:00", "18:00:00"]],
        "weekday_offpeak": [["09:00:00", "16:00:00"], ["18:00:00", "19:00:00"]],
        "weekday_eve": [["06:00:00", "07:00:00"], ["19:00:00", "24:00:00"]],
        "saturday_day": [["07:00:00", "19:00:00"]],
        "saturday_eve": [["19:00:00", "24:00:00"]],
        "sunday_day": [["07:00:00", "19:00:00"]],
        "sunday_eve": [["19:00:00", "24:00:00"]]
      },
      "default_route_type":3,
      "default_speed":20
    }


Algorithm
=========
Basically, 

- ``routes.txt`` is created from ``routes.csv``
- ``shapes.txt`` is created from ``shapes.geojson``
- ``agency.txt`` is created from ``config.json``
- ``calendar.txt`` is created in a dumb way with exactly one all-week service that applies to all trips
- ``stops.txt`` is created by making a pair of stops for each shape which lie on the shape's endpoints.  This will lead to duplicate stops in case shapes share endpoints.
- ``trips.txt`` and ``stop_times.txt`` are created by taking each route, each service window, each service subwindow, and each direction (0 and 1), and running a set of trips starting on the hour and operating at the route's speed and headway specified for that service subwindow.  In particular, there is always an even number (possibly zero) of trips running on a route at any given time, half going of in one direction and half going in the opposite direction.

Documentation
==============
Only docstrings in the code at this point.

Todo
=====
Allow for route shape variations by using MultiLineString features instead of LineStrings.