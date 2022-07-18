"""
This module contains the main logic.
"""
from typing import Optional
from functools import lru_cache

import geopandas as gpd
import pandas as pd
import numpy as np
import shapely.ops as so
import shapely.geometry as sg
import gtfs_kit as gk

from . import protofeed as pf
from . import constants as cs
from . import hashables as h


def get_duration(timestr1: str, timestr2: str, units="s") -> float:
    """
    Return the duration of the time period between the first and second
    time string in the given units.
    Allowable units are 's' (seconds), 'min' (minutes), 'h' (hours).
    Assume ``timestr1 < timestr2``.
    """
    valid_units = ["s", "min", "h"]
    assert units in valid_units, "Units must be one of {!s}".format(valid_units)

    duration = gk.timestr_to_seconds(timestr2) - gk.timestr_to_seconds(timestr1)

    if units == "s":
        result = duration
    elif units == "min":
        result = duration / 60
    else:
        result = duration / 3600

    return result


def build_stop_ids(shape_id: str) -> (str, str):
    """
    Create a pair of stop IDs based on the given shape ID.
    """
    return [cs.SEP.join(["stp", shape_id, str(i)]) for i in range(2)]


def build_stop_names(shape_id: str) -> (str, str):
    """
    Create a pair of stop names based on the given shape ID.
    """
    return ["Stop {!s} on shape {!s} ".format(i, shape_id) for i in range(2)]


def build_agency(pfeed: pf.ProtoFeed) -> pd.DataFrame:
    """
    Given a ProtoFeed, return a DataFrame representing ``agency.txt``
    """
    return pd.DataFrame(
        {
            "agency_name": pfeed.meta["agency_name"].iat[0],
            "agency_url": pfeed.meta["agency_url"].iat[0],
            "agency_timezone": pfeed.meta["agency_timezone"].iat[0],
        },
        index=[0],
    )


def build_calendar_etc(pfeed: pf.ProtoFeed) -> pd.DataFrame:
    """
    Given a ProtoFeed, return a DataFrame representing ``calendar.txt``
    and a dictionary of the form <service window ID> -> <service ID>,
    respectively.
    """
    windows = pfeed.service_windows.copy()

    # Create a service ID for each distinct days_active field and map the
    # service windows to those service IDs
    def get_sid(bitlist):
        return "srv" + "".join([str(b) for b in bitlist])

    weekdays = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    bitlists = set()

    # Create a dictionary <service window ID> -> <service ID>
    d = dict()
    for index, window in windows.iterrows():
        bitlist = window[weekdays].tolist()
        d[window["service_window_id"]] = get_sid(bitlist)
        bitlists.add(tuple(bitlist))
    service_by_window = d

    # Create calendar
    start_date = pfeed.meta["start_date"].iat[0]
    end_date = pfeed.meta["end_date"].iat[0]
    F = []
    for bitlist in bitlists:
        F.append([get_sid(bitlist)] + list(bitlist) + [start_date, end_date])
    calendar = pd.DataFrame(
        F, columns=(["service_id"] + weekdays + ["start_date", "end_date"])
    )

    return calendar, service_by_window


def build_routes(pfeed: pf.ProtoFeed) -> pd.DataFrame:
    """
    Given a ProtoFeed, return a DataFrame representing ``routes.txt``.
    """
    f = (
        pfeed.frequencies.filter(
            ["route_short_name", "route_long_name", "route_type", "shape_id"]
        )
        .drop_duplicates()
        .copy()
    )

    # Create route IDs
    f["route_id"] = "r" + f["route_short_name"].map(str)

    del f["shape_id"]

    return f


