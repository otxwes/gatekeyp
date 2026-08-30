# Copyright (c) 2026 gatekeyp contributors
"""Tests for the Phase 3.6 invite-card stego codec.

The oracle under test is ``tests.stego_ref`` — a stdlib-only mirror of the
shipped ``web/stego.js`` codec. Golden vectors pin the PRNG and CRC so the JS
and Python sides cannot drift apart silently; the committed fixture and the
E2E download -> decode path close the loop against the real browser code.
"""

import os
import random
import struct
import zlib

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests import stego_ref


def _random_png(seed: int, w: int, h: int) -> bytes:
    rng = random.Random(seed)  # noqa: S311 - deterministic test data only
    return stego_ref.write_png(w, h, bytes(rng.randrange(256) for _ in range(w * h * 4)))


def _manual_png(
    width: int,
    height: int,
    color_type: int,
    raw: bytes,
    plte: bytes | None = None,
    trns: bytes | None = None,
) -> bytes:
    """Assemble a PNG by hand (IHDR + optional PLTE/tRNS + IDAT + IEND)."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    out = bytearray(stego_ref.PNG_SIG)
    out += stego_ref._chunk(b"IHDR", ihdr)
    if plte is not None:
        out += stego_ref._chunk(b"PLTE", plte)
    if trns is not None:
        out += stego_ref._chunk(b"tRNS", trns)
    out += stego_ref._chunk(b"IDAT", zlib.compress(raw))
    out += stego_ref._chunk(b"IEND", b"")
    return bytes(out)


# ----------------------------------------------------------------------
# Golden vectors pin the wire format (the JS side must match these)
# ----------------------------------------------------------------------


def test_rng_golden_vectors() -> None:
    rng = stego_ref.make_rng()
    expected = [
        0xDC1B77AE0BF34DAD,
        0x64F0EEB9026E6076,
        0x7B07CE91E5906136,
        0x305F050C368DCC74,
        0x2CEB16E0A1C54AEC,
        0x97101DCE4E7BFB79,
    ]
    assert [rng() for _ in range(6)] == expected


def test_position_iter_is_scrambled_and_deduped() -> None:
    capacity = 100
    next_pos = stego_ref.make_position_iter(capacity)
    positions = [next_pos() for _ in range(40)]
    assert len(set(positions)) == 40  # deduped
    assert sorted(positions) != positions  # scrambled, not sequential
    assert all(0 <= p < capacity for p in positions)


def test_crc32_matches_zlib() -> None:
    for data in (b"", b"GKP1", b"event_id\nlocal:abc", b"\x00" * 512, os.urandom(300)):
        assert stego_ref.crc32(data) == (zlib.crc32(data) & 0xFFFFFFFF)


def test_container_roundtrip() -> None:
    for payload in ("event_a\nlocal:k", "event_b3c9\nlocal:" + "ab" * 32):
        assert stego_ref.parse_container(stego_ref.build_container(payload)) == payload


def test_container_rejects_corruption() -> None:
    container = stego_ref.build_container("event_a\nlocal:key")
    flipped = container[:10] + bytes([container[10] ^ 1]) + container[11:]
    assert stego_ref.parse_container(flipped) is None


def test_parse_payload() -> None:
    assert stego_ref.parse_payload("event_x\nlocal:abc") == ("event_x", "local:abc")
    assert stego_ref.parse_payload("no-newline") is None
    assert stego_ref.parse_payload("\nlocal:abc") is None
    assert stego_ref.parse_payload("event_x\n") is None
    assert stego_ref.parse_payload("  \n  ") is None


def test_qr_payload_roundtrip() -> None:
    event_id, key = "event_abcd1234", "local:0123456789abcdef"
    text = stego_ref.make_qr_payload(event_id, key)
    assert text.startswith("gkp:")
    assert stego_ref.parse_qr_payload(text) == (event_id, key)
    assert stego_ref.parse_qr_payload("https://example.com") is None
    assert stego_ref.parse_qr_payload("gkp:event_x") is None  # no colon separator


# ----------------------------------------------------------------------
# PNG codec self-consistency
# ----------------------------------------------------------------------


def test_write_parse_png_roundtrip() -> None:
    w, h = 24, 17
    rgba = bytes(random.Random(7).randrange(256) for _ in range(w * h * 4))  # noqa: S311
    png = stego_ref.write_png(w, h, rgba)
    assert png.startswith(stego_ref.PNG_SIG)
    assert stego_ref.parse_png(png) == (w, h, rgba)


def test_parse_png_rejects_non_png() -> None:
    with pytest.raises(ValueError):
        stego_ref.parse_png(b"not a png at all, just some bytes....")


def test_parse_png_detects_corruption() -> None:
    png = _random_png(9, 16, 16)
    idx = len(png) // 2
    corrupted = png[:idx] + bytes([png[idx] ^ 0x80]) + png[idx + 1 :]
    with pytest.raises(ValueError):
        stego_ref.parse_png(corrupted)


def test_parse_png_rejects_interlaced_and_bad_depth() -> None:
    png = _random_png(4, 8, 8)
    ihdr_data = png[16:29]  # 13-byte IHDR payload (right after sig + chunk header)
    rest = png[8 + 25 :]  # everything after the IHDR chunk
    # Rebuild the IHDR chunk with a valid CRC so we reach the semantic checks.
    interlaced = png[:8] + stego_ref._chunk(b"IHDR", ihdr_data[:12] + b"\x01") + rest
    with pytest.raises(ValueError, match="Interlaced"):
        stego_ref.parse_png(interlaced)
    bad_depth = png[:8] + stego_ref._chunk(b"IHDR", ihdr_data[:8] + b"\x04" + ihdr_data[9:]) + rest
    with pytest.raises(ValueError, match="8-bit"):
        stego_ref.parse_png(bad_depth)


def test_parse_png_unfilters_all_five_filter_types() -> None:
    # Hand-build an RGB PNG whose scanlines use filters 0..4 (one each) so
    # every un-filter branch — including Paeth — is exercised.
    width, height, stride = 5, 5, 3
    rng = random.Random(2)  # noqa: S311
    rgb = bytes(rng.randrange(256) for _ in range(width * height * stride))
    raw = bytearray()
    prev = bytearray(width * stride)  # unfiltered previous scanline
    for y in range(height):
        filt = y % 5
        raw.append(filt)
        line = rgb[y * width * stride : (y + 1) * width * stride]  # target row
        for x in range(width * stride):
            b = line[x]
            left = line[x - stride] if x >= stride else 0
            up = prev[x]
            up_left = prev[x - stride] if x >= stride else 0
            if filt == 0:
                v = b
            elif filt == 1:
                v = (b - left) & 0xFF
            elif filt == 2:
                v = (b - up) & 0xFF
            elif filt == 3:
                v = (b - ((left + up) >> 1)) & 0xFF
            else:
                v = (b - stego_ref._paeth(left, up, up_left)) & 0xFF
            raw.append(v)
        prev[:] = line
    w, h, out = stego_ref.parse_png(_manual_png(width, height, 2, bytes(raw)))
    assert (w, h) == (width, height)
    expected = bytearray()
    for i in range(width * height):
        expected += bytes((*rgb[i * 3 : i * 3 + 3], 255))
    assert out == bytes(expected)


def test_parse_png_expands_gray_and_palette_and_gray_alpha() -> None:
    w, h = 4, 3
    rng = random.Random(3)  # noqa: S311

    # Colour type 0: greyscale -> R=G=B, A=255.
    gray = bytes(rng.randrange(256) for _ in range(w * h))
    raw0 = bytearray()
    for y in range(h):
        raw0.append(0)
        raw0.extend(gray[y * w : (y + 1) * w])
    _w, _h, out0 = stego_ref.parse_png(_manual_png(w, h, 0, bytes(raw0)))
    for i, g in enumerate(gray):
        assert out0[i * 4 : i * 4 + 3] == bytes((g, g, g))
        assert out0[i * 4 + 3] == 255

    # Colour type 3: palette + tRNS alpha.
    plte = bytes([200, 30, 90, 10, 210, 100, 250, 250, 250])
    trns = bytes([255, 128, 0])
    idxs = bytes((i % 3) for i in range(w * h))  # one palette index per pixel
    raw3 = bytearray()
    for y in range(h):
        raw3.append(0)
        raw3.extend(idxs[y * w : (y + 1) * w])
    _w, _h, out3 = stego_ref.parse_png(_manual_png(w, h, 3, bytes(raw3), plte=plte, trns=trns))
    for i, idx in enumerate(idxs):
        assert out3[i * 4 : i * 4 + 3] == bytes(plte[idx * 3 : idx * 3 + 3])
        assert out3[i * 4 + 3] == trns[idx]

    # Colour type 4: greyscale + alpha.
    ga = bytes(rng.randrange(256) for _ in range(w * h * 2))
    raw4 = bytearray()
    for y in range(h):
        raw4.append(0)
        raw4.extend(ga[y * w * 2 : (y + 1) * w * 2])
    _w, _h, out4 = stego_ref.parse_png(_manual_png(w, h, 4, bytes(raw4)))
    for i in range(w * h):
        g, a = ga[i * 2], ga[i * 2 + 1]
        assert out4[i * 4 : i * 4 + 3] == bytes((g, g, g))
        assert out4[i * 4 + 3] == a


# ----------------------------------------------------------------------
# embed / extract round-trips
# ----------------------------------------------------------------------


@st.composite
def payload_strategy(draw: st.DrawFn) -> str:
    event_id = draw(
        st.text(
            alphabet=st.characters(blacklist_categories=("C",), blacklist_characters="\n:"),
            min_size=6,
            max_size=40,
        )
    )
    access_key = draw(st.text(alphabet="abcdef0123456789local:", min_size=8, max_size=80))
    return stego_ref.make_payload(event_id, access_key)


@given(data=st.data())
@settings(max_examples=25, deadline=None)
def test_embed_extract_roundtrip(data: st.DataObject) -> None:
    png = _random_png(data.draw(st.integers(min_value=0, max_value=10**9)), 56, 48)
    payload = data.draw(payload_strategy())
    assert stego_ref.extract(stego_ref.embed(png, payload)) == payload


def test_roundtrip_real_payload_shape() -> None:
    png = _random_png(3, 40, 32)
    payload = stego_ref.make_payload(
        "event_" + "a1b2c3d4e5f60718293a4b5c6d7e8f90",
        "local:" + "ab" * 32,
    )
    assert stego_ref.extract(stego_ref.embed(png, payload)) == payload


def test_roundtrip_long_payload() -> None:
    png = _random_png(21, 80, 60)
    payload = stego_ref.make_payload("event_" + "9" * 200, "local:" + "c0ffee" * 40)
    assert stego_ref.extract(stego_ref.embed(png, payload)) == payload


def test_majority_vote_recovers_one_corrupted_channel() -> None:
    png = _random_png(11, 48, 40)
    payload = stego_ref.make_payload("event_vote_test", "local:" + "cd" * 32)
    stego_png = stego_ref.embed(png, payload)
    width, height, pixels = stego_ref.parse_png(stego_png)
    pixels = bytearray(pixels)
    for i in range(0, len(pixels), 4):
        pixels[i] ^= 1  # fully corrupt the red channel's LSBs
    damaged = stego_ref.write_png(width, height, bytes(pixels))
    assert stego_ref.extract(damaged) == payload


def test_extract_returns_none_when_no_payload() -> None:
    assert stego_ref.extract(_random_png(5, 40, 32)) is None


def test_extract_solid_image_returns_none() -> None:
    w, h = 32, 32
    png = stego_ref.write_png(w, h, bytes([255] * (w * h * 4)))
    assert stego_ref.extract(png) is None


def test_embed_rejects_oversized_payload() -> None:
    w, h = 8, 8  # 64 pixels — cannot carry a full key
    png = stego_ref.write_png(w, h, bytes([128] * (w * h * 4)))
    with pytest.raises(ValueError, match="too small"):
        stego_ref.embed(png, stego_ref.make_payload("event_x", "local:" + "ef" * 32))


# ----------------------------------------------------------------------
# Committed fixture
# ----------------------------------------------------------------------


def test_fixture_decodes() -> None:
    assert stego_ref.FIXTURE_PATH.exists(), (
        "fixture missing — regenerate with: python -m tests.stego_ref --write-fixture"
    )
    png = stego_ref.FIXTURE_PATH.read_bytes()
    assert stego_ref.extract(png) == stego_ref.FIXTURE_PAYLOAD
    assert stego_ref.parse_payload(stego_ref.FIXTURE_PAYLOAD) == (
        stego_ref.FIXTURE_EVENT_ID,
        stego_ref.FIXTURE_ACCESS_KEY,
    )
