"""Group C scenarios: the flyer funnel (`#/flyer`) and the lite event's
share page (the `/i/{id}` redirect target of `#/e/{id}`), console-clean
throughout."""

import re

import pytest
from pages import ApiKeyGrabber, ConsoleWatcher
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_flyer_create_then_lite_view(attendee_context, server):
    page = attendee_context.new_page()
    watcher = ConsoleWatcher(page)
    grabber = ApiKeyGrabber(page)
    page.goto(f"{server.base_url}/#/flyer")
    page.locator("#flyer-form").wait_for(state="visible")
    page.fill("#flyer-title", "Shed Festival")
    page.fill("#flyer-description", "Bring a chair.")
    page.fill("#flyer-where", "The shed")
    # datetime-local is required; pick 7 days out so the value is future-proof.
    page.evaluate(
        "() => { const d = new Date(Date.now() + 7 * 864e5); d.setMinutes(0, 0, 0);"
        " document.getElementById('flyer-when').value = d.toISOString()"
        ".slice(0, 16); }"
    )
    page.click("#flyer-btn")
    page.locator("#flyer-done:not([hidden])").wait_for(timeout=15_000)
    key = grabber.latest(page)
    codes = page.locator("#flyer-done .item code").all_inner_texts()
    assert key.startswith("local:"), key
    public = next((c for c in codes if "/i/" in c), "")
    match = re.search(r"/i/([^/?]+)", public)
    assert match, f"no public event link among {codes}"
    event_id = match.group(1)

    # The card modal opened immediately — the card is the only copy of the key
    # (the no-key-text guard is pinned in test_organizer_flows).
    page.locator("#card-preview").wait_for(state="visible", timeout=10_000)

    # The share page IS the event page: #/e/{id} redirects there, key or not.
    page.goto(f"{server.base_url}/#/e/{event_id}?k={key}")
    page.locator("h1", has_text="Shed Festival").wait_for(state="visible", timeout=10_000)
    assert "/i/" in page.url
    watcher.expect_clean()


def test_lite_without_key_redirects_to_share_page(attendee_context, server):
    """A bare #/e/{id} link lands on the public share page — no key needed."""
    page = attendee_context.new_page()
    watcher = ConsoleWatcher(page)
    page.goto(f"{server.base_url}/#/flyer")
    page.locator("#flyer-form").wait_for(state="visible")
    page.fill("#flyer-title", "Key Giveaway")
    page.evaluate(
        "() => { const d = new Date(Date.now() + 7 * 864e5); d.setMinutes(0, 0, 0);"
        " document.getElementById('flyer-when').value = d.toISOString()"
        ".slice(0, 16); }"
    )
    page.click("#flyer-btn")
    page.locator("#flyer-done:not([hidden])").wait_for(timeout=15_000)
    event_id = next(
        re.search(r"/i/([^/?]+)", c).group(1)
        for c in page.locator("#flyer-done .item code").all_inner_texts()
        if re.search(r"/i/([^/?]+)", c)
    )
    page.goto(f"{server.base_url}/#/e/{event_id}")
    page.locator("h1", has_text="Key Giveaway").wait_for(state="visible", timeout=10_000)
    assert "/i/" in page.url
    watcher.expect_clean()


def test_lite_tombstoned_event_shows_ended(attendee_context, server):
    """C4: once the event is wiped (tombstone row present), the page answers
    'Event ended' instead of leaking anything."""
    import sqlite3

    page = attendee_context.new_page()
    watcher = ConsoleWatcher(page)
    grabber = ApiKeyGrabber(page)
    page.goto(f"{server.base_url}/#/flyer")
    page.locator("#flyer-form").wait_for(state="visible")
    page.fill("#flyer-title", "Vanishing Act")
    page.evaluate(
        "() => { const d = new Date(Date.now() + 7 * 864e5); d.setMinutes(0, 0, 0);"
        " document.getElementById('flyer-when').value = d.toISOString()"
        ".slice(0, 16); }"
    )
    page.click("#flyer-btn")
    page.locator("#flyer-done:not([hidden])").wait_for(timeout=15_000)
    codes = page.locator("#flyer-done .item code").all_inner_texts()
    key = grabber.latest(page)
    event_id = next(
        re.search(r"/i/([^/?]+)", c).group(1) for c in codes if re.search(r"/i/([^/?]+)", c)
    )
    # Simulate the expiry sweep having removed the event: tombstone it the
    # same way `sweep_expired` does (tempdir DB owned by this test session).
    db = sqlite3.connect(server.db_path, timeout=5)
    with db:
        db.execute(
            "INSERT OR REPLACE INTO event_tombstones (event_id, ended_at) VALUES (?, ?)",
            (event_id, "2099-01-01T00:00:00+00:00"),
        )
    db.close()
    page.goto(f"{server.base_url}/#/e/{event_id}?k={key}")
    # The redirect lands on the server-rendered ended page: honest, noindex.
    expect(page.locator("h1", has_text="Event ended")).to_be_visible(timeout=10_000)
    assert "noindex" in page.content()
    watcher.expect_clean()


def test_lite_missing_event_id_shows_empty_state(attendee_context, server):
    """C5: #/e/ without an id lands on a friendly empty state, no crash."""
    page = attendee_context.new_page()
    watcher = ConsoleWatcher(page)
    page.goto(f"{server.base_url}/#/e/")
    page.locator(".empty-title, #lite-views .empty").first.wait_for(timeout=10_000)
    watcher.expect_clean()
