from __future__ import annotations
from typing import Optional
import pathlib as pl
from dataclasses import dataclass

import geopandas as gpd
import pandas as pd
import shapely.geometry as sg

from . import constants as cs
from . import validators as vd


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
    speed_zones: Optional[gpd.GeoDataFrame] = None

    @staticmethod
    def tidy_speed_zone_group(
        speed_zones: gpd.GeoDataFrame,
        service_area: gpd.GeoDataFrame,
        default_speed: float,
    ) -> gpd.GeoDataFrame:
        """
        Buffer the bounding box of the given shapes by about 1 km, define that as the
        service area, clip the speed zones to the service area, then fill areas
        of missing speed with the given default speed.
        Return the resulting service area of (Multi)Polygons, now partitioned into speed
        zones.
        """
        # Partition the service area into speed zones, filling with ``default_speed``
        if speed_zones is None:
            result = service_area.assign(zone_id="default", speed=default_speed)
        elif service_area.geom_equals(speed_zones.unary_union).all():
            # Speed zones already partition the study area, so good
            result = speed_zones
        else:
            # Work to be done
            result = (
                speed_zones
                # Clip to service area
                .clip(service_area)
                # Union chunks
                .overlay(service_area, how="union")
                # Fill missing speeds with default
                .assign(
                    zone_id=lambda x: x.zone_id.fillna("default"),
                    speed=lambda x: x.speed.fillna(default_speed),
                )
                .filter(["zone_id", "speed", "geometry"])
                .sort_values("zone_id", ignore_index=True)
            )
        return result

    def __post_init__(self):
        # Fill missing routes types with 3 (bus)
        self.frequencies = self.frequencies.assign(
            route_type=lambda x: x.route_type.fillna(3).astype(int)
        )

        d = self.speed_by_rtype()

        # Tidy speed zones
        # Build service area as the bounding box of the shapes buffered by about 1 km
        service_area = gpd.GeoDataFrame(
            geometry=[sg.box(*self.shapes.total_bounds).buffer(0.01)], crs=cs.WGS84
        )

        def my_apply(group):
            route_type = group.route_type.iat[0]
            default_speed = d[route_type]
            return tidy_speed_zone_group(group, service_area, default_speed)

        self.speed_zones = self.speed_zones.groupby("route_type").apply(my_apply)

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

    def copy(self):
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
      - ``default_route_speed``: (required) Float. Default average speed of routes
        in kilometers per hour; used to fill missing speeds in ``speed_zones``.

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

      - ``shape_id`` (required): a unique identifier of the shape, which appears in
        ``routes.csv``.

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

    - ``stops.csv``: (optional) A CSV file containing all the required
      and optional fields of ``stops.txt`` in
      `the GTFS <https://developers.google.com/transit/gtfs/reference/#stopstxt>`_

    - ``speed_zones.geojson``: (optional) A GeoJSON file of representing speed zones
      for routes.
      The file consists of one feature collection of Polygon features
      (in WGS84 coordinates), each with the properties

      - ``zone_id`` (required): string; a unique identifier of the zone
      -  ``speed`` (required): positive float; the average speed in kilometers per hour
        of routes that travel within that polygon.

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
    d["speed_zones"] = None
    if (path / "speed_zones.geojson").exists():
        g = gpd.read_file(path / "speed_zones.geojson")
        if "zone_id" in g.columns:
            g["zone_id"] = g.zone_id.astype(str)
        d["speed_zones"] = g

    pfeed = ProtoFeed(**d)

    # Validate
    v = vd.validate(pfeed)
    if "error" in v.type.values:
        raise ValueError("Invalid ProtoFeed files:\n\n" + v.to_string(justify="left"))

    return pfeed
