# Copyright (c) 2026 gatekeyp contributors

import datetime
import json
import logging
import urllib.error
import urllib.request

from src.core.geocoding import GeoPoint
from src.core.transit import (
    DEFAULT_REGIONS,
    OtpClient,
    itinerary_from_otp,
    load_regions_from_env,
    select_region,
)


def test_select_region_inside_and_outside():
    assert select_region(40.7, -73.9, DEFAULT_REGIONS).id == "nyc"
    assert select_region(34.1, -118.3, DEFAULT_REGIONS).id == "la"
    assert select_region(45.5, -73.6, DEFAULT_REGIONS).id == "mtl"
    # Null Island fits no bbox.
    assert select_region(0.0, 0.0, DEFAULT_REGIONS) is None


def test_load_regions_from_env_override_and_default(monkeypatch):
    monkeypatch.delenv("GATEKEYP_TRANSIT_REGIONS", raising=False)
    assert load_regions_from_env() == DEFAULT_REGIONS

    override = {
        "nyc": {
            "id": "nyc",
            "min_lat": 40.4,
            "max_lat": 41.1,
            "min_lon": -74.3,
            "max_lon": -73.6,
            "router_id": "nyc",
            "timezone": "America/New_York",
            "attribution": "Transit data © MTA",
        }
    }
    monkeypatch.setenv("GATEKEYP_TRANSIT_REGIONS", json.dumps(override))
    regions = load_regions_from_env()
    assert set(regions) == {"nyc"}
    assert regions["nyc"].timezone == "America/New_York"


def test_load_regions_from_env_empty_is_default(monkeypatch):
    monkeypatch.setenv("GATEKEYP_TRANSIT_REGIONS", "")
    assert load_regions_from_env() == DEFAULT_REGIONS


def test_otp_plan_posts_graphql_query():
    requests: list[urllib.request.Request] = []

    def fetch(_request, _timeout):
        requests.append(_request)
        return json.dumps({"data": {"plan": {"itineraries": []}}}).encode()

    client = OtpClient("http://otp.example:8080", fetch=fetch, timeout=5.0)
    region = DEFAULT_REGIONS["nyc"]
    result = client.plan(
        region,
        GeoPoint(40.7, -73.9),
        GeoPoint(40.75, -73.98),
        depart_at=datetime.datetime(2026, 10, 24, 18, 30, tzinfo=datetime.UTC),
    )

    assert result == {"itineraries": []}
    assert len(requests) == 1
    request = requests[0]
    assert request.full_url == "http://otp.example:8080/otp/gtfs/v1"
    assert request.get_header("Content-type") == "application/json"

    body = json.loads(request.data)
    assert "plan(" in body["query"]
    assert body["query"].startswith("{")
    assert "numItineraries" in body["query"]
    variables = body["variables"]
    assert variables["from"] == {"lat": 40.7, "lon": -73.9}
    assert variables["to"] == {"lat": 40.75, "lon": -73.98}
    assert variables["date"] == "2026-10-24"
    assert variables["routerId"] == "nyc"
    assert variables["numItineraries"] == 3
    assert {"mode": "WALK"} in variables["transportModes"]
    assert {"mode": "TRANSIT"} in variables["transportModes"]


def test_otp_plan_returns_none_on_fetch_error(caplog):
    message = "down"

    def fetch(_request, _timeout):
        raise urllib.error.URLError(message)

    client = OtpClient("http://otp.example:8080", fetch=fetch)
    with caplog.at_level(logging.WARNING, logger="src.core.transit"):
        result = client.plan(DEFAULT_REGIONS["nyc"], GeoPoint(40.7, -73.9), GeoPoint(40.75, -73.98))

    assert result is None
    assert "OTP request failed" in caplog.text


def test_otp_plan_returns_none_on_timeout(caplog):
    message = "timed out"

    def fetch(_request, _timeout):
        raise TimeoutError(message)

    client = OtpClient("http://otp.example:8080", fetch=fetch)
    with caplog.at_level(logging.WARNING, logger="src.core.transit"):
        result = client.plan(DEFAULT_REGIONS["nyc"], GeoPoint(40.7, -73.9), GeoPoint(40.75, -73.98))

    assert result is None


