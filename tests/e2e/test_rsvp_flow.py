"""Group D scenarios: the RSVP interlock — pending keys unlock nothing,
approved keys do, denied keys never do again. Plus the session-injection path
that locks in the content-blocks regression fix."""

import pytest
from pages import AttendeePage, OrganizerPage
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

BLOCK_TEXT = "Arrive before the gates settle."


def test_pending_key_gets_pending_note_attendee_side(organizer_context, attendee_context, server):
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = organizer.create_event("Orchard Walk", "Stroll.")
    organizer.set_gate_settings()  # manual gate
    attendee = AttendeePage(attendee_context.new_page(), server.base_url)
    attendee.rsvp(
        f"{server.base_url}/#/rsvp/{handle.event_id}", name="Orchard Botanist", message="Two spots?"
    )
    key = attendee.rsvp_key()
    attendee.unlock_by_stego_png(handle.attendee_card_png(key), expect_unlock=False)
    attendee.page.locator("#join-note").wait_for(state="visible")
    assert "awaiting" in attendee.page.locator("#join-note").inner_text().lower()
    title = attendee.page.locator("#join-views .ep-title")
    assert title.count() == 0 or not title.first.is_visible()


def test_denied_key_never_opens(organizer_context, attendee_context, server):
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = organizer.create_event("Zine Table", "Fold and staple.")
    organizer.tab("rsvps")
    funnel_url = organizer.set_gate_settings()
    attendee = AttendeePage(attendee_context.new_page(), server.base_url)
    attendee.rsvp(funnel_url, name="Zine Friend")
    key = attendee.rsvp_key()
    organizer.open_workspace(handle)  # fresh reload picks up latest state
    organizer.tab("rsvps")
    organizer.deny_rsvp("Zine Friend")
    attendee.unlock_by_stego_png(handle.attendee_card_png(key), expect_unlock=False)
    # Rejected: stays on the door entry, event page never appears.
    assert attendee.page.locator("#join-views .ep-title").count() == 0
    assert attendee.page.locator("#join-event:not([hidden])").count() == 0


def test_approved_rsvp_unlocks_and_content_blocks_surface(
    organizer_context, attendee_context, server
):
    """The regression lock for the content-blocks-never-rendered bug: approved
    RSVP shortcut 'Open the event now' lazily fetches content blocks."""
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = organizer.create_event("Print Run", "One-night run.")
    del handle  # workspace ref unused: the funnel link drives the flow below
    organizer.add_content_block("logistics", BLOCK_TEXT)
    # Auto-approve 1 means the RSVP result page is already approved, which is
    # the state whose "Open the event now" shortcut skipped blocks (the bug).
    funnel = organizer.set_gate_settings(auto_approve=1)
    attendee = AttendeePage(attendee_context.new_page(), server.base_url)
    attendee.rsvp(funnel, name="Print Pal")
    attendee.unlock_from_rsvp_result()
    attendee.expect_event_title("Print Run")
    # The approved shortcut passes no content_blocks: the lazy fetch must fill
    # them in or the blocks never surface (the bug this locks down).
    attendee.page.locator("#ep-board .item", has_text=BLOCK_TEXT).wait_for(timeout=10_000)
    attendee.watcher.expect_clean()


def test_stego_png_invite_unlock(organizer_context, attendee_context, server, tmp_path):
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    organizer.create_event("Stego Salon", "Pixels as proof.")
    card = tmp_path / "invite.png"
    organizer.mint_key_and_card(card, "Salon Guest")
    assert card.exists() and card.stat().st_size > 0
    attendee = AttendeePage(attendee_context.new_page(), server.base_url)
    attendee.unlock_by_stego_png(card)
    attendee.expect_event_title("Stego Salon")
    attendee.watcher.expect_clean()


def test_queue_row_shows_attendee_message(organizer_context, attendee_context, server):
    """D3: the message an attendee brings is quoted in the queue row."""
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = organizer.create_event("Message Pipe", "Say it with your RSVP.")
    funnel = organizer.set_gate_settings()
    attendee = AttendeePage(attendee_context.new_page(), server.base_url)
    attendee.rsvp(funnel, name="Quote Seeker", message="Bring the big kettle.")
    organizer.open_workspace(handle)
    organizer.tab("board")
    organizer.tab("rsvps")
    row = organizer.page.locator(".key-detail-row", has_text="Quote Seeker")
    expect(row.locator(".kd-msg")).to_contain_text("Bring the big kettle.")
    organizer.watcher.expect_clean()


def test_gate_settings_passphrase_round_trip(organizer_context, attendee_context, server):
    """D7: require a passphrase, see the funnel enforce it, then remove it."""
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = organizer.create_event("Password Parlor", "Knock twice.")
    organizer.tab("board")
    organizer.tab("rsvps")
    organizer.page.locator("#rsvp-pass-on").check()
    organizer.page.fill("#rsvp-pass", "sesame")
    organizer.page.click("#rsvp-settings-btn")
    expect(organizer.page.locator(".toast", has_text="RSVP gate updated.")).to_be_visible()
    funnel = organizer.page.locator(".keycode-full .keycode").inner_text().strip()

    attendee = AttendeePage(attendee_context.new_page(), server.base_url)
    attendee.watcher.allow_http = (400,)  # a wrong passphrase is a 400 by design
    attendee.rsvp(funnel, name="Wrong Knock", passphrase="antlers", expect_success=False)
    attendee.expect_rsvp_note("assphrase")
    attendee.rsvp(funnel, name="Right Knock", passphrase="sesame")
    attendee.rsvp_key()  # key arrives via POST response, not rendered text
    expect(attendee.page.locator("#rsvp-views .kc-value")).to_have_count(0)
    expect(attendee.page.locator("#rsvp-views #rsvp-copy")).to_have_count(0)
    # Untick + save removes the gate again.
    organizer.open_workspace(handle)
    organizer.tab("board")
    organizer.tab("rsvps")
    organizer.page.locator("#rsvp-pass-on").uncheck()
    organizer.page.click("#rsvp-settings-btn")
    expect(organizer.page.locator(".toast", has_text="RSVP gate updated.")).to_be_visible()
    attendee.rsvp(f"{server.base_url}/#/rsvp/{handle.event_id}", name="No Gate Needed")
    organizer.watcher.expect_clean()
    attendee.watcher.expect_clean()


def test_decided_rsvp_row_is_final(organizer_context, attendee_context, server):
    """D8: an approved row shows its decision and no more Approve button —
    the queue can't double-grant."""
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    handle = organizer.create_event("Single Grant", "One yes per friend.")
    funnel = organizer.set_gate_settings()
    attendee = AttendeePage(attendee_context.new_page(), server.base_url)
    attendee.rsvp(funnel, name="Once Only")
    organizer.open_workspace(handle)
    organizer.tab("board")
    organizer.tab("rsvps")
    organizer.approve_rsvp("Once Only")
    organizer.tab("board")
    organizer.tab("rsvps")
    row = organizer.page.locator('.key-detail-row:has-text("Once Only")')
    expect(row.locator(".badge-active")).to_contain_text("Approved")
    expect(row.locator('[data-act="approve"]')).to_have_count(0)
    expect(row.locator(".kd-sub")).to_contain_text("decided")
    organizer.watcher.expect_clean()
