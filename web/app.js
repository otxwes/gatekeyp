// Gatekeyp Web UI — client-side logic

const API_BASE = "";

// State
let currentEvent = null;
let masterKey = null;

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------

async function api(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || "Request failed");
    }
    return data;
}

function showResult(element, content, isError = false) {
    element.textContent = typeof content === "string" ? content : JSON.stringify(content, null, 2);
    element.classList.remove("success", "error");
    element.classList.add(isError ? "error" : "success");
}

function showError(element, err) {
    showResult(element, err.message, true);
}

// ------------------------------------------------------------------
// Create Event
// ------------------------------------------------------------------

document.getElementById("create-event-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const resultEl = document.getElementById("create-event-result");

    const payload = {
        title: document.getElementById("title").value,
        description: document.getElementById("description").value,
        organizer_id: document.getElementById("organizer-id").value,
        location_data: document.getElementById("location-data").value || null,
    };

    try {
        const event = await api("/api/events", {
            method: "POST",
            body: JSON.stringify(payload),
        });

        currentEvent = event;
        masterKey = event.master_key;

        showResult(resultEl, event);
        showEventDetails();
        showSection("event-details");
        showSection("access-keys");
        showSection("content");
        showSection("decommission");
    } catch (err) {
        showError(resultEl, err);
    }
});

// ------------------------------------------------------------------
// Event Details
// ------------------------------------------------------------------

function showEventDetails() {
    const el = document.getElementById("event-details-content");
    el.innerHTML = `
        <p><strong>Event ID:</strong> <code>${currentEvent.event_id}</code></p>
        <p><strong>Title:</strong> ${currentEvent.title}</p>
        <p><strong>Organizer:</strong> ${currentEvent.organizer_id}</p>
        <p><strong>Master Key:</strong> <code>${currentEvent.master_key}</code></p>
        <p><strong>Expires:</strong> ${currentEvent.expires_at}</p>
    `;
}

// ------------------------------------------------------------------
// Access Keys
// ------------------------------------------------------------------

document.getElementById("generate-key-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const resultEl = document.getElementById("generate-key-result");

    const payload = {
        master_key: masterKey,
        event_id: currentEvent.event_id,
        days: parseInt(document.getElementById("key-days").value, 10),
        owner_id: document.getElementById("key-owner").value || null,
    };

    try {
        const key = await api(`/api/events/${currentEvent.event_id}/access-keys`, {
            method: "POST",
            body: JSON.stringify(payload),
        });
        showResult(resultEl, key);
        await loadAccessKeys();
    } catch (err) {
        showError(resultEl, err);
    }
});

async function loadAccessKeys() {
    const listEl = document.getElementById("access-keys-list");
    try {
        const keys = await api(`/api/events/${currentEvent.event_id}/access-keys?master_key=${encodeURIComponent(masterKey)}`);
        listEl.innerHTML = keys.length
            ? keys.map((k) => `
                <div class="key-item">
                    <div><strong>${k.type}</strong> ${k.revoked ? "🔴 revoked" : "🟢 active"}</div>
                    <div class="key-hash">${k.hash_key}</div>
                    <div>Expires: ${k.expires_at || "never"}</div>
                </div>
            `).join("")
            : "<p>No access keys yet.</p>";
    } catch (err) {
        listEl.innerHTML = `<p class="error">${err.message}</p>`;
    }
}

// ------------------------------------------------------------------
// Content
// ------------------------------------------------------------------

document.getElementById("add-content-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const resultEl = document.getElementById("add-content-result");

    const payload = {
        master_key: masterKey,
        event_id: currentEvent.event_id,
        content_type: document.getElementById("content-type").value,
        payload: document.getElementById("content-payload").value,
    };

    try {
        const block = await api(`/api/events/${currentEvent.event_id}/content`, {
            method: "POST",
            body: JSON.stringify(payload),
        });
        showResult(resultEl, block);
        await loadContentBlocks();
    } catch (err) {
        showError(resultEl, err);
    }
});

async function loadContentBlocks() {
    const listEl = document.getElementById("content-blocks");
    try {
        const details = await api(`/api/events/${currentEvent.event_id}?master_key=${encodeURIComponent(masterKey)}`);
        const blocks = details.content_blocks || [];
        listEl.innerHTML = blocks.length
            ? blocks.map((b) => `
                <div class="block-item">
                    <div><strong>${b.content_type}</strong></div>
                    <div class="block-id">${b.id}</div>
                    <div>${b.payload}</div>
                </div>
            `).join("")
            : "<p>No content blocks yet.</p>";
    } catch (err) {
        listEl.innerHTML = `<p class="error">${err.message}</p>`;
    }
}

// ------------------------------------------------------------------
// Decommission
// ------------------------------------------------------------------

document.getElementById("decommission-btn").addEventListener("click", async () => {
    const resultEl = document.getElementById("decommission-result");
    if (!confirm("Are you sure you want to decommission this event? This will revoke all keys.")) {
        return;
    }

    const payload = {
        master_key: masterKey,
        event_id: currentEvent.event_id,
    };

    try {
        const result = await api(`/api/events/${currentEvent.event_id}/decommission`, {
            method: "POST",
            body: JSON.stringify(payload),
        });
        showResult(resultEl, result);
    } catch (err) {
        showError(resultEl, err);
    }
});

// ------------------------------------------------------------------
// Utilities
// ------------------------------------------------------------------

function showSection(id) {
    document.getElementById(id).classList.remove("hidden");
}
