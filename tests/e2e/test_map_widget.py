"""Browser coverage for the tap-to-load directions map."""

import json
import re

import pytest
from pages import AttendeePage, OrganizerPage, wait_event_page
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

MINIMAL_STYLE = {
    "version": 8,
    "sources": {},
    "layers": [
        {
            "id": "bg",
            "type": "background",
            "paint": {"background-color": "#111"},
        }
    ],
}
STYLE_URL = "https://tiles.openfreemap.org/styles/dark"


def _intercept_style(page) -> None:
    """Serve a minimal MapLibre style so the suite never hits OpenFreeMap."""
    page.route(
        STYLE_URL,
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(MINIMAL_STYLE),
        ),
    )


def _open_attendee(org: OrganizerPage, attendee_context, server, handle):
    key = org.mint_key("Map Guest")
    att = AttendeePage(attendee_context.new_page(), server.base_url)
    att.unlock_by_stego_png(handle.attendee_card_png(key))
    return att


def test_standard_event_map_is_tap_to_load(organizer_context, attendee_context, server):
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Mapped Standard", "Directions.", location="Main St")
    att = _open_attendee(org, attendee_context, server, handle)

    expect(att.page.locator(".ep-meta")).to_have_text("Main St")
    expect(att.page.locator("[data-gatekeyp-map]")).to_be_visible()
    expect(att.page.locator(".event-map-load")).to_have_text("Show map")

    third_party = []
    att.page.on(
        "request",
        lambda request: (
            third_party.append(request.url) if "tiles.openfreemap.org" in request.url else None
        ),
    )
    assert third_party == []

    _intercept_style(att.page)
    att.page.locator(".event-map-load").click()
    expect(att.page.locator(".maplibregl-canvas")).to_be_visible()
    expect(att.page.locator(".event-map-load")).to_be_hidden()
    att.watcher.expect_clean()


def test_map_has_single_open_map_button(organizer_context, attendee_context, server):
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Mapped Links", "Directions.", location="Main St")
    att = _open_attendee(org, attendee_context, server, handle)

    link = att.page.locator(".event-map-links a")
    expect(link).to_have_count(1)
    expect(link).to_have_text("Open map")
    assert "btn" in (link.get_attribute("class") or "")
    href = link.get_attribute("href")
    assert "openstreetmap.org" in href and "mlat=40.75" in href and "mlon=-73.98" in href
    expect(att.page.locator("[data-copy-address]")).to_have_count(0)
    expect(att.page.locator(".event-map-links", has_text="Organic Maps")).to_have_count(0)
    expect(att.page.locator(".event-map-links", has_text="OsmAnd")).to_have_count(0)
    att.watcher.expect_clean()


def test_map_off_hides_card_but_keeps_links(organizer_context, attendee_context, server):
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event(
        "No Map Standard", "Directions without a map.", location="Main St", show_map=False
    )
    att = _open_attendee(org, attendee_context, server, handle)

    expect(att.page.locator("[data-gatekeyp-map]")).to_have_count(0)
    expect(att.page.locator(".event-map-load")).to_have_count(0)
    expect(att.page.locator(".event-map-links a", has_text="Open map")).to_have_attribute(
        "href", re.compile("openstreetmap.org/search")
    )
    expect(att.page.locator("[data-copy-address]")).to_have_count(0)
    att.watcher.expect_clean()


def test_geocode_failure_falls_back_to_osm_search(organizer_context, attendee_context, server):
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Nowhere Map", "Geocode failure.", location="nowhere")
    att = _open_attendee(org, attendee_context, server, handle)

    expect(att.page.locator("[data-gatekeyp-map]")).to_have_count(0)
    expect(att.page.locator(".event-map-links a", has_text="Open map")).to_have_attribute(
        "href", re.compile("openstreetmap.org/search")
    )
    att.watcher.expect_clean()


