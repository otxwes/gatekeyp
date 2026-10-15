"""Group D scenarios (R2b): the funnel shows the event poster and the
attendee's card modal offers the flyer as a cover option. The poster is
fetched from the unauthenticated RSVP flyer route."""

import pytest
from pages import AttendeePage, OrganizerPage
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

MEDIA_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_funnel_shows_event_flyer(organizer_context, attendee_context, server, tmp_path):
    """A flyer the organizer uploads renders on the public RSVP request page."""
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    organizer.create_event("Poster Gala", "Come see the poster.")
    png = tmp_path / "poster.png"
    png.write_bytes(MEDIA_PNG)
    organizer.upload_flyer(png)
    funnel = organizer.set_gate_settings()

    attendee = AttendeePage(attendee_context.new_page(), server.base_url)
    attendee.page.goto(funnel)
    attendee.page.reload()  # hash-only navigations don't re-render the funnel
    attendee.page.locator("#rsvp-form").wait_for(state="visible")
    expect(attendee.page.locator("#rsvp-views img.event-flyer")).to_be_visible()
    organizer.watcher.expect_clean()
    attendee.watcher.expect_clean()


def test_rsvp_card_modal_offers_flyer_cover(organizer_context, attendee_context, server, tmp_path):
    """After an RSVP, the attendee's card modal lists the event flyer as a
    cover chip (resolved from the public flyer route, no organizer session)."""
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    organizer.create_event("Card Cover Night", "Flyer on the card.")
    png = tmp_path / "poster.png"
    png.write_bytes(MEDIA_PNG)
    organizer.upload_flyer(png)
    funnel = organizer.set_gate_settings()

    attendee = AttendeePage(attendee_context.new_page(), server.base_url)
    attendee.rsvp(funnel, name="Cover Seeker")
    expect(attendee.page.locator('#modal-root .cover-chip[data-cover="flyer"]')).to_be_visible()
    attendee.watcher.expect_clean()
