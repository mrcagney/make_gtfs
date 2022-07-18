"""
Kludges to hash a few objects to use with ``functools.lru_cache``.
Inspired by https://gist.github.com/dsevero/252a5f280600c6b1118ed42826d188a9 .
"""

import shapely.geometry as sg
import pandas.util as pu
import geopandas as gpd


class HashableLineString(sg.LineString):
    def __init__(self, obj):
        super().__init__(obj)

    def __hash__(self):
        return hash(tuple(self.coords))

    def __eq__(self, other):
        return self.equals(other)


class HashableGeoDataFrame(gpd.GeoDataFrame):
    def __init__(self, obj):
        super().__init__(obj)

    def __hash__(self):
        return hash(tuple(pu.hash_pandas_object(self, index=True).values))

    def __eq__(self, other):
        return self.equals(other)
