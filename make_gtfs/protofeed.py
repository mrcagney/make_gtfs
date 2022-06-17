from __future__ import annotations
from typing import Optional
import pathlib as pl
from dataclasses import dataclass

import geopandas as gpd
import pandas as pd
import numpy as np

from . import validators as vd


#: Default average speeds by route type in kilometers per hour
SPEED_BY_RTYPE = {
    0: 11,
    1: 30,
    2: 45,
    3: 22,
    4: 22,
    5: 13,
    6: 20,
    7: 18,
    11: 22,
    12: 65,
}


@dataclass
class ProtoFeed:
    """
    A ProtoFeed instance holds the source data from which to build a GTFS feed.
    The most common way to build is from files via the function :func:`read_protofeed`.
    """

    meta: pd.DataFrame
    service_windows: pd.DataFrame
    shapes: gpd.GeoDataFrame
    frequencies: pd.DataFrame
    stops: Optional[pd.DataFrame] = None

    def __post_init__(self):
        # Fill missing routes types with 3 (bus)
        self.frequencies = self.frequencies.assign(
            route_type=lambda x: x.route_type.fillna(3).astype(int)
        )

        # Fill missing route speeds with default speeds specified in ``meta`` and
        # SPEED_BY_RTYPE
        f = self.frequencies.copy()
        if "speed" not in f.columns:
            f["speed"] = np.nan

        d = self.speed_by_rtype()
        f["speed"] = f.speed.fillna(f.route_type.map(d))
        self.frequencies = f

        # Build ``shapes_extra``, a dictionary of the form
        # <shape ID> -> <trip directions using the shape (0, 1, or 2)>
        def my_agg(group):
            d = {}
            dirs = group.direction.unique()
            if len(dirs) > 1 or 2 in dirs:
                d["direction"] = 2
            else:
                d["direction"] = dirs[0]
            return pd.Series(d)

        self.shapes_extra = dict(
            self.frequencies.groupby("shape_id").apply(my_agg).reset_index().values
        )

    def copy(self) -> ProtoFeed:
        """
        Return a copy of this ProtoFeed, that is, a feed with all the
        same attributes.
        """
        d = {}
        for k in self.__dataclass_fields__:
            v = getattr(self, k)
            if isinstance(v, (pd.DataFrame, gpd.GeoDataFrame)):
                v = v.copy()
            d[k] = v

        return ProtoFeed(**d)

    def speed_by_rtype(self) -> dict[int, float]:
        """
        Return  the dictionary :const:`SPEED_BY_RTYPE` updated with the speeds listed
        in ``self.meta``.
        """
        m = self.meta.to_dict("records")[0]
        return {k: m.get(f"speed_route_type_{k}", v) for k, v in SPEED_BY_RTYPE.items()}


def read_protofeed(path: str | pl.Path) -> ProtoFeed:
    """
    Read the data files at the given directory path
    (string or Path object) and build a ProtoFeed from them.
    Validate the resulting ProtoFeed.
    If invalid, raise a ``ValueError`` specifying the errors.
    Otherwise, return the resulting ProtoFeed.

    The data files needed to build a ProtoFeed are

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
      - ``speed_route_type_0`` (optional): float; default average speed in kilometers
        per hour for routes of route type 0; used to fill missing route speeds in
        ``frequencies.csv``
      - ``speed_route_type_<i>`` for the remaining route types 1--7, 11--12 (optional)

      Missing speed columns will be created with values set to the speeds in the
      dictionary :const:`SPEED_BY_RTYPE`.

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

    - ``shapes.geojson``: (required) A GeoJSON file representing route shapes.
      The file consists of one feature collection of LineString
      features (in WGS84 coordinates), where each feature has the property

      - ``shape_id`` (required): a unique identifier of the shape

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
      - ``shape_id``: (required) String. A shape ID that is listed in
        ``shapes.geojson`` and corresponds to the linestring of the
        (route, direction, service window) tuple.
      - ``speed`` (optional): float; the average speed of the route in kilometers
        per hour

    - ``stops.csv``: (optional) A CSV file containing all the required
      and optional fields of ``stops.txt`` in
      `the GTFS <https://developers.google.com/transit/gtfs/reference/#stopstxt>`_

    """
    path = pl.Path(path)
    d = {}
    d["meta"] = pd.read_csv(
        path / "meta.csv", dtype={"start_date": str, "end_date": str}
    )
    d["service_windows"] = pd.read_csv(path / "service_windows.csv")
    d["shapes"] = gpd.read_file(path / "shapes.geojson")
    d["frequencies"] = pd.read_csv(
        path / "frequencies.csv",
        dtype={
            "route_short_name": str,
            "service_window_id": str,
            "shape_id": str,
            "direction": int,
            "frequency": int,
        },
    )
    d["stops"] = None
    if (path / "stops.csv").exists():
        d["stops"] = pd.read_csv(
            path / "stops.csv",
            dtype={
                "stop_id": str,
                "stop_code": str,
                "zone_id": str,
                "location_type": int,
                "parent_station": str,
                "stop_timezone": str,
                "wheelchair_boarding": int,
            },
        )

    pfeed = ProtoFeed(**d)

    # Validate
    v = vd.validate(pfeed)
    if "error" in v.type.values:
        raise ValueError("Invalid ProtoFeed files:\n\n" + v.to_string(justify="left"))

    return pfeed
