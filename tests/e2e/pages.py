"""Page objects + console watcher for the gatekeyp end-to-end suite.

Selectors pin the real rendered UI (see `web/app.js` / `web/index.html`):
organizer bus routes through `#/organize`, the door through `#/join`, the
public funnel through `#/rsvp/{event_id}`, lite events through `#/e/{id}`.
"""

import re
import tempfile
import time
from pathlib import Path

from playwright.sync_api import Page, expect

from tests.stego_ref import _make_carrier, embed

SHOTS = Path("/tmp/gkp-e2e")
BENIGN_CONSOLE_PATTERNS = [
    re.compile(r"Autofocus processing"),
    re.compile(r"Third-party cookie"),
]


class ConsoleWatcher:
    """Collect console errors, page errors and non-2xx responses for a page.

    A pageerror or an unexpected console error fails the test even if the flow
    visually worked — the point of the suite is catching browser-console
    wiring bugs (like content blocks never rendering).
    """

    def __init__(self, page: Page, *, allow_http: tuple[int, ...] = ()) -> None:
        self.errors: list[str] = []
        self.page_errors: list[str] = []
        self.bad_responses: list[str] = []
        self.allow_http = allow_http
        page.on("console", lambda msg: self._console(msg.type, msg.text))
        page.on("pageerror", lambda err: self.page_errors.append(str(err)))
        page.on(
            "response",
            lambda resp: self._response(resp.status, resp.url),
        )

    def _console(self, kind: str, text: str) -> None:
        if kind not in ("error", "warning"):
            return
        if any(p.search(text) for p in BENIGN_CONSOLE_PATTERNS):
            return
        if "Failed to load resource" in text and self.allow_http:
            # Chrome logs one console.error per non-2xx response; when the
            # test explicitly allows those statuses the pair cancel out.
            if not any(f"status of {code}" in text for code in self.allow_http if code >= 400):
                self.errors.append(f"[console.{kind}] {text}")
            return
        self.errors.append(f"[console.{kind}] {text}")

    def _response(self, status: int, url: str) -> None:
        if status < 400:
            return
        if status in self.allow_http:
            return
        self.bad_responses.append(f"[HTTP {status}] {url}")

    def expect_clean(self) -> None:
        ok = not (self.errors or self.page_errors or self.bad_responses)
        if not ok:
            SHOTS.mkdir(parents=True, exist_ok=True)
            problems = self.errors + self.page_errors + self.bad_responses
            raise AssertionError("Console/HTTP watcher tripped:\n  " + "\n  ".join(problems[:20]))


class EventHandle:
    """Everything created for one E2E event, shared between page objects."""

    def __init__(self, event_id: str, organizer_key: str, title: str = "") -> None:
        self.event_id = event_id
        self.organizer_key = organizer_key
        self.title = title
        self._tmpdir = tempfile.mkdtemp(prefix="gkp-e2e-card-")

    def _card_png(self, payload: str) -> Path:
        out = Path(self._tmpdir) / f"card-{abs(hash(payload)) % 10**10}.png"
        out.write_bytes(embed(_make_carrier(), payload))
        return out

    def attendee_card_png(self, key: str) -> Path:
        """A valid attendee card whose hidden key is `key` (junk for the
        rate-limit drill, a real minted key for happy paths)."""
        return self._card_png(f"{self.event_id}\n{key}")

    def organizer_card_png(self) -> Path:
        """A valid organizer card for this event (the only way back in)."""
        return self._card_png(f"organizer\n{self.event_id}\n{self.organizer_key}")


class ApiKeyGrabber:
    """Keys are never rendered as text any more — the invite card is the only
    artifact. E2E still needs the raw values (to mint cards, join via stored
    sessions), so the raw keys are taken from the JSON responses the UI itself
    receives, as a browser proxy would."""

    def __init__(self, page: Page) -> None:
        self.values: list[str] = []
        page.on("response", self._on_response)

    def _on_response(self, response) -> None:
        if response.request.method != "POST":
            return
        try:
            body = response.json()
        except Exception:  # noqa: BLE001 — any non-JSON body is simply not a key carrier
            return
        if not isinstance(body, dict):
            return
        for field in ("organizer_key", "access_key"):
            value = body.get(field)
            if isinstance(value, str) and value:
                self.values.append(value)

    def latest(self, page: Page, timeout_ms: int = 10_000) -> str:
        deadline = time.time() + timeout_ms / 1000
        while not self.values and time.time() < deadline:
            page.wait_for_timeout(100)
        if not self.values:
            msg = "No key captured from API responses"
            raise AssertionError(msg)
        return self.values[-1]


def wait_event_page(page: Page) -> None:
    """Barrier until the attendee event page rendered its main sections."""
    page.locator("#join-event:not([hidden])").wait_for(timeout=15_000)
    page.locator("#join-views .ep-title").first.wait_for(state="visible")


