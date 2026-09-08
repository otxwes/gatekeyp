/* gatekeyp — browser app for the organizer desk and the attendee door.
 *
 * Hash-routed, no framework. Talks to the same JSON API the server exposes.
 * Keys never leave this tab: the master key and attendee keys live in
 * sessionStorage (cleared when the tab closes), and the raw key is only ever
 * shown once, in a modal, at generation time.
 */

"use strict";

/* ------------------------------------------------------------------
 * Tiny DOM + formatting helpers
 * ------------------------------------------------------------------ */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/** Escape a value for safe insertion into innerHTML. */
function esc(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

/** Full readable timestamp from an ISO string. */
function fmtDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    return d.toLocaleString(undefined, {
        year: "numeric", month: "short", day: "numeric",
        hour: "2-digit", minute: "2-digit",
    });
}

function fmtBytes(n) {
    const v = Number(n || 0);
    if (v < 1024) return `${v} B`;
    if (v < 1024 * 1024) return `${(v / 1024).toFixed(1)} KB`;
    return `${(v / (1024 * 1024)).toFixed(1)} MB`;
}

/** Short display form of a long id. */
function fmtId(id) {
    const s = String(id || "");
    return s.length > 26 ? `${s.slice(0, 13)}…${s.slice(-12)}` : s;
}

async function copyText(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch {
        try {
            const ta = document.createElement("textarea");
            ta.value = text;
            ta.setAttribute("readonly", "");
            ta.style.position = "fixed";
            ta.style.opacity = "0";
            document.body.appendChild(ta);
            ta.select();
            document.execCommand("copy");
            ta.remove();
            return true;
        } catch {
            return false;
        }
    }
}

/* ------------------------------------------------------------------
 * Session state
 * ------------------------------------------------------------------ */
// Organizer workspace: { eventId, masterKey, title }
let org = null;
// Attendee session: { eventId, accessKey, event: { ...event dict } }
let attendee = null;

const SESSION_ORG = "gatekeyp.org";
const SESSION_ATTENDEE = "gatekeyp.attendee";

function saveSession() {
    try {
        if (org) sessionStorage.setItem(SESSION_ORG, JSON.stringify(org));
        else sessionStorage.removeItem(SESSION_ORG);
        if (attendee) sessionStorage.setItem(SESSION_ATTENDEE, JSON.stringify(attendee));
        else sessionStorage.removeItem(SESSION_ATTENDEE);
    } catch {
        /* sessionStorage unavailable — keys live in memory for this tab only */
    }
}

function loadSession() {
    try {
        const o = sessionStorage.getItem(SESSION_ORG);
        const a = sessionStorage.getItem(SESSION_ATTENDEE);
        if (o) org = JSON.parse(o);
        if (a) attendee = JSON.parse(a);
    } catch {
        org = null;
        attendee = null;
    }
}

/* ------------------------------------------------------------------
 * API client
 * ------------------------------------------------------------------ */
async function api(path, options = {}) {
    const req = { method: options.method || "GET", headers: {} };
    if (options.body !== undefined) {
        req.headers["Content-Type"] = "application/json";
        req.body = JSON.stringify(options.body);
    }
    let response;
    try {
        response = await fetch(path, req);
    } catch {
        throw new Error("Network error — is the gatekeyp server running?");
    }
    let data = null;
    try {
        data = await response.json();
    } catch {
        data = null;
    }
    if (!response.ok) {
        const detail = (data && (data.detail || data.message)) || `Request failed (${response.status})`;
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
}

/** Build a query string from params, skipping empty values. */
function qs(params) {
    const parts = Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== "")
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`);
    return parts.length ? `?${parts.join("&")}` : "";
}

/** A media asset's retrieval URL, keyed for the current session. */
function mediaUrl(assetId) {
    const key = (org && org.masterKey) || (attendee && attendee.accessKey) || "";
    return `/api/media/${encodeURIComponent(assetId)}${qs({ key })}`;
}

/* ------------------------------------------------------------------
 * Toasts
 * ------------------------------------------------------------------ */
const TOAST_ICONS = { ok: "✓", error: "✕", info: "i" };

function toast(message, type = "info", title = "") {
    const region = $("#toast-region");
    if (!region) return;
    const node = document.createElement("div");
    node.className = `toast toast-${type}`;
    node.innerHTML =
        `<span class="toast-icon" aria-hidden="true">${TOAST_ICONS[type] || "i"}</span>` +
        `<div class="toast-body">${esc(title ? `${title}\n` : "")}${esc(message)}</div>` +
        `<button class="toast-close" type="button" aria-label="Dismiss">×</button>`;
    const dismiss = () => {
        node.classList.add("is-leaving");
        window.setTimeout(() => node.remove(), 200);
    };
    $(".toast-close", node).addEventListener("click", dismiss);
    region.appendChild(node);
    window.setTimeout(dismiss, 5000);
}

/* ------------------------------------------------------------------
 * Modal
 * ------------------------------------------------------------------ */
function closeModal() {
    const backdrop = $("#modal-root .modal-backdrop");
    if (backdrop) backdrop.remove();
}

function openModal({ title, body = "", confirmText = "Confirm", cancelText = "Cancel", danger = false, onConfirm }) {
    closeModal();
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML =
        `<div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">` +
        `<div class="modal-head"><h3 class="modal-title" id="modal-title">${esc(title)}</h3>` +
        `<button class="modal-close" type="button" aria-label="Close">×</button></div>` +
        `<div class="modal-body">${body}</div>` +
        `<div class="modal-actions">` +
        `<button class="btn btn-ghost" type="button" data-act="cancel">${esc(cancelText)}</button>` +
        `<button class="btn ${danger ? "btn-danger" : "btn-primary"}" type="button" data-act="confirm">${esc(confirmText)}</button>` +
        `</div></div>`;
    $("#modal-root").appendChild(backdrop);

    const close = () => backdrop.remove();
    $(".modal-close", backdrop).addEventListener("click", close);
    $('[data-act="cancel"]', backdrop).addEventListener("click", close);
    backdrop.addEventListener("click", (event) => {
        if (event.target === backdrop) close();
    });
    const confirmBtn = $('[data-act="confirm"]', backdrop);
    confirmBtn.addEventListener("click", async () => {
        confirmBtn.disabled = true;
        confirmBtn.textContent = "Working…";
        try {
            await onConfirm();
            close();
        } catch (err) {
            toast(err.message, "error", "Could not complete");
            confirmBtn.disabled = false;
            confirmBtn.textContent = confirmText;
        }
    });
    confirmBtn.focus();
}

/** Modal that shows a freshly generated key exactly once, with a copy button.
 *  When `cardOpts` (event metadata for the invite card) is given, also offers
 *  "Also make an invite card" for the fresh key. */
function openKeyModal(label, keyValue, cardOpts = null) {
    const cardButton = cardOpts
        ? `<button class="btn btn-secondary btn-block" type="button" id="key-card-btn">Also make an invite card</button>`
        : "";
    const cardHint = cardOpts
        ? `<p class="field-hint">Send the card as a file or attachment, not a photo — re-encoding it in a chat destroys the hidden key. Its printed QR is the fallback.</p>`
        : "";
    openModal({
        title: label,
        body:
            `<p>Copy this key now — it is shown only once and cannot be recovered later.</p>` +
            `<div class="keycode-full"><code class="keycode kc-value">${esc(keyValue)}</code>` +
            `<button class="btn btn-secondary" type="button" id="key-copy-btn">Copy</button></div>` +
            cardButton +
            cardHint,
        confirmText: "Done",
        cancelText: "Close",
        onConfirm: async () => {},
    });
    const copyBtn = $("#key-copy-btn");
    if (copyBtn) {
        copyBtn.addEventListener("click", async () => {
            const ok = await copyText(keyValue);
            toast(ok ? "Key copied to clipboard." : "Copy blocked — select the key manually.", ok ? "ok" : "error", "Copy");
        });
    }
    const cardBtn = $("#key-card-btn");
    if (cardBtn) {
        cardBtn.addEventListener("click", () => {
            openCardCoverModal({
                ...cardOpts,
                accessKey: keyValue,
                qrText: window.gkpStego.qrPayload(cardOpts.eventId, keyValue),
            });
        });
    }
}

