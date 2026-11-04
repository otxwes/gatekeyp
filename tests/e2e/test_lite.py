"""Group C scenarios: the lite event's share page (the `/i/{id}` redirect
target of `#/e/{id}`), console-clean throughout.

Round 8 Phase B withdrew the flyer form from the public UI, so these tests
mint lite events through the API against the dedicated lite-profile server
fixture (`lite_server`); the full profile no longer mounts those routes.
"""

import sqlite3

import pytest
from pages import ConsoleWatcher, create_lite_event
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_lite_event_share_page(lite_server, attendee_context):
    page = attendee_context.new_page()
    watcher = ConsoleWatcher(page)
    created = create_lite_event(
        page, lite_server.base_url, "Shed Festival", description="Bring a chair.", where="The shed"
    )
    event_id = created["event_id"]
    key = created["organizer_key"]
    assert key.startswith("local:"), key
    assert f"/i/{event_id}" in created["public_url"]

    # The share page IS the event page: #/e/{id} redirects there, key or not.
    page.goto(f"{lite_server.base_url}/#/e/{event_id}?k={key}")
    page.locator("h1", has_text="Shed Festival").wait_for(state="visible", timeout=10_000)
    assert "/i/" in page.url
    watcher.expect_clean()


def test_lite_without_key_redirects_to_share_page(lite_server, attendee_context):
    """A bare #/e/{id} link lands on the public share page — no key needed."""
    page = attendee_context.new_page()
    watcher = ConsoleWatcher(page)
    created = create_lite_event(page, lite_server.base_url, "Key Giveaway")
    event_id = created["event_id"]

    page.goto(f"{lite_server.base_url}/#/e/{event_id}")
    page.locator("h1", has_text="Key Giveaway").wait_for(state="visible", timeout=10_000)
    assert "/i/" in page.url
    watcher.expect_clean()


def test_lite_tombstoned_event_shows_ended(lite_server, attendee_context):
    """C4: once the event is wiped (tombstone row present), the page answers
    'Event ended' instead of leaking anything."""
    page = attendee_context.new_page()
    watcher = ConsoleWatcher(page)
    created = create_lite_event(page, lite_server.base_url, "Vanishing Act")
    event_id = created["event_id"]
    key = created["organizer_key"]

    # Simulate the expiry sweep having removed the event: tombstone it the
    # same way `sweep_expired` does (tempdir DB owned by this test session).
    db = sqlite3.connect(lite_server.db_path, timeout=5)
    with db:
        db.execute(
            "INSERT OR REPLACE INTO event_tombstones (event_id, ended_at) VALUES (?, ?)",
            (event_id, "2099-01-01T00:00:00+00:00"),
        )
    db.close()
    page.goto(f"{lite_server.base_url}/#/e/{event_id}?k={key}")
    # The redirect lands on the server-rendered ended page: honest, noindex.
    expect(page.locator("h1", has_text="Event ended")).to_be_visible(timeout=10_000)
    assert "noindex" in page.content()
    watcher.expect_clean()


def test_lite_missing_event_id_shows_empty_state(lite_server, attendee_context):
    """C5: #/e/ without an id lands on a friendly empty state, no crash."""
    page = attendee_context.new_page()
    watcher = ConsoleWatcher(page)
    page.goto(f"{lite_server.base_url}/#/e/")
    page.locator(".empty-title, #lite-views .empty").first.wait_for(timeout=10_000)
    watcher.expect_clean()


def test_full_profile_has_no_lite_routes_or_flyer_nav(server, attendee_context):
    """Round 8 Phase B: the public (full-profile) server hides the funnel."""
    page = attendee_context.new_page()
    watcher = ConsoleWatcher(page)

    page.goto(server.base_url)
    page.locator(".brand-name").wait_for(state="visible")
    expect(page.locator('.nav-link[href="#/flyer"]')).to_have_count(0)

    response = page.request.get(f"{server.base_url}/api/lite/events")
    assert response.status == 404
    response = page.request.get(f"{server.base_url}/i/event_missing")
    assert response.status == 404
    watcher.expect_clean()
