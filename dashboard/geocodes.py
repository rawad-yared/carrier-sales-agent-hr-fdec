"""Static city → (lat, lng) lookup for dashboard map rendering.

Covers every city string that appears as an origin or destination in
`data/loads.json`, plus the carrier origins used by the synthetic call
seeder. No runtime geocoding API dependency — if a new city is added
to the load board, add it here.
"""

CITY_COORDS: dict[str, tuple[float, float]] = {
    "Atlanta, GA": (33.7490, -84.3880),
    "Birmingham, AL": (33.5186, -86.8104),
    "Boise, ID": (43.6150, -116.2023),
    "Boston, MA": (42.3601, -71.0589),
    "Charlotte, NC": (35.2271, -80.8431),
    "Chicago, IL": (41.8781, -87.6298),
    "Cleveland, OH": (41.4993, -81.6944),
    "Columbus, OH": (39.9612, -82.9988),
    "Dallas, TX": (32.7767, -96.7970),
    "Denver, CO": (39.7392, -104.9903),
    "Detroit, MI": (42.3314, -83.0458),
    "Houston, TX": (29.7604, -95.3698),
    "Indianapolis, IN": (39.7684, -86.1581),
    "Jacksonville, FL": (30.3322, -81.6557),
    "Kansas City, KS": (39.1141, -94.6275),
    "Las Vegas, NV": (36.1699, -115.1398),
    "Little Rock, AR": (34.7465, -92.2896),
    "Los Angeles, CA": (34.0522, -118.2437),
    "Louisville, KY": (38.2527, -85.7585),
    "Memphis, TN": (35.1495, -90.0490),
    "Miami, FL": (25.7617, -80.1918),
    "Milwaukee, WI": (43.0389, -87.9065),
    "Minneapolis, MN": (44.9778, -93.2650),
    "Nashville, TN": (36.1627, -86.7816),
    "New Orleans, LA": (29.9511, -90.0715),
    "New York, NY": (40.7128, -74.0060),
    "Newark, NJ": (40.7357, -74.1724),
    "Oklahoma City, OK": (35.4676, -97.5164),
    "Philadelphia, PA": (39.9526, -75.1652),
    "Phoenix, AZ": (33.4484, -112.0740),
    "Pittsburgh, PA": (40.4406, -79.9959),
    "Portland, OR": (45.5152, -122.6784),
    "Richmond, VA": (37.5407, -77.4360),
    "Salt Lake City, UT": (40.7608, -111.8910),
    "San Francisco, CA": (37.7749, -122.4194),
    "Seattle, WA": (47.6062, -122.3321),
    "St. Louis, MO": (38.6270, -90.1994),
}


def lookup(city: str | None) -> tuple[float, float] | None:
    if not city:
        return None
    return CITY_COORDS.get(city)