/* ------------------------------------------------------------------
 * Theme
 * ------------------------------------------------------------------ */
function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    const sun = $(".theme-icon-sun");
    const moon = $(".theme-icon-moon");
    if (sun) sun.style.display = theme === "light" ? "" : "none";
    if (moon) moon.style.display = theme === "dark" ? "" : "none";
    try {
        localStorage.setItem("gatekeyp.theme", theme);
    } catch {
        /* ignore */
    }
}

function initTheme() {
    let theme = "light";
    try {
        theme = localStorage.getItem("gatekeyp.theme") || "light";
        if (!localStorage.getItem("gatekeyp.theme") &&
            window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
            theme = "dark";
        }
    } catch {
        /* ignore */
    }
    applyTheme(theme);
    const toggle = $("#theme-toggle");
    if (toggle) {
        toggle.addEventListener("click", () => {
            const current = document.documentElement.getAttribute("data-theme");
            applyTheme(current === "dark" ? "light" : "dark");
        });
    }
}

/* ------------------------------------------------------------------
 * Small UI hooks + render helpers
 * ------------------------------------------------------------------ */
function btnBusy(btn, busy, busyText) {
    if (!btn) return;
    if (busy) {
        btn.dataset.label = btn.textContent;
        btn.textContent = busyText;
        btn.disabled = true;
    } else {
        btn.textContent = btn.dataset.label || btn.textContent;
        btn.disabled = false;
    }
}

function note(elNode, message, kind) {
    // Monochrome UI: status is reinforced with glyphs, not hue.
    // Error / ok carries a leading mark so meaning survives color-blind
    // viewers, high-contrast overrides, and print.
    const text = message || "";
    if (kind === "error" && text) {
        elNode.textContent = `⚠ ${text}`;
    } else if (kind === "ok" && text) {
        elNode.textContent = `✓ ${text}`;
    } else {
        elNode.textContent = text;
    }
    elNode.classList.remove("is-error", "is-ok");
    if (kind === "error") elNode.classList.add("is-error");
    else if (kind === "ok") elNode.classList.add("is-ok");
}

function getField(form, name) {
    const input = form.elements[name];
    return input ? input.value.trim() : "";
}

function factRow(key, value) {
    return `<div class="fact-row"><span class="f-key">${esc(key)}</span><span class="f-val">${esc(value)}</span></div>`;
}

function emptyState(title, sub) {
    return `<div class="empty"><div class="empty-title">${esc(title)}</div>` +
        (sub ? `<p class="empty-sub">${esc(sub)}</p>` : "") +
        `</div>`;
}

const CONTENT_TYPE_LABELS = {
    description: "Description",
    schedule: "Schedule",
    location: "Location",
    logistics: "Logistics",
    agenda: "Agenda",
    speakers: "Speakers",
    notes: "Notes",
    faq: "FAQ",
};

function contentTypeLabel(type) {
    return CONTENT_TYPE_LABELS[type] || type || "Note";
}

function blockItem(block) {
    return `<div class="item">` +
        `<div class="item-head">` +
        `<span class="tag">${esc(contentTypeLabel(block.content_type))}</span>` +
        `<span class="item-title">${esc(block.content_type || "content")}</span>` +
        `</div>` +
        `<div class="item-body">${esc(block.payload || "")}</div>` +
        `<div class="item-meta">${esc(fmtDate(block.created_at))}</div>` +
        `</div>`;
}

/* ------------------------------------------------------------------
 * Router
 * ------------------------------------------------------------------ */
function parseHash() {
    const h = (location.hash || "#/").replace(/^#/, "");
    if (h === "" || h === "/") return "home";
    return h.replace(/^\//, "").split("/")[0];
}

function showView(name) {
    $$(".view").forEach((view) => {
        view.hidden = view.id !== `view-${name}`;
    });
    $$(".nav-link").forEach((link) => {
        const target = (link.getAttribute("href") || "").replace(/^#\//, "");
        const active = target === name;
        link.classList.toggle("is-active", active);
        if (active) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
    });
}

function route() {
    const name = parseHash();
    showView(name);
    if (name === "home") renderHome();
    else if (name === "organize") renderOrganize();
    else if (name === "join") renderJoin();
    else if (name === "flyer") renderFlyer();
    else if (name === "e") renderLiteEvent();
}

/* ------------------------------------------------------------------
 * Home
 * ------------------------------------------------------------------ */
function renderHome() {
    const session = $("#home-session");
    if (!session) return;
    if (org || attendee) {
        const isOrg = Boolean(org);
        const title = (org && org.title) ||
            (attendee && attendee.event && attendee.event.title) ||
            "an event";
        session.innerHTML =
            `<p class="session-msg"><strong>${isOrg ? "Organizer" : "Attendee"} session</strong> · ${esc(title)}</p>` +
            `<div class="session-actions">` +
            `<a class="btn btn-ghost" href="#/organize">${isOrg ? "Back to desk" : "Back to event"}</a>` +
            `<button class="btn btn-ghost" type="button" id="session-end">End session</button>` +
            `</div>`;
        session.hidden = false;
        $("#session-end").addEventListener("click", endAllSessions);
    } else {
        session.hidden = true;
        session.innerHTML = "";
    }
}

function endAllSessions() {
    org = null;
    attendee = null;
    saveSession();
    toast("Session ended. Keys were discarded from this tab.", "info", "Signed out");
    location.hash = "#/";
    renderHome();
}

/* ------------------------------------------------------------------
 * Organize entry (create / open)
 * ------------------------------------------------------------------ */
function bindOrganizeEntry() {
    const createForm = $("#create-event-form");
    createForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const noteEl = $("#create-note");
        const btn = $("#create-btn");
        note(noteEl, "");
        const title = getField(createForm, "title");
        const description = getField(createForm, "description");
        const organizer_id = getField(createForm, "organizer_id") || "organizer";
        const location_data = getField(createForm, "location_data") || null;
        if (!title || !description) {
            note(noteEl, "A title and description are required.", "error");
            return;
        }
        btnBusy(btn, true, "Creating…");
        try {
            const created = await api("/api/events", {
                method: "POST",
                body: { title, description, organizer_id, location_data },
            });
            org = {
                eventId: created.event_id,
                masterKey: created.master_key,
                title: created.title || title,
                meta: { description, organizerId: organizer_id, locationData: location_data },
            };
            createForm.reset();
            saveSession();
            goWorkspace();
            openKeyModal("Master key — save it", created.master_key);
            toast("Event created. Share access keys, never this master key.", "ok", "Ready");
        } catch (err) {
            note(noteEl, err.message, "error");
            btnBusy(btn, false);
        }
    });

    const openForm = $("#open-event-form");
    openForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const noteEl = $("#open-note");
        const btn = $("#open-btn");
        note(noteEl, "");
        const eventId = getField(openForm, "event_id");
        const masterKey = getField(openForm, "master_key");
        if (!eventId || !masterKey) {
            note(noteEl, "Both the event ID and master key are required.", "error");
            return;
        }
        btnBusy(btn, true, "Opening…");
        try {
            const details = await api(`/api/events/${encodeURIComponent(eventId)}${qs({ master_key: masterKey })}`);
            const eventInfo = details.event || {};
            org = {
                eventId,
                masterKey,
                title: eventInfo.title || "Untitled event",
                meta: {
                    description: eventInfo.description || "",
                    organizerId: eventInfo.organizer_id || "",
                    locationData: eventInfo.location_data || "",
                    createdAt: eventInfo.created_at || "",
                },
            };
            openForm.reset();
            saveSession();
            goWorkspace();
            toast("Workspace restored from your key.", "ok", "Welcome back");
        } catch (err) {
            note(noteEl, err.message, "error");
            btnBusy(btn, false);
        }
    });
}

