"""Save-flow: iOS gets a single "Save to Photos" action through the native
share sheet (its "Save Image" lands the card in the photo library). Every
other platform — including desktop browsers whose Web Share API supports
files — gets the plain "Download card" confirm, which downloads the PNG
directly instead of opening the mobile-style share sheet."""

import pytest
from pages import AttendeePage, OrganizerPage
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

SHARE_OK = (
    "Object.defineProperty(navigator,'canShare',{value:()=>true,configurable:true});"
    "Object.defineProperty(navigator,'share',{value:(d)=>{window.__shared=d;"
    "return Promise.resolve();},configurable:true});"
)
SHARE_ABORT = (
    "Object.defineProperty(navigator,'canShare',{value:()=>true,configurable:true});"
    "Object.defineProperty(navigator,'share',{value:()=>Promise.reject("
    "Object.assign(new Error('cancelled'),{name:'AbortError'})),configurable:true});"
)
SHARE_OFF = "Object.defineProperty(navigator,'canShare',{value:()=>false,configurable:true});"


def test_rsvp_card_share_primary_save_to_photos(
    browser, organizer_context, attendee_context, server
):
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    organizer.create_event("Photo Flow", "The card goes to the library.")
    funnel = organizer.set_gate_settings()
    page = browser.new_context(user_agent=IPHONE_UA).new_page()
    page.add_init_script(SHARE_OK)
    attendee = AttendeePage(page, server.base_url)
    attendee.rsvp(funnel, name="Photo Pal")
    # The dialog's single action is Save to Photos in the modal body: no
    # redundant local download, no bottom confirm row.
    save_btn = page.locator('#modal-root [data-act="save-share"]')
    expect(save_btn).to_have_text("Save to Photos")
    expect(page.locator('#modal-root [data-act="download-files"]')).to_have_count(0)
    order = page.evaluate(
        """[...document.querySelectorAll('#modal-root .modal-body [data-act]')]
           .map((b) => b.dataset.act)"""
    )
    assert order == ["save-share"], f"unexpected action order: {order}"
    expect(page.locator('#modal-root [data-act="confirm"]')).to_have_count(0)
    save_btn.click()
    # The confirm path renders the card and embeds the payload asynchronously;
    # the "saved" toast is the app's completion signal for the share call.
    expect(page.locator(".toast", has_text="Invite card saved.")).to_be_visible(timeout=15_000)
    shared = page.evaluate(
        "({name: window.__shared.files[0].name, type: window.__shared.files[0].type})"
    )
    assert shared["type"] == "image/png"
    assert shared["name"].endswith("invite.png"), f"unexpected share file name: {shared['name']}"


def test_desktop_share_capable_downloads_directly(
    browser, organizer_context, attendee_context, server
):
    """Desktop Chrome reports a file-capable Web Share API, but the share
    sheet is the wrong UX there — the card must download as a plain PNG."""
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    organizer.create_event("Desktop Flow", "Direct download on desktop.")
    funnel = organizer.set_gate_settings()
    page = browser.new_context().new_page()
    page.add_init_script(SHARE_OK)  # canShare/share exist, as in desktop Chrome
    attendee = AttendeePage(page, server.base_url)
    attendee.rsvp(funnel, name="Desktop Pal")

    expect(page.locator('#modal-root [data-act="save-share"]')).to_have_count(0)
    confirm = page.locator('#modal-root [data-act="confirm"]')
    expect(confirm).to_have_text("Download card")
    with page.expect_download() as dl:
        confirm.click()
    assert dl.value.suggested_filename.endswith("invite.png")


def test_card_modal_share_abort_keeps_modal(browser, organizer_context, attendee_context, server):
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    organizer.create_event("Abort Flow", "Sheet dismissed is not an error.")
    funnel = organizer.set_gate_settings()
    page = browser.new_context(user_agent=IPHONE_UA).new_page()
    page.add_init_script(SHARE_ABORT)
    attendee = AttendeePage(page, server.base_url)
    attendee.rsvp(funnel, name="Swipe Away")
    save_btn = page.locator('#modal-root [data-act="save-share"]')
    expect(save_btn).to_have_text("Save to Photos")  # iOS share label
    save_btn.click()
    # Sheet dismissed (AbortError): the locked modal stays (no cancel or close
    # button to fall back on), the button re-enables, no error toast.
    expect(save_btn).to_be_visible()
    expect(save_btn).to_have_text("Save to Photos")
    expect(page.locator('#modal-root [data-act="cancel"]')).to_have_count(0)
    expect(page.locator("#modal-root .modal-close")).to_have_count(0)
    expect(page.locator(".toast", has_text="Could not complete")).to_have_count(0)


def test_card_modal_no_share_keeps_download(organizer_context, attendee_context, server):
    organizer = OrganizerPage(organizer_context.new_page(), server.base_url)
    organizer.create_event("Plain Flow", "No share API, unchanged.")
    funnel = organizer.set_gate_settings()
    page = attendee_context.new_page()
    page.add_init_script(SHARE_OFF)
    attendee = AttendeePage(page, server.base_url)
    attendee.rsvp(funnel, name="Plain Pal")
    confirm = page.locator('#modal-root [data-act="confirm"]')
    expect(confirm).to_have_text("Download card")
    expect(page.locator('#modal-root [data-act="download-files"]')).to_have_count(0)
    with page.expect_download() as dl:
        confirm.click()
    assert dl.value.suggested_filename.endswith("invite.png")
