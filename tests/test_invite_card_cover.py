# Copyright (c) 2026 gatekeyp contributors
"""Tests for the Phase 3.7 invite-card custom covers.

Covers are a purely client-side rendering feature; the format-critical parts
are the cover-fit crop math and the contain-fit whole-image math (mirrored in
``tests.card_ref`` and pinned against the shipped JS by the JXA check) plus
the preset registry staying in lock-step across ``invite_card.js``, ``app.js``
and the oracle. The browser E2E pass covers the actual canvas drawing.
"""

from __future__ import annotations

import math
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


def test_contain_fit_golden_vectors() -> None:
    # (src_w, src_h, dst_w, dst_h) -> expected (dx, dy, dw, dh).
    cases = [
        # Landscape photo contain-fit to the full 800x1200 card: full width,
        # letterboxed top/bottom (the whole image stays on the card).
        ((1600, 900, 800, 1200), (0.0, 375.0, 800.0, 450.0)),
        # Portrait photo: full height, letterboxed left/right.
        ((900, 1600, 800, 1200), (62.5, 0.0, 675.0, 1200.0)),
        # Square photo: fills the width, centered vertically.
        ((600, 600, 800, 1200), (0.0, 200.0, 800.0, 800.0)),
        # Exact card aspect: fills the whole surface edge to edge.
        ((1600, 2400, 800, 1200), (0.0, 0.0, 800.0, 1200.0)),
        # A small source is still scaled up to fill as much as possible.
        ((200, 300, 800, 1200), (0.0, 0.0, 800.0, 1200.0)),
        # Degenerate inputs: source size unchanged, never crashes.
        ((0, 100, 800, 1200), (0.0, 0.0, 0.0, 100.0)),
        ((-5, 100, 800, 1200), (0.0, 0.0, -5.0, 100.0)),
        ((800, 600, 0, 240), (0.0, 0.0, 800.0, 600.0)),
    ]
    for (src_w, src_h, dst_w, dst_h), want in cases:
        got = card_ref.contain_fit(src_w, src_h, dst_w, dst_h)
        assert got == pytest.approx(want, abs=1e-9), (src_w, src_h, dst_w, dst_h)


