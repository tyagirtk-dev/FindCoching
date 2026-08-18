"""
Geo utilities: Haversine distance calculation used for radius-based teacher search.
"""
import math


EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def bounding_box(lat: float, lon: float, radius_km: float):
    """
    Returns a (lat_min, lat_max, lon_min, lon_max) box that safely contains the
    radius circle. Used as a cheap pre-filter in SQL before precise Haversine
    filtering in Python, so we don't compute distance against the whole table.
    """
    lat_delta = radius_km / 111.0  # ~111 km per degree latitude
    lon_delta = radius_km / (111.320 * math.cos(math.radians(lat)) or 1e-6)
    return (
        lat - lat_delta,
        lat + lat_delta,
        lon - lon_delta,
        lon + lon_delta,
    )


def find_within_radius(candidates, origin_lat, origin_lon, radius_km, lat_attr="latitude", lon_attr="longitude"):
    """
    Given an iterable of ORM objects with lat/lon attributes, return
    (object, distance_km) tuples for those within radius_km, sorted by distance.
    """
    results = []
    for obj in candidates:
        lat = getattr(obj, lat_attr)
        lon = getattr(obj, lon_attr)
        if lat is None or lon is None:
            continue
        dist = haversine_km(origin_lat, origin_lon, lat, lon)
        if dist <= radius_km:
            results.append((obj, dist))
    results.sort(key=lambda pair: pair[1])
    return results
