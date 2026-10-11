/* gatekeyp — browser app for the organizer desk and the attendee door.
 *
 * Hash-routed, no framework. Talks to the same JSON API the server exposes.
 * Keys never leave this tab: the organizer key and attendee keys live in
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
// Organizer workspace: { eventId, organizerKey, title }
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
        throw new Error("Network error — is the cellar server running?");
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
    const key = (org && org.organizerKey) || (attendee && attendee.accessKey) || "";
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

/** Modal that turns a freshly generated key into its one artifact: the invite
 *  card. The raw key text is never displayed or copied — the card's pixels are
 *  the only copy, so closing without "Make the card" destroys the key. */
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
    else if (name === "e") {
        // Lite events: the share page (/i/{id}) IS the event page — the key
        // no longer gates anything on it, so the hash route just redirects.
        const { id } = parseLiteHash();
        if (id) {
            location.href = `/i/${encodeURIComponent(id)}`;
        } else {
            const root = $("#lite-views");
            if (root) root.innerHTML = emptyState("No event here", "This page needs an event id in the link.");
        }
    } else if (name === "rsvp") renderRsvp();
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
    // Paste an organizer card image while the organize entry is showing —
    // organize entry is showing — the card is the only way back in.
    document.addEventListener("paste", async (event) => {
        const view = $("#view-organize");
        const workspace = $("#organize-workspace");
        if (!view || view.hidden || !workspace || !workspace.hidden) return;
        const items = event.clipboardData && event.clipboardData.items;
        if (items) {
            for (const item of items) {
                if (item.type && item.type.startsWith("image/")) {
                    const file = item.getAsFile && item.getAsFile();
                    if (file) {
                        event.preventDefault();
                        const bytes = new Uint8Array(await file.arrayBuffer());
                        if (window.gkpStego.classifyInvite(bytes) !== "png") break; // not ours
                        const payload = await window.gkpStego.extract(bytes);
                        const parsed = payload !== null ? window.gkpStego.parsePayload(payload) : null;
                        if (parsed && parsed.role === "organizer") {
                            try {
                                await openOrganizerWorkspace(parsed.eventId, parsed.accessKey);
                                toast("Workspace restored from your organizer card.", "ok", "Welcome back");
                            } catch (err) {
                                toast(err.message, "error", "Could not read the card");
                            }
                        } else {
                            toast(
                                parsed
                                    ? "That is an attendee invite — attendee cards belong on the Join tab."
                                    : "No event found in that image.",
                                "error",
                                "Could not read the card"
                            );
                        }
                        return;
                    }
                }
            }
        }
    });

    const createForm = $("#create-event-form");
    createForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const noteEl = $("#create-note");
        const btn = $("#create-btn");
        note(noteEl, "");
        const title = getField(createForm, "title");
        const description = getField(createForm, "description");
        const location_data = getField(createForm, "location_data") || null;
        if (!title || !description) {
            note(noteEl, "A title and description are required.", "error");
            return;
        }
        btnBusy(btn, true, "Creating…");
        try {
            const created = await api("/api/events", {
                method: "POST",
                body: { title, description, organizer_id: "organizer", location_data },
            });
            org = {
                eventId: created.event_id,
                organizerKey: created.organizer_key,
                title: created.title || title,
                meta: { description, locationData: location_data },
            };
            // Optional flyer: upload it onto the event, then record it as the
            // event's flyer so card covers can reuse it.
            const flyerInput = $("#create-flyer");
            if (flyerInput && flyerInput.files && flyerInput.files.length) {
                const fd = new FormData();
                fd.append("file", flyerInput.files[0]);
                const url = `/api/events/${encodeURIComponent(org.eventId)}/media${qs({ key: org.organizerKey })}`;
                const resp = await fetch(url, { method: "POST", body: fd });
                if (!resp.ok) {
                    const data = await resp.json().catch(() => ({}));
                    throw new Error(data.detail || "Flyer upload failed");
                }
                const uploaded = await resp.json();
                await api(`/api/events/${encodeURIComponent(org.eventId)}/flyer`, {
                    method: "POST",
                    body: { organizer_key: org.organizerKey, asset_id: (uploaded && uploaded.id) || null },
                });
            }
            createForm.reset();
            saveSession();
            goWorkspace();
            openCardCoverModal({
                ...inviteCardOpts(),
                accessKey: created.organizer_key,
                organizer: true,
                fresh: true,
            });
            toast("Event created. Share access keys, never this organizer key.", "ok", "Ready");
        } catch (err) {
            note(noteEl, err.message, "error");
            btnBusy(btn, false);
        }
    });

    const openForm = $("#open-event-form");
    if (openForm) openForm.addEventListener("submit", (event) => event.preventDefault());
}

/** Show the workspace container, then sync the URL hash so the router
 *  stays consistent — necessary when entering from another view (e.g.
 *  dropping an organizer card on the Join page). */
