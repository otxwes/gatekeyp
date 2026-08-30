/* gatekeyp — invite_card.js: the portrait invite card (Phase 3.6).
 *
 * Draws a monochrome paper-and-ink card on an offscreen canvas (the Phase 3.5
 * motif vocabulary: keylines, hatch, dotted tooth, serif display type, the
 * keyhole mark), renders the QR fallback, then passes the PNG through
 * `gkpStego.embed()` so the invite payload (`event_id\naccess_key`) is hidden
 * in the pixels. The resulting PNG downloads as the attendee's credential —
 * drop it at the door to unlock.
 *
 * Depends on: gkpStego (web/stego.js) and the vendored qrcode-generator
 * (web/vendor/qrcode-generator.js).
 */

"use strict";

window.gkpInviteCard = (function () {
    const CARD_W = 800;
    const CARD_H = 1200;

    // Design tokens — mirrors the web design system (monochrome, paper & ink).
    const INK = "#111111";
    const INK_SOFT = "#4d4d4d";
    const INK_FAINT = "#6b6b6b";
    const PAPER = "#ffffff";
    const PAPER_DEEP = "#f6f6f6";
    const LINE = "#e2e2e2";
    const LINE_STRONG = "#c9c9c9";
    const FONT_SERIF = "'Iowan Old Style', 'Palatino Linotype', Palatino, Georgia, serif";
    const FONT_SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
    const FONT_MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, monospace";

    function wrapText(ctx, text, x, y, maxWidth, lineHeight, maxLines) {
        const words = String(text).split(/\s+/).filter(Boolean);
        let line = "";
        let lines = 0;
        for (const word of words) {
            const probe = line ? `${line} ${word}` : word;
            if (line && ctx.measureText(probe).width > maxWidth) {
                ctx.fillText(line, x, y);
                line = word;
                y += lineHeight;
                lines += 1;
                if (maxLines && lines >= maxLines) return y;
            } else {
                line = probe;
            }
        }
        if (line) {
            ctx.fillText(line, x, y);
            lines += 1;
        }
        return y;
    }

    function drawDots(ctx, x, y, w, h, step) {
        ctx.save();
        ctx.fillStyle = "rgba(0, 0, 0, 0.05)";
        for (let yy = y; yy < y + h; yy += step) {
            const offset = (Math.floor(yy / step) % 2) ? step / 2 : 0;
            for (let xx = x + offset; xx < x + w; xx += step) {
                ctx.beginPath();
                ctx.arc(xx, yy, 1.3, 0, Math.PI * 2);
                ctx.fill();
            }
        }
        ctx.restore();
    }

    function drawHatch(ctx, x, y, w, h, gap, lineWidth) {
        ctx.save();
        ctx.beginPath();
        ctx.rect(x, y, w, h);
        ctx.clip();
        ctx.strokeStyle = LINE;
        ctx.lineWidth = lineWidth;
        for (let i = -h; i < w; i += gap) {
            ctx.beginPath();
            ctx.moveTo(x + i, y + h);
            ctx.lineTo(x + i + h, y);
            ctx.stroke();
        }
        ctx.restore();
    }

    function drawKeyhole(ctx, cx, cy, r) {
        ctx.save();
        ctx.strokeStyle = INK;
        ctx.lineWidth = Math.max(2, r * 0.24);
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fillStyle = INK;
        ctx.beginPath();
        ctx.arc(cx, cy, r * 0.34, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }

    function drawQr(ctx, qr, x, y, size) {
        const n = qr.getModuleCount();
        const cell = size / n;
        ctx.save();
        ctx.fillStyle = PAPER_DEEP;
        ctx.fillRect(x - 16, y - 16, size + 32, size + 32);
        ctx.strokeStyle = LINE_STRONG;
        ctx.lineWidth = 2;
        ctx.strokeRect(x - 16, y - 16, size + 32, size + 32);
        ctx.fillStyle = INK;
        for (let row = 0; row < n; row++) {
            for (let col = 0; col < n; col++) {
                if (qr.isDark(row, col)) {
                    ctx.fillRect(x + col * cell, y + row * cell, Math.ceil(cell), Math.ceil(cell));
                }
            }
        }
        ctx.restore();
    }

    function buildQr(text) {
        if (typeof window.qrcode !== "function" || !text) return null;
        try {
            const qr = window.qrcode(0, "M");
            qr.addData(text, "Byte");
            qr.make();
            return qr;
        } catch {
            return null; // QR is a fallback — never block the card on it.
        }
    }

    function fmtEventId(eventId) {
        const id = String(eventId || "");
        return id.length > 34 ? `${id.slice(0, 15)}…${id.slice(-14)}` : id;
    }

    /**
     * object-fit:cover crop rectangle for drawing a `srcW x srcH` source into a
     * `dstW x dstH` box (center-crop, preserve aspect, never stretch). Pure and
     * deterministic — pinned against the Python oracle in the JXA check.
     */
    function coverFit(srcW, srcH, dstW, dstH) {
        if (!(srcW > 0) || !(srcH > 0) || !(dstW > 0) || !(dstH > 0)) {
            return { sx: 0, sy: 0, sw: srcW, sh: srcH };
        }
        const scale = Math.max(dstW / srcW, dstH / srcH);
        const sw = dstW / scale;
        const sh = dstH / scale;
        return { sx: (srcW - sw) / 2, sy: (srcH - sh) / 2, sw, sh };
    }

    /** Monochrome cover presets (Phase 3.7) — texture-only, from the motif set. */
    function drawPreset(ctx, id, x, y, w, h) {
        if (id === "hatch") {
            drawHatch(ctx, x + 6, y + 6, w - 12, h - 12, 12, 1);
        } else if (id === "keyline") {
            const maxInset = Math.min(w, h) / 2 - 6;
            ctx.save();
            ctx.strokeStyle = LINE;
            ctx.lineWidth = 2;
            for (let i = 0; i < 4; i++) {
                const inset = Math.min(14 + i * 26, maxInset);
                if (inset > 0) ctx.strokeRect(x + inset, y + inset, w - inset * 2, h - inset * 2);
            }
            ctx.restore();
        } else if (id === "dots") {
            drawDots(ctx, x, y, w, h, 22);
        } else if (id === "keyhole") {
            const step = 56;
            for (let yy = y + 28; yy < y + h; yy += step) {
                const offset = (Math.floor((yy - y) / step) % 2) ? step / 2 : 0;
                for (let xx = x + offset + 28; xx < x + w; xx += step) {
                    drawKeyhole(ctx, xx, yy, 11);
                }
            }
        }
    }

    /**
     * Draw the cover band (x, y, w, h). `cover` is absent / {type:"none"} (classic
     * paper — nothing drawn), {type:"preset", id}, or {type:"image"} whose loaded
     * `image` element is drawn cover-fit. The frame keyline always sits on top.
     */
    function drawCoverBand(ctx, x, y, w, h, cover, image) {
        const c = cover && cover.type ? cover : { type: "none" };
        if (c.type === "none") return;
        ctx.save();
        ctx.fillStyle = PAPER_DEEP;
        ctx.fillRect(x, y, w, h);
        if (c.type === "image" && image) {
            const srcW = image.naturalWidth || image.width || 0;
            const srcH = image.naturalHeight || image.height || 0;
            const r = coverFit(srcW, srcH, w, h);
            ctx.drawImage(image, r.sx, r.sy, r.sw, r.sh, x, y, w, h);
        } else if (c.type === "preset") {
            drawPreset(ctx, c.id, x, y, w, h);
        }
        ctx.strokeStyle = LINE_STRONG;
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, w, h);
        ctx.restore();
    }

    /** Render just the cover band at w x h (used for picker swatches). */
    function renderCover(canvas, w, h, cover, image) {
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        // Always frame the swatch (paper ground + keyline) so "None" reads as
        // paper rather than a blank block.
        ctx.fillStyle = PAPER_DEEP;
        ctx.fillRect(0, 0, w, h);
        drawCoverBand(ctx, 0, 0, w, h, cover, image);
        if (!cover || cover.type === "none") {
            ctx.strokeStyle = LINE_STRONG;
            ctx.lineWidth = 2;
            ctx.strokeRect(0, 0, w, h);
        }
        return canvas;
    }

    /** Resolve a {type:"image"} cover to a loaded Image (async). */
    function loadCoverImage(cover) {
        return new Promise((resolve, reject) => {
            if (!cover || cover.type !== "image") return resolve(null);
            if (cover.image) return resolve(cover.image);
            const src = cover.url || cover.src;
            if (!src) return reject(new Error("No cover image."));
            const img = new Image();
            img.onload = () => {
                cover.image = img;
                resolve(img);
            };
            img.onerror = () => reject(new Error("Could not load that cover image."));
            img.src = src;
        });
    }

    /** Draw the card onto `canvas`. Pure and deterministic (testable). */
    function render(canvas, opts) {
        const o = opts || {};
        const scale = o.scale > 0 ? o.scale : 1;
        const title = String(o.title || "Untitled event");
        const organizer = String(o.organizerId || "an organizer");
        const location = String(o.location || "");
        const eventId = String(o.eventId || "");
        const accessKey = String(o.accessKey || "");

        const ctx = canvas.getContext("2d");
        canvas.width = Math.round(CARD_W * scale);
        canvas.height = Math.round(CARD_H * scale);
        ctx.scale(scale, scale);

        // Paper ground + dotted tooth.
        ctx.fillStyle = PAPER;
        ctx.fillRect(0, 0, CARD_W, CARD_H);
        drawDots(ctx, 0, 0, CARD_W, CARD_H, 28);

        // Top stamp band: double keyline + hatch strip + eyebrow + keyhole.
        ctx.fillStyle = PAPER_DEEP;
        ctx.fillRect(16, 16, CARD_W - 32, 118);
        ctx.strokeStyle = LINE_STRONG;
        ctx.lineWidth = 2;
        ctx.strokeRect(24, 24, CARD_W - 48, 102);
        ctx.strokeStyle = LINE;
        ctx.lineWidth = 1;
        ctx.strokeRect(32, 32, CARD_W - 64, 86);
        drawHatch(ctx, 32, 96, CARD_W - 64, 14, 10, 1);

        ctx.fillStyle = INK_SOFT;
        ctx.font = `600 22px ${FONT_SANS}`;
        ctx.textBaseline = "middle";
        ctx.fillText("gatekeyp — you're invited", 52, 64);
        ctx.font = `500 18px ${FONT_SANS}`;
        ctx.fillStyle = INK_FAINT;
        ctx.fillText("PRINTED KEY · INK ON PAPER", 52, 94);
        drawKeyhole(ctx, CARD_W - 78, 62, 20);

        // Optional custom cover band (Phase 3.7): preset pattern or uploaded
        // photo drawn cover-fit. Absent / "none" keeps the classic paper look.
        drawCoverBand(ctx, 48, 150, CARD_W - 96, 240, o.cover, o.coverImage || null);

        // Serif display title.
        ctx.fillStyle = INK;
        ctx.font = `600 78px ${FONT_SERIF}`;
        ctx.textBaseline = "alphabetic";
        wrapText(ctx, title, 48, 430, CARD_W - 96, 96, 3);

        // Rule under the title.
        ctx.strokeStyle = LINE_STRONG;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(48, 560);
        ctx.lineTo(CARD_W - 48, 560);
        ctx.stroke();

        // Meta block.
        ctx.fillStyle = INK_SOFT;
        ctx.font = `500 30px ${FONT_SANS}`;
        ctx.fillText(`by ${organizer}`, 48, 596);
        if (location) {
            ctx.font = `500 26px ${FONT_SANS}`;
            ctx.fillStyle = INK_FAINT;
            wrapText(ctx, location, 48, 650, CARD_W - 96, 38, 2);
        }

        // QR fallback (survives re-encoding by photo apps).
        const qr = buildQr(String(o.qrText || ""));
        if (qr) {
            ctx.fillStyle = INK_SOFT;
            ctx.font = `600 20px ${FONT_SANS}`;
            ctx.textBaseline = "alphabetic";
            ctx.fillText("SCAN TO UNLOCK", 52, 826);
            drawQr(ctx, qr, 56, 850, 250);
        }

        // Bottom rail: event id + monogram + privacy note.
        ctx.fillStyle = INK_FAINT;
        ctx.font = `500 24px ${FONT_MONO}`;
        ctx.fillText(fmtEventId(eventId), 48, CARD_H - 110);
        ctx.font = `500 18px ${FONT_SANS}`;
        ctx.fillStyle = LINE_STRONG;
        ctx.fillText("GKP·1  —  the key lives in these pixels", 48, CARD_H - 64);
        drawKeyhole(ctx, CARD_W - 88, CARD_H - 86, 16);
    }

    function safeFileName(title) {
        const name = String(title || "invite").replace(/[^a-z0-9._ -]+/gi, "").trim().slice(0, 48);
        return name || "invite";
    }

    /**
     * Draw, embed the invite payload and trigger a download of the stego PNG.
     *
     * opts: { eventId, accessKey, title, organizerId, location }
     * Returns the Blob (for tests / preview) after downloading.
     */
    async function download(opts) {
        const o = opts || {};
        const coverImage = o.cover && o.cover.type === "image" ? await loadCoverImage(o.cover) : null;
        const payload = window.gkpStego.makePayload(o.eventId, o.accessKey);
        const canvas = document.createElement("canvas");
        render(canvas, { ...o, coverImage });
        const png = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
        const stegoBlob = await window.gkpStego.embed(png, payload);
        const url = URL.createObjectURL(stegoBlob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${safeFileName(opts.title)}-invite.png`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 5000);
        return stegoBlob;
    }

    return { render, download, safeFileName, renderCover, coverFit, loadCoverImage };
})();
