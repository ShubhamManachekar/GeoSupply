"""
GeoSupply AI — Static OSINT registries.

Maritime chokepoints and India's 12 major ports. These are stable physical
facts (coordinates, baseline transit volumes) — live status is derived at
runtime from GDELT event density and Open-Meteo weather.
"""
from __future__ import annotations

# id, name, lat, lon, approx daily transits (ships), monitor radius km, blurb
CHOKEPOINTS: list[dict] = [
    {"id": "hormuz", "name": "Strait of Hormuz", "lat": 26.57, "lon": 56.25,
     "daily_transits": 115, "radius_km": 500,
     "description": "~20% of global oil; critical for India's crude imports"},
    {"id": "malacca", "name": "Strait of Malacca", "lat": 2.5, "lon": 101.0,
     "daily_transits": 250, "radius_km": 600,
     "description": "Primary Asia-Europe artery; ~30% of global trade"},
    {"id": "suez", "name": "Suez Canal", "lat": 30.45, "lon": 32.35,
     "daily_transits": 60, "radius_km": 400,
     "description": "Europe-Asia shortcut; ~12% of global trade"},
    {"id": "babelmandeb", "name": "Bab el-Mandeb", "lat": 12.58, "lon": 43.33,
     "daily_transits": 60, "radius_km": 500,
     "description": "Red Sea gateway; exposure to Yemen conflict"},
    {"id": "bosporus", "name": "Bosporus Strait", "lat": 41.12, "lon": 29.06,
     "daily_transits": 110, "radius_km": 300,
     "description": "Black Sea grain & energy exports"},
    {"id": "panama", "name": "Panama Canal", "lat": 9.08, "lon": -79.68,
     "daily_transits": 36, "radius_km": 300,
     "description": "Americas inter-ocean link; drought-sensitive"},
    {"id": "gibraltar", "name": "Strait of Gibraltar", "lat": 35.95, "lon": -5.6,
     "daily_transits": 300, "radius_km": 300,
     "description": "Mediterranean-Atlantic gateway"},
    {"id": "taiwan", "name": "Taiwan Strait", "lat": 24.0, "lon": 119.0,
     "daily_transits": 240, "radius_km": 600,
     "description": "Semiconductor supply corridor; PLA activity watch"},
    {"id": "goodhope", "name": "Cape of Good Hope", "lat": -34.36, "lon": 18.47,
     "daily_transits": 100, "radius_km": 600,
     "description": "Suez/Red Sea diversion route"},
]

# India's 12 major ports (name, state, lat, lon)
INDIA_PORTS: list[dict] = [
    {"name": "Mumbai",                "state": "Maharashtra",     "lat": 18.95, "lon": 72.84},
    {"name": "JNPT (Nhava Sheva)",    "state": "Maharashtra",     "lat": 18.95, "lon": 72.95},
    {"name": "Kandla (Deendayal)",    "state": "Gujarat",         "lat": 23.03, "lon": 70.22},
    {"name": "Mundra",                "state": "Gujarat",         "lat": 22.74, "lon": 69.70},
    {"name": "Chennai",               "state": "Tamil Nadu",      "lat": 13.10, "lon": 80.30},
    {"name": "Ennore (Kamarajar)",    "state": "Tamil Nadu",      "lat": 13.25, "lon": 80.34},
    {"name": "Tuticorin (V.O.C.)",    "state": "Tamil Nadu",      "lat": 8.75,  "lon": 78.20},
    {"name": "Kochi",                 "state": "Kerala",          "lat": 9.97,  "lon": 76.27},
    {"name": "New Mangalore",         "state": "Karnataka",       "lat": 12.93, "lon": 74.81},
    {"name": "Visakhapatnam",         "state": "Andhra Pradesh",  "lat": 17.69, "lon": 83.29},
    {"name": "Paradip",               "state": "Odisha",          "lat": 20.27, "lon": 86.67},
    {"name": "Kolkata (SMP)",         "state": "West Bengal",     "lat": 22.55, "lon": 88.31},
]