class OrganizerPage:
    """Wraps the organizer flows: create, keys, content, bulletins, media, RSVP tab."""

    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base = base_url
        self.watcher = ConsoleWatcher(page)
        self.keys = ApiKeyGrabber(page)

    def go(self, route: str = "#/organize") -> None:
        self.page.goto(f"{self.base}/{route}")

    def create_event(self, title: str, description: str, *, location: str = "") -> "EventHandle":
        """Drive `#create-event-form`; org key comes from the one-show modal."""
        self.go()
        self.page.fill("#title", title)
        self.page.fill("#description", description)
        if location:
            self.page.fill("#location-data", location)
        self.page.click("#create-btn")
        self.page.locator("#modal-root .modal").wait_for(timeout=10_000)
        org_key = self.keys.latest(self.page)
        # The fresh organizer card modal opens immediately — Cancel it here;
        # tests that need the card itself use mint_key_and_card.
        self.page.locator('[data-act="cancel"]').click()
        self.page.locator(".ws-title").wait_for(state="visible")
        event_id = self.page.locator("#ws-event-id").inner_text().strip()
        return EventHandle(event_id, org_key, title)

    def open_workspace(self, handle: EventHandle) -> None:
        """Re-enter the workspace through a fresh tab by dropping a generated
        organizer card — the card is the only way back in (no id+key form).
        The active page and watcher move to the new tab."""
        old = self.page
        page = old.context.new_page()
        self.page = page
        self.watcher = ConsoleWatcher(page)
        self.keys = ApiKeyGrabber(page)
        page.goto(f"{self.base}/#/organize")
        page.locator("#org-drop").wait_for(state="visible")
        page.locator("#org-drop-file").set_input_files(str(handle.organizer_card_png()))
        page.locator(".ws-title").wait_for(state="visible")
        old.close()

    def tab(self, name: str) -> None:
        self.page.click(f'.tab[data-tab="{name}"]')

    def post_bulletin(self, title: str, body: str, media_file: str | Path | None = None) -> None:
        """Create a board post (title + content, optionally with a media
        attachment). The single post type — supports comments."""
        self.tab("board")
        self.page.fill("#bulletin-title", title)
        self.page.fill("#bulletin-body", body)
        if media_file:
            self.page.locator("#media-file").set_input_files(media_file)
        self.page.click("#board-post-btn")
        expect(self.page.locator(".bulletin-card", has_text=title)).to_be_visible()

    def upload_flyer(self, file_path: str | Path) -> None:
        """Upload (or replace) the event flyer from the board's flyer card."""
        self.tab("board")
        self.page.locator("#board-flyer-file").set_input_files(file_path)
        self.page.click("#board-flyer-btn")
        expect(self.page.locator(".toast", has_text="Event flyer updated.")).to_be_visible()

    def mint_key(self, owner: str, days: int = 30) -> str:
        """Mint an access key; the raw value arrives only via the POST response
        (the UI never renders it as text). Closes the card-centric modal."""
        self.tab("keys")
        self.page.fill("#key-owner", owner)
        self.page.fill("#key-days", str(days))
        self.page.click("#gen-key-btn")
        self.page.locator("#modal-root .modal").wait_for(timeout=10_000)
        key = self.keys.latest(self.page)
        self.page.locator('[data-act="cancel"]').click()
        return key

    def mint_key_and_card(self, file_path: Path, owner: str, days: int = 30) -> str:
        """Mint a key and immediately make its invite card — the only supported
        way to keep a key now. The card modal opens immediately after
        generation; confirm downloads the stego PNG to `file_path`."""
        self.tab("keys")
        self.page.fill("#key-owner", owner)
        self.page.fill("#key-days", str(days))
        self.page.click("#gen-key-btn")
        self.page.locator("#modal-root .modal").wait_for(timeout=10_000)
        key = self.keys.latest(self.page)
        with self.page.expect_download() as dl:
            self.page.locator('[data-act="confirm"]').click()
        dl.value.save_as(str(file_path))
        return key

    def set_gate_settings(self, *, auto_approve: int | None = None) -> str:
        """Save RSVP gate settings; returns the public funnel share link."""
        self.tab("rsvps")
        if auto_approve is not None:
            self.page.fill("#rsvp-auto", str(auto_approve))
        self.page.click("#rsvp-settings-btn")
        self.page.wait_for_timeout(600)  # settings save is fetch + silent re-render
        return self.page.locator(".keycode-full .keycode").inner_text().strip()

    def approve_rsvp(self, name: str) -> None:
        # The queue is fetched when the tab renders — re-render it first so a
        # request that arrived after the last render is in the list.
        self.tab("board")
        self.tab("rsvps")
        row = self.page.locator(f'.key-detail-row:has-text("{name}")')
        row.get_by_role("button", name="Approve").click()

    def deny_rsvp(self, name: str) -> None:
        self.tab("board")
        self.tab("rsvps")
        row = self.page.locator(f'.key-detail-row:has-text("{name}")')
        row.get_by_role("button", name="Deny").click()

    # -- Organizer CRUD edges (Group A) -----------------------------------

    def confirm_modal(self) -> None:
        """Click the primary confirm button of the current modal dialog."""
        self.page.locator('#modal-root [data-act="confirm"]').click()

    def bulletin_card(self, title: str):
        self.tab("board")
        return self.page.locator("#ws-main .bulletin-card", has_text=title)

    def open_bulletin(self, title: str):
        """Expand a bulletin card so its comments render, return the card.
        Posts start expanded; the head click only toggles from collapsed."""
        card = self.bulletin_card(title)
        if not card.locator(".bulletin-body").is_visible():
            card.locator(".bulletin-head").click()
        card.locator(".bulletin-body").wait_for(state="visible")
        card.locator(".comment-row, .c-meta").first.wait_for(state="visible")
        return card

    def delete_bulletin(self, title: str) -> None:
        card = self.bulletin_card(title)
        if not card.locator(".bulletin-body").is_visible():
            card.locator(".bulletin-head").click()
            card.locator(".bulletin-body").wait_for(state="visible")
        card.locator('[data-act="delete-bulletin"]').click()
        self.confirm_modal()
        expect(self.bulletin_card(title)).to_have_count(0)

    def delete_first_comment(self, title: str) -> None:
        card = self.open_bulletin(title)
        card.locator('[data-act="delete-comment"]').first.click()
        expect(card.locator(".c-meta")).to_have_count(0)

    def copy_rsvp_link(self) -> str:
        """RSVP tab: copy funnel link (clipboard API is denied headless, so the
        app toasts 'Copy blocked' — both toasts prove the button is wired and
        the shown URL is the funnel route)."""
        self.tab("rsvps")
        url = self.page.locator("#ws-main .keycode-full .keycode").inner_text().strip()
        self.page.click("#rsvp-copy-link")
        expect(
            self.page.locator(".toast", has_text=re.compile("copied|Copy blocked"))
        ).to_be_visible()
        return url

    def revoke_key(self, _key: str | None = None) -> None:
        """Revoke the first active access key via its row button (the raw key
        text isn't retrievable — keys live only in card pixels)."""
        self.tab("keys")
        self.page.locator('[data-act="revoke-key"]').first.click()
        self.confirm_modal()
        expect(self.page.locator(".toast", has_text="Access key revoked.")).to_be_visible()
        expect(self.page.locator(".badge-revoked").first).to_be_visible()

    def decommission(self, handle: EventHandle) -> None:
        """Decommission via the header action + type-to-confirm modal.
        Assumes the workspace is already open (e.g. right after minting)."""
        self.page.click("#ws-decommission")
        self.page.locator("#decom-confirm").fill(handle.title)
        self.confirm_modal()
        expect(self.page.locator(".toast", has_text="Event decommissioned")).to_be_visible()

    def reload_restores_workspace(self, handle: EventHandle) -> None:
        """Reload the workspace tab: the organizer session survives."""
        self.open_workspace(handle)
        title = self.page.locator(".ws-title").first.inner_text()
        self.page.reload()
        self.page.locator("#ws-main").wait_for(state="visible")
        expect(self.page.locator(".ws-title").first).to_have_text(title)
        assert handle.event_id in self.page.locator("#ws-event-id").inner_text()

    def close_workspace(self) -> None:
        self.page.click("#ws-end")
        self.page.locator("#org-drop").wait_for(state="visible")
        expect(
            self.page.locator(".toast", has_text="Organizer key discarded from this tab.")
        ).to_be_visible()