def test_map_load_failure_shows_unavailable(organizer_context, attendee_context, server):
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Broken Map", "Style failure.", location="Main St")
    att = _open_attendee(org, attendee_context, server, handle)

    att.page.route(STYLE_URL, lambda route: route.abort())
    att.page.locator(".event-map-load").click()
    expect(att.page.locator(".event-map-load")).to_have_text("Map unavailable")
    expect(att.page.locator(".event-map-load")).to_be_visible()
    expect(att.page.locator(".event-map-links a", has_text="Open map")).to_be_visible()


def test_map_hang_shows_unavailable_after_watchdog(organizer_context, attendee_context, server):
    """A style request that never answers (VPN/DNS blackhole) must not leave
    the card silently blank: the button hides while the map initializes, so a
    watchdog has to flip the card back to a disabled "Map unavailable"."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Hung Map", "Style hangs.", location="Main St")
    att = _open_attendee(org, attendee_context, server, handle)

    att.page.route(STYLE_URL, lambda *_: None)  # intercepted, never resolved
    att.page.locator(".event-map-load").click()
    expect(att.page.locator(".event-map-load")).to_have_text("Map unavailable", timeout=15_000)
    expect(att.page.locator(".event-map-load")).to_be_visible()
    expect(att.page.locator(".event-map-load")).to_be_disabled()
    expect(att.page.locator(".event-map-links a", has_text="Open map")).to_be_visible()


def test_map_canvas_fills_the_card(organizer_context, attendee_context, server):
    """The MapLibre container must keep the card's height after its stylesheet
    loads: maplibre-gl.css sets `.maplibregl-map { position: relative }` on the
    same element, which cancels `inset: 0` and collapsed the container to 0px
    (the map then painted only the style background — an empty dark card)."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Sized Map", "Geometry.", location="Main St")
    att = _open_attendee(org, attendee_context, server, handle)

    _intercept_style(att.page)
    att.page.locator(".event-map-load").click()
    expect(att.page.locator(".maplibregl-canvas")).to_be_visible()
    att.page.wait_for_timeout(500)

    figure = att.page.locator(".event-map").bounding_box()
    wrapper = att.page.locator(".event-map-canvas").bounding_box()
    canvas = att.page.locator(".maplibregl-canvas").bounding_box()
    assert wrapper["height"] > 150, f"container collapsed: {wrapper}"
    assert abs(canvas["height"] - wrapper["height"]) < 2, f"canvas {canvas} vs wrapper {wrapper}"
    assert canvas["height"] <= figure["height"] + 1, f"canvas overflows the card: {canvas}"


