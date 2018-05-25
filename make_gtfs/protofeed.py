from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np

from . import constants as cs
from . import validators as vd


class ProtoFeed(object):
    """
    A ProtoFeed instance holds the source data
    from which to build a GTFS feed, plus a little metadata.

    Attributes are

    - ``service_windows``: DataFrame
    - ``frequencies``: DataFrame; has speeds filled in
    - ``meta``: DataFrame
    - ``shapes``: GeoDataFrame
    - ``shapes_extra``: dictionary of the form <shape ID> ->
      <trip directions using the shape (0, 1, or 2)>
    """

    def __init__(self, frequencies=None, meta=None, service_windows=None,
      shapes=None, stops=None):

        self.frequencies = frequencies
        self.meta = meta
        self.service_windows = service_windows
        self.shapes = shapes
        self.stops = stops

        # Clean frequencies
        freq = self.frequencies
        if freq is not None:
            cols = freq.columns

            # Fill missing route types with 3 (bus)
            freq['route_type'].fillna(3, inplace=True)
            freq['route_type'] = freq['route_type'].astype(int)

            # Create route speeds and fill in missing values with default speeds
            if 'speed' not in cols:
                freq['speed'] = np.nan
            freq['speed'].fillna(self.meta['default_route_speed'].iat[0],
              inplace=True)

        self.frequencies = freq

        # Build shapes extra from shape IDs in frequencies
        if self.frequencies is not None:
            def my_agg(group):
                d = {}
                dirs = group.direction.unique()
                if len(dirs) > 1 or 2 in dirs:
                    d['direction'] = 2
                else:
                    d['direction'] = dirs[0]
                return pd.Series(d)

            self.shapes_extra = dict(
                self.frequencies
                .groupby('shape_id')
                .apply(my_agg)
                .reset_index()
                .values
            )
        else:
            self.shapes_extra = None

    def copy(self):
        """
        Return a copy of this ProtoFeed, that is, a feed with all the
        same attributes.
        """
        other = ProtoFeed()
        for key in cs.PROTOFEED_ATTRS:
            value = getattr(self, key)
            if isinstance(value, pd.DataFrame):
                # Pandas copy DataFrame
                value = value.copy()
            setattr(other, key, value)

        return other

def read_protofeed(path):
    """
    Read the data files at the given directory path
    (string or Path object) and build a ProtoFeed from them.
    Validate the resulting ProtoFeed.
    If invalid, raise a ``ValueError`` specifying the errors.
    Otherwise, return the resulting ProtoFeed.

    The data files needed to build a ProtoFeed are

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

    """
    path = Path(path)

    service_windows = pd.read_csv(
      path/'service_windows.csv')

    meta = pd.read_csv(path/'meta.csv',
      dtype={'start_date': str, 'end_date': str})

    shapes = gpd.read_file(str(path/'shapes.geojson'), driver='GeoJSON')

    if (path/'stops.csv').exists():
        stops = (
            pd.read_csv(path/'stops.csv', dtype={
                'stop_id': str,
                'stop_code': str,
                'zone_id': str,
                'location_type': int,
                'parent_station': str,
                'stop_timezone': str,
                'wheelchair_boarding': int,
            })
            .drop_duplicates(subset=['stop_lon', 'stop_lat'])
            .dropna(subset=['stop_lon', 'stop_lat'], how='any')
        )
    else:
        stops = None

    frequencies = pd.read_csv(path/'frequencies.csv', dtype={
        'route_short_name': str,
        'service_window_id': str,
        'shape_id': str,
        'direction': int,
        'frequency': int,
    })

    pfeed = ProtoFeed(frequencies, meta, service_windows, shapes, stops)

    # Validate
    v = vd.validate(pfeed)
    if 'error' in v.type.values:
        raise ValueError(
          "Invalid ProtoFeed files:\n\n" + v.to_string(justify='left'))

    return pfeed