function goWorkspace() {
    const entry = $("#organize-entry");
    const workspace = $("#organize-workspace");
    if (entry) entry.hidden = true;
    if (workspace) workspace.hidden = false;
    renderWorkspace();
    if (location.hash !== "#/organize") {
        location.hash = "#/organize";
    }
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
let wsTab = "board";

const WS_TABS = [
    ["board", "Board"],
    ["keys", "Access keys"],
    ["rsvps", "RSVP funnel"],
];

const WS_LOADERS = {
    board: wsBoard,
    keys: wsKeys,
    rsvps: wsRsvps,
};

async function fetchEventDetails() {
    return api(`/api/events/${encodeURIComponent(org.eventId)}${qs({ organizer_key: org.organizerKey })}`);
}

function renderWorkspace() {
    const root = $("#organize-views");
    if (!root || !org) return;
    root.innerHTML =
        `<header class="ws-head">` +
        `<div class="ws-titles">` +
        `<h2 class="ws-title">${esc(org.title || "Event workspace")}</h2>` +
        (org.meta && org.meta.description ? `<p class="ws-sub">${esc(org.meta.description)}</p>` : "") +
        (org.meta && org.meta.locationData ? `<p class="ws-loc">${esc(org.meta.locationData)}</p>` : "") +
        `<span id="ws-event-id" hidden>${esc(org.eventId)}</span>` +
        `</div>` +
        `<div class="ws-actions">` +
        `<button class="btn btn-ghost" type="button" id="ws-organizer-card">Organizer card</button>` +
        `<button class="btn btn-ghost" type="button" id="ws-end">Close workspace</button>` +
        `<button class="btn btn-danger" type="button" id="ws-decommission">Decommission</button>` +
        `</div>` +
        `</header>` +
        `<nav class="tabs" role="tablist" aria-label="Workspace sections">` +
        WS_TABS.map(([id, label]) =>
            `<button class="tab" type="button" role="tab" data-tab="${id}" aria-selected="${id === wsTab}">${esc(label)}</button>`
        ).join("") +
        `</nav>` +
        `<div class="ws-body">` +
        `<main class="ws-main" role="tabpanel" id="ws-main"></main>` +
        `</div>`;

    const orgCardBtn = $("#ws-organizer-card");
    if (orgCardBtn) {
        orgCardBtn.addEventListener("click", () => {
            if (!org || !org.organizerKey) return;
            openCardCoverModal({
                ...inviteCardOpts(),
                accessKey: org.organizerKey,
                organizer: true,
            });
        });
    }

    $("#ws-end").addEventListener("click", () => {
        org = null;
        saveSession();
        location.hash = "#/organize";
        renderOrganize();
        toast("Workspace closed. Organizer key discarded from this tab.", "info", "Signed out");
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
    const loader = WS_LOADERS[wsTab] || wsBoard;
    try {
        await loader(main);
    } catch (err) {
        main.innerHTML = emptyState("Could not load", err.message);
    }
}

/* ------------------------------------------------------------------
 * Workspace: Board tab (single post type: title + content + comments,
 * with an optional media attachment)
 * ------------------------------------------------------------------ */
/** Render a bulletin's optional attached media tile (if media_id matches). */
function bulletinMediaHTML(bulletin, assetsById) {
    const asset = bulletin && bulletin.media_id ? assetsById[bulletin.media_id] : null;
    if (!asset) return "";
    const isImage = (asset.mime_type || "").startsWith("image/");
    const preview = isImage
        ? `<img class="mt-preview" src="${esc(mediaUrl(asset.id))}" alt="${esc(asset.filename)}" loading="lazy" referrerpolicy="no-referrer">`
        : `<div class="mt-fallback" aria-hidden="true">📄</div>`;
    return `<div class="b-media">` +
        `<div class="media-tile" data-asset="${esc(asset.id)}">` +
        preview +
        `<div class="mt-info">` +
        `<span class="mt-name" title="${esc(asset.filename)}">${esc(asset.filename)}</span>` +
        `<span class="mt-size">${fmtBytes(asset.size_bytes)} · ${esc(asset.mime_type)}</span>` +
        `</div>` +
        `<div class="mt-actions"><a class="btn btn-ghost btn-sm" href="${esc(mediaUrl(asset.id))}" target="_blank" rel="noopener">Open</a></div>` +
        `</div></div>`;
}

function boardPostHTML(post, assetsById) {
    const time = esc(fmtDate(post.created_at));
    if (post._type === "media") {
        return mediaTile(post);
    }
    if (post._type === "block") { // legacy content block
        const label = esc(contentTypeLabel(post.content_type));
        return `<div class="item board-post">` +
            `<div class="item-head">` +
            `<span class="tag">${label}</span>` +
            `<span class="item-title">${esc(post.content_type || "note")}</span>` +
            `</div>` +
            `<div class="item-body">${esc(post.payload || "")}</div>` +
            `<div class="item-meta">${time}</div>` +
            `</div>`;
    }
    // bulletin (keep card + attached media together so a delete removes both)
    return `<div class="board-entry">` +
        bulletinCardHTML(post, true) +
        bulletinMediaHTML(post, assetsById) +
        `</div>`;
}

async function wsBoard(main) {
    const [details, bulletins, assets] = await Promise.all([
        fetchEventDetails(),
        api(`/api/events/${encodeURIComponent(org.eventId)}/bulletins${qs({ key: org.organizerKey })}`).catch(() => []),
        api(`/api/events/${encodeURIComponent(org.eventId)}/media${qs({ key: org.organizerKey })}`).catch(() => []),
    ]);
    const assetsById = {};
    assets.forEach((a) => { assetsById[a.id] = a; });
    const flyerAsset = (details.event && details.event.flyer_asset_id)
        ? (assetsById[details.event.flyer_asset_id] || null)
        : null;
    const attached = new Set(bulletins.map((b) => b.media_id).filter(Boolean));
    const blocks = (details.content_blocks || []).map((b) => ({ ...b, _type: "block" }));
    const posts = [
        ...blocks,
        ...bulletins.map((b) => ({ ...b, _type: "bulletin" })),
        ...assets.filter((a) => !attached.has(a.id)).map((a) => ({ ...a, _type: "media" })),
    ].sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));

    const flyerCurrent = flyerAsset
        ? `<div class="media-tile flyer-current" data-asset="${esc(flyerAsset.id)}">` +
          `${(flyerAsset.mime_type || "").startsWith("image/")
              ? `<img class="mt-preview" src="${esc(mediaUrl(flyerAsset.id))}" alt="${esc(flyerAsset.filename)}" loading="lazy" referrerpolicy="no-referrer">`
              : `<div class="mt-fallback" aria-hidden="true">📄</div>`}` +
          `<div class="mt-info"><span class="mt-name">${esc(flyerAsset.filename)}</span></div>` +
          `</div>`
        : emptyState("No flyer yet", "Upload one to use as the card cover.");

    main.innerHTML =
        (posts.length
            ? `<section class="card"><h3 class="card-title">Posts</h3>` +
              `<div id="board-posts">${posts.map((p) => boardPostHTML(p, assetsById)).join("")}</div>` +
              `</section>`
            : `<section class="card">${emptyState("No posts yet", "Write the first one below.")}</section>`) +

        `<section class="card">` +
        `<h3 class="card-title">Event flyer</h3>` +
        `<div id="board-flyer-current">${flyerCurrent}</div>` +
        `<form id="board-flyer-form" autocomplete="off">` +
        `<div class="field"><label for="board-flyer-file">Upload or replace the event flyer</label>` +
        `<input type="file" id="board-flyer-file" accept="image/*,application/pdf,text/plain"></div>` +
        `<button class="btn btn-primary" type="submit" id="board-flyer-btn">Upload flyer</button>` +
        `</form>` +
        `</section>` +

        `<section class="card">` +
        `<h3 class="card-title">New post</h3>` +
        `<form id="board-post-form" autocomplete="off">` +
        `<div class="field"><label for="bulletin-title">Title</label>` +
        `<input id="bulletin-title" name="title" type="text" maxlength="256" required></div>` +
        `<div class="field"><label for="bulletin-body">Content</label>` +
        `<textarea id="bulletin-body" name="body" rows="4" maxlength="65536" required></textarea></div>` +
        `<div class="field"><label for="media-file">Attachment (optional)</label>` +
        `<input id="media-file" name="media" type="file"></div>` +
        `<button class="btn btn-primary" type="submit" id="board-post-btn">Post</button>` +
        `</form>` +
        `</section>`;

    // Bind bulletin cards
    $$(".bulletin-card", main).forEach((card) => bindBulletinCard(card, true));
    // Bind standalone media tiles
    bindMediaTiles(main);

    // Upload or replace the event flyer.
    $("#board-flyer-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const input = $("#board-flyer-file");
        if (!input || !input.files || !input.files.length) return;
        const btn = $("#board-flyer-btn");
        btnBusy(btn, true, "Uploading…");
        try {
            const fd = new FormData();
            fd.append("file", input.files[0]);
            const url = `/api/events/${encodeURIComponent(org.eventId)}/media${qs({ key: org.organizerKey })}`;
            const resp = await fetch(url, { method: "POST", body: fd });
            if (!resp.ok) {
                const data = await resp.json().catch(() => ({}));
                throw new Error(data.detail || `Upload failed (${resp.status})`);
            }
            const uploaded = await resp.json();
            const newId = (uploaded && uploaded.id) || null;
            await api(`/api/events/${encodeURIComponent(org.eventId)}/flyer`, {
                method: "POST",
                body: { organizer_key: org.organizerKey, asset_id: newId },
            });
            // Replace removes the old flyer asset to avoid bloat.
            const oldId = flyerAsset ? flyerAsset.id : null;
            if (oldId && oldId !== newId) {
                await api(`/api/media/${encodeURIComponent(oldId)}${qs({ key: org.organizerKey })}`, { method: "DELETE" }).catch(() => {});
            }
            toast("Event flyer updated.", "ok", "Saved");
            await wsBoard(main);
        } catch (err) {
            toast(err.message, "error", "Could not upload flyer");
            btnBusy(btn, false);
        }
    });

    // Submit
    $("#board-post-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const btn = $("#board-post-btn");
        btnBusy(btn, true, "Posting…");
        try {
            const title = getField(event.target, "title");
            const body = getField(event.target, "body");
            if (!title || !body) throw new Error("Title and content are required.");

            // Optional attachment: upload first, then attach to the post.
            const input = $("#media-file");
            let mediaId = null;
            if (input && input.files && input.files.length) {
                const fd = new FormData();
                fd.append("file", input.files[0]);
                const url = `/api/events/${encodeURIComponent(org.eventId)}/media${qs({ key: org.organizerKey })}`;
                const resp = await fetch(url, { method: "POST", body: fd });
                if (!resp.ok) {
                    const data = await resp.json().catch(() => ({}));
                    throw new Error(data.detail || `Upload failed (${resp.status})`);
                }
                const uploaded = await resp.json();
                mediaId = (uploaded && uploaded.id) || null;
            }

            await api(`/api/events/${encodeURIComponent(org.eventId)}/bulletins`, {
                method: "POST",
                body: {
                    key: org.organizerKey,
                    event_id: org.eventId,
                    title,
                    body,
                    author_id: "organizer",
                    media_id: mediaId,
                },
            });
            toast("Post published.", "ok", "Board updated");
            await wsBoard(main);
        } catch (err) {
            toast(err.message, "error", "Could not post");
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
              `<input class="cf-author" id="cf-a-${esc(bulletin.id)}" name="author" type="text" maxlength="256" autocomplete="off"></div>` +
              `<div class="field cf-body"><label for="cf-b-${esc(bulletin.id)}">Reply</label>` +
              `<input class="cf-body" id="cf-b-${esc(bulletin.id)}" name="body" type="text" maxlength="16384" required autocomplete="off"></div>` +
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
    // Posts are expanded by default so the content is visible without a click.
    let open = true;
    let loaded = false;
    body.hidden = false;
    card.classList.add("bulletin-open");
    head.setAttribute("aria-expanded", "true");

    const load = async () => {
        if (loaded) return;
        commentsBox.innerHTML = `<span class="badge badge-neutral">Loading…</span>`;
        try {
            const theKey = (org && org.organizerKey) || (attendee && attendee.accessKey) || "";
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

    const toggle = async () => {
        open = !open;
        body.hidden = !open;
        card.classList.toggle("bulletin-open", open);
        head.setAttribute("aria-expanded", String(open));
        if (open) await load();
    };
    head.addEventListener("click", toggle);
    head.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggle();
        }
    });

    // Load content immediately since the post starts expanded.
    load();

    if (manage) {
        const delBtn = $('[data-act="delete-bulletin"]', card);
        delBtn.addEventListener("click", () => {
            openModal({
                title: "Delete bulletin",
                body: "Delete this bulletin and all of its comments? This cannot be undone.",
                confirmText: "Delete",
                danger: true,
                onConfirm: async () => {
                    await api(`/api/bulletins/${encodeURIComponent(card.dataset.bid)}${qs({ key: org.organizerKey })}`, { method: "DELETE" });
                    const holder = card.closest(".board-entry") || card;
                    holder.remove();
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
                await api(`/api/comments/${encodeURIComponent(row.dataset.cid)}${qs({ key: org.organizerKey })}`, { method: "DELETE" });
                row.remove();
                toast("Comment deleted.", "ok", "Removed");
            } catch (err) {
                toast(err.message, "error", "Could not delete");
            }
        });
    });
}

/* ------------------------------------------------------------------
 * Media tile helpers (used by the board and attendee views)
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
                        await api(`/api/media/${encodeURIComponent(assetId)}${qs({ key: org.organizerKey })}`, { method: "DELETE" });
                        tile.remove();
                        toast("Media deleted.", "ok", "Removed");
                    },
                });
            });
        }
    });
}

/* ------------------------------------------------------------------
 * Workspace: Access keys tab
 * ------------------------------------------------------------------ */
/** Build the invite-card metadata for the current workspace event. The card
 *  carries no visible event metadata — `eventId` is hidden in the pixels and
 *  `title` is used only for the downloaded file name. */
function inviteCardOpts() {
    return {
        eventId: (org && org.eventId) || "",
        title: (org && org.title) || "Untitled event",
    };
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

/** Modal: pick a cover (preset pattern, the event flyer, or an own image
 *  spread across the whole card) then download the invite card. Shared by the
 *  one-shot card button and the per-row "Card" action — purely client-side,
 *  the key never leaves the tab. */
function openCardCoverModal(card) {
    let cover = { type: "none" };
    let flyer = null; // { image, url } resolved from the event's flyer if any

    // Resolve the event's flyer as a cover option (organizer flows only).
    const resolveFlyer = async () => {
        if (!org || !org.organizerKey) return;
        try {
            const details = await fetchEventDetails();
            const fId = details.event && details.event.flyer_asset_id;
            if (!fId) return;
            flyer = { image: await window.gkpInviteCard.loadCoverImage({ type: "image", src: mediaUrl(fId) }), url: mediaUrl(fId) };
        } catch {
            flyer = null;
        }
    };

    resolveFlyer().then(() => {
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
        const flyerChip = flyer
            ? `<button class="cover-chip" type="button" data-cover="flyer" aria-pressed="false">` +
              `<canvas width="176" height="60" data-flyer-swatch></canvas>` +
              `<span>Flyer</span></button>`
            : "";
        const body =
            `<div class="field"><label>Cover</label>` +
            `<div class="cover-picker">${chips}${flyerChip}` +
            `<label class="cover-chip cover-upload" id="cover-upload-chip" for="cover-file" role="button" tabindex="0">` +
            `<span class="cover-upload-icon" aria-hidden="true">＋</span>` +
            `<span>Own image…</span>` +
            `</label>` +
            `<input type="file" id="cover-file" accept="image/*" hidden>` +
            `</div>` +
            `</div>` +
            `<div class="card-preview-wrap"><canvas id="card-preview" width="200" height="300" aria-label="Invite card preview"></canvas></div>`;

        openModal({
            title: card.organizer ? "Make a organizer card" : "Make an invite card",
            body,
            confirmText: "Download card",
            cancelText: "Cancel",
            onConfirm: async () => {
                await window.gkpInviteCard.download({
                    ...card,
                    cover,
                    coverImage: cover.image || null,
                });
                toast(
                    card.organizer
                        ? "Organizer card downloaded — it reopens the event on this tab."
                        : "Invite card downloaded — the key is hidden in its pixels.",
                    "ok",
                    "Card ready"
                );
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
        // Paint the flyer onto its chip.
        if (flyer) {
            const fs = $(`[data-flyer-swatch]`, backdrop);
            if (fs) window.gkpInviteCard.renderCover(fs, fs.width, fs.height, { type: "image" }, flyer.image);
        }

        const selectCover = (next) => {
            cover = next;
            const isImage = next.type === "image";
            const isFlyer = next.flyer === true;
            $$(".cover-chip[data-cover]", backdrop).forEach((chip) => {
                const sel = (next.type === "none" && chip.dataset.cover === "none")
                    || (next.type === "preset" && chip.dataset.cover === next.id)
                    || (isFlyer && chip.dataset.cover === "flyer");
                chip.classList.toggle("is-selected", sel);
                chip.setAttribute("aria-pressed", String(sel));
            });
            const upload = $("#cover-upload-chip");
            if (upload) upload.classList.toggle("is-selected", isImage && !isFlyer);
            refreshPreview();
        };

        $$(".cover-chip[data-cover]", backdrop).forEach((chip) => {
            chip.addEventListener("click", () => {
                const id = chip.dataset.cover;
                if (id === "flyer" && flyer) {
                    selectCover({ type: "image", image: flyer.image, url: flyer.url, name: "Flyer", flyer: true });
                } else {
                    selectCover(id === "none" ? { type: "none" } : { type: "preset", id });
                }
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
                    selectCover({ type: "image", image: img, url, name: file.name });
                };
                img.onerror = () => toast("Could not read that image file.", "error", "Cover");
                img.src = url;
            });
        }

        refreshPreview();
    });
}

function keyRowHTML(key) {
    const expires = key.expires_at ? new Date(key.expires_at) : null;
    const expired = Boolean(expires) && expires.getTime() < Date.now();
    const active = !key.revoked && !expired;
    const label = key.revoked ? "Revoked" : expired ? "Expired" : "Active";
    const badgeClass = key.revoked ? "badge-revoked" : expired ? "badge-warn" : "badge-active";
    const owner = key.owner_id ? key.owner_id : "unnamed key";
    const revokeBtn = active
        ? `<button class="btn btn-danger btn-sm" type="button" data-act="revoke-key" aria-label="Revoke ${esc(owner)}">Revoke</button>`
        : "";
    return `<div class="key-detail-row" data-key-hash="${esc(key.id || key.hash_key)}">` +
        `<span class="badge ${badgeClass}">${esc(label)}</span>` +
        `<div class="kd-info">` +
        `<div class="kd-name">${esc(owner)}</div>` +
        `<div class="kd-sub">created ${esc(fmtDate(key.created_at))} · expires ${esc(fmtDate(key.expires_at))}</div>` +
        `</div>` +
        revokeBtn +
        `</div>`;
}

async function wsKeys(main) {
    const keys = await api(`/api/events/${encodeURIComponent(org.eventId)}/access-keys${qs({ organizer_key: org.organizerKey })}`);
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
        `<input id="key-owner" name="owner" type="text" maxlength="256" autocomplete="off"></div>` +
        `<div class="field"><label for="key-days">Lifetime (days)</label>` +
        `<input id="key-days" name="days" type="number" min="1" max="365" value="30"></div>` +
        `<button class="btn btn-primary" type="submit" id="gen-key-btn">Generate</button>` +
        `</form>` +
        `</section>`;

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
                body: { organizer_key: org.organizerKey, event_id: org.eventId, days, owner_id },
            });
            openCardCoverModal({
                ...inviteCardOpts(),
                accessKey: key.access_key,
                fresh: true,
            });
            toast("Access key generated.", "ok", "New key");
            await wsKeys(main);
        } catch (err) {
            toast(err.message, "error", "Could not generate");
            btnBusy(btn, false);
        }
    });

    // Revoke an active key by its stored hash (the raw key is only in
    // card pixels, so there's nothing to type).
    $$("[data-act=revoke-key]", main).forEach((revokeBtn) => {
        revokeBtn.addEventListener("click", () => {
            const row = revokeBtn.closest("[data-key-hash]");
            const hash = row ? row.dataset.keyHash : "";
            if (!hash) return;
            openModal({
                title: "Revoke access key",
                body: `Revoke this access key? The attendee's card will stop working immediately.`,
                confirmText: "Revoke",
                danger: true,
                onConfirm: async () => {
                    try {
                        await api(`/api/events/${encodeURIComponent(org.eventId)}/access-keys/revoke-by-hash`, {
                            method: "POST",
                            body: { organizer_key: org.organizerKey, event_id: org.eventId, key_hash: hash },
                        });
                        toast("Access key revoked.", "ok", "Done");
                        await wsKeys(main);
                    } catch (err) {
                        toast(err.message, "error", "Could not revoke");
                    }
                },
            });
        });
    });
}

/* ------------------------------------------------------------------
 * Workspace: RSVP funnel tab (Phase B)
 * ------------------------------------------------------------------ */
function rsvpBadge(status) {
    if (status === "approved") return `<span class="badge badge-active">Approved</span>`;
    if (status === "denied") return `<span class="badge badge-revoked">Denied</span>`;
    return `<span class="badge badge-neutral">Pending</span>`;
}

function rsvpRowHTML(rsvp) {
    const actions =
        rsvp.status === "pending"
            ? `<button class="btn btn-secondary btn-sm" type="button" data-act="approve" data-rsvp="${esc(rsvp.id)}">Approve</button>` +
              `<button class="btn btn-danger btn-sm" type="button" data-act="deny" data-rsvp="${esc(rsvp.id)}">Deny</button>`
            : rsvp.status === "approved"
              ? `<button class="btn btn-danger btn-sm" type="button" data-act="deny" data-rsvp="${esc(rsvp.id)}">Deny</button>`
              : "";
    const decided = rsvp.status === "pending" ? "" : ` · decided ${esc(fmtDate(rsvp.decided_at))}`;
    const note = rsvp.message
        ? `<div class="kd-sub kd-msg">“${esc(rsvp.message)}”</div>`
        : "";
    return `<div class="key-detail-row" data-rsvp-id="${esc(rsvp.id)}">` +
        rsvpBadge(rsvp.status) +
        `<div class="kd-info">` +
        `<div class="kd-name">${esc(rsvp.display_name || "Unnamed")}</div>` +
        `<div class="kd-sub">${rsvp.contact ? `${esc(rsvp.contact)} · ` : ""}asked ${esc(fmtDate(rsvp.created_at))}${decided}</div>` +
        note +
        `</div>` +
        (actions ? `<div class="kd-actions">${actions}</div>` : "") +
        `</div>`;
}


async function wsRsvps(main) {
    const eventId = encodeURIComponent(org.eventId);
    const [rsvps, settings] = await Promise.all([
        api(`/api/events/${eventId}/rsvp/list${qs({ key: org.organizerKey })}`),
        api(`/api/events/${eventId}/rsvp/settings${qs({ key: org.organizerKey })}`),
    ]);
    const shareUrl = `${location.href.split("#")[0]}#/rsvp/${org.eventId}`;
    const dial = settings.auto_approve;
    main.innerHTML =
        `<section class="card">` +
        `<div class="keycode-full"><code class="keycode">${esc(shareUrl)}</code>` +
        `<button class="btn btn-secondary" type="button" id="rsvp-copy-link">Copy link</button></div>` +
        `</section>` +
        `<section class="card">` +
        `<h3 class="card-title">Gate settings</h3>` +
        `<form id="rsvp-settings-form" class="inline-form" autocomplete="off">` +
        `<div class="field">` +
        `<label class="check-wrap" for="rsvp-pass-on">` +
        `<input type="checkbox" id="rsvp-pass-on"${settings.passphrase_required ? " checked" : ""}>` +
        `<span>Require a passphrase to RSVP</span>` +
        `</label>` +
        `<input type="password" id="rsvp-pass" placeholder="${settings.passphrase_required ? "Passphrase is set — type to replace it" : "Choose a passphrase"}" autocomplete="off">` +
        `</div>` +
        `<div class="field">` +
        `<label for="rsvp-auto">Auto-approve the first N RSVPs</label>` +
        `<input type="number" id="rsvp-auto" min="0" step="1" placeholder="Off — every request waits for you"` +
        `${Number.isInteger(dial) ? ` value="${dial}"` : ""}>` +
        `</div>` +
        `<p id="rsvp-settings-note" class="form-note" role="status" aria-live="polite"></p>` +
        `<button class="btn btn-primary" type="submit" id="rsvp-settings-btn">Save gate settings</button>` +
        `</form>` +
        `</section>` +
        `<section class="card">` +
        `<h3 class="card-title">RSVP queue</h3>` +
        `<div class="key-list">` +
        (rsvps.length ? rsvps.map(rsvpRowHTML).join("") : emptyState("No RSVPs yet", "Share the funnel link above.")) +
        `</div>` +
        `</section>`;


    $("#rsvp-copy-link").addEventListener("click", async () => {
        const ok = await copyText(shareUrl);
        toast(ok ? "RSVP link copied to clipboard." : "Copy blocked — select the link manually.", ok ? "ok" : "error", "Copy");
    });

    // Approve / deny per row. Approving grants the pre-minted key (idempotent);
    // denying revokes it. A denied row shows no actions — the attendee must
    // submit a fresh RSVP, which mints a fresh key.
    $$('[data-act="approve"], [data-act="deny"]', main).forEach((btn) => {
        btn.addEventListener("click", async () => {
            const decision = btn.dataset.act;
            btnBusy(btn, true, decision === "approve" ? "Approving…" : "Denying…");
            try {
                await api(`/api/events/${eventId}/rsvp/decide`, {
                    method: "POST",
                    body: { organizer_key: org.organizerKey, rsvp_id: btn.dataset.rsvp, decision },
                });
                toast(
                    decision === "approve"
                        ? "RSVP approved — the attendee's card opens the event now."
                        : "RSVP denied — that card will be rejected at the door.",
                    "ok",
                    "Decision saved",
                );
                await wsRsvps(main);
            } catch (err) {
                toast(err.message, "error", "Could not save the decision");
                btnBusy(btn, false);
            }
        });
    });


    // Gate settings. The API sets or clears the whole gate on each save (there
    // is no "keep current passphrase" verb), so saving with the box ticked
    // requires typing the passphrase again; unticking clears it on purpose.
    $("#rsvp-settings-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const noteEl = $("#rsvp-settings-note");
        const btn = $("#rsvp-settings-btn");
        note(noteEl, "");
        const passOn = $("#rsvp-pass-on").checked;
        const passValue = $("#rsvp-pass").value.trim();
        if (passOn && !passValue && settings.passphrase_required) {
            note(noteEl, "Type the passphrase again to keep the gate (or untick the box to remove it).", "error");
            return;
        }
        if (passOn && !passValue) {
            note(noteEl, "Type a passphrase, or untick the box to drop the gate.", "error");
            return;
        }
        const autoRaw = $("#rsvp-auto").value.trim();
        const auto = autoRaw === "" ? null : Number(autoRaw);
        if (auto !== null && (!Number.isInteger(auto) || auto < 0)) {
            note(noteEl, "Auto-approve must be a whole number of 0 or more.", "error");
            return;
        }
        btnBusy(btn, true, "Saving…");
        try {
            await api(`/api/events/${eventId}/rsvp/settings`, {
                method: "POST",
                body: {
                    organizer_key: org.organizerKey,
                    passphrase: passOn && passValue ? passValue : null,
                    auto_approve: auto,
                },
            });
            note(noteEl, "Gate settings saved.", "ok");
            toast("RSVP gate updated.", "ok", "Saved");
        } catch (err) {
            note(noteEl, err.message, "error");
        } finally {
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
            `<p>This permanently revokes every access key for <strong>${esc(org.title || "this event")}</strong>, and ` +
            `content access ends. No attendee will be able to unlock this event again. ` +
            `This cannot be undone.</p>` +
            `<div class="field"><label for="decom-confirm">Type the event title to confirm</label>` +
            `<input id="decom-confirm" type="text" required spellcheck="false" autocomplete="off"></div>`,
        confirmText: "Decommission",
        danger: true,
        onConfirm: async () => {
            const input = $("#decom-confirm");
            const typed = input ? input.value.trim() : "";
            if (typed !== org.title) {
                throw new Error("Type the event title exactly as shown to confirm.");
            }
            await api(`/api/events/${encodeURIComponent(org.eventId)}/decommission`, {
                method: "POST",
                body: { organizer_key: org.organizerKey, event_id: org.eventId },
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

/**
 * Restore the organizer workspace for an event from its organizer key.
 * Shared by the two-field form and the organizer card / gkporg: keyline
 * decoders — the organizer key travels the same way in all three.
 */
async function openOrganizerWorkspace(eventId, organizerKey) {
    const details = await api(`/api/events/${encodeURIComponent(eventId)}${qs({ organizer_key: organizerKey })}`);
    const eventInfo = details.event || {};
    org = {
        eventId,
        organizerKey,
        title: eventInfo.title || "Untitled event",
        meta: {
            description: eventInfo.description || "",
            locationData: eventInfo.location_data || "",
            createdAt: eventInfo.created_at || "",
        },
    };
    saveSession();
    goWorkspace();
}

/**
 * Route an invite payload where its role says: attendee keys unlock the event
 * page on this tab; organizer (organizer) payloads restore the workspace.
 */
async function routeInvitePayload(parsed) {
    if (parsed.role === "organizer") {
        await openOrganizerWorkspace(parsed.eventId, parsed.accessKey);
        toast("Workspace restored from your organizer card.", "ok", "Welcome back");
        return;
    }
    await unlockEvent(parsed.eventId, parsed.accessKey);
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
        if (title) title.textContent = drop.dataset.resetTitle || "Drop your invite here";
        if (sub) sub.textContent = drop.dataset.resetSub || "or paste it with ⌘V";
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

        // Hidden-key path — PNG cards drop the key straight out of the pixels.
        // The stego layer is the only channel (Phase B removed the printed-QR
        // fallback: a scannable key is a secrecy downgrade).
        let parsed = null;
        if (kind === "png") {
            const payload = await window.gkpStego.extract(bytes);
            parsed = payload !== null ? window.gkpStego.parsePayload(payload) : null;
        }
        // Honest, specific rejection instead of a generic failure.
        if (!parsed) throw new Error(window.gkpStego.inviteRejectReason(kind));

        // The payload's role routes it: attendee keys unlock the event page,
        // organizer organizer cards restore the workspace.
        await routeInvitePayload(parsed);
    } catch (err) {
        toast(err.message, "error", "Could not read the card");
    } finally {
        setDropBusy(drop, false);
    }
}

/**
 * Organizer card drop / paste / choose on the organize entry: organizer
 * payloads restore the workspace; anything else gets a clear rejection.
 */
async function handleOrganizerCardFile(file) {
    if (!file) return;
    const drop = $("#org-drop");
    setDropBusy(drop, true, "Reading the card…");
    try {
        const bytes = new Uint8Array(await file.arrayBuffer());
        const kind = window.gkpStego.classifyInvite(bytes);
        let parsed = null;
        if (kind === "png") {
            const payload = await window.gkpStego.extract(bytes);
            parsed = payload !== null ? window.gkpStego.parsePayload(payload) : null;
        }
        if (!parsed) throw new Error(window.gkpStego.inviteRejectReason(kind));
        if (parsed.role !== "organizer") {
            throw new Error("That is an attendee invite — attendee cards belong on the Join tab.");
        }
        await openOrganizerWorkspace(parsed.eventId, parsed.accessKey);
        toast("Workspace restored from your organizer card.", "ok", "Welcome back");
    } catch (err) {
        toast(err.message, "error", "Could not read the card");
    } finally {
        setDropBusy(drop, false);
    }
}

function bindOrgDrop() {
    const drop = $("#org-drop");
    const fileInput = $("#org-drop-file");
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
        handleOrganizerCardFile(file);
    });
    if (fileInput) {
        fileInput.addEventListener("change", () => {
            handleOrganizerCardFile(fileInput.files && fileInput.files[0]);
            fileInput.value = "";
        });
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
    // Paste anywhere while the join entry is visible: an invite or organizer
    // card image, routed by the payload's role.
    document.addEventListener("paste", async (event) => {
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
    });
}

/* ------------------------------------------------------------------
 * Join unlock (invite → key → event page)
 * ------------------------------------------------------------------ */
async function unlockEvent(eventId, accessKey) {
    const drop = $("#key-drop");
    const noteEl = $("#join-note");
    note(noteEl, "");
    setDropBusy(drop, true, "Unlocking…");
    try {
        // The gateway answers any valid key+content pair with the event dict.
        const result = await api("/api/access", {
            method: "POST",
            body: { key: accessKey, content_id: eventId },
        });
        if (result && result.status === "pending") {
            // Pre-minted RSVP key: valid but awaiting the organizer's approval.
            note(noteEl, result.message || "Your RSVP is awaiting organizer approval.", "info");
            return;
        }
        if (!result || result.status !== "success") {
            throw new Error((result && result.message) || "The key did not unlock this event.");
        }
        attendee = { eventId, accessKey, event: result.data || {} };
        saveSession();
        const entry = $("#join-entry");
        const evt = $("#join-event");
        if (entry) entry.hidden = true;
        if (evt) {
            evt.hidden = false;
            renderEventPage();
        }
        toast("Event unlocked.", "ok", "Welcome");
    } catch (err) {
        note(noteEl, err.message, "error");
    } finally {
        setDropBusy(drop, false);
    }
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
 * RSVP funnel (Phase B): public attendee page (#/rsvp/{event_id})
 * ------------------------------------------------------------------ */
function parseRsvpHash() {
    const h = (location.hash || "#/").replace(/^#/, "");
    if (!h.startsWith("/rsvp/")) return "";
    return h.slice("/rsvp/".length).split("/")[0];
}

async function renderRsvp() {
    const root = $("#rsvp-views");
    if (!root) return;
    const eventId = parseRsvpHash();
    if (!eventId) {
        root.innerHTML = emptyState("No event here", "This RSVP link is missing its event id.");
        return;
    }
    root.innerHTML = emptyState("Loading…");
    try {
        const view = await api(`/api/events/${encodeURIComponent(eventId)}/rsvp/view`);
        if (view.status === "ended") {
            root.innerHTML = emptyState("Event ended", "All data for this event was wiped at the end of its life.");
            return;
        }
        const event = (view && view.event) || {};
        root.innerHTML =
            `<header class="ep-head">` +
            `<p class="eyebrow ep-eyebrow">RSVP</p>` +
            `<h2 class="ep-title">${esc(event.title || "Untitled event")}</h2>` +
            `<p class="ep-lede">${esc(event.description || "")}</p>` +
            `</header>` +
            `<form id="rsvp-form" class="card form-card" autocomplete="off">` +
            `<h3 class="card-title">Request an invite</h3>` +
            `<div class="field">` +
            `<label for="rsvp-name">Name <span class="req">*</span></label>` +
            `<input type="text" id="rsvp-name" name="display_name" required maxlength="64" autocomplete="off">` +
            `</div>` +
            `<div class="field">` +
            `<label for="rsvp-contact">How the organizer can reach you <span class="opt">optional</span></label>` +
            `<input type="text" id="rsvp-contact" name="contact" maxlength="256" autocomplete="off">` +
            `</div>` +
            `<div class="field">` +
            `<label for="rsvp-message">Message to the organizer <span class="opt">optional</span></label>` +
            `<textarea id="rsvp-message" name="message" rows="3" maxlength="512" autocomplete="off"></textarea>` +
            `</div>` +
            (view.passphrase_required
                ? `<div class="field">` +
                  `<label for="rsvp-passphrase">Passphrase <span class="req">*</span></label>` +
                  `<input type="password" id="rsvp-passphrase" name="passphrase" autocomplete="off">` +
                  `<p class="field-hint">The organizer gated this event with a shared passphrase.</p>` +
                  `</div>`
                : "") +
            // Honeypot: humans never see this field (CSS-hidden + no tab
            // focus). Bots that fill it get a canned acknowledgement and
            // nothing is stored or minted.
            `<div class="field field-hp" aria-hidden="true">` +
            `<label for="rsvp-website">Website</label>` +
            `<input type="text" id="rsvp-website" name="website" tabindex="-1" autocomplete="off">` +
            `</div>` +
            `<p id="rsvp-note" class="form-note" role="status" aria-live="polite"></p>` +
            `<button type="submit" class="btn btn-primary btn-block" id="rsvp-btn">Request invite</button>` +
            `</form>`;
        bindRsvpForm(eventId, event, Boolean(view.passphrase_required));
    } catch (err) {
        root.innerHTML = emptyState("Could not load this event", err.message);
    }
}


function bindRsvpForm(eventId, event, passphraseRequired) {
    const form = $("#rsvp-form");
    if (!form) return;
    const noteEl = $("#rsvp-note");
    const btn = $("#rsvp-btn");
    form.addEventListener("submit", async (submitEvent) => {
        submitEvent.preventDefault();
        note(noteEl, "");
        const name = getField(form, "display_name");
        if (!name) {
            note(noteEl, "A name is required.", "error");
            return;
        }
        const passphrase = passphraseRequired ? getField(form, "passphrase") : null;
        if (passphraseRequired && !passphrase) {
            note(noteEl, "This event needs its passphrase.", "error");
            return;
        }
        btnBusy(btn, true, "Sending…");
        try {
            const result = await api(`/api/events/${encodeURIComponent(eventId)}/rsvp`, {
                method: "POST",
                body: {
                    display_name: name,
                    contact: getField(form, "contact") || null,
                    message: getField(form, "message") || null,
                    passphrase: passphrase || null,
                    website: getField(form, "website") || null,
                },
            });
            showRsvpResult(eventId, event, result);
        } catch (err) {
            note(noteEl, err.message, "error");
        } finally {
            btnBusy(btn, false);
        }
    });
}


/** The one-time RSVP result: the pre-minted key's only artifact is the invite
 *  card — the raw key text is never displayed. */
function showRsvpResult(eventId, event, result) {
    const root = $("#rsvp-views");
    if (!root) return;
    const key = (result && result.access_key) || "";
    if (!key) {
        // Honeypot-style canned reply — humans never reach this (their
        // submissions always mint a key).
        root.innerHTML = emptyState("Request received", "Your access card will arrive once approved.");
        return;
    }
    const approved = result.status === "approved";
    root.innerHTML =
        `<header class="ep-head">` +
        `<p class="eyebrow ep-eyebrow">RSVP received</p>` +
        `<h2 class="ep-title">${esc(result.display_name || "You're on the list")}</h2>` +
        `<p class="ep-lede">${approved
            ? "You're approved — the card below opens the event right now."
            : "Your card works the moment the organizer approves your RSVP. Approve or deny is their call."}</p>` +
        `</header>` +
        (approved
            ? `<button class="btn btn-secondary btn-block" type="button" id="rsvp-unlock">Open the event now</button>`
            : `<a class="btn btn-ghost btn-block" href="#/join">Go to the door →</a>`);
    // Immediate card creation: the fresh key's only artifact is its card, so
    // the cover modal opens on top of the result without a button hop.
    openCardCoverModal({ eventId, title: event.title, accessKey: key, fresh: true });
    const unlock = $("#rsvp-unlock");
    if (unlock) {
        unlock.addEventListener("click", () => {
            // An approved RSVP's key already carries the content grants, so
            // the door flow (and this shortcut) both work immediately.
            attendee = { eventId, accessKey: key, event };
            saveSession();
            toast("Event unlocked.", "ok", "Welcome");
            location.hash = "#/join";
        });
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
        (event.location_data
            ? `<p class="ep-meta">${esc(event.location_data)}</p>`
            : "") +
        `<div class="ep-actions"><button class="btn btn-ghost btn-sm" type="button" id="attendee-end">Leave</button></div>` +
        `</header>` +
        `<div class="ep-main">` +
        `<section class="card"><h3 class="card-title">Board</h3>` +
        `<div id="ep-board">Loading…</div></section>` +
        `</div>`;

    $("#attendee-end").addEventListener("click", () => {
        attendee = null;
        saveSession();
        location.hash = "#/join";
        renderJoin();
        toast("Key dropped. To re-enter, use the invite again.", "info", "Signed out");
    });

    loadAttendeeBoard();
}

async function loadAttendeeBoard() {
    const box = $("#ep-board");
    if (!box) return;
    try {
        // Fetch content blocks (may already be in attendee.event from door unlock)
        let blocks = attendee.event.content_blocks;
        if (blocks === undefined) {
            const result = await api("/api/access", {
                method: "POST",
                body: { key: attendee.accessKey, content_id: attendee.eventId },
            });
            blocks = (result && result.data && result.data.content_blocks) || [];
            attendee.event = { ...attendee.event, content_blocks: blocks };
            saveSession();
        }
        const [bulletins, assets] = await Promise.all([
            api(`/api/events/${encodeURIComponent(attendee.eventId)}/bulletins${qs({ key: attendee.accessKey })}`).catch(() => []),
            api(`/api/events/${encodeURIComponent(attendee.eventId)}/media${qs({ key: attendee.accessKey })}`).catch(() => []),
        ]);
        const assetsById = {};
        assets.forEach((a) => { assetsById[a.id] = a; });
        const attached = new Set(bulletins.map((b) => b.media_id).filter(Boolean));

        const posts = [
            ...blocks.map((b) => ({ ...b, _type: "block" })),
            ...bulletins.map((b) => ({ ...b, _type: "bulletin" })),
            ...assets.filter((a) => !attached.has(a.id)).map((a) => ({ ...a, _type: "media" })),
        ].sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));

        if (!posts.length) {
            box.innerHTML = emptyState("Nothing posted yet");
            return;
        }
        box.innerHTML = posts.map((post) => {
            switch (post._type) {
            case "bulletin":
                return `<div class="board-entry">` +
                    bulletinCardHTML(post, false) +
                    bulletinMediaHTML(post, assetsById) +
                    `</div>`;
            case "media":
                return attendeeMediaTile(post);
            default:
                return `<div class="item board-post">` +
                    `<div class="item-head">` +
                    `<span class="tag">${esc(contentTypeLabel(post.content_type))}</span>` +
                    `<span class="item-title">${esc(post.content_type || "note")}</span>` +
                    `</div>` +
                    `<div class="item-body">${esc(post.payload || "")}</div>` +
                    `<div class="item-meta">${esc(fmtDate(post.created_at))}</div>` +
                    `</div>`;
            }
        }).join("");

        $$(".bulletin-card", box).forEach((card) => bindBulletinCard(card, false));
        // Attendee media tiles: open links, no delete/copy
        $$("img.mt-preview", box).forEach((img) => {
            img.addEventListener("error", () => {
                const fallback = document.createElement("div");
                fallback.className = "mt-fallback";
                fallback.setAttribute("aria-hidden", "true");
                fallback.textContent = "📄";
                img.replaceWith(fallback);
            });
        });
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

/* ------------------------------------------------------------------
 * Lite events (ephemeral flyer funnel)
 * ------------------------------------------------------------------ */

/** Ask the instance to relay the organizer key to an attendee's LXMF address. */
async function deliverByMesh(eventId, organizerKey, statusEl) {
    const address = prompt(
        "LXMF address of the attendee (32 hex characters, e.g. from Sideband):"
    );
    if (!address) return;
    statusEl.textContent = "Queueing over mesh…";
    try {
        const body = await api(
            `/api/lite/events/${encodeURIComponent(eventId)}/deliver`,
            { body: { destination: address.trim(), organizer_key: organizerKey }, method: "POST" }
        );
        statusEl.textContent = body.detail || "Queued over mesh.";
    } catch (err) {
        statusEl.textContent = `Mesh delivery failed: ${err.message}`;
    }
}

/** Render the flyer creation funnel result panel. */
function showFlyerDone(done, body) {
    const publicUrl = body.public_url || `${location.origin}/i/${body.event_id}`;
    const eventHref = `/i/${encodeURIComponent(body.event_id)}`;
    const meshPanel = body.mesh_delivery_available
        ? `<div class="item"><button type="button" class="btn" id="mesh-deliver-btn">` +
          `Send key over mesh (LXMF)</button>` +
          `<p class="key-hint" id="mesh-deliver-status"></p></div>`
        : "";
    done.innerHTML =
        `<header class="view-head"><h2 class="view-title">Your event is live</h2></header>` +
        `<div class="card form-card">` +
        `<div class="field"><label>Share link</label>` +
        `<div class="item"><code>${esc(publicUrl)}</code></div></div>` +
        meshPanel +
        `<div class="item"><a class="btn btn-primary" href="${esc(eventHref)}">` +
        `Open the event page</a></div>` +
        `</div>`;
    const meshBtn = document.getElementById("mesh-deliver-btn");
    if (meshBtn) {
        meshBtn.addEventListener("click", () => {
            deliverByMesh(
                body.event_id,
                body.organizer_key,
                document.getElementById("mesh-deliver-status")
            );
        });
    }
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

    // Past-time validation: the page vanishes ttl hours after the event
    // time, so a time already in the past can never hold an event.
    const noteEl = $("#flyer-note");
    const updateNote = () => {
        if (!noteEl) return;
        const ttl = Number($("#flyer-ttl")?.value || 48);
        const whenRaw = $("#flyer-when")?.value;
        const whenDate = whenRaw ? new Date(whenRaw) : null;
        if (whenDate && !Number.isNaN(whenDate.getTime())) {
            const wipes = new Date(whenDate.getTime() + ttl * 3600 * 1000);
            if (wipes.getTime() <= Date.now()) {
                note(noteEl, "The event time has already passed — pick a time in the future.", "error");
                return;
            }
        }
        noteEl.textContent = "";
    };
    ["#flyer-when", "#flyer-ttl"].forEach((sel) => {
        const el = $(sel);
        if (el) el.addEventListener("input", updateNote);
        if (el) el.addEventListener("change", updateNote);
    });
    updateNote();

    // Oversized flyer: tell the human at pick time, not at submit. The cap
    // mirrors the server's MAX_MEDIA_SIZE_BYTES - keep the two in sync.
    const MAX_FLYER_BYTES = 25 * 1024 * 1024;
    const flyerFileEl = $("#flyer-file");
    if (flyerFileEl) {
        flyerFileEl.addEventListener("change", () => {
            const f = flyerFileEl.files?.[0];
            if (f && f.size > MAX_FLYER_BYTES) {
                note(noteEl, `Flyer is too large (${fmtBytes(f.size)}). Pick a file under 25 MB — every invitee downloads it.`, "error");
            } else {
                updateNote();
            }
        });
    }

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
            const whenRaw = $("#flyer-when")?.value;
            if (whenRaw) fd.set("when", new Date(whenRaw).toISOString());
            fd.set("where", $("#flyer-where").value);
            fd.set("ttl_hours", String(Number($("#flyer-ttl")?.value || 48)));
            const file = $("#flyer-file")?.files?.[0];
            if (file && file.size > MAX_FLYER_BYTES) {
                throw new Error(`Flyer is too large (${fmtBytes(file.size)}). Pick a file under 25 MB — every invitee downloads it.`);
            }
            if (file) fd.set("flyer", file, file.name);
            const resp = await fetch("/api/lite/events", { method: "POST", body: fd });
            const body = await resp.json().catch(() => ({}));
            if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`);
            entry.hidden = true;
            showFlyerDone(done, body);
            done.hidden = false;
            // Same immediate card creation as every other mint: the card is
            // the only copy of the organizer key.
            openCardCoverModal({
                eventId: body.event_id,
                title: body.title,
                accessKey: body.organizer_key,
                organizer: true,
                fresh: true,
            });
            toast("Copy the organizer key before leaving this page.", "ok", "Event is live");
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

/* ------------------------------------------------------------------
 * Boot
 * ------------------------------------------------------------------ */
function init() {
    loadSession();
    bindOrganizeEntry();
    bindOrgDrop();
    bindJoinDrop();
    window.addEventListener("hashchange", route);
    route();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}
