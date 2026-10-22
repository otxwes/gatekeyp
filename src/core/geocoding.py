# Copyright (c) 2026 gatekeyp contributors

"""Cached, rate-limited Nominatim forward geocoding."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

DEFAULT_MAP_STYLE_URL = "https://tiles.openfreemap.org/styles/dark"
DEFAULT_GEOCODER_URL = "https://nominatim.openstreetmap.org"
DEFAULT_GEOCODER_USER_AGENT = "gatekeyp/0.1 (+https://cellar.otxwes.nohost.me)"

_MIN_REQUEST_INTERVAL_SECONDS = 1.0


@dataclass(frozen=True)
class GeoPoint:
    """A WGS84 point returned by the geocoder."""

    lat: float
    lon: float


class Geocoder(Protocol):
    """Forward-geocode a free-text address."""

    def geocode(self, address: str) -> GeoPoint | None:
        """Return the first match, or None when the lookup fails."""
        ...


def _default_fetch(request: urllib.request.Request, timeout: float) -> bytes:
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()


class NominatimGeocoder:
    """Cached, rate-limited Nominatim client.

    Nominatim's usage policy requires a valid User-Agent, at most one
    request per second, and caching. The clock, sleep and fetch hooks are
    injectable so tests never touch the network.
    """

    def __init__(
        self,
        base_url: str,
        user_agent: str,
        *,
        timeout: float = 3.0,
        cache_ttl: float = 86400.0,
        max_cache: int = 256,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
        fetch: Callable[[urllib.request.Request, float], bytes] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self.max_cache = max_cache
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self._fetch = fetch or _default_fetch
        self._cache: dict[str, tuple[float, GeoPoint]] = {}
        self._lock = threading.Lock()
        self._last_request: float | None = None

    @staticmethod
    def _cache_key(address: str) -> str:
        """Normalize an address so whitespace/case variants share a cache row."""
        return " ".join(address.split()).strip().lower()

    def _cached(self, key: str) -> GeoPoint | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        cached_at, point = entry
        if self._clock() - cached_at > self.cache_ttl:
            del self._cache[key]
            return None
        return point

    def _store(self, key: str, point: GeoPoint) -> None:
        if len(self._cache) >= self.max_cache:
            oldest = min(self._cache, key=lambda cached: self._cache[cached][0])
            del self._cache[oldest]
        self._cache[key] = (self._clock(), point)

    def _wait_for_slot(self) -> None:
        """Enforce Nominatim's one-request-per-second limit."""
        if self._last_request is None:
            self._last_request = self._clock()
            return
        elapsed = self._clock() - self._last_request
        if elapsed < _MIN_REQUEST_INTERVAL_SECONDS:
            self._sleep(_MIN_REQUEST_INTERVAL_SECONDS - elapsed)
        self._last_request = self._clock()

    def geocode(self, address: str) -> GeoPoint | None:
        """Return the first Nominatim result for ``address``, or None."""
        normalized = self._cache_key(address)
        if not normalized:
            return None

        with self._lock:
            cached = self._cached(normalized)
            if cached is not None:
                return cached
            self._wait_for_slot()

        query = urllib.parse.urlencode({"q": address.strip(), "format": "jsonv2", "limit": 1})
        request = urllib.request.Request(  # noqa: S310
            f"{self.base_url}/search?{query}",
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
        )

        try:
            payload = self._fetch(request, self.timeout)
            results = json.loads(payload)
            first = results[0]
            point = GeoPoint(lat=float(first["lat"]), lon=float(first["lon"]))
        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            IndexError,
        ):
            logger.warning("Geocoding request failed")
            return None

        with self._lock:
            self._store(normalized, point)
        return point


def build_geocoder_from_env() -> NominatimGeocoder | None:
    """Build the configured geocoder, or None when maps/geocoding are off."""
    map_style_url = os.environ.get("GATEKEYP_MAP_STYLE_URL", DEFAULT_MAP_STYLE_URL).strip()
    geocoder_url = os.environ.get("GATEKEYP_GEOCODER_URL", DEFAULT_GEOCODER_URL).strip()
    if not map_style_url or not geocoder_url:
        return None
    user_agent = os.environ.get("GATEKEYP_GEOCODER_USER_AGENT", DEFAULT_GEOCODER_USER_AGENT).strip()
    return NominatimGeocoder(base_url=geocoder_url, user_agent=user_agent)