/** Show the workspace container (inside the organize view). */
function goWorkspace() {
    const entry = $("#organize-entry");
    const workspace = $("#organize-workspace");
    if (entry) entry.hidden = true;
    if (workspace) workspace.hidden = false;
    renderWorkspace();
}

function renderOrganize() {
    const entry = $("#organize-entry");
    const workspace = $("#organize-workspace");
    if (org) {
        if (entry) entry.hidden = true;
        if (workspace) {
            workspace.hidden = false;
            renderWorkspace();
        }
    } else {
        if (workspace) workspace.hidden = true;
        if (entry) entry.hidden = false;
    }
}

/* ------------------------------------------------------------------
 * Workspace shell
 * ------------------------------------------------------------------ */
let wsTab = "content";

const WS_TABS = [
    ["content", "Content"],
    ["bulletins", "Bulletin board"],
    ["media", "Media"],
    ["keys", "Access keys"],
];

const WS_LOADERS = {
    content: wsContent,
    bulletins: wsBulletins,
    media: wsMedia,
    keys: wsKeys,
};

async function fetchEventDetails() {
    return api(`/api/events/${encodeURIComponent(org.eventId)}${qs({ master_key: org.masterKey })}`);
}

function renderWorkspace() {
    const root = $("#organize-views");
    if (!root || !org) return;
    root.innerHTML =
        `<header class="ws-head">` +
        `<div class="ws-titles">` +
        `<h2 class="ws-title">${esc(org.title || "Event workspace")}</h2>` +
        `<p class="ws-meta">${esc(org.eventId)}</p>` +
        `</div>` +
        `<div class="ws-actions">` +
        `<button class="btn btn-ghost" type="button" id="ws-end">Close workspace</button>` +
        `<button class="btn btn-danger" type="button" id="ws-decommission">Decommission</button>` +
        `</div>` +
        `</header>` +
        `<div class="master-banner" role="note">` +
        `<span class="badge badge-warn">Master</span>` +
        `<button class="btn btn-secondary btn-sm" type="button" id="ws-copy-key">Copy master key</button>` +
        `</div>` +
        `<nav class="tabs" role="tablist" aria-label="Workspace sections">` +
        WS_TABS.map(([id, label]) =>
            `<button class="tab" type="button" role="tab" data-tab="${id}" aria-selected="${id === wsTab}">${esc(label)}</button>`
        ).join("") +
        `</nav>` +
        `<div class="ws-body">` +
        `<main class="ws-main" role="tabpanel" id="ws-main"></main>` +
        `</div>`;

    $("#ws-end").addEventListener("click", () => {
        org = null;
        saveSession();
        location.hash = "#/organize";
        renderOrganize();
        toast("Workspace closed. Master key discarded from this tab.", "info", "Signed out");
    });
    $("#ws-copy-key").addEventListener("click", async () => {
        const ok = await copyText(org.masterKey);
        toast(ok ? "Master key copied to clipboard." : "Copy blocked.", ok ? "ok" : "error", "Copy");
    });
    $$(".tab", root).forEach((tab) => {
        tab.addEventListener("click", () => {
            if (tab.dataset.tab !== wsTab) {
                wsTab = tab.dataset.tab;
                renderWorkspace();
            }
        });
    });
    $("#ws-decommission").addEventListener("click", openDecommissionModal);
    loadWsTab();
}

async function loadWsTab() {
    const main = $("#ws-main");
    if (!main) return;
    main.innerHTML = `<div class="empty"><div class="empty-title">Loading…</div></div>`;
    const loader = WS_LOADERS[wsTab] || wsContent;
    try {
        await loader(main);
    } catch (err) {
        main.innerHTML = emptyState("Could not load", err.message);
    }
}

/* ------------------------------------------------------------------
 * Workspace: Content tab
 * ------------------------------------------------------------------ */
async function wsContent(main) {
    const details = await fetchEventDetails();
    const event = details.event || {};
    const blocks = details.content_blocks || [];
    main.innerHTML =
        `<section class="card">` +
        `<h3 class="card-title">About this event</h3>` +
        `<p class="section-text">${esc(event.description || "")}</p>` +
        `<div class="fact-list">` +
        factRow("Title", event.title) +
        factRow("Event ID", fmtId(event.id)) +
        factRow("Organizer", event.organizer_id) +
        (event.location_data ? factRow("Where", event.location_data) : "") +
        factRow("Created", fmtDate(event.created_at)) +
        `</div>` +
        `</section>` +
        `<section class="card">` +
        `<h3 class="card-title">Content blocks</h3>` +
        `<div class="item-list">` +
        (blocks.length
            ? blocks.map(blockItem).join("")
            : emptyState("No content blocks yet")) +
        `</div>` +
        `</section>` +
        `<section class="card">` +
        `<h3 class="card-title">Add a block</h3>` +
        `<form id="add-block-form" class="inline-form" autocomplete="off">` +
        `<div class="field"><label for="block-type">Type</label>` +
        `<input id="block-type" name="content_type" list="block-types" maxlength="64" value="description" required spellcheck="false"></div>` +
        `<div class="field"><label for="block-payload">Content</label>` +
        `<textarea id="block-payload" name="payload" rows="3" maxlength="65536" required placeholder="What should attendees know?"></textarea></div>` +
        `<button class="btn btn-primary" type="submit" id="add-block-btn">Add block</button>` +
        `</form>` +
        `<datalist id="block-types">${Object.keys(CONTENT_TYPE_LABELS).map((t) => `<option value="${esc(t)}">`).join("")}</datalist>` +
        `</section>`;

    $("#add-block-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const content_type = getField(form, "content_type");
        const payload = getField(form, "payload");
        if (!content_type || !payload) return;
        const btn = $("#add-block-btn");
        btnBusy(btn, true, "Adding…");
        try {
            await api(`/api/events/${encodeURIComponent(org.eventId)}/content`, {
                method: "POST",
                body: { master_key: org.masterKey, event_id: org.eventId, content_type, payload },
            });
            toast("Content block added.", "ok", "Saved");
            await wsContent(main);
        } catch (err) {
            toast(err.message, "error", "Could not add block");
            btnBusy(btn, false);
        }
    });
}

/* ------------------------------------------------------------------
 * Shared bulletin + comment rendering
 * ------------------------------------------------------------------ */
function bulletinCardHTML(bulletin, manage) {
    return `<article class="bulletin-card" data-bid="${esc(bulletin.id)}">` +
        `<div class="bulletin-head" role="button" tabindex="0" aria-expanded="false">` +
        `<span class="b-title">${esc(bulletin.title)}</span>` +
        `<span class="b-count" data-count></span>` +
        `<span class="b-toggle" aria-hidden="true">▾</span>` +
        `</div>` +
        `<div class="bulletin-body" data-body hidden>` +
        `<div class="b-body-text" data-body-text></div>` +
        `<div class="bulletin-meta">` +
        `<span class="badge badge-neutral">by ${esc(bulletin.author_id || "anon")}</span>` +
        `<span class="badge badge-ghost">${esc(fmtDate(bulletin.created_at))}</span>` +
        `</div>` +
        `<div class="comments" data-comments></div>` +
        (manage
            ? `<div class="bulletin-foot">` +
              `<button class="btn btn-danger btn-sm" type="button" data-act="delete-bulletin">Delete bulletin</button>` +
              `</div>`
            : `<form class="comment-form" autocomplete="off">` +
              `<div class="field cf-author"><label for="cf-a-${esc(bulletin.id)}">Your name</label>` +
              `<input class="cf-author" id="cf-a-${esc(bulletin.id)}" name="author" type="text" maxlength="256" placeholder="Anonymous" autocomplete="off"></div>` +
              `<div class="field cf-body"><label for="cf-b-${esc(bulletin.id)}">Reply</label>` +
              `<input class="cf-body" id="cf-b-${esc(bulletin.id)}" name="body" type="text" maxlength="16384" placeholder="A thought…" required autocomplete="off"></div>` +
              `<button class="btn btn-ghost" type="submit">Post</button>` +
              `</form>`) +
        `</div>` +
        `</article>`;
}

