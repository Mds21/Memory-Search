"""Tiny offline reverse geocoder (nearest known place within ~150 km). Replace with GeoNames/Nominatim for full coverage."""
import math

# (name, region, country, lat, lon)
PLACES = [
    ("Panaji", "Goa", "India", 15.4909, 73.8278), ("Calangute", "Goa", "India", 15.5439, 73.7553),
    ("Mumbai", "Maharashtra", "India", 19.0760, 72.8777), ("Pune", "Maharashtra", "India", 18.5204, 73.8567),
    ("Nagpur", "Maharashtra", "India", 21.1458, 79.0882), ("Nashik", "Maharashtra", "India", 19.9975, 73.7898),
    ("Delhi", "Delhi", "India", 28.6139, 77.2090), ("Jaipur", "Rajasthan", "India", 26.9124, 75.7873),
    ("Udaipur", "Rajasthan", "India", 24.5854, 73.7125), ("Agra", "Uttar Pradesh", "India", 27.1767, 78.0081),
    ("Varanasi", "Uttar Pradesh", "India", 25.3176, 82.9739), ("Lucknow", "Uttar Pradesh", "India", 26.8467, 80.9462),
    ("Kolkata", "West Bengal", "India", 22.5726, 88.3639), ("Chennai", "Tamil Nadu", "India", 13.0827, 80.2707),
    ("Madurai", "Tamil Nadu", "India", 9.9252, 78.1198), ("Bengaluru", "Karnataka", "India", 12.9716, 77.5946),
    ("Mysuru", "Karnataka", "India", 12.2958, 76.6394), ("Hyderabad", "Telangana", "India", 17.3850, 78.4867),
    ("Kochi", "Kerala", "India", 9.9312, 76.2673), ("Munnar", "Kerala", "India", 10.0889, 77.0595),
    ("Ahmedabad", "Gujarat", "India", 23.0225, 72.5714), ("Manali", "Himachal Pradesh", "India", 32.2396, 77.1887),
    ("Shimla", "Himachal Pradesh", "India", 31.1048, 77.1734), ("Rishikesh", "Uttarakhand", "India", 30.0869, 78.2676),
    ("Leh", "Ladakh", "India", 34.1526, 77.5771), ("Srinagar", "Jammu and Kashmir", "India", 34.0837, 74.7973),
    ("Amritsar", "Punjab", "India", 31.6340, 74.8723), ("Bhopal", "Madhya Pradesh", "India", 23.2599, 77.4126),
    ("Patna", "Bihar", "India", 25.5941, 85.1376), ("Guwahati", "Assam", "India", 26.1445, 91.7362),
    ("London", "England", "United Kingdom", 51.5074, -0.1278), ("Paris", "Ile-de-France", "France", 48.8566, 2.3522),
    ("Rome", "Lazio", "Italy", 41.9028, 12.4964), ("Madrid", "Madrid", "Spain", 40.4168, -3.7038),
    ("Barcelona", "Catalonia", "Spain", 41.3874, 2.1686), ("Berlin", "Berlin", "Germany", 52.5200, 13.4050),
    ("Amsterdam", "North Holland", "Netherlands", 52.3676, 4.9041), ("Zurich", "Zurich", "Switzerland", 47.3769, 8.5417),
    ("Dubai", "Dubai", "UAE", 25.2048, 55.2708), ("Singapore", "Singapore", "Singapore", 1.3521, 103.8198),
    ("Bangkok", "Bangkok", "Thailand", 13.7563, 100.5018), ("Bali", "Bali", "Indonesia", -8.4095, 115.1889),
    ("Tokyo", "Tokyo", "Japan", 35.6762, 139.6503), ("Kyoto", "Kyoto", "Japan", 35.0116, 135.7681),
    ("Seoul", "Seoul", "South Korea", 37.5665, 126.9780), ("Sydney", "New South Wales", "Australia", -33.8688, 151.2093),
    ("New York", "New York", "USA", 40.7128, -74.0060), ("San Francisco", "California", "USA", 37.7749, -122.4194),
    ("Los Angeles", "California", "USA", 34.0522, -118.2437), ("Mexico City", "CDMX", "Mexico", 19.4326, -99.1332),
    ("Toronto", "Ontario", "Canada", 43.6532, -79.3832), ("Cairo", "Cairo", "Egypt", 30.0444, 31.2357),
    ("Cape Town", "Western Cape", "South Africa", -33.9249, 18.4241), ("Colombo", "Western", "Sri Lanka", 6.9271, 79.8612),
    ("Kathmandu", "Bagmati", "Nepal", 27.7172, 85.3240),
]


def _hav(a_lat, a_lon, b_lat, b_lon) -> float:
    p = math.pi / 180
    dlat, dlon = (b_lat - a_lat) * p, (b_lon - a_lon) * p
    x = math.sin(dlat / 2) ** 2 + math.cos(a_lat * p) * math.cos(b_lat * p) * math.sin(dlon / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))


def reverse(lat: float, lon: float, max_km: float = 150.0) -> str | None:
    best = min(PLACES, key=lambda p: _hav(lat, lon, p[3], p[4]))
    if _hav(lat, lon, best[3], best[4]) > max_km:
        return None
    name, region, country, *_ = best
    return f"{name}, {region}, {country}" if region != name else f"{name}, {country}"
