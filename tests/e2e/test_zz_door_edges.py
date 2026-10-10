"""Group B door-rejection edges (non-card image, revoked key, rate limit).

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
    att.unlock_by_stego_png(handle.attendee_card_png(key), expect_unlock=False)
    att.page.locator("#join-note:not(:empty)").wait_for(timeout=10_000)
    note = att.join_note().lower()
    assert "invalid" in note or "rate limit" in note, note
    assert att.page.locator("#join-views .ep-title").count() == 0
    org.watcher.expect_clean()
    att.watcher.expect_clean()


def test_non_card_image_is_rejected_cleanly(attendee_context, server):
    """B9: dropping an image that is not a card does nothing harmful — no
    unlock, no console noise, the door just answers with a toast."""
    plain_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
        fh.write(plain_png)
        plain_path = fh.name
    att = AttendeePage(attendee_context.new_page(), server.base_url)
    att.unlock_by_stego_png(plain_path, expect_unlock=False)
    att.page.wait_for_timeout(500)
    assert att.page.locator("#join-views .ep-title").count() == 0
    att.watcher.expect_clean()


def test_door_rate_limits_failure_streak(organizer_context, attendee_context, server):
    """B10: a streak of bad keys ends with the door answering
    'Rate limit exceeded' instead of grinding through every attempt."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Flood Gate", "Enough.")
    att = AttendeePage(attendee_context.new_page(), server.base_url)
    att.drop_until_rate_limited(handle)
    assert att.page.locator("#join-views .ep-title").count() == 0
    org.watcher.expect_clean()
    att.watcher.expect_clean()