def _plan_fixture():
    return {
        "from": {"name": "Origin", "lat": 40.7, "lon": -73.9},
        "to": {"name": "Venue", "lat": 40.75, "lon": -73.98},
        "itineraries": [
            {
                "startTime": 1792881000000,
                "endTime": 1792883100000,
                "duration": 2100,
                "legs": [
                    {
                        "mode": "WALK",
                        "duration": 240.0,
                        "distance": 300.0,
                        "from": {"name": "Origin", "lat": 40.7, "lon": -73.9},
                        "to": {"name": "Bedford Av", "lat": 40.7, "lon": -73.95},
                        "startTime": 1792881000000,
                        "endTime": 1792881240000,
                    },
                    {
                        "mode": "TRANSIT",
                        "duration": 1500.0,
                        "distance": 4000.0,
                        "from": {
                            "name": "Bedford Av",
                            "lat": 40.7,
                            "lon": -73.95,
                            "stop": {"name": "Bedford Av"},
                        },
                        "to": {
                            "name": "1 Av",
                            "lat": 40.72,
                            "lon": -73.97,
                            "stop": {"name": "1 Av"},
                        },
                        "route": {
                            "shortName": "L",
                            "longName": "14 St-Canarsie Local",
                            "color": "6CBE45",
                            "agency": {"name": "MTA"},
                        },
                        "headsign": "Canarsie",
                        "intermediateStops": [
                            {"name": "Lorimer St"},
                            {"name": "Graham Av"},
                            {"name": "Grand St"},
                        ],
                        "startTime": 1792881240000,
                        "endTime": 1792882740000,
                    },
                    {
                        "mode": "WALK",
                        "duration": 360.0,
                        "distance": 450.0,
                        "from": {"name": "1 Av", "lat": 40.72, "lon": -73.97},
                        "to": {"name": "Venue", "lat": 40.75, "lon": -73.98},
                        "startTime": 1792882740000,
                        "endTime": 1792883100000,
                    },
                ],
            }
        ],
    }.copy()


def test_itinerary_from_otp_maps_legs_and_times():
    region = DEFAULT_REGIONS["nyc"]
    result = itinerary_from_otp(_plan_fixture(), region)

    assert result["attribution"] == "Transit data © MTA"
    assert result["origin"]["label"] == "Origin"
    assert result["destination"]["label"] == "Venue"
    assert result["duration_minutes"] == 35
    # Times carry the region offset (-04:00 for America/New_York on Oct 24).
    assert result["depart_at"].endswith("-04:00")
    assert result["arrive_at"].endswith("-04:00")

    legs = result["legs"]
    assert [leg["mode"] for leg in legs] == ["WALK", "TRANSIT", "WALK"]

    walk = legs[0]
    assert walk["minutes"] == 4
    assert walk["distance_m"] == 300
    assert walk["from"] == "Origin"
    assert walk["to"] == "Bedford Av"

    transit = legs[1]
    assert transit["agency"] == "MTA"
    assert transit["line"] == "L"
    assert transit["headsign"] == "Canarsie"
    assert transit["color"] == "#6CBE45"
    assert transit["stops"] == 3
    assert transit["from_stop"] == "Bedford Av"
    assert transit["to_stop"] == "1 Av"


def test_itinerary_from_otp_returns_none_without_itineraries():
    assert itinerary_from_otp({"itineraries": []}, DEFAULT_REGIONS["nyc"]) is None


def test_itinerary_from_otp_returns_none_on_malformed_leg():
    plan = _plan_fixture()
    del plan["itineraries"][0]["legs"][1]["route"]
    del plan["itineraries"][0]["legs"][1]["startTime"]

    assert itinerary_from_otp(plan, DEFAULT_REGIONS["nyc"]) is None
