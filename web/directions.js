/* Transit directions widget: static itinerary on submit, never persisted
 * beyond the browser's own localStorage copy. No geolocation, no third-party
 * requests — the plan POST goes to this origin's /api/directions only. */
(function () {
    "use strict";

    const ENDPOINT = "/api/directions";
    const STORE_PREFIX = "gatekeyp.directions.";

    const FALLBACK_BY_STATUS = {
        400: "Could not find that address.",
        403: "This key does not open that event.",
        404: "Event not found.",
        429: "Directions unavailable right now.",
        503: "Directions unavailable right now.",
    };

    function esc(text) {
        return String(text == null ? "" : text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function terse(message) {
        return /^[.!?]$/.test(message.slice(-1)) ? message : `${message}.`;
    }

    /* Server times are ISO 8601 in the venue region, e.g.
     * "2030-01-01T18:30:00-05:00" — show the venue-local clock directly,
     * never the viewer's timezone. */
    function clockTime(iso) {
        if (typeof iso !== "string" || iso.length < 16) return "";
        return esc(iso.slice(11, 16));
    }

    function legText(leg) {
        if (leg.mode === "WALK") {
            return `Walk ${esc(leg.minutes)} min · ${esc(leg.distance_m)} m · ${esc(leg.from)} → ${esc(leg.to)}`;
        }
        return `${esc(leg.line)} ${esc(leg.headsign)} · ${clockTime(leg.depart)}–${clockTime(leg.arrive)} · ${esc(leg.from_stop)} → ${esc(leg.to_stop)}${leg.stops ? ` · ${esc(leg.stops)} stops` : ""}`;
    }

    function itineraryHtml(itinerary) {
        return (
            `<p class="dir-head"><strong>${esc(itinerary.duration_minutes)} min</strong>` +
            ` · ${clockTime(itinerary.depart_at)} → ${clockTime(itinerary.arrive_at)}</p>` +
            `<ul class="dir-legs">` +
            (itinerary.legs || [])
                .map((leg) => `<li class="dir-leg">${legText(leg)}</li>`)
                .join("") +
            `</ul>` +
            (itinerary.attribution
                ? `<p class="dir-attribution">${esc(itinerary.attribution)}</p>`
                : "")
        );
    }

    /* The endpoint may one day answer alternatives alongside the main
     * itinerary; treat the body plus its `alternatives` as the display list,
     * first one expanded. */
    function displayList(body) {
        return [body]
            .concat(Array.isArray(body.alternatives) ? body.alternatives : [])
            .filter(Boolean)
            .slice(0, 3);
    }

    function resultHtml(body) {
        const list = displayList(body);
        let html = `<div class="dir-itin">${itineraryHtml(list[0])}</div>`;
        for (let i = 1; i < list.length; i += 1) {
            html += `<details class="dir-alt">` +
                `<summary>${esc(list[i].duration_minutes)} min · ${clockTime(list[i].depart_at)} → ${clockTime(list[i].arrive_at)}</summary>` +
                `<div class="dir-itin">${itineraryHtml(list[i])}</div>` +
                `</details>`;
        }
        return html;
    }

    function storeKey(el) {
        return STORE_PREFIX + el.dataset.eventId;
    }

    function showResult(el, body) {
        const result = el.querySelector(".dir-result");
        const error = el.querySelector(".dir-error");
        error.hidden = true;
        error.textContent = "";
        result.innerHTML =
            `<button class="dir-clear" type="button" data-act="dir-clear">Clear</button>` +
            resultHtml(body);
    }

    function showFailure(el, message) {
        const result = el.querySelector(".dir-result");
        result.textContent = "";
        const error = el.querySelector(".dir-error");
        error.hidden = false;
        error.textContent = terse(message);
    }

    function restore(el, input) {
        let stored = null;
        try {
            stored = JSON.parse(window.localStorage.getItem(storeKey(el)) || "null");
        } catch {
            stored = null;
        }
        if (!stored || typeof stored !== "object" || !stored.itinerary) return;
        if (typeof stored.start === "string") input.value = stored.start;
        showResult(el, stored.itinerary);
    }

    function mount(el) {
        if (!el || el.dataset.dirMounted === "1") return;
        el.dataset.dirMounted = "1";
        const eventId = el.dataset.eventId || "";
        const key = el.dataset.key || "";
        const endpoint = el.dataset.endpoint || ENDPOINT;
        const inputId = `dir-from-${eventId}`;
        el.innerHTML =
            `<form class="dir-form">` +
            `<label class="dir-label" for="${esc(inputId)}">From</label> ` +
            `<input class="dir-input" id="${esc(inputId)}" type="text" autocomplete="off" maxlength="256"> ` +
            `<button class="dir-submit" type="submit">Get directions</button>` +
            `</form>` +
            `<div class="dir-result"></div>` +
            `<p class="dir-error" hidden></p>`;

        const input = el.querySelector(".dir-input");
        const submit = el.querySelector(".dir-submit");

        restore(el, input);

        el.addEventListener("click", (clickEvent) => {
            if (!clickEvent.target.closest("[data-act='dir-clear']")) return;
            try {
                window.localStorage.removeItem(storeKey(el));
            } catch {
                /* storage unavailable: keep the visual clear anyway */
            }
            el.querySelector(".dir-result").textContent = "";
        });

        el.querySelector(".dir-form").addEventListener("submit", (submitEvent) => {
            submitEvent.preventDefault();
            const start = input.value.trim();
            if (!eventId || !start) return;
            submit.disabled = true;
            const payload = { event_id: eventId, start: start };
            if (key) payload.key = key;
            const onError = (message) => {
                submit.disabled = false;
                showFailure(el, message);
            };
            window
                .fetch(endpoint, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                })
                .then((response) => {
                    if (response.ok) {
                        return response.json().then((body) => {
                            submit.disabled = false;
                            try {
                                window.localStorage.setItem(
                                    storeKey(el),
                                    JSON.stringify({ start: start, itinerary: body })
                                );
                            } catch {
                                /* storage unavailable; the result still shows */
                            }
                            showResult(el, body);
                        });
                    }
                    return response
                        .json()
                        .then(
                            (body) =>
                               errorMessage(body && body.detail, response.status),
                            () => errorMessage("", response.status)
                        )
                        .then((message) => onError(message));
                })
                .catch(() => onError("Directions unavailable right now."));
        });
    }

    function errorMessage(detail, status) {
        return detail || FALLBACK_BY_STATUS[status] || "Directions unavailable right now.";
    }

    function autoMount() {
        document.querySelectorAll("[data-gatekeyp-directions]").forEach(mount);
    }

    window.GatekeypDirections = { mount, autoMount };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", autoMount);
    } else {
        autoMount();
    }
})();
