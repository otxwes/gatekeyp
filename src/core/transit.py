# Copyright (c) 2026 gatekeyp contributors

"""Transit regions, the OTP GTFS-GraphQL client, and itinerary mapping."""

from __future__ import annotations

import datetime
import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.core.geocoding import GeoPoint

logger = logging.getLogger(__name__)

_GRAPHQL_ENDPOINT = "/otp/gtfs/v1"

_QUERY = """
{{
  plan(
    from: $from
    to: $to
    date: $date
    transportModes: [
      {{mode: WALK}}
      {{mode: TRANSIT}}
    ]
    numItineraries: $numItineraries
    routerId: $routerId
  ) {{
    from {{ name lat lon }}
    to {{ name lat lon }}
    itineraries {{
      startTime
      endTime
      duration
      legs {{
        mode
        duration
        distance
        from {{ name lat lon stop {{ name }} }}
        to {{ name lat lon stop {{ name }} }}
        route {{ shortName longName color agency {{ name }} }}
        headsign
        intermediateStops {{ name }}
        startTime
        endTime
      }}
    }}
  }}
}}
""".strip()


@dataclass(frozen=True)
class TransitRegion:
    """A configured transit region: bbox, OTP router, timezone, attribution."""

    id: str
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    router_id: str
    timezone: str
    attribution: str

    def contains(self, lat: float, lon: float) -> bool:
        return self.min_lat <= lat <= self.max_lat and self.min_lon <= lon <= self.max_lon


DEFAULT_REGIONS: dict[str, TransitRegion] = {
    "nyc": TransitRegion(
        "nyc", 40.4, 41.1, -74.3, -73.6, "nyc", "America/New_York", "Transit data © MTA"
    ),
    "la": TransitRegion(
        "la",
        33.6,
        34.4,
        -118.7,
        -117.6,
        "la",
        "America/Los_Angeles",
        "Transit data © LA Metro",
    ),
    "mtl": TransitRegion(
        "mtl", 45.3, 45.8, -74.1, -73.4, "mtl", "America/Toronto", "Transit data © STM/exo"
    ),
}


def load_regions_from_env() -> dict[str, TransitRegion]:
    """Load regions from ``GATEKEYP_TRANSIT_REGIONS`` JSON, falling back to defaults."""
    raw = os.environ.get("GATEKEYP_TRANSIT_REGIONS", "").strip()
    if not raw:
        return DEFAULT_REGIONS
    try:
        parsed = json.loads(raw)
        return {
            key: TransitRegion(
                id=data["id"],
                min_lat=float(data["min_lat"]),
                max_lat=float(data["max_lat"]),
                min_lon=float(data["min_lon"]),
                max_lon=float(data["max_lon"]),
                router_id=data["router_id"],
                timezone=data["timezone"],
                attribution=data["attribution"],
            )
            for key, data in parsed.items()
        }
    except (ValueError, TypeError, KeyError):
        logger.warning("Invalid GATEKEYP_TRANSIT_REGIONS; using defaults")
        return DEFAULT_REGIONS


def select_region(
    lat: float, lon: float, regions: dict[str, TransitRegion]
) -> TransitRegion | None:
    """Return the region whose bbox contains the point, or None."""
    for region in regions.values():
        if region.contains(lat, lon):
            return region
    return None


def _default_fetch(request: urllib.request.Request, timeout: float) -> bytes:
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()


class OtpClient:
    """OpenTripPlanner 2.x GTFS-GraphQL client."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 5.0,
        fetch: Callable[[urllib.request.Request, float], bytes] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._fetch = fetch or _default_fetch

    def plan(
        self,
        region: TransitRegion,
        origin: GeoPoint,
        destination: GeoPoint,
        *,
        depart_at: datetime.datetime | None = None,
    ) -> dict | None:
        """Return the raw ``data.plan`` dict, or None on error/timeout/empty."""
        when = depart_at or datetime.datetime.now(ZoneInfo(region.timezone))
        variables = {
            "from": {"lat": origin.lat, "lon": origin.lon},
            "to": {"lat": destination.lat, "lon": destination.lon},
            "date": when.date().isoformat(),
            "transportModes": [{"mode": "WALK"}, {"mode": "TRANSIT"}],
            "numItineraries": 3,
            "routerId": region.router_id,
        }
        payload = json.dumps({"query": _QUERY, "variables": variables}).encode()
        request = urllib.request.Request(  # noqa: S310
            f"{self.base_url}{_GRAPHQL_ENDPOINT}",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            body = json.loads(self._fetch(request, self.timeout))
            return body["data"]["plan"]
        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            IndexError,
        ):
            logger.warning("OTP request failed")
            return None


def _walk_leg_minutes(seconds: float) -> int:
    return round(seconds / 60.0)


def _format_time(epoch_ms: int, region: TransitRegion) -> str:
    moment = datetime.datetime.fromtimestamp(epoch_ms / 1000.0, tz=ZoneInfo(region.timezone))
    return moment.isoformat()


def itinerary_from_otp(plan: dict, region: TransitRegion) -> dict | None:
    """Map an OTP plan to the §7.4 response shape, or None when empty/malformed."""
    try:
        first = plan["itineraries"][0]
    except (KeyError, IndexError, TypeError):
        return None

    try:
        return _map_itinerary(first, region)
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _map_itinerary(itinerary: dict, region: TransitRegion) -> dict:
    origin = itinerary["legs"][0]["from"]
    destination = itinerary["legs"][-1]["to"]

    legs: list[dict] = []
    for leg in itinerary["legs"]:
        mode = leg["mode"]
        if mode == "WALK":
            legs.append(
                {
                    "mode": "WALK",
                    "minutes": _walk_leg_minutes(leg["duration"]),
                    "distance_m": round(leg.get("distance", 0.0)),
                    "from": leg["from"]["name"],
                    "to": leg["to"]["name"],
                }
            )
            continue

        from_stop = leg["from"].get("stop", {})
        to_stop = leg["to"].get("stop", {})
        stops = len(leg.get("intermediateStops", [])) or 1
        legs.append(
            {
                "mode": "TRANSIT",
                "agency": leg["route"]["agency"]["name"],
                "line": leg["route"].get("shortName") or leg["route"].get("longName", ""),
                "headsign": leg.get("headsign", ""),
                "color": f"#{leg['route']['color']}" if leg["route"].get("color") else None,
                "stops": stops,
                "depart": _format_time(leg["startTime"], region),
                "arrive": _format_time(leg["endTime"], region),
                "from_stop": from_stop.get("name", leg["from"]["name"]),
                "to_stop": to_stop.get("name", leg["to"]["name"]),
            }
        )

    return {
        "origin": {"label": origin["name"], "lat": origin["lat"], "lon": origin["lon"]},
        "destination": {
            "label": destination["name"],
            "lat": destination["lat"],
            "lon": destination["lon"],
        },
        "depart_at": _format_time(itinerary["startTime"], region),
        "arrive_at": _format_time(itinerary["endTime"], region),
        "duration_minutes": round(itinerary["duration"] / 60.0),
        "legs": legs,
        "attribution": region.attribution,
    }
