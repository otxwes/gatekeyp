"""Browser coverage for the transit directions widget (standard + lite)."""

import pytest
from pages import AttendeePage, OrganizerPage, wait_event_page
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _open_attendee(org: OrganizerPage, attendee_context, server, handle):
    key = org.mint_key("Dir Guest")
    att = AttendeePage(attendee_context.new_page(), server.base_url)
    att.unlock_by_stego_png(handle.attendee_card_png(key))
    return att


def _lite_event(organizer_context, server) -> str:
    """Create a lite event and return its public /i/{id} URL."""
    page = organizer_context.new_page()
    page.goto(f"{server.base_url}/#/flyer")
    page.fill("#flyer-title", "Route Lite")
    page.fill("#flyer-description", "Public directions.")
    page.fill("#flyer-when", "2030-01-01T20:00")
    page.fill("#flyer-where", "Main St")
    page.click("#flyer-btn")
    page.locator("#modal-root .modal").wait_for(timeout=10_000)
    with page.expect_download():
        page.locator('[data-act="confirm"]').click()
    page.locator("#flyer-done").wait_for(state="visible")
    return page.locator("#flyer-done code").inner_text().strip()


def test_standard_event_directions_render(organizer_context, attendee_context, server):
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Route Stand", "Directions.", location="Main St")
    att = _open_attendee(org, attendee_context, server, handle)

    form = att.page.locator(".dir-form")
    expect(form).to_be_visible()
    expect(att.page.locator(".dir-label")).to_have_text("From")
    expect(att.page.locator(".dir-submit")).to_have_text("Get directions")

    # No request before submit (§7.5).
    requested = []
    att.page.on(
        "request",
        lambda request: requested.append(request.url) if "/api/directions" in request.url else None,
    )

    att.page.fill(".dir-input", "Bedford Av subway")
    att.page.click(".dir-submit")

    result = att.page.locator(".dir-result")
    expect(result).to_contain_text("35 min")
    expect(result).to_contain_text("18:30")
    expect(result).to_contain_text("19:05")
    expect(result).to_contain_text("L Canarsie Rockaway Pkwy")
    legs = att.page.locator(".dir-legs .dir-leg")
    expect(legs.first).to_contain_text("Walk 4 min")
    expect(legs.nth(1)).to_contain_text("Bedford Av → 1 Av")
    expect(result).to_contain_text("Transit data © MTA")
    expect(att.page.locator(".event-map-links a", has_text="Open map")).to_be_visible()
    att.watcher.expect_clean()

    # Submit issued exactly one directions request; none was made on load.
    assert len([u for u in requested if "/api/directions" in u]) == 1


def test_directions_failure_keeps_open_map(organizer_context, attendee_context, server, mock_otp):
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Route Down", "OTP failure.", location="Main St")
    att = _open_attendee(org, attendee_context, server, handle)
    att.watcher.allow_http = (500, 503)  # the drill
    mock_otp.fail = True

    att.page.locator(".dir-form").wait_for(state="visible")
    att.page.fill(".dir-input", "Bedford Av subway")
    att.page.click(".dir-submit")

    expect(att.page.locator(".dir-error")).to_have_text("Directions unavailable right now.")
    expect(att.page.locator(".event-map-links a", has_text="Open map")).to_be_visible()
    expect(att.page.locator(".dir-result .dir-itin")).to_have_count(0)


def test_directions_restore_from_local_storage(organizer_context, attendee_context, server):
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Route Persist", "Local storage.", location="Main St")
    att = _open_attendee(org, attendee_context, server, handle)

    att.page.fill(".dir-input", "Bedford Av subway")
    att.page.click(".dir-submit")
    result = att.page.locator(".dir-result")
    expect(result).to_contain_text("35 min")

    att.page.reload()
    wait_event_page(att.page)
    expect(att.page.locator(".dir-result")).to_contain_text("35 min")
    expect(att.page.locator(".dir-result")).to_contain_text("L Canarsie Rockaway Pkwy")
    expect(att.page.locator(".dir-input")).to_have_value("Bedford Av subway")
    expect(att.page.locator(".dir-clear", has_text="Clear")).to_be_visible()

    att.page.locator(".dir-clear").click()
    expect(att.page.locator(".dir-result .dir-itin")).to_have_count(0)

    # A later reload stays clear (the store entry was really removed).
    att.page.reload()
    wait_event_page(att.page)
    expect(att.page.locator(".dir-result .dir-itin")).to_have_count(0)
    att.watcher.expect_clean()


def test_map_off_hides_directions(organizer_context, attendee_context, server):
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event(
        "No Map No Dir", "Directions without a map.", location="Main St", show_map=False
    )
    att = _open_attendee(org, attendee_context, server, handle)

    expect(att.page.locator("[data-gatekeyp-directions]")).to_have_count(0)
    expect(att.page.locator(".dir-form")).to_have_count(0)
    expect(att.page.locator(".event-map-links a", has_text="Open map")).to_be_visible()
    att.watcher.expect_clean()


def test_lite_page_directions_render(organizer_context, server):
    public_url = _lite_event(organizer_context, server)
    page = organizer_context.new_page()
    page.goto(public_url)

    expect(page.locator("[data-gatekeyp-directions]")).to_be_visible()
    expect(page.locator('script[src="/directions.js"]')).to_have_count(1)
    expect(page.locator('meta[name="referrer"]')).to_have_attribute("content", "no-referrer")

    page.fill(".dir-input", "Bedford Av subway")
    page.click(".dir-submit")
    result = page.locator(".dir-result")
    expect(result).to_contain_text("35 min")
    expect(result).to_contain_text("L Canarsie Rockaway Pkwy")
    expect(page.locator(".event-map-links a", has_text="Open map")).to_be_visible()