async function bindBulletinCard(card, manage) {
    const head = $(".bulletin-head", card);
    const body = $(".bulletin-body", card);
    const countEl = $("[data-count]", card);
    const commentsBox = $("[data-comments]", card);
    const bodyText = $("[data-body-text]", card);
    let open = false;
    let loaded = false;

    const toggle = async () => {
        open = !open;
        body.hidden = !open;
        card.classList.toggle("bulletin-open", open);
        head.setAttribute("aria-expanded", String(open));
        if (!open) return;
        if (loaded) return;
        commentsBox.innerHTML = `<span class="badge badge-neutral">Loading…</span>`;
        try {
            const theKey = (org && org.masterKey) || (attendee && attendee.accessKey) || "";
            const [detail, comments] = await Promise.all([
                api(`/api/bulletins/${encodeURIComponent(card.dataset.bid)}${qs({ key: theKey })}`),
                api(`/api/bulletins/${encodeURIComponent(card.dataset.bid)}/comments${qs({ key: theKey })}`),
            ]);
            loaded = true;
            if (bodyText) bodyText.textContent = detail.body || "";
            countEl.textContent = `${comments.length} comment${comments.length === 1 ? "" : "s"}`;
            renderComments(commentsBox, comments, manage);
        } catch {
            commentsBox.innerHTML = `<span class="badge badge-revoked">Could not load comments</span>`;
        }
    };
    head.addEventListener("click", toggle);
    head.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggle();
        }
    });

    if (manage) {
        const delBtn = $('[data-act="delete-bulletin"]', card);
        delBtn.addEventListener("click", () => {
            openModal({
                title: "Delete bulletin",
                body: "Delete this bulletin and all of its comments? This cannot be undone.",
                confirmText: "Delete",
                danger: true,
                onConfirm: async () => {
                    await api(`/api/bulletins/${encodeURIComponent(card.dataset.bid)}${qs({ key: org.masterKey })}`, { method: "DELETE" });
                    card.remove();
                    toast("Bulletin deleted.", "ok", "Removed");
                },
            });
        });
    } else {
        const form = $(".comment-form", card);
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const author = getField(form, "author") || "Anonymous";
            const bodyValue = getField(form, "body");
            if (!bodyValue) return;
            const btn = $("button[type=submit]", form);
            const theKey = attendee.accessKey;
            btnBusy(btn, true, "Posting…");
            try {
                await api(`/api/bulletins/${encodeURIComponent(card.dataset.bid)}/comments`, {
                    method: "POST",
                    body: { key: theKey, bulletin_id: card.dataset.bid, author_id: author, body: bodyValue },
                });
                form.querySelector(".cf-body").value = "";
                const comments = await api(`/api/bulletins/${encodeURIComponent(card.dataset.bid)}/comments${qs({ key: theKey })}`);
                renderComments(commentsBox, comments, false);
                countEl.textContent = `${comments.length} comment${comments.length === 1 ? "" : "s"}`;
                toast("Comment posted.", "ok", "Thanks");
            } catch (err) {
                toast(err.message, "error", "Could not post");
            } finally {
                btnBusy(btn, false);
            }
        });
    }
}

function renderComments(box, comments, manage) {
    if (!Array.isArray(comments) || !comments.length) {
        box.innerHTML = `<span class="badge badge-neutral">No comments yet.</span>`;
        return;
    }
    box.innerHTML = comments.map((comment) =>
        `<div class="comment" data-cid="${esc(comment.id)}">` +
        `<div class="c-body">${esc(comment.body)}</div>` +
        `<span class="c-meta">${esc(comment.author_id || "anon")} · ${esc(fmtDate(comment.created_at))}</span>` +
        (manage
            ? `<button class="c-del" type="button" data-act="delete-comment">delete</button>`
            : `<span></span>`) +
        `</div>`
    ).join("");
    if (!manage) return;
    $$("[data-act=delete-comment]", box).forEach((delBtn) => {
        delBtn.addEventListener("click", async () => {
            const row = delBtn.closest(".comment");
            try {
                await api(`/api/comments/${encodeURIComponent(row.dataset.cid)}${qs({ key: org.masterKey })}`, { method: "DELETE" });
                row.remove();
                toast("Comment deleted.", "ok", "Removed");
            } catch (err) {
                toast(err.message, "error", "Could not delete");
            }
        });
    });
}

/* ------------------------------------------------------------------
 * Workspace: Bulletin board tab
 * ------------------------------------------------------------------ */
async function wsBulletins(main) {
    const bulletins = await api(`/api/events/${encodeURIComponent(org.eventId)}/bulletins${qs({ key: org.masterKey })}`);
    main.innerHTML =
        `<section class="card">` +
        `<h3 class="card-title">Bulletin board</h3>` +
        `<div class="bulletin-list">` +
        (bulletins.length
            ? bulletins.map((b) => bulletinCardHTML(b, true)).join("")
            : emptyState("The board is quiet")) +
        `</div>` +
        `</section>` +
        `<section class="card">` +
        `<h3 class="card-title">Post a bulletin</h3>` +
        `<form id="add-bulletin-form" autocomplete="off">` +
        `<div class="field"><label for="bulletin-title">Title</label>` +
        `<input id="bulletin-title" name="title" type="text" maxlength="256" required placeholder="Update — doors at 7"></div>` +
        `<div class="field"><label for="bulletin-body">Details</label>` +
        `<textarea id="bulletin-body" name="body" rows="4" maxlength="65536" required></textarea></div>` +
        `<button class="btn btn-primary" type="submit" id="add-bulletin-btn">Post bulletin</button>` +
        `</form>` +
        `</section>`;

    $$(".bulletin-card", main).forEach((card) => bindBulletinCard(card, true));
    $("#add-bulletin-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const title = getField(form, "title");
        const body = getField(form, "body");
        if (!title || !body) return;
        const btn = $("#add-bulletin-btn");
        btnBusy(btn, true, "Posting…");
        try {
            await api(`/api/events/${encodeURIComponent(org.eventId)}/bulletins`, {
                method: "POST",
                body: { key: org.masterKey, event_id: org.eventId, title, body, author_id: "organizer" },
            });
            toast("Bulletin posted.", "ok", "Board updated");
            await wsBulletins(main);
        } catch (err) {
            toast(err.message, "error", "Could not post");
            btnBusy(btn, false);
        }
    });
}

/* ------------------------------------------------------------------
 * Workspace: Media tab
 * ------------------------------------------------------------------ */
function mediaTile(asset) {
    const isImage = (asset.mime_type || "").startsWith("image/");
    const preview = isImage
        ? `<img class="mt-preview" src="${esc(mediaUrl(asset.id))}" alt="" loading="lazy" referrerpolicy="no-referrer">`
        : `<div class="mt-fallback" aria-hidden="true">📄</div>`;
    return `<figure class="media-tile" data-asset="${esc(asset.id)}">` +
        preview +
        `<figcaption class="mt-info">` +
        `<span class="mt-name" title="${esc(asset.filename)}">${esc(asset.filename)}</span>` +
        `<span class="mt-size">${fmtBytes(asset.size_bytes)} · ${esc(asset.mime_type)}</span>` +
        `</figcaption>` +
        `<div class="mt-actions">` +
        `<button class="btn btn-ghost btn-sm" type="button" data-act="copy-url">Copy link</button>` +
        `<button class="btn btn-danger btn-sm" type="button" data-act="delete-media">Delete</button>` +
        `</div>` +
        `</figure>`;
}