def build_shapes(pfeed: pf.ProtoFeed) -> pd.DataFrame:
    """
    Given a ProtoFeed, return DataFrame representing ``shapes.txt``.
    Only use shape IDs that occur in both ``pfeed.shapes`` and
    ``pfeed.frequencies``.
    Create reversed shapes where routes traverse shapes in both
    directions.
    """
    rows = []
    for shape, geom in pfeed.shapes[["shape_id", "geometry"]].itertuples(index=False):
        if shape not in pfeed.shapes_extra:
            continue
        if pfeed.shapes_extra[shape] == 2:
            # Add shape and its reverse
            shid = shape + "-1"
            new_rows = [[shid, i, lon, lat] for i, (lon, lat) in enumerate(geom.coords)]
            rows.extend(new_rows)
            shid = shape + "-0"
            new_rows = [
                [shid, i, lon, lat]
                for i, (lon, lat) in enumerate(reversed(geom.coords))
            ]
            rows.extend(new_rows)
        else:
            # Add shape
            shid = "{}{}{}".format(shape, cs.SEP, pfeed.shapes_extra[shape])
            new_rows = [[shid, i, lon, lat] for i, (lon, lat) in enumerate(geom.coords)]
            rows.extend(new_rows)

    return pd.DataFrame(
        rows, columns=["shape_id", "shape_pt_sequence", "shape_pt_lon", "shape_pt_lat"]
    )


