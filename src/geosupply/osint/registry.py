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