function bindMediaTiles(root) {
    $$("img.mt-preview", root).forEach((img) => {
        img.addEventListener("error", () => {
            const fallback = document.createElement("div");
            fallback.className = "mt-fallback";
            fallback.setAttribute("aria-hidden", "true");
            fallback.textContent = "📄";
            img.replaceWith(fallback);
        });
    });
    $$("[data-asset]", root).forEach((tile) => {
        const assetId = tile.dataset.asset;
        const copyBtn = $('[data-act="copy-url"]', tile);
        if (copyBtn) {
            copyBtn.addEventListener("click", async () => {
                const url = location.origin + mediaUrl(assetId);
                const ok = await copyText(url);
                toast(ok ? "Media link copied — only usable with a key." : "Copy blocked.", ok ? "ok" : "error", "Copy");
            });
        }
        const delBtn = $('[data-act="delete-media"]', tile);
        if (delBtn) {
            delBtn.addEventListener("click", () => {
                openModal({
                    title: "Delete media",
                    body: "Delete this file? It cannot be recovered.",
                    confirmText: "Delete",
                    danger: true,
                    onConfirm: async () => {
                        await api(`/api/media/${encodeURIComponent(assetId)}${qs({ key: org.masterKey })}`, { method: "DELETE" });
                        tile.remove();
                        toast("Media deleted.", "ok", "Removed");
                    },
                });
            });
        }
    });
}

async function wsMedia(main) {
    const assets = await api(`/api/events/${encodeURIComponent(org.eventId)}/media${qs({ key: org.masterKey })}`);
    main.innerHTML =
        `<section class="card">` +
        `<h3 class="card-title">Media library</h3>` +
        (assets.length
            ? `<div class="media-grid">${assets.map((asset) => mediaTile(asset)).join("")}</div>`
            : emptyState("No media yet")) +
        `</section>` +
        `<section class="card">` +
        `<h3 class="card-title">Upload a file</h3>` +
        `<form id="upload-form" class="up-zone">` +
        `<div class="field"><label for="media-file">Choose a file</label>` +
        `<input id="media-file" type="file" required></div>` +
        `<button class="btn btn-primary" type="submit" id="upload-btn">Upload</button>` +
        `</form>` +
        `</section>`;

    bindMediaTiles(main);
    $("#upload-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const input = $("#media-file");
        if (!input || !input.files.length) return;
        const btn = $("#upload-btn");
        const fd = new FormData();
        fd.append("file", input.files[0]);
        btnBusy(btn, true, "Uploading…");
        const url = `/api/events/${encodeURIComponent(org.eventId)}/media${qs({ key: org.masterKey })}`;
        let response;
        try {
            response = await fetch(url, { method: "POST", body: fd });
        } catch {
            toast("Upload failed — is the server running?", "error", "Upload failed");
            btnBusy(btn, false);
            return;
        }
        let detail = "";
        try {
            const data = await response.json();
            detail = data.detail || data.message || "";
        } catch {
            /* not json */
        }
        if (!response.ok) {
            toast(detail || `Upload failed (${response.status})`, "error", "Upload failed");
            btnBusy(btn, false);
            return;
        }
        toast("Media uploaded.", "ok", "Added");
        await wsMedia(main);
    });
}

/* ------------------------------------------------------------------
 * Workspace: Access keys tab
 * ------------------------------------------------------------------ */
/** Build the invite-card metadata for the current workspace event. The card
 *  itself carries no event metadata — `eventId` drives the hidden payload and
 *  QR, `title` is used only for the downloaded file name. */
function inviteCardOpts() {
    return {
        eventId: (org && org.eventId) || "",
        title: (org && org.title) || "Untitled event",
    };
}

/** Modal: make an invite card for an existing key by entering its value. */
function openKeyCardModal(owner) {
    openModal({
        title: "Make an invite card",
        body:
            `<p>The raw access key is shown only once at generation and is not stored again. ` +
            `Enter the <strong>${esc(owner || "key")}</strong> value you were given to embed it in a card.</p>` +
            `<div class="field"><label for="key-card-key">Access key</label>` +
            `<input type="password" id="key-card-key" spellcheck="false" autocomplete="off" placeholder="local:…"></div>` +
            `<p class="field-hint">Send the finished card as a file or attachment — re-encoding it destroys the hidden key (its printed QR is the fallback).</p>`,
        confirmText: "Make card",
        cancelText: "Cancel",
        onConfirm: async () => {
            const input = $("#key-card-key");
            const accessKey = input ? input.value.trim() : "";
            if (!/^local:[0-9a-f]{64}$/i.test(accessKey)) {
                throw new Error("Enter the full access key — it starts with local: followed by 64 hex digits.");
            }
            openCardCoverModal({
                ...inviteCardOpts(),
                accessKey,
                qrText: window.gkpStego.qrPayload((org && org.eventId) || "", accessKey),
            });
        },
    });
    window.setTimeout(() => {
        const input = $("#key-card-key");
        if (input) input.focus();
    }, 0);
}

/* ------------------------------------------------------------------
 * Invite card cover picker (Phase 3.7)
 * ------------------------------------------------------------------ */
const COVER_PRESETS = [
    { id: "none", label: "None" },
    { id: "hatch", label: "Hatch" },
    { id: "keyline", label: "Keyline" },
    { id: "dots", label: "Dots" },
    { id: "keyhole", label: "Keyhole" },
];

/** Modal: pick a cover (preset pattern for the hero band, or an own image
 *  spread across the whole card) then download the invite card. Shared by the
 *  one-shot card button and the per-row "Card" action — purely client-side,
 *  the key never leaves the tab. */
