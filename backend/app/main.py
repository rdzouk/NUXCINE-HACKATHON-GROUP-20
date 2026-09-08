from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


app = FastAPI(title="VORA local API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PLACES = [
    {"id": "carrefour-warda", "name": "Carrefour Warda", "lat": 3.8480, "lng": 11.5021, "quartier": "Centre-ville", "aliases": ["warda", "carrefour warda"]},
    {"id": "mvan", "name": "Mvan", "lat": 3.8167, "lng": 11.5167, "quartier": "Mvan", "aliases": ["mvan"]},
    {"id": "bastos", "name": "Bastos", "lat": 3.8833, "lng": 11.5167, "quartier": "Bastos", "aliases": ["bastos"]},
    {"id": "mokolo-market", "name": "Mokolo Market", "lat": 3.8680, "lng": 11.5100, "quartier": "Mokolo", "aliases": ["mokolo", "mokolo market"]},
    {"id": "yaounde-airport", "name": "Yaounde Nsimalen Airport", "lat": 3.7226, "lng": 11.5533, "quartier": "Nsimalen", "aliases": ["airport", "nsimalen", "yaounde airport"]},
]


class Coordinate(BaseModel):
    lat: float
    lng: float
    label: str | None = None


class QuoteRequest(BaseModel):
    pickup: Coordinate
    dropoff: Coordinate
    seats: int = Field(default=1, ge=1, le=6)
    mode: str = "exclusive"


def distance_meters(first: Coordinate, second: Coordinate) -> float:
    earth_radius = 6_371_000
    lat_delta = radians(second.lat - first.lat)
    lng_delta = radians(second.lng - first.lng)
    haversine = sin(lat_delta / 2) ** 2 + cos(radians(first.lat)) * cos(radians(second.lat)) * sin(lng_delta / 2) ** 2
    return earth_radius * 2 * asin(sqrt(haversine))


def encode_polyline(points: list[tuple[float, float]]) -> str:
    result = []
    previous_lat = previous_lng = 0
    for lat, lng in points:
        for index, (value, previous) in enumerate(((lat, previous_lat), (lng, previous_lng))):
            scaled = round(value * 100000)
            delta = scaled - previous
            encoded = ~(delta << 1) if delta < 0 else delta << 1
            while encoded >= 0x20:
                result.append(chr((0x20 | (encoded & 0x1F)) + 63))
                encoded >>= 5
            result.append(chr(encoded + 63))
            if index == 0:
                previous_lat = scaled
            else:
                previous_lng = scaled
    return "".join(result)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "vora-local-api"}


@app.get("/places/search")
def search_places(q: str = Query(min_length=1), limit: int = Query(default=8, ge=1, le=20)) -> dict:
    query = q.strip().lower()
    matches = []
    for place in PLACES:
        haystack = [place["name"].lower(), place["quartier"].lower(), *place["aliases"]]
        if any(query in value for value in haystack):
            match_type = "exact_alias" if query in place["aliases"] else "fuzzy_landmark"
            matches.append({**place, "match_type": match_type})
    return {"results": matches[:limit]}


@app.get("/places/reverse")
def reverse_place(lat: float, lng: float) -> dict:
    nearest = min(PLACES, key=lambda place: distance_meters(Coordinate(lat=lat, lng=lng), Coordinate(lat=place["lat"], lng=place["lng"])))
    return {"id": nearest["id"], "name": nearest["name"], "lat": nearest["lat"], "lng": nearest["lng"], "quartier": nearest["quartier"], "match_type": "nearest_landmark"}


@app.post("/rides/quote")
def quote_ride(request: QuoteRequest) -> dict:
    distance = distance_meters(request.pickup, request.dropoff)
    duration = max(5, round(distance / 5.5 / 60))
    fare = round(500 + distance / 1000 * 250, -2)
    corridor_fare = round(fare * 0.7 / request.seats, -2) if request.mode == "shared" else None
    route_polyline = encode_polyline([
        (request.pickup.lat, request.pickup.lng),
        ((request.pickup.lat + request.dropoff.lat) / 2, (request.pickup.lng + request.dropoff.lng) / 2),
        (request.dropoff.lat, request.dropoff.lng),
    ])
    return {
        "quote_id": f"local-{int(datetime.now(timezone.utc).timestamp())}",
        "distance_m": round(distance),
        "duration_s": duration * 60,
        "fare_xaf": int(fare),
        "corridor_fare_xaf": int(corridor_fare) if corridor_fare is not None else None,
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        "route_polyline": route_polyline,
        "breakdown": {"base_xaf": 500, "distance_xaf": int(fare - 500)},
    }