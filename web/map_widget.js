/* Shared directions-map widget: lazy-loads MapLibre only on tap. */
(function () {
    "use strict";

    const MAPLIBRE_JS = "/vendor/maplibre/maplibre-gl.mjs";
    const MAPLIBRE_CSS = "/vendor/maplibre/maplibre-gl.css";
    const MAPLIBRE_WORKER = "/vendor/maplibre/maplibre-gl-worker.mjs";

    let libPromise = null;

    function loadLib() {
        if (libPromise) return libPromise;
        libPromise = (async () => {
            if (!document.querySelector(`link[href="${MAPLIBRE_CSS}"]`)) {
                const link = document.createElement("link");
                link.rel = "stylesheet";
                link.href = MAPLIBRE_CSS;
                document.head.appendChild(link);
            }
            const mod = await import(MAPLIBRE_JS);
            const maplibregl = mod.default || mod;
            maplibregl.setWorkerUrl(MAPLIBRE_WORKER);
            return maplibregl;
        })();
        return libPromise;
    }

    function fail(el) {
        const button = el.querySelector(".event-map-load");
        if (button) {
            button.textContent = "Map unavailable";
            button.disabled = true;
            button.hidden = false;
        }
        el.dataset.mapFailed = "1";
    }

    function initMap(el, maplibregl) {
        const lat = Number(el.dataset.lat);
        const lon = Number(el.dataset.lon);
        const style = el.dataset.style;
        const canvas = el.querySelector(".event-map-canvas");
        if (!canvas || !style || !Number.isFinite(lat) || !Number.isFinite(lon)) {
            fail(el);
            return;
        }
        let loaded = false;
        const map = new maplibregl.Map({
            container: canvas,
            style,
            center: [lon, lat],
            zoom: 16,
            cooperativeGestures: true,
            dragRotate: false,
            touchPitch: false,
            pitchWithRotate: false,
            attributionControl: false,
        });

        map.on("error", () => {
            if (!loaded) fail(el);
        });
        map.on("load", () => {
            loaded = true;
            new maplibregl.Marker().setLngLat([lon, lat]).addTo(map);
            map.addControl(
                new maplibregl.NavigationControl({ showCompass: false }),
                "top-right"
            );
        });

        el.classList.add("is-live");
        const button = el.querySelector(".event-map-load");
        if (button) button.hidden = true;
    }

    function mount(el) {
        if (!el || el.dataset.mapMounted === "1") return;
        el.dataset.mapMounted = "1";
        const button = el.querySelector(".event-map-load");
        if (!button) return;
        button.addEventListener("click", async () => {
            button.disabled = true;
            try {
                const maplibregl = await loadLib();
                initMap(el, maplibregl);
            } catch {
                fail(el);
            }
        });
    }

    function autoMount() {
        document.querySelectorAll("[data-gatekeyp-map]").forEach(mount);
    }

    async function copyText(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch {
            try {
                const textarea = document.createElement("textarea");
                textarea.value = text;
                textarea.setAttribute("readonly", "");
                textarea.style.position = "fixed";
                textarea.style.opacity = "0";
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand("copy");
                textarea.remove();
                return true;
            } catch {
                return false;
            }
        }
    }

    document.addEventListener("click", (event) => {
        const target = event.target.closest("[data-copy-address]");
        if (!target) return;
        const address = target.dataset.address || "";
        if (!address) return;
        event.preventDefault();
        copyText(address).then((ok) => {
            if (!ok) return;
            const original = target.textContent;
            target.textContent = "Copied";
            window.setTimeout(() => {
                target.textContent = original;
            }, 1500);
        });
    });

    window.GatekeypMap = { mount, autoMount };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", autoMount);
    } else {
        autoMount();
    }
})();
