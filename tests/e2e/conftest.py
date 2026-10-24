"""Fixtures for the browser end-to-end suite (run via `uv run pytest tests/e2e -m e2e`).

A session-scoped gatekeyp server boots on port 8777 against a throwaway SQLite
database in the system temp dir, seeded with the deterministic `.env.dev`
secrets so invite/door flows behave exactly like local dev. The developer's
real `keys.db` and the dev server on :8000 are never touched.
"""

import datetime
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_PORT = 8777
BASE_URL = f"http://127.0.0.1:{E2E_PORT}"


@dataclass(frozen=True)
class Artifacts:
    """Everything a scenario needs to talk to the E2E server."""

    base_url: str
    db_path: str
    organizer_key: str
    hmac_secret: str


def _parse_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


@pytest.fixture
def mock_nominatim() -> Iterator[str]:
    """A local Nominatim stand-in; tests never call the real service."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/search":
                self.send_response(404)
                self.end_headers()
                return
            query = parse_qs(parsed.query).get("q", [""])[0]
            body = b"[]" if "nowhere" in query.lower() else b'[{"lat":"40.75","lon":"-73.98"}]'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            """Keep the test output quiet."""

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _otp_plan() -> dict:
    """A deterministic GTFS-GraphQL plan: one walk + one transit leg (NYC)."""
    zone = ZoneInfo("America/New_York")

    def ms(moment: datetime.datetime) -> int:
        return int(moment.timestamp() * 1000)

    depart = datetime.datetime(2030, 1, 1, 18, 30, tzinfo=zone)
    walk_end = depart + datetime.timedelta(minutes=4)
    arrive = depart + datetime.timedelta(minutes=35)
    transit_end = arrive
    return {
        "data": {
            "plan": {
                "itineraries": [
                    {
                        "startTime": ms(depart),
                        "endTime": ms(arrive),
                        "duration": 2100.0,
                        "legs": [
                            {
                                "mode": "WALK",
                                "duration": 240.0,
                                "distance": 300.0,
                                "from": {"name": "Origin", "lat": 40.74, "lon": -73.99},
                                "to": {"name": "Bedford Av", "lat": 40.75, "lon": -73.98},
                            },
                            {
                                "mode": "TRANSIT",
                                "duration": 1560.0,
                                "distance": 3600.0,
                                "from": {
                                    "name": "Bedford Av",
                                    "lat": 40.75,
                                    "lon": -73.98,
                                    "stop": {"name": "Bedford Av"},
                                },
                                "to": {
                                    "name": "1 Av",
                                    "lat": 40.73,
                                    "lon": -73.98,
                                    "stop": {"name": "1 Av"},
                                },
                                "route": {
                                    "shortName": "L",
                                    "longName": "L Canarsie Local",
                                    "color": "EE352E",
                                    "agency": {"name": "MTA"},
                                },
                                "headsign": "Canarsie Rockaway Pkwy",
                                "intermediateStops": [
                                    {"name": "Graham Av"},
                                    {"name": "Grand St"},
                                ],
                                "startTime": ms(walk_end),
                                "endTime": ms(transit_end),
                            },
                        ],
                    }
                ]
            }
        }
    }


@dataclass
class MockOtp:
    """The mock OTP base URL plus a switch the failure test flips."""

    base_url: str
    fail: bool = False

    def __str__(self) -> str:
        return self.base_url


@pytest.fixture
def mock_otp() -> Iterator[MockOtp]:
    """A local OpenTripPlanner stand-in answering the GTFS-GraphQL plan query.

    The handler serves the fixture plan verbatim; `mock_otp.fail = True`
    flips it to a 500 so tests can drive the OTP-down fallback."""
    mock = MockOtp("")

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            if mock.fail:
                self.send_response(500)
                self.end_headers()
                return
            body = json.dumps(_otp_plan()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            """Keep the test output quiet."""

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        mock.base_url = f"http://127.0.0.1:{httpd.server_port}"
        yield mock
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture
def server(mock_nominatim: str, mock_otp: MockOtp) -> Iterator[Artifacts]:
    """One E2E server per test: restarts are cheap and give each scenario a
    pristine DB and pristine rate-limit buckets (the funnel limiter otherwise
    shares `127.0.0.1` across the whole suite and trips after 5 RSVPs)."""
    secrets = _parse_env_file(REPO_ROOT / ".env.dev")
    tmp = Path(tempfile.mkdtemp(prefix="gkp-e2e-"))
    env = {
        **os.environ,
        **secrets,
        "GATEKEYP_DB_PATH": str(tmp / "keys.db"),
        "GATEKEYP_PORT": str(E2E_PORT),
        "GATEKEYP_GEOCODER_URL": mock_nominatim,
        "GATEKEYP_OTP_URL": str(mock_otp),
    }
    proc = subprocess.Popen(
        ["uv", "run", "python", "-m", "src.api.server"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 30
    last_err = "no response"
    while True:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=2) as resp:
                if resp.status == 200:
                    break
        except Exception as err:  # noqa: BLE001 - probe loop
            last_err = str(err)
        if proc.poll() is not None:
            raise RuntimeError(f"E2E server exited early with code {proc.returncode}")
        if time.time() > deadline:
            proc.terminate()
            raise RuntimeError(f"E2E server never became healthy: {last_err}")
        time.sleep(0.3)

    yield Artifacts(
        base_url=BASE_URL,
        db_path=str(tmp / "keys.db"),
        organizer_key=secrets["GATEKEYP_ORGANIZER_KEY"],
        hmac_secret=secrets["GATEKEYP_HMAC_SECRET"],
    )

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def organizer_context(server, browser):
    """A fresh, isolated browser context acting as the organizer."""
    context = browser.new_context()
    context.grant_permissions(["clipboard-read", "clipboard-write"])
    yield context
    context.close()


@pytest.fixture
def attendee_context(server, browser):
    """A fresh, isolated browser context acting as an attendee."""
    return browser.new_context(viewport={"width": 1280, "height": 800})