function openCardCoverModal(card) {
    let cover = { type: "none" };
    const chips = COVER_PRESETS.map((p) => {
        const selected = p.id === "none" ? " is-selected" : "";
        const pressed = p.id === "none" ? "true" : "false";
        return (
            `<button class="cover-chip${selected}" type="button" data-cover="${esc(p.id)}" aria-pressed="${pressed}">` +
            `<canvas width="176" height="60" data-swatch="${esc(p.id)}"></canvas>` +
            `<span>${esc(p.label)}</span>` +
            `</button>`
        );
    }).join("");
    const body =
        `<p class="field-hint">Pick a cover — a monochrome pattern for the hero band, or your own image spread across the whole card (nothing cropped; the QR tucks into a corner). ` +
        `The hidden key and the printed QR are untouched.</p>` +
        `<div class="field"><label>Cover</label>` +
        `<div class="cover-picker">${chips}` +
        `<label class="cover-chip cover-upload" id="cover-upload-chip" for="cover-file" role="button" tabindex="0">` +
        `<span class="cover-upload-icon" aria-hidden="true">＋</span>` +
        `<span>Own image…</span>` +
        `</label>` +
        `<input type="file" id="cover-file" accept="image/*" hidden>` +
        `</div>` +
        `<p class="field-hint" id="cover-file-hint">No image chosen — presets only.</p>` +
        `</div>` +
        `<div class="card-preview-wrap"><canvas id="card-preview" width="200" height="300" aria-label="Invite card preview"></canvas></div>`;

    openModal({
        title: "Make an invite card",
        body,
        confirmText: "Download card",
        cancelText: "Cancel",
        onConfirm: async () => {
            await window.gkpInviteCard.download({
                ...card,
                cover,
                coverImage: cover.image || null,
            });
            toast("Invite card downloaded — the key is hidden in its pixels.", "ok", "Card ready");
        },
    });

    const backdrop = $("#modal-root .modal-backdrop");
    const preview = $("#card-preview");

    const refreshPreview = () => {
        window.gkpInviteCard.render(preview, {
            ...card,
            cover,
            coverImage: cover.image || null,
            scale: 0.25,
        });
    };

    // Paint a live swatch of each preset onto its chip.
    $$("[data-swatch]", backdrop).forEach((swatch) => {
        window.gkpInviteCard.renderCover(swatch, swatch.width, swatch.height, { type: "preset", id: swatch.dataset.swatch });
    });

    const selectCover = (next) => {
        cover = next;
        const isPreset = next.type === "preset";
        const isNone = next.type === "none";
        const isImage = next.type === "image";
        $$(".cover-chip[data-cover]", backdrop).forEach((chip) => {
            const sel = (isNone && chip.dataset.cover === "none") || (isPreset && chip.dataset.cover === next.id);
            chip.classList.toggle("is-selected", sel);
            chip.setAttribute("aria-pressed", String(sel));
        });
        const upload = $("#cover-upload-chip");
        if (upload) upload.classList.toggle("is-selected", isImage);
        refreshPreview();
    };

    $$(".cover-chip[data-cover]", backdrop).forEach((chip) => {
        chip.addEventListener("click", () => {
            const id = chip.dataset.cover;
            selectCover(id === "none" ? { type: "none" } : { type: "preset", id });
        });
    });

    const fileInput = $("#cover-file");
    if (fileInput) {
        fileInput.addEventListener("change", () => {
            const file = fileInput.files && fileInput.files[0];
            if (!file) return;
            const url = URL.createObjectURL(file);
            const img = new Image();
            img.onload = () => {
                const hint = $("#cover-file-hint");
                if (hint) hint.textContent = `Own image: ${file.name}`;
                selectCover({ type: "image", image: img, url, name: file.name });
            };
            img.onerror = () => toast("Could not read that image file.", "error", "Cover");
            img.src = url;
        });
    }

    refreshPreview();
}

function keyRowHTML(key) {
    const expires = key.expires_at ? new Date(key.expires_at) : null;
    const expired = Boolean(expires) && expires.getTime() < Date.now();
    const label = key.revoked ? "Revoked" : expired ? "Expired" : "Active";
    const badgeClass = key.revoked ? "badge-revoked" : expired ? "badge-warn" : "badge-active";
    const owner = key.owner_id ? key.owner_id : "unnamed key";
    const cardAction = (key.revoked || expired)
        ? ""
        : `<div class="kd-actions">` +
            `<button class="btn btn-ghost btn-sm" type="button" data-act="card" data-owner="${esc(owner)}">Card</button>` +
            `</div>`;
    return `<div class="key-detail-row" data-key-id="${esc(key.id || key.hash_key)}">` +
        `<span class="badge ${badgeClass}">${esc(label)}</span>` +
        `<div class="kd-info">` +
        `<div class="kd-name">${esc(owner)}</div>` +
        `<div class="kd-sub">created ${esc(fmtDate(key.created_at))} · expires ${esc(fmtDate(key.expires_at))}</div>` +
        `</div>` +
        cardAction +
        `</div>`;
}

async function wsKeys(main) {
    const keys = await api(`/api/events/${encodeURIComponent(org.eventId)}/access-keys${qs({ master_key: org.masterKey })}`);
    main.innerHTML =
        `<section class="card">` +
        `<h3 class="card-title">Access keys</h3>` +
        `<div class="key-list">` +
        (keys.length
            ? keys.map(keyRowHTML).join("")
            : emptyState("No access keys yet")) +
        `</div>` +
        `</section>` +
        `<section class="card">` +
        `<h3 class="card-title">Generate a key</h3>` +
        `<form id="gen-key-form" class="inline-form" autocomplete="off">` +
        `<div class="field"><label for="key-owner">For (name or handle)</label>` +
        `<input id="key-owner" name="owner" type="text" maxlength="256" placeholder="@person" autocomplete="off"></div>` +
        `<div class="field"><label for="key-days">Lifetime (days)</label>` +
        `<input id="key-days" name="days" type="number" min="1" max="365" value="30"></div>` +
        `<button class="btn btn-primary" type="submit" id="gen-key-btn">Generate</button>` +
        `</form>` +
        `</section>` +
        `<section class="card">` +
        `<h3 class="card-title">Revoke a key</h3>` +
        `<form id="revoke-key-form" class="inline-form" autocomplete="off">` +
        `<div class="field"><label for="revoke-key">Access key</label>` +
        `<input id="revoke-key" name="access_key" type="password" maxlength="2048" placeholder="local:…" required spellcheck="false" autocomplete="off"></div>` +
        `<button class="btn btn-danger" type="submit" id="revoke-key-btn">Revoke</button>` +
        `</form>` +
        `</section>`;

    // "Card" action per key row — the raw key value is entered once more
    // (it is shown only at generation and never stored again).
    $$('[data-act="card"]', main).forEach((btn) => {
        btn.addEventListener("click", () => openKeyCardModal(btn.dataset.owner || "key"));
    });

    $("#gen-key-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const owner_id = getField(form, "owner") || null;
        const days = Math.min(Math.max(parseInt(getField(form, "days"), 10) || 30, 1), 365);
        const btn = $("#gen-key-btn");
        btnBusy(btn, true, "Generating…");
        try {
            const key = await api(`/api/events/${encodeURIComponent(org.eventId)}/access-keys`, {
                method: "POST",
                body: { master_key: org.masterKey, event_id: org.eventId, days, owner_id },
            });
            openKeyModal("Access key — share it", key.access_key, inviteCardOpts());
            toast("Access key generated.", "ok", "New key");
            await wsKeys(main);
        } catch (err) {
            toast(err.message, "error", "Could not generate");
            btnBusy(btn, false);
        }
    });

    $("#revoke-key-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const access_key = getField(form, "access_key");
        if (!access_key) return;
        const btn = $("#revoke-key-btn");
        btnBusy(btn, true, "Revoking…");
        try {
            await api(`/api/events/${encodeURIComponent(org.eventId)}/access-keys/revoke`, {
                method: "POST",
                body: { master_key: org.masterKey, event_id: org.eventId, access_key },
            });
            toast("Access key revoked.", "ok", "Done");
            await wsKeys(main);
        } catch (err) {
            toast(err.message, "error", "Could not revoke");
            btnBusy(btn, false);
        }
    });
}

/* ------------------------------------------------------------------
 * Workspace: Decommission (header action)
 * ------------------------------------------------------------------ */
function openDecommissionModal() {
    openModal({
        title: "Decommission event?",
        body:
            `<p>This permanently revokes every access key for <strong>${esc(org.eventId)}</strong>, and ` +
            `content access ends. No attendee will be able to unlock this event again. ` +
            `This cannot be undone.</p>` +
            `<div class="field"><label for="decom-confirm">Type the event ID to confirm</label>` +
            `<input id="decom-confirm" type="text" required spellcheck="false" autocomplete="off"></div>`,
        confirmText: "Decommission",
        danger: true,
        onConfirm: async () => {
            const input = $("#decom-confirm");
            const typed = input ? input.value.trim() : "";
            if (typed !== org.eventId) {
                throw new Error("Type the event ID exactly as shown to confirm.");
            }
            await api(`/api/events/${encodeURIComponent(org.eventId)}/decommission`, {
                method: "POST",
                body: { master_key: org.masterKey, event_id: org.eventId },
            });
            org = null;
            saveSession();
            location.hash = "#/organize";
            renderOrganize();
            toast("Event decommissioned. All keys revoked.", "ok", "Archived");
        },
    });
    const input = $("#decom-confirm");
    if (input) window.setTimeout(() => input.focus(), 0);
}

