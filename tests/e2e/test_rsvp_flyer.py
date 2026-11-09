"""Group D scenarios (R2b): the funnel shows the event poster and the
organizer's chosen card style reaches the attendee's card. The poster and the
dedicated card art are fetched from unauthenticated RSVP routes."""

import struct
import zlib

import pytest
from pages import AttendeePage, OrganizerPage
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

MEDIA_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _solid_png(rgb: tuple[int, int, int], size: int = 2) -> bytes:
    """A tiny solid-colour PNG so a card preview can be pixel-checked."""
    raw = b"".join(b"\x00" + bytes(rgb) * size for _ in range(size))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


RED_PNG = _solid_png((220, 20, 20))


def _expect_red_preview(page, selector: str) -> None:
    """Sample the centre of a rendered card preview and assert it is the red art."""
    r, g, b, a = page.evaluate(
        """(selector) => {
            const canvas = document.querySelector(selector);
            const ctx = canvas.getContext('2d');
            const d = ctx.getImageData(100, 150, 1, 1).data;
            return [d[0], d[1], d[2], d[3]];
        }""",
        selector,
    )
    assert a > 0 and r > 180 and g < 90 and b < 90, (r, g, b, a)


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
    gets no cover picker of their own, and the rendered preview is the flyer."""
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = organizer.create_event("Card Cover Night", "Flyer on the card.")
    png = tmp_path / "poster.png"
    png.write_bytes(RED_PNG)
    organizer.upload_flyer(png)
    organizer.set_card_style("flyer")
    funnel = organizer.set_gate_settings()
    _expect_red_preview(organizer.page, "#rsvp-card-preview")

    view = organizer.page.request.get(
        f"{server.base_url}/api/events/{handle.event_id}/rsvp/view"
    ).json()
    assert view["event"]["card_style"] == {"type": "flyer"}

    attendee = AttendeePage(attendee_context.new_page(), server.base_url)
    attendee.rsvp(funnel, name="Cover Seeker")
    expect(attendee.page.locator("#card-preview")).to_be_visible()
    expect(attendee.page.locator("#modal-root .cover-chip")).to_have_count(0)
    _expect_red_preview(attendee.page, "#card-preview")
    attendee.watcher.expect_clean()


def test_card_style_mapping_in_the_browser(organizer_context, server):
    """Execute the shipped coverFromCardStyle against every public style."""
    page = organizer_context.new_page()
    page.goto(f"{server.base_url}/#/organize")
    mapping = page.evaluate(
        """() => ({
            none: coverFromCardStyle({ type: "none" }, "evt_1"),
            preset: coverFromCardStyle({ type: "preset", id: "hatch" }, "evt_1"),
            flyer: coverFromCardStyle({ type: "flyer" }, "evt_1"),
            image: coverFromCardStyle(
                { type: "image", url: "/api/events/evt_1/rsvp/card-cover" },
                "evt_1"
            ),
            bogus: coverFromCardStyle({ type: "bogus" }, "evt_1"),
        })"""
    )
    assert mapping == {
        "none": {"type": "none"},
        "preset": {"type": "preset", "id": "hatch"},
        "flyer": {
            "type": "image",
            "url": "/api/events/evt_1/rsvp/flyer",
            "flyer": True,
        },
        "image": {
            "type": "image",
            "url": "/api/events/evt_1/rsvp/card-cover",
        },
        "bogus": {"type": "none"},
    }


def test_flyer_chip_works_before_the_preview_loads(organizer_context, server, tmp_path):
    """Clicking Flyer before its swatch image loads still saves the flyer
    style, not an unknown preset."""
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = organizer.create_event("Slow Flyer", "The chip works before the image lands.")
    png = tmp_path / "poster.png"
    png.write_bytes(RED_PNG)
    organizer.upload_flyer(png)
    # Make the public flyer fetch fail so the chip's swatch never loads.
    organizer.page.route("**/rsvp/flyer", lambda route: route.abort())
    organizer.set_card_style("flyer")

    settings = organizer.page.request.get(
        f"{server.base_url}/api/events/{handle.event_id}/rsvp/settings",
        params={"key": handle.organizer_key},
    ).json()
    assert settings["card_style"] == {"type": "flyer"}


def test_organizer_uploads_dedicated_card_art(
    organizer_context, attendee_context, server, tmp_path
):
    """A dedicated card image is stored separately from the flyer and served
    publicly to attendee browsers."""
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = organizer.create_event("Card Art", "A dedicated card image.")
    png = tmp_path / "art.png"
    png.write_bytes(RED_PNG)
    organizer.upload_card_art(png)
    funnel = organizer.set_gate_settings()
    _expect_red_preview(organizer.page, "#rsvp-card-preview")

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
    _expect_red_preview(attendee.page, "#card-preview")
    attendee.watcher.expect_clean()


def test_organizer_changes_card_style_at_any_time(organizer_context, attendee_context, server):
    """The RSVP tab can save a new style later; the saved chip stays selected
    and a later RSVP renders the new style with no picker."""
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

    funnel = organizer.set_gate_settings()
    attendee = AttendeePage(attendee_context.new_page(), server.base_url)
    attendee.rsvp(funnel, name="Late Guest")
    expect(attendee.page.locator("#card-preview")).to_be_visible()
    expect(attendee.page.locator("#modal-root .cover-chip")).to_have_count(0)
    organizer.watcher.expect_clean()
    attendee.watcher.expect_clean()
