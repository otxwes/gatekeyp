"""Fixtures for the browser end-to-end suite (run via `uv run pytest tests/e2e -m e2e`).

A session-scoped gatekeyp server boots on port 8777 against a throwaway SQLite
database in the system temp dir, seeded with the deterministic `.env.dev`
secrets so invite/door flows behave exactly like local dev. The developer's
real `keys.db` and the dev server on :8000 are never touched.
"""

import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

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
def server() -> Iterator[Artifacts]:
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