class AttendeePage:
    """Attendee door + event page (`#/join`) and RSVP funnel (`#/rsvp/{event_id}`)."""

    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base = base_url
        self.watcher = ConsoleWatcher(page)
        self.keys = ApiKeyGrabber(page)

    def go_join(self) -> None:
        self.page.goto(f"{self.base}/#/join")
        self.page.locator("#key-drop").wait_for(state="visible")

    def unlock_by_stego_png(self, png_path: str | Path, *, expect_unlock: bool = True) -> None:
        """Drop a card image on the door's zone — the only unlock path."""
        self.go_join()
        self.page.locator("#key-drop-file").set_input_files(str(png_path))
        if expect_unlock:
            wait_event_page(self.page)

    def inject_session(self, event_id: str, key: str, event: dict | None = None) -> None:
        """Seed attendee sessionStorage like a prior unlock, then reload —
        exercises the lazy `loadAttendeeDetails` content-block path."""
        payload = {"eventId": event_id, "accessKey": key, "event": event or {}}
        self.page.goto(f"{self.base}/#/join")
        self.page.evaluate(
            "payload => sessionStorage.setItem('gatekeyp.attendee', JSON.stringify(payload))",
            payload,
        )
        self.page.reload()
        wait_event_page(self.page)

    def expect_event_title(self, title: str) -> None:
        expect(self.page.locator("#join-views .ep-title", has_text=title)).to_be_visible()

    def leave_event(self) -> None:
        self.page.click("#attendee-end")
        self.page.locator("#key-drop").wait_for(state="visible")

    def rsvp_key(self) -> str:
        """The funnel's access key, taken from the POST response (never text)."""
        return self.keys.latest(self.page)

    def unlock_from_rsvp_result(self) -> None:
        """'Open the event now' on the approved-RSVP result page. The
        fresh-key card modal auto-opens on top — dismiss it first."""
        self.page.locator('[data-act="cancel"]').click()
        self.page.click("#rsvp-unlock")
        self.page.locator("#join-views .ep-title").first.wait_for(state="visible")

    def rsvp(
        self,
        url: str,
        *,
        name: str,
        contact: str = "",
        message: str = "",
        passphrase: str | None = None,
        expect_success: bool = True,
    ) -> None:
        self.page.goto(url)
        self.page.reload()  # hash-only navigations don't re-render the funnel
        self.page.locator("#rsvp-form").wait_for(state="visible")
        self.page.fill("#rsvp-name", name)
        if contact:
            self.page.fill("#rsvp-contact", contact)
        if message:
            self.page.fill("#rsvp-message", message)
        if passphrase is not None:
            self.page.fill("#rsvp-passphrase", passphrase)
        self.page.click("#rsvp-form button[type=submit]")
        if expect_success:
            # The fresh key's card modal opens immediately on success.
            self.page.locator("#card-preview").wait_for(state="visible", timeout=15_000)
        else:
            self.page.locator("#rsvp-note:not(:empty)").wait_for(timeout=10_000)

    # -- Attendee robustness (Group B) ------------------------------------

    def join_note(self) -> str:
        return self.page.locator("#join-note").inner_text().strip()

    def expect_join_note(self, text: str) -> None:
        expect(self.page.locator("#join-note")).to_contain_text(text)

    def drop_card_and_read_note(self, png: Path) -> str:
        """Drop a card on the door then wait until the note actually says
        something (unlockEvent clears the note first, so poll for non-empty)."""
        self.go_join()
        self.page.locator("#key-drop-file").set_input_files(str(png))
        el = self.page.locator("#join-note")
        for _ in range(40):
            text = el.inner_text().strip()
            if text:
                return text
            self.page.wait_for_timeout(100)
        return ""

    def drop_until_rate_limited(self, handle: EventHandle) -> None:
        """Drop cards with junk keys until the door answers Rate limit exceeded."""
        import string

        alphabet = string.ascii_letters + string.digits
        for i in range(10):
            junk = "".join(alphabet[(i * 7 + j) % len(alphabet)] for j in range(24))
            note = self.drop_card_and_read_note(handle.attendee_card_png(f"local:{junk}"))
            if "rate limit" in note.lower():
                return
            if "in backoff" in note.lower():
                return
        message = "door never rate-limited the failure streak"
        raise AssertionError(message)

    def end_session(self) -> None:
        """Leave (drop key): the door returns and a Signed-out toast fires."""
        self.page.click("#attendee-end")
        self.page.locator("#key-drop").wait_for(state="visible")
        expect(
            self.page.locator(".toast", has_text="Key dropped. To re-enter, use the invite again.")
        ).to_be_visible()

    def reload_keeps_session(self) -> None:
        title = self.page.locator("#join-views .ep-title").first.inner_text()
        self.page.reload()
        wait_event_page(self.page)
        expect(self.page.locator("#join-views .ep-title").first).to_have_text(title)

    def expect_bulletin_visible(self, title: str) -> None:
        expect(self.page.locator("#ep-board .bulletin-card", has_text=title)).to_be_visible()

    def comment_on_bulletin(self, bulletin_title: str, author: str, body: str) -> None:
        """Post a comment from the attendee view. The card starts expanded; the
        head click only toggles from collapsed."""
        card = self.page.locator("#ep-board .bulletin-card", has_text=bulletin_title).first
        if not card.locator(".bulletin-body").is_visible():
            card.locator(".bulletin-head").click()
        card.locator(".comment-form").wait_for(state="visible")
        card.locator("input.cf-author").fill(author)
        card.locator("input.cf-body").fill(body)
        card.locator(".comment-form button[type=submit]").click()
        expect(card.locator(".c-meta").first).to_contain_text(author)

    def expect_rsvp_note(self, text: str) -> None:
        expect(self.page.locator("#rsvp-note")).to_contain_text(text)