def build_stops(
    pfeed: pf.ProtoFeed, shapes: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """
    Given a ProtoFeed, return a DataFrame representing ``stops.txt``.
    If ``pfeed.stops`` is not ``None``, then return that.
    Otherwise, require built shapes output by :func:`build_shapes`,
    create one stop at the beginning (the first point) of each shape
    and one at the end (the last point) of each shape,
    and drop stops with duplicate coordinates.
    Note that this will yield one stop for shapes that are loops.
    """
    if pfeed.stops is not None:
        stops = pfeed.stops.copy()
    else:
        if shapes is None:
            raise ValueError("Must input shapes built by build_shapes()")

        geo_shapes = gk.geometrize_shapes_0(shapes)
        rows = []
        for shape, geom in geo_shapes[["shape_id", "geometry"]].itertuples(index=False):
            #
            stop_ids = build_stop_ids(shape)
            stop_names = build_stop_names(shape)
            for i in range(2):
                stop_id = stop_ids[i]
                stop_name = stop_names[i]
                stop_lon, stop_lat = geom.interpolate(i, normalized=True).coords[0]
                rows.append([stop_id, stop_name, stop_lon, stop_lat])

        stops = pd.DataFrame(
            rows, columns=["stop_id", "stop_name", "stop_lon", "stop_lat"]
        ).drop_duplicates(subset=["stop_lon", "stop_lat"])

    return stops


def build_trips(
    pfeed: pf.ProtoFeed,
    routes: pd.DataFrame,
    service_by_window: dict,
) -> pd.DataFrame:
    """
    Given a ProtoFeed and its corresponding routes and service-by-window,
    return a DataFrame representing ``trips.txt``.
    Trip IDs encode route, direction, and service window information
    to make it easy to compute stop times later.
    """
    # Put together the route and service data
    routes = (
        routes[["route_id", "route_short_name"]]
        .merge(pfeed.frequencies)
        .merge(pfeed.service_windows)
    )
    # For each row in routes, add trips at the specified frequency in
    # the specified direction
    rows = []
    for index, row in routes.iterrows():
        shape = row["shape_id"]
        route = row["route_id"]
        window = row["service_window_id"]
        start, end = row[["start_time", "end_time"]].values
        duration = get_duration(start, end, "h")
        frequency = row["frequency"]
        if not frequency:
            # No trips during this service window
            continue
        # Rounding down occurs here if the duration isn't integral
        # (bad input)
        num_trips_per_direction = int(frequency * duration)
        service = service_by_window[window]
        direction = row["direction"]
        if direction == 2:
            directions = [0, 1]
        else:
            directions = [direction]
        for direction in directions:
            # Warning: this shape-ID-making logic needs to match that
            # in ``build_shapes``
            shid = "{}{}{}".format(shape, cs.SEP, direction)
            rows.extend(
                [
                    [
                        route,
                        cs.SEP.join(
                            ["t", route, window, start, str(direction), str(i)]
                        ),
                        direction,
                        shid,
                        service,
                    ]
                    for i in range(num_trips_per_direction)
                ]
            )

    return pd.DataFrame(
        rows, columns=["route_id", "trip_id", "direction_id", "shape_id", "service_id"]
    )


def buffer_side(linestring: sg.LineString, side: str, buffer: float) -> sg.Polygon:
    """
    Given a Shapely LineString, a side of the LineString
    (string; 'left' = left hand side of LineString,
    'right' = right hand side of LineString, or
    'both' = both sides), and a buffer size in the distance units of
    the LineString, buffer the LineString on the given side by
    the buffer size and return the resulting Shapely polygon.
    """
    b = linestring.buffer(buffer, cap_style=2)
    if side in ["left", "right"] and buffer > 0:
        # Make a tiny buffer to split the normal-size buffer
        # in half across the linestring
        eps = min(buffer / 2, 0.001)
        b0 = linestring.buffer(eps, cap_style=3)
        diff = b.difference(b0)
        polys = so.polygonize(diff)
        # Buffer sides slightly to include original linestring
        if side == "left":
            b = list(polys)[0].buffer(1.1 * eps)
        else:
            b = list(polys)[-1].buffer(1.1 * eps)

    return b


def get_stops_nearby(
    geo_stops: gpd.GeoDataFrame,
    linestring: sg.LineString,
    side: str,
    buffer: float = cs.BUFFER,
) -> gpd.GeoDataFrame:
    """
    Given a GeoDataFrame of stops, a Shapely LineString in the
    same coordinate system, a side of the LineString
    (string; 'left' = left hand side of LineString,
    'right' = right hand side of LineString, or
    'both' = both sides), and a buffer in the distance units of that
    coordinate system, do the following.
    Return a GeoDataFrame of all the stops that lie within
    ``buffer`` distance units to the ``side`` of the LineString.
    """
    b = buffer_side(linestring, side, buffer)

    # Collect stops
    return geo_stops.loc[geo_stops.intersects(b)].copy()


# def build_stop_times(
#     pfeed: pf.ProtoFeed,
#     routes: pd.DataFrame,
#     shapes: pd.DataFrame,
#     stops: pd.DataFrame,
#     trips: pd.DataFrame,
#     buffer: float = cs.BUFFER,
# ) -> pd.DataFrame:
#     """
#     Given a ProtoFeed and its corresponding routes,
#     shapes, stops, and trips DataFrames,
#     return a DataFrame representing ``stop_times.txt``.
#     Includes the optional ``shape_dist_traveled`` column in meters.
#     Do not make stop times for trips with no nearby stops.
#     """
#     # Get the table of trips and add frequency and service window details
#     routes = routes.filter(["route_id", "route_short_name"]).merge(
#         pfeed.frequencies.drop(["shape_id"], axis=1)
#     )
#     trips = trips.assign(
#         service_window_id=lambda x: x.trip_id.map(lambda y: y.split(cs.SEP)[2])
#     ).merge(routes)

#     # Get the geometries of GTFS ``shapes``, not ``pfeed.shapes``
#     geometry_by_shape = dict(
#         gk.geometrize_shapes_0(shapes, use_utm=True)
#         .filter(["shape_id", "geometry"])
#         .values
#     )

#     # Save on distance computations by memoizing
#     dist_by_stop_by_shape = {shape: {} for shape in geometry_by_shape}

#     def compute_stops_dists_times(geo_stops, linestring, shape, start_time, end_time):
#         """
#         Given a GeoDataFrame of stops on one side of a given Shapely
#         LineString with given shape ID, compute distances and departure
#         times of a trip traversing the LineString from start to end
#         at the given start and end times (in seconds past midnight)
#         and stopping at the stops encountered along the way.
#         Do not assume that the stops are ordered by trip encounter.
#         Return three lists of the same length: the stop IDs in order
#         that the trip encounters them, the shape distances traveled
#         along distances at the stops, and the times the stops are
#         encountered, respectively.
#         """
#         g = geo_stops.copy()
#         dists_and_stops = []
#         for i, stop in enumerate(g["stop_id"].values):
#             if stop in dist_by_stop_by_shape[shape]:
#                 d = dist_by_stop_by_shape[shape][stop]
#             else:
#                 d = gk.get_segment_length(linestring, g.geometry.iat[i])  # meters
#                 dist_by_stop_by_shape[shape][stop] = d
#             dists_and_stops.append((d, stop))
#         dists, stops = zip(*sorted(dists_and_stops))
#         D = linestring.length  # meters
#         dists_are_reasonable = all([dist < D + 100 for dist in dists])
#         if not dists_are_reasonable:
#             # Assume equal distances between stops :-(
#             n = len(stops)
#             delta = D / (n - 1)
#             dists = [i * delta for i in range(n)]

#         # Compute times using distances, start and end stop times,
#         # and linear interpolation
#         t0, t1 = start_time, end_time
#         d0, d1 = dists[0], dists[-1]
#         # Interpolate
#         times = np.interp(dists, [d0, d1], [t0, t1])
#         return stops, dists, times

#     # Iterate through trips and set stop times based on stop ID
#     # and service window frequency.
#     # Remember that every trip has a valid shape ID.
#     # Gather stops geographically from ``stops``.
#     rows = []
#     geo_stops = gk.geometrize_stops_0(stops, use_utm=True)
#     # Look on the side of the traffic side of street for this timezone
#     side = cs.TRAFFIC_BY_TIMEZONE[pfeed.meta.agency_timezone.iat[0]]
#     for index, row in trips.iterrows():
#         shape = row["shape_id"]
#         geom = geometry_by_shape[shape]
#         stops = get_stops_nearby(geo_stops, geom, side, buffer=buffer)
#         # Don't make stop times for trips without nearby stops
#         if stops.empty:
#             continue
#         length = geom.length  # meters
#         speed = row["speed"] * 1000 / 3600  # meters per second
#         duration = int(length / speed)  # seconds
#         frequency = row["frequency"]
#         if not frequency:
#             # No stop times for this trip/frequency combo
#             continue
#         headway = 3600 / frequency  # seconds
#         trip = row["trip_id"]
#         __, route, window, base_timestr, direction, i = trip.split(cs.SEP)
#         direction = int(direction)
#         base_time = gk.timestr_to_seconds(base_timestr)
#         start_time = base_time + headway * int(i)
#         end_time = start_time + duration
#         stops, dists, times = compute_stops_dists_times(
#             stops, geom, shape, start_time, end_time
#         )
#         new_rows = [
#             [trip, stop, j, time, time, dist]
#             for j, (stop, time, dist) in enumerate(zip(stops, times, dists))
#         ]
#         rows.extend(new_rows)

#     g = pd.DataFrame(
#         rows,
#         columns=[
#             "trip_id",
#             "stop_id",
#             "stop_sequence",
#             "arrival_time",
#             "departure_time",
#             "shape_dist_traveled",
#         ],
#     )

#     # Convert seconds back to time strings
#     g[["arrival_time", "departure_time"]] = g[
#         ["arrival_time", "departure_time"]
#     ].applymap(lambda x: gk.timestr_to_seconds(x, inverse=True))
#     return g


def compute_shape_point_speeds(
    shapes: pd.DataFrame,
    speed_zones: gpd.GeoDataFrame,
    route_type: int,
    *,
    use_utm: bool = False,
) -> gpd.GeoDataFrame:
    """
    Intersect the given GTFS shapes table with the given speed zones subset to the given
    route type to assign speeds to each shape point.
    Also add points and speeds where the speed zones intersect the linestrings
    corresponding to the shapes (the boundary points).
    Return a GeoDataFrame with the columns

    - shape_id
    - shape_dist_traveled: in meters
    - shape_pt_sequence: -1 if a boundary point
    - geometry: Point object representing shape point
    - route_type: ``route_type``
    - speed: in kilometers per hour
    - speed_zone_id: speed zone ID

    Use UTM coordinates if specified.
    Return an empty GeoDataFrame if there are no speed zones for the given route type.
    """
    speed_zones = speed_zones.loc[lambda x: x.route_type == route_type]
    if speed_zones.empty:
        return gpd.GeoDataFrame()

    # Get UTM CRS to compute distances in metres
    lat, lon = shapes[["shape_pt_lat", "shape_pt_lon"]].values[0]
    utm_crs = gk.get_utm_crs(lat, lon)
    speed_zones = speed_zones.to_crs(utm_crs)

    # Build shape points
    def compute_dists(group):
        p2 = group.geometry.shift(1)
        group["dist"] = group.geometry.distance(p2, align=False)
        group["shape_dist_traveled"] = group.dist.fillna(0).cumsum()
        return group

    shape_points = (
        gpd.GeoDataFrame(
            shapes,
            geometry=gpd.points_from_xy(shapes.shape_pt_lon, shapes.shape_pt_lat),
            crs=cs.WGS84,
        )
        .to_crs(utm_crs)
        .sort_values(["shape_id", "shape_pt_sequence"])
        .groupby("shape_id")
        .apply(compute_dists)
        .drop(["dist", "shape_pt_lat", "shape_pt_lon"], axis="columns")
    )

    # Get points where shapes intersect speed zone boundaries
    shapes_g = (
        gk.geometrize_shapes_0(shapes)
        .to_crs(utm_crs)
        .assign(boundary_points=lambda x: x.intersection(speed_zones.boundary))
    )

    # Assign distances to those boundary points
    rows = []
    for shape_id, group in shapes_g.groupby("shape_id"):
        bd = group.boundary_points.iat[0]
        if bd and not bd.is_empty:
            for point in bd.geoms:
                dist = group.geometry.iat[0].project(point)
                rows.append([shape_id, dist, point])

    boundary_points = gpd.GeoDataFrame(
        rows,
        columns=["shape_id", "shape_dist_traveled", "geometry"],
        crs=utm_crs,
    )

    # Concatenate shape points and boundary points and assign speeds
    g = (
        pd.concat(
            [
                shape_points,
                boundary_points.assign(shape_pt_sequence=-1),
            ]
        )
        .sjoin(speed_zones)
        .drop("index_right", axis="columns")
        .sort_values(
            ["shape_id", "shape_dist_traveled", "shape_pt_sequence"], ignore_index=True
        )
    )

    if not use_utm:
        # Convert back to WGS84
        g = g.to_crs(cs.WGS84)

    return g.filter(
        [
            "shape_id",
            "shape_pt_sequence",
            "shape_dist_traveled",
            "geometry",
            "route_type",
            "speed_zone_id",
            "speed",
        ]
    )


def build_stop_times_for_trip(
    trip_id: str,
    stops_g_nearby: gpd.GeoDataFrame,
    shape_id: str,
    linestring: sg.LineString,
    speed_zones: gpd.GeoDataFrame,
    route_type: int,
    shape_point_speeds: gpd.GeoDataFrame,
    default_speed: float,
    start_time: int,
) -> pd.DataFrame:
    """
    Build stop times for the given trip ID.

    Assume all coordinates are in meters, distances are in meters, and speeds are in
    kilometers per hour.
    """
    # Subset frames and convert speeds to meters per second
    k = 1000 / 3600
    sps = (
        shape_point_speeds.loc[lambda x: x.shape_id == shape_id]
        .assign(speed=lambda x: x.speed * k)
        .filter(["shape_id", "shape_dist_traveled", "speed_zone_id", "speed"])
    )
    speed_zones = speed_zones.loc[lambda x: x.route_type == route_type].assign(
        speed=lambda x: x.speed * k
    )
    default_speed *= k

    # Get stop distances along linestring, and intersect with speed zones to get speeds
    f = (
        stops_g_nearby.assign(
            shape_dist_traveled=lambda x: x.apply(
                lambda row: linestring.project(row.geometry), axis=1
            ),
        )
        .sjoin(speed_zones)
        .sort_values("shape_dist_traveled", ignore_index=True)
        .filter(["stop_id", "shape_dist_traveled", "speed_zone_id", "speed"])
    )

    # Insert stops into shape point speeds at appropriate distances,
    # fill default speed, and assign distance weighted speeds to each point.
    # Use the latter later to compute distance-weighted average speeds between stops.
    return (
        pd.concat([f, sps])
        .sort_values("shape_dist_traveled", ignore_index=True)
        .assign(
            speed=lambda x: x.speed.replace({np.inf: default_speed}),
            dist_to_next=lambda x: x.shape_dist_traveled.diff().shift(-1).fillna(0),
            weight_to_next=lambda x: x.dist_to_next * x.speed,
            shape_weight_traveled=lambda x: x.weight_to_next.cumsum()
            .shift(1)
            .fillna(0),
        )
        # Drop the shape points, keeping only the stops,
        # then compute distances, distance-weighted speeds, and times between successive stops.
        .loc[lambda x: x.stop_id.notna()]
        .assign(
            trip_id=trip_id,
            dist_to_next=lambda x: x.shape_dist_traveled.diff().shift(-1).fillna(0),
            weight_to_next=lambda x: x.shape_weight_traveled.diff().shift(-1).fillna(0),
            speed_to_next=lambda x: (x.weight_to_next / x.dist_to_next).fillna(0),
            duration_to_next=lambda x: (x.dist_to_next / x.speed_to_next).fillna(0),
            arrival_time=lambda x: x.duration_to_next.shift(1).cumsum().fillna(0)
            + start_time,
            departure_time=lambda x: x.arrival_time,
            stop_sequence=lambda x: range(len(x.index)),
        )
        .filter(
            [
                "trip_id",
                "stop_id",
                "stop_sequence",
                "arrival_time",
                "departure_time",
                "shape_dist_traveled",
            ]
        )
    )


@lru_cache()
def _build_stop_times_for_trip(
    trip_id: str,
    stops_g_nearby: h.HashableGeoDataFrame,
    shape_id: str,
    linestring: h.HashableLineString,
    speed_zones: h.HashableGeoDataFrame,
    route_type: int,
    shape_point_speeds: h.HashableGeoDataFrame,
    default_speed: float,
    start_time: int,
) -> pd.DataFrame:
    """
    Caching version of :func:`build_stop_times_for_trip` for greater speed and internal
    use.
    Needs hashable GeoDataFrames and LineStrings to work.
    """
    return build_stop_times_for_trip(
        trip_id,
        stops_g_nearby,
        shape_id,
        linestring,
        speed_zones,
        route_type,
        shape_point_speeds,
        default_speed,
        start_time,
    )


def build_stop_times(
    pfeed: pf.ProtoFeed,
    routes: pd.DataFrame,
    shapes: pd.DataFrame,
    stops: pd.DataFrame,
    trips: pd.DataFrame,
    buffer: float = cs.BUFFER,
) -> pd.DataFrame:
    """
    Given a ProtoFeed and its corresponding routes,
    shapes, stops, and trips DataFrames,
    return a DataFrame representing ``stop_times.txt``.
    Includes the optional ``shape_dist_traveled`` column rounded to the nearest meter.
    Does not make stop times for trips with no stops within the buffer.
    """
    # Get the table of trips and add frequency and service window details
    routes = routes.filter(["route_id", "route_short_name"]).merge(
        pfeed.frequencies.drop(["shape_id"], axis=1)
    )
    trips = trips.assign(
        service_window_id=lambda x: x.trip_id.map(lambda y: y.split(cs.SEP)[2])
    ).merge(routes)

    # Get the geometries of GTFS ``shapes``, not ``pfeed.shapes``
    shapes_gi = gk.geometrize_shapes_0(shapes, use_utm=True).set_index("shape_id")
    stops_g = gk.geometrize_stops_0(stops, use_utm=True)

    # For each trip get its shape and stops nearby and set stops times based on its
    # service window frequency.
    # Remember that every trip has a valid shape ID.
    frames = []
    # Look on the correct side of the street for stops
    side = cs.TRAFFIC_BY_TIMEZONE[pfeed.meta.agency_timezone.iat[0]]
    speed_zones = h.HashableGeoDataFrame(pfeed.speed_zones.to_crs(pfeed.utm_crs))
    for (route_type, shape_id, speed), group in trips.groupby(
        ["route_type", "shape_id", "speed"]
    ):
        shape_point_speeds = h.HashableGeoDataFrame(
            compute_shape_point_speeds(
                shapes, pfeed.speed_zones, route_type, use_utm=True
            )
        )
        linestring = h.HashableLineString(shapes_gi.loc[shape_id].geometry)
        stops_g_nearby = h.HashableGeoDataFrame(
            get_stops_nearby(stops_g, linestring, side, buffer=buffer)
        )

        if stops_g_nearby.empty:
            # No stops to make times for
            continue

        for __, row in group.iterrows():
            frequency = row["frequency"]
            if not frequency:
                # The trip actually doesn't run
                continue

            trip_id = row["trip_id"]
            headway = 3600 / frequency  # seconds
            __, route, window, base_timestr, direction, i = trip_id.split(cs.SEP)
            direction = int(direction)
            base_time = gk.timestr_to_seconds(base_timestr)
            start_time = base_time + headway * int(i)  # seconds
            f = (
                _build_stop_times_for_trip(
                    "tmp_trip_id",
                    stops_g_nearby,
                    shape_id,
                    linestring,
                    speed_zones,
                    route_type,
                    shape_point_speeds,
                    speed,
                    0,
                )
                # Fill in trip ID and start times.
                # Doing it after the fact to take advantage of caching?
                .assign(
                    trip_id=trip_id,
                    arrival_time=lambda x: x.arrival_time + start_time,
                    departure_time=lambda x: x.arrival_time,
                )
            )
            frames.append(f)

    if not frames:
        f = pd.DataFrame(
            columns=[
                "trip_id",
                "stop_id",
                "stop_sequence",
                "arrival_time",
                "departure_time",
            ]
        )
    else:
        f = pd.concat(frames, ignore_index=True).assign(
            shape_dist_traveled=lambda x: x.shape_dist_traveled.round()
        )
        # Convert seconds back to time strings
        f[["arrival_time", "departure_time"]] = f[
            ["arrival_time", "departure_time"]
        ].applymap(lambda x: gk.timestr_to_seconds(x, inverse=True))

    # Free memory
    _build_stop_times_for_trip.cache_clear()

    return f


def build_feed(pfeed: pf.ProtoFeed, buffer: float = cs.BUFFER) -> gk.Feed:
    """
    Convert the given ProtoFeed to a GTFS Feed with meter distance units.
    Look at a distance of ``buffer`` meters from route shapes to find stops.
    Output distance units will be in meters
    """
    # Create Feed tables
    agency = build_agency(pfeed)
    calendar, service_by_window = build_calendar_etc(pfeed)
    routes = build_routes(pfeed)
    shapes = build_shapes(pfeed)
    stops = build_stops(pfeed, shapes)
    trips = build_trips(pfeed, routes, service_by_window)
    stop_times = build_stop_times(pfeed, routes, shapes, stops, trips, buffer=buffer)

    # Create Feed and remove unused stops etc.
    return gk.Feed(
        agency=agency,
        calendar=calendar,
        routes=routes,
        shapes=shapes,
        stops=stops,
        stop_times=stop_times,
        trips=trips,
        dist_units="m",
    ).drop_zombies()
