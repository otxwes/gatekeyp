# Copyright (c) 2026 gatekeyp contributors
"""Reference mirror of the Phase 3.7 invite-card cover helpers.

The shipped JS (``web/invite_card.js``) draws custom covers on the invite
card: a cover-fit crop for uploaded images and a small set of monochrome
preset patterns. This module is a stdlib-only mirror of the format-critical
math (``cover_fit`` for the preset hero band, ``contain_fit`` for the
full-card upload path, ``backdrop_crop`` for the blurred letterbox fill
behind that art) plus the canonical preset registry, so the JS and
Python sides cannot drift apart silently — the JXA check pins the shipped JS
against these values.
"""

from __future__ import annotations

# Canonical cover presets — must stay in lock-step with COVER_PRESETS in
# web/app.js and the drawPreset branches in web/invite_card.js.
COVER_PRESET_IDS = ("none", "hatch", "keyline", "dots", "keyhole")

# Card geometry — must stay in lock-step with CARD_W / CARD_H in
# web/invite_card.js (the full-card upload path renders against this size).
CARD_W = 800
CARD_H = 1200


def cover_fit(
    src_w: float, src_h: float, dst_w: float, dst_h: float
) -> tuple[float, float, float, float]:
    """object-fit:cover crop rectangle -> (sx, sy, sw, sh).

    Mirrors ``coverFit`` in web/invite_card.js: center-crop, preserve aspect,
    never stretch. Degenerate (non-positive) inputs return the source rect
    uncropped.
    """
    if not (src_w > 0 and src_h > 0 and dst_w > 0 and dst_h > 0):
        return (0.0, 0.0, float(src_w), float(src_h))
    scale = max(dst_w / src_w, dst_h / src_h)
    sw = dst_w / scale
    sh = dst_h / scale
    return ((src_w - sw) / 2, (src_h - sh) / 2, sw, sh)


def contain_fit(
    src_w: float, src_h: float, dst_w: float, dst_h: float
) -> tuple[float, float, float, float]:
    """object-fit:contain destination rect -> (dx, dy, dw, dh).

    Mirrors ``containFit`` in web/invite_card.js: the WHOLE source is scaled
    to the largest centered rect that fits the box — never cropped, aspect
    preserved, letterbox fills the rest. Degenerate (non-positive) inputs
    return the source size unchanged (same convention as ``cover_fit``).
    """
    if not (src_w > 0 and src_h > 0 and dst_w > 0 and dst_h > 0):
        return (0.0, 0.0, float(src_w), float(src_h))
    scale = min(dst_w / src_w, dst_h / src_h)
    dw = src_w * scale
    dh = src_h * scale
    return ((dst_w - dw) / 2, (dst_h - dh) / 2, dw, dh)


def backdrop_crop(src_w: float, src_h: float) -> tuple[float, float, float, float]:
    """Blurred-backdrop cover-crop window for the full-card upload path.

    Mirrors ``backdropCrop`` in web/invite_card.js: the letterbox around the
    contain-fitted art is filled with a blurred cover-extend of the same
    picture, and that backdrop is cropped from the source with the
    object-fit:cover math against the card (800x1200) — so the bands continue
    the image instead of showing paper.
    """
    return cover_fit(src_w, src_h, CARD_W, CARD_H)
