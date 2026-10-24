import logging
import urllib.error
import urllib.parse
import urllib.request

import pytest

from src.core.geocoding import (
    DEFAULT_GEOCODER_URL,
    DEFAULT_GEOCODER_USER_AGENT,
    DEFAULT_MAP_STYLE_URL,
    GeoPoint,
    NominatimGeocoder,
    build_geocoder_from_env,
)


def test_geocode_returns_first_result():
    requests: list[urllib.request.Request] = []

    def fetch(_request, _timeout):
        requests.append(_request)
        return b'[{"lat":"40.75","lon":"-73.98"}]'

    geocoder = NominatimGeocoder(
        base_url="https://geo.example",
        user_agent="test-agent",
        fetch=fetch,
    )

    assert geocoder.geocode("Main St") == GeoPoint(40.75, -73.98)
    assert len(requests) == 1
    url = requests[0].full_url
    assert "https://geo.example/search?" in url
    assert "q=Main+St" in url
    assert "format=jsonv2" in url
    assert "limit=1" in url
    assert requests[0].get_header("User-agent") == "test-agent"
    assert requests[0].get_header("Accept") == "application/json"


def test_geocode_returns_none_on_empty_results():
    geocoder = NominatimGeocoder(
        base_url="https://geo.example",
        user_agent="test-agent",
        fetch=lambda _request, _timeout: b"[]",
    )

    assert geocoder.geocode("Main St") is None


def test_geocode_returns_none_on_fetch_error(caplog):
    def fetch(_request, _timeout):
        message = "down"
        raise urllib.error.URLError(message)

    geocoder = NominatimGeocoder(
        base_url="https://geo.example",
        user_agent="test-agent",
        fetch=fetch,
    )

    with caplog.at_level(logging.WARNING, logger="src.core.geocoding"):
        assert geocoder.geocode("Secret Venue, 123 Main St") is None

    assert "Geocoding request failed" in caplog.text
    assert "Secret Venue" not in caplog.text
    assert "Main St" not in caplog.text


def test_geocode_caches_positive_results():
    calls = 0

    def fetch(_request, _timeout):
        nonlocal calls
        calls += 1
        return b'[{"lat":"40.75","lon":"-73.98"}]'

    geocoder = NominatimGeocoder(
        base_url="https://geo.example",
        user_agent="test-agent",
        fetch=fetch,
    )

    assert geocoder.geocode("Main St") == GeoPoint(40.75, -73.98)
    assert geocoder.geocode("Main St") == GeoPoint(40.75, -73.98)
    assert calls == 1


def test_geocode_normalizes_cache_key():
    calls = 0

    def fetch(_request, _timeout):
        nonlocal calls
        calls += 1
        return b'[{"lat":"40.75","lon":"-73.98"}]'

    geocoder = NominatimGeocoder(
        base_url="https://geo.example",
        user_agent="test-agent",
        fetch=fetch,
    )

    assert geocoder.geocode("  Main St  ") == GeoPoint(40.75, -73.98)
    assert geocoder.geocode("main st") == GeoPoint(40.75, -73.98)
    assert calls == 1


def test_geocode_viewbox_bias_adds_params():
    requests: list[urllib.request.Request] = []

    def fetch(request, _timeout):
        requests.append(request)
        return b'[{"lat":"40.75","lon":"-73.98"}]'

    geocoder = NominatimGeocoder(
        base_url="https://geo.example",
        user_agent="test-agent",
        fetch=fetch,
    )

    viewbox = (40.5, 41.0, -74.3, -73.6)
    assert geocoder.geocode("Main St", viewbox=viewbox) == GeoPoint(40.75, -73.98)

    url = urllib.parse.unquote(requests[0].full_url)
    assert "bounded=0" in url
    # Nominatim ordering: min_lon,min_lat,max_lon,max_lat
    assert "viewbox=-74.3,40.5,-73.6,41.0" in url

    # Same address without viewbox must not carry the params.
    requests.clear()
    assert geocoder.geocode("Other St") == GeoPoint(40.75, -73.98)
    other_url = urllib.parse.unquote(requests[0].full_url)
    assert "viewbox=" not in other_url
    assert "bounded=" not in other_url