def test_missing_widget_marks_map_unavailable(organizer_context, attendee_context, server):
    """A stale cached index.html (widget script never arrives) must not leave
    an inert "Show map" button — the app marks the card unavailable instead
    of silently skipping the mount."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Stale Widget", "Widget missing.", location="Main St")
    key = org.mint_key("Map Guest")
    att = AttendeePage(attendee_context.new_page(), server.base_url)
    att.page.route("**/map_widget.js", lambda route: route.abort())
    att.unlock_by_stego_png(handle.attendee_card_png(key))

    expect(att.page.locator(".event-map-load")).to_have_text("Map unavailable")
    expect(att.page.locator(".event-map-load")).to_be_disabled()
    expect(att.page.locator(".event-map-links a", has_text="Open map")).to_be_visible()


def test_lite_page_renders_map_widget(organizer_context, server):
    page = organizer_context.new_page()
    page.goto(f"{server.base_url}/#/flyer")
    page.fill("#flyer-title", "Mapped Lite")
    page.fill("#flyer-description", "Public directions.")
    page.fill("#flyer-when", "2030-01-01T20:00")
    page.fill("#flyer-where", "Main St")
    page.click("#flyer-btn")
    page.locator("#modal-root .modal").wait_for(timeout=10_000)
    with page.expect_download() as download:
        page.locator('[data-act="confirm"]').click()
    assert download.value.suggested_filename.endswith("organizer card.png")
    page.locator("#flyer-done").wait_for(state="visible")
    public_url = page.locator("#flyer-done code").inner_text().strip()

    page.goto(public_url)
    expect(page.locator("[data-gatekeyp-map]")).to_be_visible()
    expect(page.locator(".event-map-load")).to_have_text("Show map")
    expect(page.locator(".event-map-links a")).to_have_text("Open map")
    expect(page.locator('meta[name="referrer"]')).to_have_attribute("content", "no-referrer")
    _intercept_style(page)
    page.locator(".event-map-load").click()
    expect(page.locator(".maplibregl-canvas")).to_be_visible()
    page.wait_for_timeout(500)
    # Same container-collapse guard as the SPA page: the lite inline CSS must
    # keep the card height after maplibre-gl.css sets position: relative.
    wrapper = page.locator(".event-map-canvas").bounding_box()
    canvas = page.locator(".maplibregl-canvas").bounding_box()
    assert wrapper["height"] > 150, f"lite container collapsed: {wrapper}"
    assert abs(canvas["height"] - wrapper["height"]) < 2, f"canvas {canvas} vs wrapper {wrapper}"


def test_lite_map_off_hides_card_but_keeps_links(organizer_context, server):
    page = organizer_context.new_page()
    page.goto(f"{server.base_url}/#/flyer")
    page.fill("#flyer-title", "No Map Lite")
    page.fill("#flyer-description", "Public directions.")
    page.fill("#flyer-when", "2030-01-01T20:00")
    page.fill("#flyer-where", "Main St")
    page.uncheck("#flyer-show-map")
    page.click("#flyer-btn")
    page.locator("#modal-root .modal").wait_for(timeout=10_000)
    with page.expect_download() as download:
        page.locator('[data-act="confirm"]').click()
    assert download.value.suggested_filename.endswith("organizer card.png")
    page.locator("#flyer-done").wait_for(state="visible")
    public_url = page.locator("#flyer-done code").inner_text().strip()

    page.goto(public_url)
    expect(page.locator("[data-gatekeyp-map]")).to_have_count(0)
    expect(page.locator(".event-map-load")).to_have_count(0)
    expect(page.locator(".event-map-links a", has_text="Open map")).to_have_attribute(
        "href", re.compile("openstreetmap.org/search")
    )
    expect(page.locator("[data-copy-address]")).to_have_count(0)


def test_workspace_toggle_updates_attendee_page(organizer_context, attendee_context, server):
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Toggle Map", "Directions.", location="Main St")
    att = _open_attendee(org, attendee_context, server, handle)
    expect(att.page.locator("[data-gatekeyp-map]")).to_be_visible()

    toggle = org.page.locator("#ws-map-toggle")
    expect(toggle).to_be_enabled()
    with org.page.expect_response(
        lambda response: response.url.endswith("/map") and response.request.method == "POST"
    ) as off_response:
        toggle.uncheck()
    assert off_response.value.json()["show_map"] is False

    att.page.reload()
    wait_event_page(att.page)
    expect(att.page.locator("[data-gatekeyp-map]")).to_have_count(0)
    expect(att.page.locator(".event-map-links a", has_text="Open map")).to_be_visible()

    with org.page.expect_response(
        lambda response: response.url.endswith("/map") and response.request.method == "POST"
    ) as on_response:
        toggle.check()
    assert on_response.value.json()["show_map"] is True

    att.page.reload()
    wait_event_page(att.page)
    expect(att.page.locator("[data-gatekeyp-map]")).to_be_visible()
    att.watcher.expect_clean()


def test_no_referrer_header_and_meta(organizer_context, server):
    page = organizer_context.new_page()
    response = page.request.get(f"{server.base_url}/health")
    assert response.headers["referrer-policy"] == "no-referrer"
    page.goto(server.base_url)
    expect(page.locator('meta[name="referrer"]')).to_have_attribute("content", "no-referrer")
