"""Group B door-rejection edges (invalid-form paste, revoked key, rate limit).

The server fixture is function-scoped, so each scenario here gets its own
pristine limiter bucket; ordering no longer matters.
"""

import pytest
from pages import AttendeePage, OrganizerPage

pytestmark = pytest.mark.e2e


def test_revoked_key_rejected_by_door(organizer_context, attendee_context, server):
    """B8: a minted-then-revoked key no longer unlocks."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Chalk Circle", "Rubbed out.")
    key = org.mint_key("Revoked Guest")
    org.revoke_key(key)

    att = AttendeePage(attendee_context.new_page(), server.base_url)
    att.unlock_by_keyline(handle.attendee_keyline(key), expect_unlock=False)
    att.page.locator("#join-note:not(:empty)").wait_for(timeout=10_000)
    note = att.join_note().lower()
    assert "invalid" in note or "rate limit" in note, note
    assert att.page.locator("#join-views .ep-title").count() == 0
    org.watcher.expect_clean()
    att.watcher.expect_clean()


def test_malformed_paste_is_ignored_by_door(attendee_context, server):
    """B9: pasting non-keyline text does nothing harmful — no unlock, no
    console noise, the door just stays put."""
    att = AttendeePage(attendee_context.new_page(), server.base_url)
    att.unlock_by_keyline("definitely not a keyline, just some prose", expect_unlock=False)
    att.page.wait_for_timeout(500)
    assert att.page.locator("#join-event:not([hidden])").count() == 0
    assert att.page.locator("#join-views .ep-title").count() == 0
    att.watcher.expect_clean()


def test_door_rate_limits_failure_streak(organizer_context, attendee_context, server):
    """B10: a streak of bad keys ends with the door answering
    'Rate limit exceeded' instead of grinding through every attempt."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Flood Gate", "Enough.")
    att = AttendeePage(attendee_context.new_page(), server.base_url)
    att.paste_until_rate_limited(handle)
    assert att.page.locator("#join-views .ep-title").count() == 0
    org.watcher.expect_clean()
    att.watcher.expect_clean()
