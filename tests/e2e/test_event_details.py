"""Round 8 Phase A: the organizer edits event details and hides fields; the
attendee page renders only what is visible, and the hidden values are absent
from the `/api/access` payload itself (proven at the network level)."""

import pytest
from pages import AttendeePage, OrganizerPage
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _save_details(org: OrganizerPage, **fields: object) -> None:
    org.tab("details")
    fills = {
        "title": "#details-title",
        "description": "#details-description",
        "location": "#details-location",
        "date": "#details-date",
        "time": "#details-time",
        "timezone": "#details-timezone",
    }
    for name, selector in fills.items():
        if name in fields:
            org.page.fill(selector, fields[name])
    toggles = {
        "show_description": "#details-show-description",
        "show_location": "#details-show-location",
        "show_date": "#details-show-date",
        "show_time": "#details-show-time",
    }
    for name, selector in toggles.items():
        if name not in fields:
            continue
        if fields[name]:
            org.page.check(selector)
        else:
            org.page.uncheck(selector)
    org.page.click("#details-save")
    expect(org.page.locator(".toast", has_text="Event details saved.")).to_be_visible()


def _access_payload(page, key: str, event_id: str) -> dict:
    """Call the gateway from the browser and return the event data dict."""
    return page.evaluate(
        """async ([key, eventId]) => {
            const resp = await fetch('/api/access', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key, content_id: eventId }),
            });
            const body = await resp.json();
            return body.data;
        }""",
        [key, event_id],
    )


def test_organizer_edits_details_and_hides_fields(organizer_context, attendee_context, server):
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Draft Gathering", "Original plan", location="Old Hall")

    _save_details(
        org,
        title="Renamed Gathering",
        description="Secret plan",
        location="Secret Hall",
        date="2026-12-31",
        time="19:30",
        timezone="EST",
        show_description=False,
        show_location=False,
    )
    expect(org.page.locator(".ws-title")).to_have_text("Renamed Gathering")

    # The organizer key still sees everything on the wire.
    organizer_view = org.page.evaluate(
        """async ([key, eventId]) => {
            const resp = await fetch('/api/access', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key, content_id: eventId }),
            });
            return (await resp.json()).data;
        }""",
        [handle.organizer_key, handle.event_id],
    )
    assert organizer_view["description"] == "Secret plan"
    assert organizer_view["location_data"] == "Secret Hall"
    assert organizer_view["event_date"] == "2026-12-31"

    key = org.mint_key("Details Guest")
    att = AttendeePage(attendee_context.new_page(), server.base_url)
    att.unlock_by_stego_png(handle.attendee_card_png(key))
    page = att.page

    att.expect_event_title("Renamed Gathering")
    expect(page.locator(".ep-when")).to_have_text("2026-12-31 · 19:30 EST")
    expect(page.locator("#ep-location")).to_be_empty()

    # Network level: the hidden values are absent from the API response, not
    # merely hidden by CSS.
    data = _access_payload(page, key, handle.event_id)
    assert "description" not in data
    assert "location_data" not in data
    assert "location_lat" not in data
    assert "map_style_url" not in data
    assert data["title"] == "Renamed Gathering"
    assert data["event_date"] == "2026-12-31"
    assert data["event_time"] == "19:30"
    assert data["event_timezone"] == "EST"
    att.watcher.expect_clean()


def test_hiding_time_hides_timezone_and_date(organizer_context, attendee_context, server):
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Timed Gathering", "Visible plan", location="Town Hall")

    _save_details(
        org,
        date="2026-12-31",
        time="19:30",
        timezone="EST",
        show_time=False,
        show_date=False,
    )

    key = org.mint_key("Timed Guest")
    att = AttendeePage(attendee_context.new_page(), server.base_url)
    att.unlock_by_stego_png(handle.attendee_card_png(key))
    page = att.page

    att.expect_event_title("Timed Gathering")
    expect(page.locator(".ep-when")).to_have_count(0)

    data = _access_payload(page, key, handle.event_id)
    assert "event_time" not in data
    assert "event_timezone" not in data
    assert "event_date" not in data
    # The description was never hidden, so it stays.
    assert data["description"] == "Visible plan"
    att.watcher.expect_clean()


def test_details_survive_workspace_reload(organizer_context, server):
    """Saved fields come back when the organizer re-enters the workspace."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Persisted Gathering", "Start", location="Old Hall")
    _save_details(org, description="Edited description", date="2027-01-02")

    org.open_workspace(handle)
    org.tab("details")
    expect(org.page.locator("#details-description")).to_have_value("Edited description")
    expect(org.page.locator("#details-date")).to_have_value("2027-01-02")
    org.watcher.expect_clean()


def test_create_form_accepts_schedule_fields(organizer_context, attendee_context, server):
    """Date, time, and timezone can be set on the create form, not just edited
    afterwards, and reach the attendee page."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event(
        "Created With Schedule",
        "Made in one step",
        date="2027-02-14",
        time="20:00",
        timezone="PST",
    )

    key = org.mint_key("Schedule Guest")
    att = AttendeePage(attendee_context.new_page(), server.base_url)
    att.unlock_by_stego_png(handle.attendee_card_png(key))
    att.expect_event_title("Created With Schedule")
    expect(att.page.locator(".ep-when")).to_have_text("2027-02-14 · 20:00 PST")

    data = _access_payload(att.page, key, handle.event_id)
    assert data["event_date"] == "2027-02-14"
    assert data["event_time"] == "20:00"
    assert data["event_timezone"] == "PST"
    att.watcher.expect_clean()


def test_visibility_toggles_sit_under_their_fields(organizer_context, server):
    """Each show/hide toggle follows the field it controls, not a shared row."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    org.create_event("Order Check", "Checkbox order")
    org.tab("details")
    org.page.locator("#details-form").wait_for(state="visible")

    tops = org.page.evaluate(
        """() => {
            const ids = [
              'details-description', 'details-show-description',
              'details-location', 'details-show-location',
              'details-date', 'details-show-date',
              'details-time', 'details-timezone', 'details-show-time',
            ];
            const out = {};
            for (const id of ids) {
              const el = document.getElementById(id);
              out[id] = el.getBoundingClientRect().top;
            }
            return out;
        }"""
    )
    assert tops["details-description"] < tops["details-show-description"] < tops["details-location"]
    assert tops["details-location"] < tops["details-show-location"] < tops["details-date"]
    assert tops["details-date"] < tops["details-show-date"] < tops["details-time"]
    assert tops["details-time"] < tops["details-timezone"] < tops["details-show-time"]
    org.watcher.expect_clean()
