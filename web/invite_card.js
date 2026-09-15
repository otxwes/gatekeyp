/* gatekeyp — invite_card.js: the portrait invite card (Phase 3.6).
 *
 * Draws a monochrome paper-and-ink card on an offscreen canvas (the Phase 3.5
 * motif vocabulary: keylines, hatch, dotted tooth, serif display type, the
 * keyhole mark), then passes the PNG through `gkpStego.embed()` so the invite
 * payload (`event_id\naccess_key`) is hidden in the pixels. The resulting PNG
 * downloads as the attendee's credential — drop it at the door to unlock.
 * No printed QR (Phase B): the stego layer is the only channel — a scannable
 * key is a secrecy downgrade, so the card carries no visible key material.
 *
 * Depends on: gkpStego (web/stego.js).
 */

"use strict";

window.gkpInviteCard = (function () {
    const CARD_W = 800;
    const CARD_H = 1200;

    // Design tokens — mirrors the web design system (monochrome, paper & ink).
    const INK = "#111111";
    const PAPER = "#ffffff";
    const PAPER_DEEP = "#f6f6f6";
    const LINE = "#e2e2e2";
    const LINE_STRONG = "#c9c9c9";

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

    /**
     * object-fit:contain destination rectangle for fitting a `srcW x srcH`
     * source wholly inside a `dstW x dstH` box (largest centered rect, aspect
     * preserved, never cropped — letterbox instead). Pure and deterministic —
     * pinned against the Python oracle in the JXA check alongside coverFit.
     */
    function containFit(srcW, srcH, dstW, dstH) {
        if (!(srcW > 0) || !(srcH > 0) || !(dstW > 0) || !(dstH > 0)) {
            return { dx: 0, dy: 0, dw: srcW, dh: srcH };
        }
        const scale = Math.min(dstW / srcW, dstH / srcH);
        const dw = srcW * scale;
        const dh = srcH * scale;
        return { dx: (dstW - dw) / 2, dy: (dstH - dh) / 2, dw, dh };
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

    /**
     * Cover-crop window for the full-card backdrop: object-fit:cover against
     * the card. Pure and deterministic — pinned against the Python oracle in
     * the JXA check alongside coverFit / containFit.
     */
    function backdropCrop(srcW, srcH) {
        return coverFit(srcW, srcH, CARD_W, CARD_H);
    }

    /**
     * Cover-extend the picture across the WHOLE card: a twice-downscaled
     * cover-crop of the same image upscaled back to card size — a smooth,
     * engine-independent blur (no ctx.filter dependency) painted behind the
     * contain-fitted art, so the letterbox reads as a continuation of the
     * picture instead of paper. Returns the crop used, or null if the image
     * has no pixels.
     */
    function drawBlurBackdrop(ctx, image) {
        const srcW = image.naturalWidth || image.width || 0;
        const srcH = image.naturalHeight || image.height || 0;
        if (!(srcW > 0) || !(srcH > 0)) return null;
        const crop = backdropCrop(srcW, srcH);
        const mid = document.createElement("canvas");
        mid.width = 96;
        mid.height = Math.max(1, Math.round((mid.width * CARD_H) / CARD_W));
        mid.getContext("2d").drawImage(image, crop.sx, crop.sy, crop.sw, crop.sh, 0, 0, mid.width, mid.height);
        const tiny = document.createElement("canvas");
        tiny.width = 24;
        tiny.height = Math.max(1, Math.round((tiny.width * CARD_H) / CARD_W));
        tiny.getContext("2d").drawImage(mid, 0, 0, mid.width, mid.height, 0, 0, tiny.width, tiny.height);
        ctx.save();
        ctx.imageSmoothingEnabled = true;
        if ("imageSmoothingQuality" in ctx) ctx.imageSmoothingQuality = "high";
        ctx.drawImage(tiny, 0, 0, tiny.width, tiny.height, 0, 0, CARD_W, CARD_H);
        ctx.restore();
        return crop;
    }

    /**
     * Spread an uploaded image across the WHOLE card surface (object-fit:
     * contain — the entire picture is always on the card, never cropped). The
     * letterbox around the art is filled with a blurred cover-extend of the
     * same picture, so the edges read as a natural continuation of the image
     * — no paper bands, no drawn outline. Returns the drawn rect.
     */
    function drawImageFullCard(ctx, image) {
        const srcW = image.naturalWidth || image.width || 0;
        const srcH = image.naturalHeight || image.height || 0;
        const r = containFit(srcW, srcH, CARD_W, CARD_H);
        drawBlurBackdrop(ctx, image);
        if (srcW > 0 && srcH > 0) {
            ctx.drawImage(image, 0, 0, srcW, srcH, r.dx, r.dy, r.dw, r.dh);
        }
        return r;
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

    /* ----------------------------------------------------------
     * Master-card markings (Phase 3.8)
     *
     * An organizer master card is the same paper, but stamped: a
     * paper-backed chip reading "MASTER CARD" (letterspaced serif caps,
     * double keyline border — the stamp motif) sits under the top keyhole,
     * and classic cards get a keeper note above the bottom keyhole. The chip
     * is drawn on top of any cover, including full-bleed photos, so the card
     * can never be mistaken for an attendee invite.
     * ---------------------------------------------------------- */
    function drawSpacedCaps(ctx, text, cx, baseline, spacing) {
        const chars = [...text];
        const widths = chars.map((ch) => ctx.measureText(ch).width);
        const total = widths.reduce((sum, w) => sum + w, 0) + spacing * (chars.length - 1);
        let x = cx - total / 2;
        chars.forEach((ch, i) => {
            ctx.fillText(ch, x, baseline);
            x += widths[i] + spacing;
        });
    }

    function drawMasterChip(ctx) {
        ctx.save();
        const cx = CARD_W / 2;
        const cy = 130;
        ctx.font = "600 21px Georgia, 'Times New Roman', serif";
        const chipW = Math.ceil(ctx.measureText("MASTER CARD").width) + 9 * 10 + 48;
        const chipH = 46;
        const x = cx - chipW / 2;
        const y = cy - chipH / 2;
        ctx.fillStyle = PAPER;
        ctx.fillRect(x, y, chipW, chipH);
        ctx.strokeStyle = INK;
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, chipW, chipH);
        ctx.lineWidth = 1;
        ctx.strokeRect(x + 4, y + 4, chipW - 8, chipH - 8);
        ctx.fillStyle = INK;
        ctx.textBaseline = "middle";
        drawSpacedCaps(ctx, "MASTER CARD", cx, cy + 1, 9);
        ctx.restore();
    }

    function drawMasterNote(ctx) {
        ctx.save();
        ctx.fillStyle = INK;
        ctx.globalAlpha = 0.72;
        ctx.font = "italic 400 17px Georgia, 'Times New Roman', serif";
        ctx.textAlign = "center";
        ctx.fillText("The one key this event answers to — keep it private.", CARD_W / 2, CARD_H - 128);
        ctx.restore();
    }

    /** Draw the card onto `canvas`. Pure and deterministic (testable). */
    function render(canvas, opts) {
        const o = opts || {};
        const scale = o.scale > 0 ? o.scale : 1;

        const ctx = canvas.getContext("2d");
        canvas.width = Math.round(CARD_W * scale);
        canvas.height = Math.round(CARD_H * scale);
        ctx.scale(scale, scale);

        const fullBleed = Boolean(o.coverImage && o.cover && o.cover.type === "image");

        // Paper ground. Full-card photos skip the paper texture (dotted
        // tooth, keyline frame, top keyhole): the art owns the entire surface.
        ctx.fillStyle = PAPER;
        ctx.fillRect(0, 0, CARD_W, CARD_H);
        if (!fullBleed) {
            drawDots(ctx, 0, 0, CARD_W, CARD_H, 28);

            // Slim keyline frame — the card's edge. No words, no stamp band.
            ctx.strokeStyle = LINE_STRONG;
            ctx.lineWidth = 2;
            ctx.strokeRect(24, 24, CARD_W - 48, CARD_H - 48);
            ctx.strokeStyle = LINE;
            ctx.lineWidth = 1;
            ctx.strokeRect(32, 32, CARD_W - 64, CARD_H - 64);

            // Top ornament: a single keyhole, centered.
            drawKeyhole(ctx, CARD_W / 2, 78, 18);
        }

        // Cover. An uploaded image is spread across the WHOLE card surface
        // (object-fit:contain — the entire picture is on the card, nothing
        // cropped; the letterbox is a blurred extension of the picture, so no
        // paper bands or outlines show at the edges); presets pattern the
        // 704×600 hero band; absent / "none" keeps paper.
        if (fullBleed) {
            drawImageFullCard(ctx, o.coverImage);
        } else {
            drawCoverBand(ctx, 48, 120, CARD_W - 96, 600, o.cover, o.coverImage || null);
        }

        // No printed QR on the card (Phase B): the stego layer is the only
        // channel — a scannable key would be a secrecy downgrade.

        // Bottom ornament: a single keyhole, centered. Full-bleed photo cards
        // skip it — the art runs edge to edge.
        if (!fullBleed) drawKeyhole(ctx, CARD_W / 2, CARD_H - 70, 12);

        // Master-card stamp (drawn on top of any cover, including full-bleed
        // photos — the chip carries its own paper ground so it always reads).
        if (o.organizer) {
            drawMasterChip(ctx);
            if (!fullBleed) drawMasterNote(ctx);
        }
    }

    function safeFileName(title) {
        const name = String(title || "invite").replace(/[^a-z0-9._ -]+/gi, "").trim().slice(0, 48);
        return name || "invite";
    }

    /**
     * Draw, embed the invite payload and trigger a download of the stego PNG.
     *
     * opts: { eventId, accessKey, title, cover, coverImage, scale, organizer }
     * `organizer: true` makes a MASTER card — same viewport, stamped face,
     * the hidden payload tagged `organizer` (see stego.js). Returns the Blob
     * (for tests / preview) after downloading.
     */
    async function download(opts) {
        const o = opts || {};
        const coverImage = o.cover && o.cover.type === "image" ? await loadCoverImage(o.cover) : null;
        const payload = window.gkpStego.makePayload(o.eventId, o.accessKey, o.organizer ? "organizer" : undefined);
        const canvas = document.createElement("canvas");
        render(canvas, { ...o, coverImage });
        const png = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
        const stegoBlob = await window.gkpStego.embed(png, payload);
        const url = URL.createObjectURL(stegoBlob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${safeFileName(opts.title)}-${o.organizer ? "master-card" : "invite"}.png`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 5000);
        return stegoBlob;
    }

    return { render, download, safeFileName, renderCover, coverFit, containFit, loadCoverImage };
})();
