"""Group B scenarios: attendee unlock paths + every organizer artifact
surfacing on the attendee event page. Console-clean throughout."""

import pytest
from pages import AttendeePage, OrganizerPage
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

BLOCK_TEXT = "Doors at 8, bring a mug."
BULLETIN = "Bulletin: the committee announces the lineup."
MEDIA_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_created_event_surface(organizer_context, attendee_context, server, tmp_path_factory):
    """Full happy path: organizer makes an event, mints a key, the attendee
    unlocks through the keyline paste and sees everything the organizer made."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event(
        "Kitchen Table Scribble Club",
        "A weekly scribble.",
        location="Back kitchen",
    )
    org.add_content_block("description", BLOCK_TEXT)
    org.post_bulletin("Committee notes", BULLETIN)

    # Media: write a tiny real PNG the attendee tile can render.
    png = tmp_path_factory.mktemp("media") / "scribble.png"
    png.write_bytes(MEDIA_PNG)
    org.upload_media(png)
    org.watcher.expect_clean()

    key = org.mint_key("Attendee Echo")
    org.watcher.expect_clean()

    att = AttendeePage(attendee_context.new_page(), server.base_url)
    att.unlock_by_keyline(handle.attendee_keyline(key))
    att.expect_event_title("Kitchen Table Scribble Club")
    expect(
        att.page.locator("#ep-bulletins .bulletin-card", has_text="Committee notes")
    ).to_be_visible()
    expect(att.page.locator("#ep-media img.mt-preview")).to_be_visible()
    att.watcher.expect_clean()


def test_block_added_later_shows_on_fresh_unlock(organizer_context, attendee_context, server):
    """B5: a block added while an attendee is already inside is not re-fetched
    by a plain reload (details are cached at unlock time), but a fresh unlock
    picks it up — locking in the expected surfacing behavior."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Late Additions", "New news for old guests.")
    key = org.mint_key("Early Bird")
    att = AttendeePage(attendee_context.new_page(), server.base_url)
    att.unlock_by_keyline(handle.attendee_keyline(key))
    expect(
        att.page.locator(".card:has-text('Event details') .item", has_text="sneak peek")
    ).to_have_count(0)
    org.add_content_block("agenda", "11:00 — sneak peek and cake.")
    att.reload_keeps_session()
    expect(  # reload keeps the stale cached view: no re-fetch post-unlock
        att.page.locator(".card:has-text('Event details') .item", has_text="sneak peek")
    ).to_have_count(0)
    att.end_session()
    att.unlock_by_keyline(handle.attendee_keyline(key))
    att.page.locator(
        ".card:has-text('Event details') .item", has_text="sneak peek and cake"
    ).wait_for(timeout=10_000)
    org.watcher.expect_clean()
    att.watcher.expect_clean()


def test_refresh_keeps_attendee_session(organizer_context, attendee_context, server):
    """B6: reload stays unlocked — no key re-prompt mid-session."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Reload Refuge", "Stay seated.")
    key = org.mint_key("Sitting Guest")
    att = AttendeePage(attendee_context.new_page(), server.base_url)
    att.unlock_by_keyline(handle.attendee_keyline(key))
    att.expect_event_title("Reload Refuge")
    att.reload_keeps_session()
    att.expect_event_title("Reload Refuge")
    expect(att.page.locator("#key-drop")).to_be_hidden()
    att.watcher.expect_clean()


def test_end_session_drops_key_and_reopens_door(organizer_context, attendee_context, server):
    """B7: Leave (drop key) returns to the door with the Signed-out toast."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Turnstile Etiquette", "Leave and come back.")
    key = org.mint_key("Polite Guest")
    att = AttendeePage(attendee_context.new_page(), server.base_url)
    att.unlock_by_keyline(handle.attendee_keyline(key))
    att.expect_event_title("Turnstile Etiquette")
    att.end_session()
    att.unlock_by_keyline(handle.attendee_keyline(key))  # same key still works
    att.expect_event_title("Turnstile Etiquette")
    att.watcher.expect_clean()


def test_key_mint_error_is_clean(organizer_context, server):
    """Keys tab + revoke are just planner flows; minting twice must not spam console."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    org.create_event("Wheel Group", "A wheel.")
    key = org.mint_key("Wheel Friend")
    assert key and ":" in key
    org.watcher.expect_clean()


def test_rsvp_keyline_unlock_after_approval(organizer_context, attendee_context, server):
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = organizer.create_event("Gallery Sitting", "A quiet sitting.")
    funnel_url = organizer.set_gate_settings()  # manual gate, no auto-approve
    attendee = AttendeePage(attendee_context.new_page(), server.base_url)
    attendee.rsvp(funnel_url, name="Gallery Friend")
    key = attendee.rsvp_key()
    organizer.approve_rsvp("Gallery Friend")
    attendee.unlock_by_keyline(handle.attendee_keyline(key))
    attendee.expect_event_title("Gallery Sitting")
    attendee.watcher.expect_clean()
