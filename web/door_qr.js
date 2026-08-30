/* gatekeyp — door_qr.js: decode the QR fallback from an image the attendee
 * drops or pastes at the door (Phase 3.6 resilience batch).
 *
 * Re-encoded copies of a card (chat apps, screenshots, camera photos) destroy
 * the LSB-hidden key, but the QR printed on the card survives — that's the
 * documented fallback. We draw the image to an offscreen canvas (capped so a
 * 12 MP photo doesn't thrash memory), hand the RGBA buffer to the vendored
 * jsQR decoder and return the decoded text (or null when nothing is found).
 *
 * Depends on: the vendored jsQR (web/vendor/jsqr.js).
 */

"use strict";

window.gkpDoorQr = (function () {
    const MAX_EDGE = 1600; // longest edge cap before decoding

    function loadImage(url) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = () => reject(new Error("Could not decode that image."));
            img.src = url;
        });
    }

    /** Decode the QR payload from an image File/Blob; returns text or null. */
    async function decode(file) {
        if (!file || !window.jsQR) return null;
        const url = URL.createObjectURL(file);
        try {
            const img = await loadImage(url);
            const scale = Math.min(1, MAX_EDGE / Math.max(img.naturalWidth, img.naturalHeight));
            const w = Math.max(1, Math.round(img.naturalWidth * scale));
            const h = Math.max(1, Math.round(img.naturalHeight * scale));
            const canvas = document.createElement("canvas");
            canvas.width = w;
            canvas.height = h;
            const ctx = canvas.getContext("2d", { willReadFrequently: true });
            ctx.drawImage(img, 0, 0, w, h);
            const { data, width, height } = ctx.getImageData(0, 0, w, h);
            const result = window.jsQR(data, width, height, { inversionAttempts: "attemptBoth" });
            return result ? result.data : null;
        } catch {
            return null;
        } finally {
            URL.revokeObjectURL(url);
        }
    }

    return { decode };
})();