/* ------------------------------------------------------------------
 * Door: invite-card drop / paste / choose (Phase 3.6)
 * ------------------------------------------------------------------ */
function setDropBusy(drop, busy, label) {
    if (!drop) return;
    const title = drop.querySelector(".key-drop-title");
    const sub = drop.querySelector(".key-drop-sub");
    if (busy) {
        drop.classList.add("is-busy");
        if (title) title.textContent = label || "Reading…";
    } else {
        drop.classList.remove("is-busy");
        if (title) title.textContent = "Drop your invite card here";
        if (sub) sub.textContent = "or paste it with ⌘V — the key lives in its pixels";
    }
}

async function handleInvitePng(file) {
    if (!file) return;
    const drop = $("#key-drop");
    const noteEl = $("#join-note");
    if (noteEl) note(noteEl, "");
    setDropBusy(drop, true, "Reading the key…");
    try {
        const bytes = new Uint8Array(await file.arrayBuffer());
        const kind = window.gkpStego.classifyInvite(bytes);

        // 1) Hidden-key path — PNG cards drop the key straight out of the pixels.
        let parsed = null;
        if (kind === "png") {
            const payload = await window.gkpStego.extract(bytes);
            parsed = payload !== null ? window.gkpStego.parsePayload(payload) : null;
        }
        // 2) QR fallback — any raster image (re-encoded / photographed cards).
        //    The hidden key dies on re-encode, but the printed QR survives.
        if (!parsed) {
            const qrText = await window.gkpDoorQr.decode(file);
            const qp = qrText ? window.gkpStego.parseQrPayload(qrText.trim()) : null;
            if (qp) parsed = { eventId: qp.eventId, accessKey: qp.accessKey, viaQr: true };
        }
        // 3) Honest, specific rejection instead of a generic failure.
        if (!parsed) throw new Error(window.gkpStego.inviteRejectReason(kind));

        const form = $("#join-form");
        if (form) {
            form.elements.event_id.value = parsed.eventId;
            form.elements.access_key.value = parsed.accessKey;
        }
        if (drop) drop.classList.add("is-done");
        toast(
            parsed.viaQr
                ? "QR fallback read from your card — unlock when ready."
                : "Key read from your card — unlock when ready.",
            "ok",
            parsed.viaQr ? "Invite found (QR)" : "Invite found"
        );
        const btn = $("#join-btn");
        if (btn) btn.focus();
    } catch (err) {
        toast(err.message, "error", "Could not read the card");
    } finally {
        setDropBusy(drop, false);
    }
}

function bindJoinDrop() {
    const drop = $("#key-drop");
    const fileInput = $("#key-drop-file");
    if (!drop) return;
    drop.addEventListener("click", () => {
        if (fileInput) fileInput.click();
    });
    drop.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            if (fileInput) fileInput.click();
        }
    });
    ["dragenter", "dragover"].forEach((type) => {
        drop.addEventListener(type, (event) => {
            event.preventDefault();
            drop.classList.add("is-drag");
        });
    });
    ["dragleave", "drop"].forEach((type) => {
        drop.addEventListener(type, (event) => {
            event.preventDefault();
            drop.classList.remove("is-drag");
        });
    });
    drop.addEventListener("drop", (event) => {
        const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
        handleInvitePng(file);
    });
    if (fileInput) {
        fileInput.addEventListener("change", () => {
            handleInvitePng(fileInput.files && fileInput.files[0]);
            fileInput.value = "";
        });
    }
    // Paste anywhere while the join entry is visible: an image card or gkp: text.
    document.addEventListener("paste", (event) => {
        const entry = $("#join-entry");
        if (!entry || entry.hidden) return;
        const items = event.clipboardData && event.clipboardData.items;
        if (items) {
            for (const item of items) {
                if (item.type && item.type.startsWith("image/")) {
                    const file = item.getAsFile && item.getAsFile();
                    if (file) {
                        event.preventDefault();
                        handleInvitePng(file);
                        return;
                    }
                }
            }
        }
        const text = event.clipboardData && event.clipboardData.getData("text");
        const parsed = text ? window.gkpStego.parseQrPayload(text.trim()) : null;
        if (parsed) {
            const form = $("#join-form");
            if (form) {
                event.preventDefault();
                form.elements.event_id.value = parsed.eventId;
                form.elements.access_key.value = parsed.accessKey;
                toast("Invite pasted — unlock when ready.", "ok", "Invite found");
            }
        }
    });
}

/* ------------------------------------------------------------------
 * Join entry (unlock)
 * ------------------------------------------------------------------ */
function bindJoinEntry() {
    const form = $("#join-form");
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const noteEl = $("#join-note");
        const btn = $("#join-btn");
        note(noteEl, "");
        const eventId = getField(form, "event_id");
        const accessKey = getField(form, "access_key");
        if (!eventId || !accessKey) {
            note(noteEl, "Both the event ID and your access key are required.", "error");
            return;
        }
        btnBusy(btn, true, "Unlocking…");
        try {
            // The gateway answers any valid key+content pair with the event dict.
            const result = await api("/api/access", {
                method: "POST",
                body: { key: accessKey, content_id: eventId },
            });
            if (!result || result.status !== "success") {
                throw new Error((result && result.message) || "The key did not unlock this event.");
            }
            attendee = { eventId, accessKey, event: result.data || {} };
            form.reset();
            saveSession();
            $("#join-entry").hidden = true;
            $("#join-event").hidden = false;
            renderEventPage();
            toast("Event unlocked.", "ok", "Welcome");
        } catch (err) {
            note(noteEl, err.message, "error");
        } finally {
            btnBusy(btn, false);
        }
    });
}

function renderJoin() {
    const entry = $("#join-entry");
    const evt = $("#join-event");
    if (attendee) {
        if (entry) entry.hidden = true;
        if (evt) {
            evt.hidden = false;
            renderEventPage();
        }
    } else {
        if (evt) evt.hidden = true;
        if (entry) entry.hidden = false;
    }
}

/* ------------------------------------------------------------------
 * Attendee event page
 * ------------------------------------------------------------------ */
function renderEventPage() {
    const root = $("#join-views");
    if (!root || !attendee) return;
    const event = attendee.event || {};
    root.innerHTML =
        `<header class="ep-head">` +
        `<p class="eyebrow ep-eyebrow">You're invited</p>` +
        `<h2 class="ep-title">${esc(event.title || "Untitled event")}</h2>` +
        `<p class="ep-lede">${esc(event.description || "")}</p>` +
        `<div class="ep-meta">` +
        (event.location_data ? `<span class="ep-meta-item">📍 ${esc(event.location_data)}</span>` : "") +
        `<span class="ep-meta-item">by ${esc(event.organizer_id || "organizer")}</span>` +
        `<button class="btn btn-ghost btn-sm" type="button" id="attendee-end">Leave (drop key)</button>` +
        `</div>` +
        `</header>` +
        `<div class="ep-main">` +
        `<section class="card"><h3 class="card-title">Bulletin board</h3>` +
        `<div id="ep-bulletins" class="bulletin-list">Loading…</div></section>` +
        `<section class="card"><h3 class="card-title">Media</h3>` +
        `<div id="ep-media">Loading…</div></section>` +
        `</div>`;

    $("#attendee-end").addEventListener("click", () => {
        attendee = null;
        saveSession();
        location.hash = "#/join";
        renderJoin();
        toast("Key dropped. To re-enter, use the invite again.", "info", "Signed out");
    });

    loadAttendeeBulletins();
    loadAttendeeMedia();
}

