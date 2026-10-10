"""Group A organizer CRUD edges: blocks, media, bulletins, cards, revoke,
decommission, workspace session. Plus the stream of links on the RSVP tab.

Documented non-goal: "delete a content block" (plan A4) has no product
surface — the server exposes no DELETE for content blocks and the workspace
offers no control for it, so there is nothing to drive end-to-end.
"""

import pytest
from pages import AttendeePage, OrganizerPage
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

MEDIA_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_each_block_type_adds_and_renders(organizer_context, server):
    """A3: description / schedule / location blocks each land in the list."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    org.create_event("Block Smorgasbord", "Every field gets its turn.")
    for content_type, payload in [
        ("description", "The long story of the club."),
        ("schedule", "Doors 20:00, last entry 23:00."),
        ("location", "Loading bay B, sublevel 2."),
    ]:
        org.add_content_block(content_type, payload)
    expect(org.page.locator(".item-list .item")).to_have_count(3)
    org.watcher.expect_clean()


def test_media_upload_then_delete(organizer_context, server, tmp_path):
    """A5: a media tile can be uploaded and then deleted via its control."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    org.create_event("Poster Swap", "Pictures on the board.")
    png = tmp_path / "poster.png"
    png.write_bytes(MEDIA_PNG)
    org.upload_media(png)
    expect(org.page.locator(".media-tile")).to_have_count(1)
    org.delete_media_tiles()
    org.tab("media")
    expect(org.page.locator(".media-tile")).to_have_count(0)
    org.watcher.expect_clean()


def test_bulletin_comment_and_cleanup(organizer_context, attendee_context, server):
    """A6: organizer posts, attendee comments, organizer deletes the comment
    and then the whole bulletin; the attendee page reflects both removals."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Cleanup Notice Board", "Housekeeping notes.")
    org.post_bulletin("Victuals", "Soup at noon, bring mugs.")

    key = org.mint_key("Mug Enthusiast")
    att = AttendeePage(attendee_context.new_page(), server.base_url)
    att.unlock_by_stego_png(handle.attendee_card_png(key))
    att.expect_bulletin_visible("Victuals")
    att.comment_on_bulletin("Victuals", "Mug Enthusiast", "See you there")

    org.open_workspace(handle)
    org.delete_first_comment("Victuals")
    org.delete_bulletin("Victuals")

    att.reload_keeps_session()
    expect(att.page.locator("#ep-bulletins .bulletin-card")).to_have_count(0)
    att.watcher.expect_clean()


def test_mint_produces_downloadable_stego_card(organizer_context, server, tmp_path):
    """A7: mint shows the one-time modal and the derived card is a real PNG."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    org.create_event("Card Craft", "Pixels as proof.")
    card = tmp_path / "card-craft.png"
    key = org.mint_key_and_card(card, "Card Guest")
    assert len(key) >= 16, f"minted key looks wrong: {key!r}"
    assert card.stat().st_size > 500  # real stego payload, not an empty file
    assert card.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    org.watcher.expect_clean()


def test_rsvp_funnel_link_is_shareable(organizer_context, server):
    """A8: the RSVP tab exposes the funnel URL and the copy affordance fires."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Funnel Link Check", "Pass it along.")
    url = org.copy_rsvp_link()
    assert f"#/rsvp/{handle.event_id}" in url, url
    org.watcher.expect_clean()


def test_revoke_marks_key_revoked(organizer_context, server):
    """A9: revoking flips the listed key to a Revoked badge."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    org.create_event("Revocation Drill", "Keys come and go.")
    key = org.mint_key("Short Lived")
    org.revoke_key(key)
    org.watcher.expect_clean()


def test_decommission_ends_event_for_everyone(organizer_context, attendee_context, server):
    """A10: decommission revokes all keys; the funnel answers 'Event ended'
    and the attendee's key stops unlocking."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Bonfire Archive", "One good burn.")
    key = org.mint_key("Ashes Guest")
    att = AttendeePage(attendee_context.new_page(), server.base_url)
    att.unlock_by_stego_png(handle.attendee_card_png(key))
    att.expect_event_title("Bonfire Archive")

    org.decommission(handle)

    att.end_session()  # drop the now-useless local session first
    att.unlock_by_stego_png(handle.attendee_card_png(key), expect_unlock=False)
    att.expect_join_note("Invalid key")
    att.page.goto(f"{server.base_url}/#/rsvp/{handle.event_id}")
    expect(att.page.locator(".empty-title", has_text="Event ended")).to_be_visible()
    org.watcher.expect_clean()
    att.watcher.expect_clean()


def test_workspace_session_survives_reload_and_ends_clean(organizer_context, server):
    """A11: reload keeps the organizer session; Close workspace returns to the
    bootstrap form and discards the key from the tab."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = org.create_event("Reload Check", "Persist me.")
    org.reload_restores_workspace(handle)
    org.close_workspace()
    org.watcher.expect_clean()


def test_mint_modal_never_shows_key_text(organizer_context, server):
    """Card-first UX: the one-show modal renders no key text and no copy
    button — the invite card is the only artifact a fresh key gets."""
    org = OrganizerPage(organizer_context.new_page(), server.base_url)
    org.create_event("No Text Please", "Pixels only.")
    org.tab("keys")
    org.page.fill("#key-owner", "Quiet Guest")
    org.page.click("#gen-key-btn")
    org.page.locator("#card-preview").wait_for(state="visible", timeout=10_000)
    assert org.keys.latest(org.page)  # key did arrive — but only on the wire
    expect(org.page.locator("#modal-root .kc-value")).to_have_count(0)
    expect(org.page.locator("#modal-root #key-copy-btn")).to_have_count(0)
    # The one-shot warning moved here with the modal hop removed.
    expect(
        org.page.locator("#modal-root .modal", has_text="destroys the key forever")
    ).to_be_visible()
    org.page.locator('[data-act="cancel"]').click()
    expect(org.page.locator(".ws-banner #ws-copy-key, #ws-copy-key")).to_have_count(0)
    org.watcher.expect_clean()