# Country gazetteer for risk scoring: iso2 → (display name, alias keywords)
COUNTRY_GAZETTEER: dict[str, tuple[str, list[str]]] = {
    "IN": ("India", ["india", "indian", "new delhi", "modi"]),
    "CN": ("China", ["china", "chinese", "beijing", "pla "]),
    "PK": ("Pakistan", ["pakistan", "islamabad", "karachi"]),
    "US": ("United States", ["united states", "u.s.", "washington", "pentagon", "white house"]),
    "RU": ("Russia", ["russia", "russian", "moscow", "kremlin"]),
    "UA": ("Ukraine", ["ukraine", "ukrainian", "kyiv", "kiev"]),
    "IR": ("Iran", ["iran", "iranian", "tehran"]),
    "IL": ("Israel", ["israel", "israeli", "tel aviv", "idf"]),
    "PS": ("Palestine", ["gaza", "palestin", "west bank"]),
    "YE": ("Yemen", ["yemen", "houthi", "sanaa"]),
    "TW": ("Taiwan", ["taiwan", "taipei"]),
    "KP": ("North Korea", ["north korea", "pyongyang", "dprk"]),
    "SA": ("Saudi Arabia", ["saudi", "riyadh"]),
    "TR": ("Turkey", ["turkey", "turkiye", "ankara", "erdogan"]),
    "EG": ("Egypt", ["egypt", "cairo", "suez"]),
    "MM": ("Myanmar", ["myanmar", "burma", "yangon"]),
    "BD": ("Bangladesh", ["bangladesh", "dhaka"]),
    "LK": ("Sri Lanka", ["sri lanka", "colombo"]),
    "SD": ("Sudan", ["sudan", "khartoum"]),
    "SY": ("Syria", ["syria", "damascus"]),
    "VE": ("Venezuela", ["venezuela", "caracas", "maduro"]),
    "NG": ("Nigeria", ["nigeria", "abuja", "lagos"]),
    "ET": ("Ethiopia", ["ethiopia", "addis ababa"]),
    "PH": ("Philippines", ["philippines", "manila"]),
    "GB": ("United Kingdom", ["united kingdom", "britain", "london", "uk "]),
    "FR": ("France", ["france", "french", "paris"]),
    "DE": ("Germany", ["germany", "german", "berlin"]),
    "JP": ("Japan", ["japan", "japanese", "tokyo"]),
    "KR": ("South Korea", ["south korea", "seoul"]),
    "AF": ("Afghanistan", ["afghanistan", "kabul", "taliban"]),
}

# Country centroids for dashboard focus mode: iso2 → (lat, lon, zoom)
COUNTRY_CENTROIDS: dict[str, tuple[float, float, float]] = {
    "IN": (22.5, 79.0, 4.2), "CN": (35.0, 103.0, 3.6), "PK": (30.0, 69.0, 4.6),
    "US": (39.0, -98.0, 3.4), "RU": (60.0, 90.0, 2.8), "UA": (48.8, 31.0, 4.8),
    "IR": (32.0, 53.0, 4.6), "IL": (31.4, 35.0, 6.0), "PS": (31.4, 34.4, 7.0),
    "YE": (15.5, 47.5, 5.2), "TW": (23.7, 121.0, 6.0), "KP": (40.0, 127.0, 5.4),
    "SA": (24.0, 45.0, 4.6), "TR": (39.0, 35.0, 4.8), "EG": (26.5, 30.0, 5.0),
    "MM": (21.0, 96.0, 4.8), "BD": (23.7, 90.3, 5.6), "LK": (7.8, 80.7, 6.4),
    "SD": (15.5, 30.0, 4.8), "SY": (35.0, 38.5, 5.6), "VE": (7.0, -66.0, 4.8),
    "NG": (9.0, 8.0, 5.0), "ET": (9.0, 39.5, 5.0), "PH": (12.0, 122.0, 4.8),
    "GB": (54.0, -2.5, 4.6), "FR": (46.5, 2.5, 4.8), "DE": (51.0, 10.0, 4.8),
    "JP": (36.5, 138.0, 4.6), "KR": (36.3, 127.8, 5.6), "AF": (33.9, 66.0, 5.0),
}

