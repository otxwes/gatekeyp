# Copyright (c) 2026 gatekeyp contributors
"""Tests for the Phase 3.7 invite-card custom covers.

Covers are a purely client-side rendering feature; the format-critical part is
the cover-fit crop math (mirrored in ``tests.card_ref`` and pinned against the
shipped JS by the JXA check) plus the preset registry staying in lock-step
across ``invite_card.js``, ``app.js`` and the oracle. The browser E2E pass
covers the actual canvas drawing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests import card_ref

_HERE = Path(__file__).resolve().parent
_WEB = _HERE.parent / "web"


def test_cover_fit_golden_vectors() -> None:
    # (src_w, src_h, dst_w, dst_h) -> expected (sx, sy, sw, sh).
    cases = [
        # Exact 2:3 aspect into a 2:3 box: full source, scaled, no crop.
        ((200, 300, 400, 600), (0.0, 0.0, 200.0, 300.0)),
        # Landscape photo into the card's 704x240 cover band: fills width,
        # center-crops top/bottom.
        ((800, 600, 704, 240), (0.0, (600 - 240 / (704 / 800)) / 2, 800.0, 240 / (704 / 800))),
        # Portrait photo into the same band: fills width, heavy height crop.
        ((400, 800, 704, 240), (0.0, (800 - 240 / (704 / 400)) / 2, 400.0, 240 / (704 / 400))),
        # Wide source into a square box: center-crops the sides.
        ((200, 100, 100, 100), (50.0, 0.0, 100.0, 100.0)),
        # Tall source into a square box: center-crops the ends.
        ((100, 200, 100, 100), (0.0, 50.0, 100.0, 100.0)),
        # Degenerate inputs: uncropped source rect, never crashes.
        ((0, 100, 704, 240), (0.0, 0.0, 0.0, 100.0)),
        ((-5, 100, 704, 240), (0.0, 0.0, -5.0, 100.0)),
        ((800, 600, 0, 240), (0.0, 0.0, 800.0, 600.0)),
    ]
    for (src_w, src_h, dst_w, dst_h), want in cases:
        got = card_ref.cover_fit(src_w, src_h, dst_w, dst_h)
        assert got == pytest.approx(want, abs=1e-9), (src_w, src_h, dst_w, dst_h)


@given(
    src_w=st.floats(min_value=1, max_value=4096, allow_nan=False, allow_infinity=False),
    src_h=st.floats(min_value=1, max_value=4096, allow_nan=False, allow_infinity=False),
    dst_w=st.floats(min_value=1, max_value=4096, allow_nan=False, allow_infinity=False),
    dst_h=st.floats(min_value=1, max_value=4096, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200, deadline=None)
def test_cover_fit_is_object_fit_cover(src_w, src_h, dst_w, dst_h) -> None:
    """Cover-fit properties: the full source scaled by the fit scale covers the
    destination, the visible crop scaled by the same scale exactly fills it, the
    crop is a centered window on the source (its aspect matches the box, not the
    source), and it never exceeds the source bounds."""
    sx, sy, sw, sh = card_ref.cover_fit(src_w, src_h, dst_w, dst_h)

    # Object-fit:cover sizing — the unscaled source scaled by the fit scale
    # covers the destination in at least one dimension and never under-fills.
    scale = max(dst_w / src_w, dst_h / src_h)
    assert src_w * scale >= dst_w - 1e-9
    assert src_h * scale >= dst_h - 1e-9

    # After the crop, the scaled crop exactly fills the destination.
    assert sw * scale == pytest.approx(dst_w, rel=1e-9)
    assert sh * scale == pytest.approx(dst_h, rel=1e-9)

    # The crop is a window into the scaled source: its aspect is the box's.
    assert sw / sh == pytest.approx(dst_w / dst_h, rel=1e-9)

    # The crop is centered and within the source.
    assert sx == pytest.approx((src_w - sw) / 2, rel=1e-9)
    assert sy == pytest.approx((src_h - sh) / 2, rel=1e-9)
    assert sx >= -1e-9 and sy >= -1e-9
    assert sx + sw <= src_w + 1e-9
    assert sy + sh <= src_h + 1e-9


def test_preset_ids_in_shipped_js_match_oracle() -> None:
    """drawPreset's branches in invite_card.js must cover the oracle's preset
    set (minus "none", which drawPreset never receives)."""
    js = (_WEB / "invite_card.js").read_text(encoding="utf-8")
    ids = set(re.findall(r'id === "([a-z]+)"', js))
    assert ids == set(card_ref.COVER_PRESET_IDS) - {"none"}


def test_app_picker_presets_match_oracle() -> None:
    """The picker's COVER_PRESETS in app.js must match the oracle exactly."""
    app = (_WEB / "app.js").read_text(encoding="utf-8")
    ids = set(re.findall(r'\{ id: "([a-z]+)", label:', app))
    assert ids == set(card_ref.COVER_PRESET_IDS)