@given(
    src_w=st.floats(min_value=1, max_value=8192, allow_nan=False, allow_infinity=False),
    src_h=st.floats(min_value=1, max_value=8192, allow_nan=False, allow_infinity=False),
    dst_w=st.floats(min_value=1, max_value=8192, allow_nan=False, allow_infinity=False),
    dst_h=st.floats(min_value=1, max_value=8192, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200, deadline=None)
def test_contain_fit_is_object_fit_contain(src_w, src_h, dst_w, dst_h) -> None:
    """Contain-fit properties: the whole source is visible (never cropped),
    the scaled source exactly fills one axis and never overfills either, the
    aspect is preserved, and the drawn rect is centered inside the box."""
    dx, dy, dw, dh = card_ref.contain_fit(src_w, src_h, dst_w, dst_h)
    scale = min(dst_w / src_w, dst_h / src_h)

    # The whole source, scaled by the fit scale, is exactly the drawn rect.
    assert dw == pytest.approx(src_w * scale, rel=1e-9)
    assert dh == pytest.approx(src_h * scale, rel=1e-9)

    # Never overfills; exactly fills at least one axis (nothing cropped).
    assert dw <= dst_w + 1e-9
    assert dh <= dst_h + 1e-9
    assert math.isclose(dw, dst_w, rel_tol=1e-9, abs_tol=1e-9) or math.isclose(
        dh, dst_h, rel_tol=1e-9, abs_tol=1e-9
    )

    # Aspect preserved and the rect is centered inside the box.
    assert dw / dh == pytest.approx(src_w / src_h, rel=1e-9)
    assert dx == pytest.approx((dst_w - dw) / 2, rel=1e-9)
    assert dy == pytest.approx((dst_h - dh) / 2, rel=1e-9)
    assert dx >= -1e-9 and dy >= -1e-9


def test_invite_card_ships_full_card_upload_path() -> None:
    """The shipped card module must expose containFit and the full-card image
    path (the math itself is pinned to the oracle by the JXA check)."""
    js = (_WEB / "invite_card.js").read_text(encoding="utf-8")
    assert "function containFit(" in js
    assert "drawImageFullCard" in js
    assert "containFit, loadCoverImage" in js


def test_backdrop_crop_golden_vectors() -> None:
    # (src_w, src_h) -> expected (sx, sy, sw, sh): the blurred letterbox fill
    # behind the art is a cover-fit crop of the source against the 800x1200
    # card (same math as cover_fit, card-sized destination box).
    cases = [
        # Landscape source: keeps full height, trims the sides.
        ((1600, 900), (500.0, 0.0, 600.0, 900.0)),
        # Portrait source: keeps full width, trims top/bottom.
        ((900, 1600), (0.0, 125.0, 900.0, 1350.0)),
        # Mildly wide portrait: center-crops the sides.
        ((1200, 1500), (100.0, 0.0, 1000.0, 1500.0)),
        # Square source: crops to the card's 2:3 aspect.
        ((600, 600), (100.0, 0.0, 400.0, 600.0)),
        # Exact card aspect: the whole source is the window.
        ((1600, 2400), (0.0, 0.0, 1600.0, 2400.0)),
        # Extreme landscape: a narrow centered slice (275/6 = 45.8333…,
        # 94/3 = 31.3333…).
        ((123, 47), (275 / 6, 0.0, 94 / 3, 47.0)),
    ]
    for (src_w, src_h), want in cases:
        got = card_ref.backdrop_crop(src_w, src_h)
        assert got == pytest.approx(want, abs=1e-9), (src_w, src_h)


@given(
    src_w=st.floats(min_value=1, max_value=8192, allow_nan=False, allow_infinity=False),
    src_h=st.floats(min_value=1, max_value=8192, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=150, deadline=None)
def test_backdrop_crop_covers_card(src_w, src_h) -> None:
    """Backdrop properties: scaled by the fit scale the crop exactly fills the
    card, its aspect is the card's (not the source's), it is a centered window
    inside the source, and it never leaves the source bounds."""
    sx, sy, sw, sh = card_ref.backdrop_crop(src_w, src_h)
    scale = max(card_ref.CARD_W / src_w, card_ref.CARD_H / src_h)

    # Scaled by the fit scale, the crop exactly fills the card.
    assert sw * scale == pytest.approx(card_ref.CARD_W, rel=1e-9)
    assert sh * scale == pytest.approx(card_ref.CARD_H, rel=1e-9)

    # It is a centered window with the card's aspect, inside the source.
    assert sw / sh == pytest.approx(card_ref.CARD_W / card_ref.CARD_H, rel=1e-9)
    assert sx == pytest.approx((src_w - sw) / 2, rel=1e-9)
    assert sy == pytest.approx((src_h - sh) / 2, rel=1e-9)
    assert sx >= -1e-9 and sy >= -1e-9
    assert sx + sw <= src_w + 1e-9 and sy + sh <= src_h + 1e-9


def test_invite_card_full_bleed_blurs_letterbox_without_outline() -> None:
    """The full-card path fills the letterbox with the blurred cover-extend
    backdrop and no longer strokes a hairline outline around the art."""
    js = (_WEB / "invite_card.js").read_text(encoding="utf-8")
    body = re.search(r"function drawImageFullCard\(ctx, image\) \{.*?\n    \}", js, re.DOTALL)
    assert body, "drawImageFullCard not found in invite_card.js"
    assert "drawBlurBackdrop(ctx, image);" in body.group(0)
    assert "strokeRect" not in body.group(0), "no outline may be drawn around the art"
    assert "containFit(srcW, srcH, CARD_W, CARD_H)" in body.group(0)
    assert "function backdropCrop(" in js
    assert "function drawBlurBackdrop(" in js


def test_invite_card_photo_cards_skip_paper_ornaments() -> None:
    """Full-card photos must not show the dotted paper, keyline frame or the
    keyhole ornaments on top of the art."""
    js = (_WEB / "invite_card.js").read_text(encoding="utf-8")
    assert re.search(r"if \(!fullBleed\) \{\s*\n\s*drawDots\(", js)
    assert re.search(r"if \(!fullBleed\) drawKeyhole\(ctx, CARD_W / 2, CARD_H - 70, 12\);", js)