async function loadAttendeeBulletins() {
    const box = $("#ep-bulletins");
    if (!box) return;
    try {
        const bulletins = await api(`/api/events/${encodeURIComponent(attendee.eventId)}/bulletins${qs({ key: attendee.accessKey })}`);
        if (bulletins && bulletins.length) {
            box.innerHTML = bulletins.map((b) => bulletinCardHTML(b, false)).join("");
            $$(".bulletin-card", box).forEach((card) => bindBulletinCard(card, false));
        } else {
            box.innerHTML = emptyState("Nothing posted yet");
        }
    } catch (err) {
        box.innerHTML = emptyState("Could not load the board", err.message);
    }
}

function attendeeMediaTile(asset) {
    const isImage = (asset.mime_type || "").startsWith("image/");
    const preview = isImage
        ? `<img class="mt-preview" src="${esc(mediaUrl(asset.id))}" alt="${esc(asset.filename)}" loading="lazy" referrerpolicy="no-referrer">`
        : `<div class="mt-fallback" aria-hidden="true">📄</div>`;
    return `<div class="media-tile" data-asset="${esc(asset.id)}">` +
        preview +
        `<div class="mt-info">` +
        `<span class="mt-name" title="${esc(asset.filename)}">${esc(asset.filename)}</span>` +
        `<span class="mt-size">${fmtBytes(asset.size_bytes)} · ${esc(asset.mime_type)}</span>` +
        `</div>` +
        `<div class="mt-actions"><a class="btn btn-ghost btn-sm" href="${esc(mediaUrl(asset.id))}" target="_blank" rel="noopener">Open</a></div>` +
        `</div>`;
}

async function loadAttendeeMedia() {
    const box = $("#ep-media");
    if (!box) return;
    try {
        const assets = await api(`/api/events/${encodeURIComponent(attendee.eventId)}/media${qs({ key: attendee.accessKey })}`);
        if (assets && assets.length) {
            box.innerHTML = `<div class="media-grid">${assets.map(attendeeMediaTile).join("")}</div>`;
            $$("img.mt-preview", box).forEach((img) => {
                img.addEventListener("error", () => {
                    const fallback = document.createElement("div");
                    fallback.className = "mt-fallback";
                    fallback.setAttribute("aria-hidden", "true");
                    fallback.textContent = "📄";
                    img.replaceWith(fallback);
                });
            });
        } else {
            box.innerHTML = emptyState("No media yet");
        }
    } catch (err) {
        box.innerHTML = emptyState("Could not load media", err.message);
    }
}

/* ------------------------------------------------------------------
 * Lite events (ephemeral flyer funnel)
 * ------------------------------------------------------------------ */

/** Render the flyer creation funnel result panel. */
function showFlyerDone(done, body) {
    const publicUrl = body.public_url || `${location.origin}/i/${body.event_id}`;
    const eventHref =
        `#/e/${encodeURIComponent(body.event_id)}?k=${encodeURIComponent(body.master_key)}`;
    done.innerHTML =
        `<header class="view-head"><p class="eyebrow">Lite events</p>` +
        `<h2 class="view-title">Your event is live</h2></header>` +
        `<div class="card form-card">` +
        `<h3 class="card-title">Save the master key now</h3>` +
        `<p class="key-hint">It is shown <strong>only once</strong> and never stored anywhere ` +
        `you can read later. Keep it to manage this event until it auto-wipes.</p>` +
        `<code class="key-hint">${esc(body.master_key)}</code>` +
        `<div class="field"><label>Share link (anyone)</label>` +
        `<div class="item"><code>${esc(publicUrl)}</code></div></div>` +
        `<div class="item"><a class="btn btn-primary" href="${esc(eventHref)}">` +
        `Open the event page</a></div>` +
        `</div>`;
}

async function renderFlyer() {
    const entry = $("#flyer-entry");
    const done = $("#flyer-done");
    if (!entry || !done) return;
    entry.hidden = false;
    done.hidden = true;

    const form = $("#flyer-form");
    if (!form || form.dataset.bound) return;
    form.dataset.bound = "1";
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const note = $("#flyer-note");
        const btn = $("#flyer-btn");
        note.textContent = "";
        btn.disabled = true;
        try {
            const fd = new FormData();
            fd.set("title", $("#flyer-title").value);
            fd.set("description", $("#flyer-description").value);
            fd.set("when", $("#flyer-when").value);
            fd.set("where", $("#flyer-where").value);
            fd.set("ttl_hours", String(Number($("#flyer-ttl")?.value || 48)));
            const file = $("#flyer-file")?.files?.[0];
            if (file) fd.set("flyer", file, file.name);
            const resp = await fetch("/api/lite/events", { method: "POST", body: fd });
            const body = await resp.json().catch(() => ({}));
            if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`);
            entry.hidden = true;
            showFlyerDone(done, body);
            toast("Copy the master key before leaving this page.", "ok", "Event is live");
        } catch (err) {
            note.textContent = err.message;
        } finally {
            btn.disabled = false;
        }
    });
}

/** Pull the lite event id (and optional key) out of `#/e/{id}?k=…`. */
function parseLiteHash() {
    const raw = (location.hash || "#/").replace(/^#/, "");
    const [path, query] = raw.split("?");
    if (!path.startsWith("/e/")) return { id: "", key: "" };
    const params = new URLSearchParams(query || "");
    return { id: path.slice(3), key: params.get("k") || "" };
}

function liteKeyForm() {
    return `<form id="lite-key-form" class="card form-card" autocomplete="off">` +
        `<h3 class="card-title">Unlock this event</h3>` +
        `<div class="field"><label for="lite-key">Event key</label>` +
        `<input type="password" id="lite-key" required placeholder="local:…" autocomplete="off"></div>` +
        `<p class="key-hint">Your key unlocks the event details and never leaves this tab.</p>` +
        `<button type="submit" class="btn btn-primary btn-block">Unlock</button></form>`;
}

async function renderLiteEvent() {
    const root = $("#lite-views");
    if (!root) return;
    const { id, key } = parseLiteHash();
    if (!id) {
        root.innerHTML = emptyState("No event here", "This page needs an event id in the link.");
        return;
    }
    if (!key) {
        root.innerHTML = liteKeyForm();
        $("#lite-key-form").addEventListener("submit", (event) => {
            event.preventDefault();
            const entered = $("#lite-key").value.trim();
            location.hash = `#/e/${encodeURIComponent(id)}?k=${encodeURIComponent(entered)}`;
        });
        return;
    }
    root.innerHTML = `<p class="form-note">Unlocking…</p>`;
    try {
        const data = await api(`/api/lite/events/${encodeURIComponent(id)}${qs({ key })}`);
        const evt = data.event || {};
        const flyer = data.flyer_asset_id
            ? `<img class="lite-flyer" src="/api/lite/events/${encodeURIComponent(id)}/flyer" alt="${esc(evt.title || "Flyer")}">`
            : "";
        root.innerHTML =
            `<div class="view-head"><p class="eyebrow">Lite event</p>` +
            `<h2 class="view-title">${esc(evt.title || "")}</h2></div>` +
            `${flyer}` +
            (evt.description ? `<p>${esc(evt.description)}</p>` : "") +
            (data.when ? `<p><strong>When:</strong> ${esc(data.when)}</p>` : "") +
            (data.where ? `<p><strong>Where:</strong> ${esc(data.where)}</p>` : "") +
            `<p class="form-note">This page is temporary — everything is wiped ` +
            `${esc(fmtDate(data.expires_at))}.</p>`;
    } catch (err) {
        if (/ended|expired/i.test(err.message)) {
            root.innerHTML = emptyState("Event ended", "All data for this event was wiped.");
        } else {
            root.innerHTML = emptyState("Could not unlock this event", err.message);
        }
    }
}

/* ------------------------------------------------------------------
 * Boot
 * ------------------------------------------------------------------ */
function init() {
    loadSession();
    initTheme();
    bindOrganizeEntry();
    bindJoinDrop();
    bindJoinEntry();
    window.addEventListener("hashchange", route);
    route();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}