# Active war zones / maritime blockade & exclusion areas.
# Static physical facts (location, baseline); live intensity is computed each
# cycle from conflict-event density inside radius_km (see intel.compute_war_zones).
WAR_ZONES: list[dict] = [
    {"id": "ukraine", "name": "Ukraine Front", "lat": 48.0, "lon": 37.5,
     "radius_km": 450, "kind": "war", "baseline": 0.85,
     "description": "Russia-Ukraine war — active front line and deep-strike zone"},
    {"id": "gaza", "name": "Gaza / Israel-Lebanon", "lat": 32.2, "lon": 35.0,
     "radius_km": 250, "kind": "war", "baseline": 0.8,
     "description": "Gaza conflict + northern front exchanges"},
    {"id": "redsea", "name": "Red Sea Shipping Risk Area", "lat": 14.5, "lon": 42.5,
     "radius_km": 600, "kind": "blockade", "baseline": 0.7,
     "description": "Houthi attacks on shipping — de-facto blockade; reroutes via Cape"},
    {"id": "blacksea", "name": "Black Sea Exclusion Zone", "lat": 44.0, "lon": 32.0,
     "radius_km": 450, "kind": "exclusion", "baseline": 0.6,
     "description": "Naval drone/mine risk; grain-corridor constraints"},
    {"id": "sudan", "name": "Sudan Civil War", "lat": 15.0, "lon": 30.0,
     "radius_km": 550, "kind": "war", "baseline": 0.6,
     "description": "SAF-RSF civil war; Port Sudan logistics risk"},
    {"id": "sahel", "name": "Sahel Insurgency Belt", "lat": 14.5, "lon": 0.0,
     "radius_km": 800, "kind": "war", "baseline": 0.5,
     "description": "Mali/Burkina/Niger insurgencies"},
    {"id": "myanmar", "name": "Myanmar Civil Conflict", "lat": 21.5, "lon": 96.0,
     "radius_km": 450, "kind": "war", "baseline": 0.5,
     "description": "Post-coup civil conflict; border trade disruption with India"},
    {"id": "lac", "name": "LAC India-China Watch", "lat": 33.5, "lon": 78.8,
     "radius_km": 350, "kind": "exclusion", "baseline": 0.3,
     "description": "Line of Actual Control standoff sectors (Ladakh-Arunachal)"},
    {"id": "loc", "name": "LoC India-Pakistan Watch", "lat": 34.1, "lon": 74.5,
     "radius_km": 250, "kind": "exclusion", "baseline": 0.3,
     "description": "Line of Control — ceasefire violations watch"},
    {"id": "taiwanadiz", "name": "Taiwan ADIZ Pressure Zone", "lat": 23.5, "lon": 119.5,
     "radius_km": 400, "kind": "exclusion", "baseline": 0.4,
     "description": "PLA air/naval incursion pressure around Taiwan"},
    {"id": "hormuzrisk", "name": "Hormuz Seizure Risk Area", "lat": 26.5, "lon": 56.5,
     "radius_km": 300, "kind": "blockade", "baseline": 0.4,
     "description": "Tanker seizure/GPS-jamming incidents at Hormuz approaches"},
]

# Live news streams (official 24/7 YouTube live channels — free embeds).
# kind: "news" | "cam". embed = https://www.youtube.com/embed/live_stream?channel=ID
LIVE_STREAMS: list[dict] = [
    {"id": "aljazeera", "name": "Al Jazeera English", "kind": "news", "region": "GLOBAL",
     "channel_id": "UCNye-wNBqNL5ZzHSJj3l8Bg"},
    {"id": "dwnews", "name": "DW News", "kind": "news", "region": "GLOBAL",
     "channel_id": "UCknLrEdhRCp1aegoMqRaCZg"},
    {"id": "france24", "name": "France 24 English", "kind": "news", "region": "GLOBAL",
     "channel_id": "UCQfwfsi5VrQ8yKZ-UWmAEFg"},
    {"id": "skynews", "name": "Sky News", "kind": "news", "region": "GLOBAL",
     "channel_id": "UCoMdktPbSTixAyNGwb-UYkQ"},
    {"id": "trtworld", "name": "TRT World", "kind": "news", "region": "GLOBAL",
     "channel_id": "UC7fWeaHhqgM4Ry-RMpM2YYw"},
    {"id": "ndtv", "name": "NDTV 24x7", "kind": "news", "region": "INDIA",
     "channel_id": "UCZFMm1mMw0F81Z37aaEzTUA"},
    {"id": "indiatoday", "name": "India Today", "kind": "news", "region": "INDIA",
     "channel_id": "UCYPvAwZP8pZhSMW8qs7cVCw"},
    {"id": "wion", "name": "WION", "kind": "news", "region": "INDIA",
     "channel_id": "UC_gUM8rL-Lrg6O3adPW9K1g"},
    {"id": "timesnow", "name": "Times Now", "kind": "news", "region": "INDIA",
     "channel_id": "UC6RJ7-PaXg6TIH2BzZfTV7w"},
    {"id": "earthcam-nyc", "name": "EarthCam — Times Square NYC", "kind": "cam",
     "region": "GLOBAL", "channel_id": "UCStl5dDLm9ZJVDdSZK0bN-Q"},
]
