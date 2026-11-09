"""Group D scenarios (R2b): the funnel shows the event poster and the
organizer's chosen card style reaches the attendee's card. The poster and the
dedicated card art are fetched from unauthenticated RSVP routes."""

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


def test_organizer_flyer_style_reaches_attendee_card(
    organizer_context, attendee_context, server, tmp_path
):
    """Selecting Flyer in the RSVP tab styles the attendee's card; the attendee
    gets no cover picker of their own."""
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = organizer.create_event("Card Cover Night", "Flyer on the card.")
    png = tmp_path / "poster.png"
    png.write_bytes(MEDIA_PNG)
    organizer.upload_flyer(png)
    organizer.set_card_style("flyer")
    funnel = organizer.set_gate_settings()

    view = organizer.page.request.get(
        f"{server.base_url}/api/events/{handle.event_id}/rsvp/view"
    ).json()
    assert view["event"]["card_style"] == {"type": "flyer"}

    attendee = AttendeePage(attendee_context.new_page(), server.base_url)
    attendee.rsvp(funnel, name="Cover Seeker")
    expect(attendee.page.locator("#card-preview")).to_be_visible()
    expect(attendee.page.locator("#modal-root .cover-chip")).to_have_count(0)
    attendee.watcher.expect_clean()


def test_organizer_uploads_dedicated_card_art(
    organizer_context, attendee_context, server, tmp_path
):
    """A dedicated card image is stored separately from the flyer and served
    publicly to attendee browsers."""
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = organizer.create_event("Card Art", "A dedicated card image.")
    png = tmp_path / "art.png"
    png.write_bytes(MEDIA_PNG)
    organizer.upload_card_art(png)
    funnel = organizer.set_gate_settings()

    settings = organizer.page.request.get(
        f"{server.base_url}/api/events/{handle.event_id}/rsvp/settings",
        params={"key": handle.organizer_key},
    ).json()
    assert settings["card_style"]["type"] == "image"
    cover_url = settings["card_style"]["url"]
    assert cover_url.endswith("/rsvp/card-cover")
    cover = organizer.page.request.get(f"{server.base_url}{cover_url}")
    assert cover.ok
    assert cover.headers["content-type"] == "image/png"

    attendee = AttendeePage(attendee_context.new_page(), server.base_url)
    attendee.rsvp(funnel, name="Art Seeker")
    expect(attendee.page.locator("#card-preview")).to_be_visible()
    expect(attendee.page.locator("#modal-root .cover-chip")).to_have_count(0)
    attendee.watcher.expect_clean()


def test_organizer_changes_card_style_at_any_time(organizer_context, server):
    """The RSVP tab can save a new style later; the saved chip stays selected."""
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = organizer.create_event("Restyle", "Change it later.")
    organizer.set_card_style("hatch")
    view = organizer.page.request.get(
        f"{server.base_url}/api/events/{handle.event_id}/rsvp/view"
    ).json()
    assert view["event"]["card_style"] == {"type": "preset", "id": "hatch"}

    organizer.set_card_style("dots")
    view = organizer.page.request.get(
        f"{server.base_url}/api/events/{handle.event_id}/rsvp/view"
    ).json()
    assert view["event"]["card_style"] == {"type": "preset", "id": "dots"}

    organizer.tab("board")
    organizer.tab("rsvps")
    expect(
        organizer.page.locator('#rsvp-card-form .cover-chip[data-cover="dots"]')
    ).to_have_attribute("aria-pressed", "true")
    organizer.watcher.expect_clean()