def test_geocode_viewbox_changes_cache_key():
    calls: list[urllib.request.Request] = []

    def fetch(request, _timeout):
        calls.append(request)
        return b'[{"lat":"40.75","lon":"-73.98"}]'

    geocoder = NominatimGeocoder(
        base_url="https://geo.example",
        user_agent="test-agent",
        fetch=fetch,
    )

    viewbox = (40.5, 41.0, -74.3, -73.6)
    assert geocoder.geocode("Main St", viewbox=viewbox) == GeoPoint(40.75, -73.98)
    assert geocoder.geocode("Main St", viewbox=viewbox) == GeoPoint(40.75, -73.98)
    assert len(calls) == 1  # cached under the viewbox-scoped key

    assert geocoder.geocode("Main St") == GeoPoint(40.75, -73.98)
    assert len(calls) == 2  # plain key is a separate cache row


def test_geocode_no_cache_skips_cache():
    calls = 0

    def fetch(_request, _timeout):
        nonlocal calls
        calls += 1
        return b'[{"lat":"40.75","lon":"-73.98"}]'

    geocoder = NominatimGeocoder(
        base_url="https://geo.example",
        user_agent="test-agent",
        fetch=fetch,
    )

    assert geocoder.geocode("Private Origin", use_cache=False) == GeoPoint(40.75, -73.98)
    assert geocoder.geocode("Private Origin", use_cache=False) == GeoPoint(40.75, -73.98)
    assert calls == 2
    # Nothing was retained, so an ordinary lookup still hits the network.
    assert geocoder.geocode("Private Origin") == GeoPoint(40.75, -73.98)
    assert calls == 3


def test_geocode_rate_limits_requests():
    now = [0.0]
    sleeps: list[float] = []

    def clock():
        return now[0]

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    def fetch(_request, _timeout):
        return b'[{"lat":"40.75","lon":"-73.98"}]'

    geocoder = NominatimGeocoder(
        base_url="https://geo.example",
        user_agent="test-agent",
        clock=clock,
        sleep=sleep,
        fetch=fetch,
    )

    assert geocoder.geocode("First St") == GeoPoint(40.75, -73.98)
    assert geocoder.geocode("Second St") == GeoPoint(40.75, -73.98)

    assert len(sleeps) == 1
    assert sleeps[0] == pytest.approx(1.0)


def test_build_geocoder_from_env_disabled(monkeypatch):
    monkeypatch.setenv("GATEKEYP_MAP_STYLE_URL", "")
    monkeypatch.setenv("GATEKEYP_GEOCODER_URL", DEFAULT_GEOCODER_URL)
    assert build_geocoder_from_env() is None

    monkeypatch.setenv("GATEKEYP_MAP_STYLE_URL", DEFAULT_MAP_STYLE_URL)
    monkeypatch.setenv("GATEKEYP_GEOCODER_URL", "")
    assert build_geocoder_from_env() is None


def test_build_geocoder_from_env_enabled(monkeypatch):
    monkeypatch.setenv("GATEKEYP_MAP_STYLE_URL", DEFAULT_MAP_STYLE_URL)
    monkeypatch.setenv("GATEKEYP_GEOCODER_URL", "https://geo.example")
    monkeypatch.setenv("GATEKEYP_GEOCODER_USER_AGENT", "custom-agent")

    geocoder = build_geocoder_from_env()

    assert isinstance(geocoder, NominatimGeocoder)
    assert geocoder.base_url == "https://geo.example"
    assert geocoder.user_agent == "custom-agent"


def test_build_geocoder_from_env_uses_default_user_agent(monkeypatch):
    monkeypatch.setenv("GATEKEYP_MAP_STYLE_URL", DEFAULT_MAP_STYLE_URL)
    monkeypatch.setenv("GATEKEYP_GEOCODER_URL", DEFAULT_GEOCODER_URL)
    monkeypatch.delenv("GATEKEYP_GEOCODER_USER_AGENT", raising=False)

    geocoder = build_geocoder_from_env()

    assert isinstance(geocoder, NominatimGeocoder)
    assert geocoder.user_agent == DEFAULT_GEOCODER_USER_AGENT
