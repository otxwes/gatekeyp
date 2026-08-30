# Copyright (c) 2026 gatekeyp contributors
"""Reference mirror of the Phase 3.7 invite-card cover helpers.

The shipped JS (``web/invite_card.js``) draws custom covers on the invite
card: a cover-fit crop for uploaded images and a small set of monochrome
preset patterns. This module is a stdlib-only mirror of the format-critical
math (``cover_fit``) plus the canonical preset registry, so the JS and Python
sides cannot drift apart silently — the JXA check pins the shipped JS against
these values.
"""

from __future__ import annotations

# Canonical cover presets — must stay in lock-step with COVER_PRESETS in
# web/app.js and the drawPreset branches in web/invite_card.js.
COVER_PRESET_IDS = ("none", "hatch", "keyline", "dots", "keyhole")


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
