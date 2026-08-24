"""Lightweight geospatial and subject-search helpers.
No external geocoding/search API is required for nearby teacher search.
"""
import math
import re
import unicodedata

EARTH_RADIUS_KM = 6371.0

# Small, deterministic alias map: cheap to run and useful for common tutoring searches.
SUBJECT_ALIASES = {
    "math": {"math", "maths", "mathematics", "arithmetic", "algebra", "geometry", "calculus"},
    "science": {"science", "general science", "physics", "chemistry", "biology"},
    "computer": {"computer", "computers", "computer science", "coding", "programming", "python", "java"},
    "english": {"english", "spoken english", "grammar", "ielts", "communication"},
    "hindi": {"hindi", "हिंदी"},
    "biology": {"biology", "botany", "zoology", "life science"},
    "physics": {"physics"},
    "chemistry": {"chemistry"},
    "neet": {"neet", "medical entrance", "medical", "biology", "physics", "chemistry"},
    "jee": {"jee", "engineering entrance", "iit", "mathematics", "maths", "physics", "chemistry"},
    "social science": {"social science", "history", "geography", "civics", "political science", "economics"},
    "commerce": {"commerce", "accountancy", "accounts", "economics", "business studies"},
}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").lower()
    value = re.sub(r"[^\w\s+#.-]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def search_terms(query: str):
    q = normalize_text(query)
    if not q:
        return set()
    terms = {q}
    terms.update(t for t in re.split(r"[\s,;/|]+", q) if t)
    for key, aliases in SUBJECT_ALIASES.items():
        if q == key or q in aliases or any(t in aliases for t in terms):
            terms.add(key)
            terms.update(aliases)
    return {t for t in terms if t}


def subject_match_score(query: str, teacher) -> float:
    """Return a relevance score. Zero means no subject/class match."""
    q = normalize_text(query)
    if not q:
        return 1.0
    hay_subjects = normalize_text(getattr(teacher, "subjects", ""))
    hay_classes = normalize_text(getattr(teacher, "classes", ""))
    if not hay_subjects:
        return 0.0
    terms = search_terms(q)
    score = 0.0
    for subject in [normalize_text(s) for s in getattr(teacher, "subjects_list", lambda: [])()]:
        if not subject:
            continue
        if subject == q:
            score = max(score, 100.0)
        elif q in subject or subject in q:
            score = max(score, 85.0)
        elif any(t in subject or subject in t for t in terms):
            score = max(score, 65.0)
        elif any(t in hay_subjects for t in terms if len(t) >= 3):
            score = max(score, 45.0)
    # A class/level query such as "10" can still be useful when combined with a subject.
    if q and q in hay_classes:
        score = max(score, 25.0)
    return score


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def bounding_box(lat: float, lon: float, radius_km: float):
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.320 * math.cos(math.radians(lat)) or 1e-6)
    return lat - lat_delta, lat + lat_delta, lon - lon_delta, lon + lon_delta


def find_within_radius(candidates, origin_lat, origin_lon, radius_km, lat_attr="latitude", lon_attr="longitude"):
    results = []
    for obj in candidates:
        lat = getattr(obj, lat_attr, None)
        lon = getattr(obj, lon_attr, None)
        if lat is None or lon is None:
            continue
        dist = haversine_km(origin_lat, origin_lon, lat, lon)
        if dist <= radius_km:
            results.append((obj, dist))
    results.sort(key=lambda pair: pair[1])
    return results
