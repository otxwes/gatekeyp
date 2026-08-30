# Copyright (c) 2026 gatekeyp contributors
"""Reference implementation of the ``web/stego.js`` invite-card codec.

This is the test oracle for the shipped browser codec: it mirrors
``web/stego.js`` function-for-function so the automated suite (and the E2E
download -> decode path) can validate the JS without a browser. Any change to
the on-disk format MUST be applied here and in ``web/stego.js`` together, then
the committed fixture regenerated::

    python -m tests.stego_ref --write-fixture

Stdlib only (``zlib``, ``struct``, ``binascii``) so the tests run headless.
"""

from __future__ import annotations

import binascii
import struct
import zlib
from pathlib import Path

SEED = 0x9E3779B97F4A7C15
MASK64 = (1 << 64) - 1
EMBED_MAGIC = b"GKP"
EMBED_VERSION = 1
CONTAINER_MAGIC = b"GKP1"
CONTAINER_VERSION = 1
HEADER_BITS = 64  # magic(24) + version(8) + len(32)
MAX_PAYLOAD_LEN = 4096
PNG_SIG = b"\x89PNG\r\n\x1a\n"

# Payload baked into the committed fixture (realistic shape: event id + local key).
FIXTURE_EVENT_ID = "event_e2e1234567890abcdef"
FIXTURE_ACCESS_KEY = "local:" + "0123456789abcdef" * 4
FIXTURE_PAYLOAD = f"{FIXTURE_EVENT_ID}\n{FIXTURE_ACCESS_KEY}"

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "invite_fixture.png"


def crc32(data: bytes) -> int:
    """Standard zlib/PNG CRC-32 — must match the JS table implementation."""
    return binascii.crc32(data) & 0xFFFFFFFF


def make_rng(seed: int = SEED):
    """xorshift64 state machine — byte-for-byte identical to web/stego.js."""
    state = seed & MASK64

    def next_value() -> int:
        nonlocal state
        x = state
        x ^= (x << 13) & MASK64
        x ^= x >> 7
        x ^= (x << 17) & MASK64
        state = x & MASK64
        return state

    return next_value


def make_position_iter(capacity: int):
    """Deterministic scrambled, deduped pixel-order generator (mirrors JS)."""
    rng = make_rng()
    seen: set[int] = set()

    def next_pos() -> int:
        while True:
            p = rng() % capacity
            if p not in seen:
                seen.add(p)
                return p

    return next_pos


class PngError(ValueError):
    """Raised when a PNG cannot be parsed or is unsupported.

    Message constants live on the class (satisfying ruff TRY003/EM101) and the
    test ``match=`` assertions share the same strings.
    """

    MSG_NOT_PNG = "Not a PNG image."
    MSG_NO_IHDR = "Not a PNG image (missing IHDR)."
    MSG_TRUNCATED = "Corrupt PNG (truncated chunk)."
    MSG_CHECKSUM = "Corrupt PNG (chunk checksum mismatch)."
    MSG_DUP_IHDR = "Corrupt PNG (duplicate IHDR)."
    MSG_BAD_IHDR = "Corrupt PNG (bad IHDR length)."
    MSG_DEPTH = "Only 8-bit PNGs are supported."
    MSG_INTERLACED = "Interlaced PNGs are not supported."
    MSG_NO_IDAT = "Corrupt PNG (no image data)."
    MSG_NO_PLTE = "Corrupt PNG (palette image without PLTE)."
    MSG_SHORT = "Corrupt PNG (image data too short)."
    MSG_COLOR_TYPE = "Unsupported PNG colour type {0}."
    MSG_FILTER = "Corrupt PNG (unknown filter {0})."


class StegoError(ValueError):
    """Raised when a payload cannot be embedded or decoded."""

    MSG_IMAGE_SMALL = "This image is too small to carry the invite key."
    MSG_PAYLOAD_BIG = "Payload too large."


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _walk_chunks(  # noqa: C901, PLR0912 - PNG chunk walk is inherently branchy
    data: bytes,
) -> tuple[int, int, int, bytes, bytes | None, bytes | None]:
    """Walk a PNG's chunks, verifying CRCs, and return the essentials.

    Returns ``(width, height, colour_type, idat, plte, trns)``.
    """
    off = 8
    width = height = color_type = 0
    idat = bytearray()
    plte: bytes | None = None
    trns: bytes | None = None
    saw_ihdr = False
    while off + 8 <= len(data):
        (length,) = struct.unpack(">I", data[off : off + 4])
        ctype = data[off + 4 : off + 8].decode("latin-1")
        data_start = off + 8
        data_end = data_start + length
        if data_end + 4 > len(data):
            raise PngError(PngError.MSG_TRUNCATED)
        stored = struct.unpack(">I", data[data_end : data_end + 4])[0]
        if crc32(data[off + 4 : data_end]) != stored:
            raise PngError(PngError.MSG_CHECKSUM)
        if ctype == "IHDR":
            if saw_ihdr:
                raise PngError(PngError.MSG_DUP_IHDR)
            saw_ihdr = True
            if length != 13:
                raise PngError(PngError.MSG_BAD_IHDR)
            width, height = struct.unpack(">II", data[data_start : data_start + 8])
            bit_depth, color_type = data[data_start + 8], data[data_start + 9]
            interlace = data[data_start + 12]
            if bit_depth != 8:
                raise PngError(PngError.MSG_DEPTH)
            if interlace != 0:
                raise PngError(PngError.MSG_INTERLACED)
        elif ctype == "PLTE":
            plte = bytes(data[data_start:data_end])
        elif ctype == "tRNS":
            trns = bytes(data[data_start:data_end])
        elif ctype == "IDAT":
            idat.extend(data[data_start:data_end])
        elif ctype == "IEND":
            break
        off = data_end + 4
    if not saw_ihdr or width == 0 or height == 0:
        raise PngError(PngError.MSG_NO_IHDR)
    if not idat:
        raise PngError(PngError.MSG_NO_IDAT)
    return width, height, color_type, bytes(idat), plte, trns


def _unfilter_scanlines(  # noqa: C901, PLR0912 - per-colour-type expansion
    raw: bytes,
    width: int,
    height: int,
    stride: int,
    color_type: int,
    plte: bytes | None,
    trns: bytes | None,
) -> bytes:
    """Unfilter every scanline and expand the pixels to RGBA."""
    row_len = stride * width
    expected = height * (1 + row_len)
    if len(raw) < expected:
        raise PngError(PngError.MSG_SHORT)
    rgba = bytearray(width * height * 4)
    prev = bytearray(row_len)
    rp = 0
    for y in range(height):
        filt = raw[rp]
        rp += 1
        line = bytearray(row_len)
        for x in range(row_len):
            raw_byte = raw[rp]
            rp += 1
            left = line[x - stride] if x >= stride else 0
            up = prev[x]
            up_left = prev[x - stride] if x >= stride else 0
            if filt == 0:
                v = raw_byte
            elif filt == 1:
                v = (raw_byte + left) & 0xFF
            elif filt == 2:
                v = (raw_byte + up) & 0xFF
            elif filt == 3:
                v = (raw_byte + ((left + up) >> 1)) & 0xFF
            elif filt == 4:
                v = (raw_byte + _paeth(left, up, up_left)) & 0xFF
            else:
                raise PngError(PngError.MSG_FILTER.format(filt))
            line[x] = v
        for x in range(width):
            si = x * stride
            di = (y * width + x) * 4
            if color_type == 0:
                g = line[si]
                rgba[di : di + 3] = bytes((g, g, g))
                alpha = 0 if (trns is not None and len(trns) and line[si] == trns[0]) else 255
                rgba[di + 3] = alpha
            elif color_type == 2:
                rgba[di : di + 3] = line[si : si + 3]
                rgba[di + 3] = 255
            elif color_type == 3:
                idx = line[si]
                rgba[di : di + 3] = plte[idx * 3 : idx * 3 + 3]
                rgba[di + 3] = trns[idx] if trns is not None and idx < len(trns) else 255
            elif color_type == 4:
                g = line[si]
                rgba[di : di + 3] = bytes((g, g, g))
                rgba[di + 3] = line[si + 1]
            else:
                rgba[di : di + 4] = line[si : si + 4]
        prev[:] = line
    return bytes(rgba)


def parse_png(data: bytes) -> tuple[int, int, bytes]:
    """Parse an 8-bit non-interlaced PNG into (width, height, RGBA bytes).

    Mirrors web/stego.js parsePng. Raises PngError (a ValueError subclass) on
    malformed input.
    """
    if len(data) < 41 or data[:8] != PNG_SIG:
        raise PngError(PngError.MSG_NOT_PNG)
    width, height, color_type, idat, plte, trns = _walk_chunks(data)
    strides = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    if color_type not in strides:
        raise PngError(PngError.MSG_COLOR_TYPE.format(color_type))
    stride = strides[color_type]
    if color_type == 3 and plte is None:
        raise PngError(PngError.MSG_NO_PLTE)
    raw = zlib.decompress(idat)
    return width, height, _unfilter_scanlines(raw, width, height, stride, color_type, plte, trns)


def _chunk(ctype: bytes, data: bytes) -> bytes:
    head = struct.pack(">I", len(data)) + ctype
    return head + data + struct.pack(">I", crc32(ctype + data))


def write_png(width: int, height: int, rgba: bytes) -> bytes:
    """Encode RGBA pixels as an 8-bit PNG (filter 0) — mirrors web/stego.js."""
    row_len = width * 4
    raw = bytearray(height * (1 + row_len))
    for y in range(height):
        raw[y * (1 + row_len)] = 0
        raw[y * (1 + row_len) + 1 : (y + 1) * (1 + row_len)] = rgba[y * row_len : (y + 1) * row_len]
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw))
    out = bytearray(PNG_SIG)
    out += _chunk(b"IHDR", ihdr)
    out += _chunk(b"IDAT", idat)
    out += _chunk(b"IEND", b"")
    return bytes(out)


def make_payload(event_id: str, access_key: str) -> str:
    return f"{event_id}\n{access_key}"


def parse_payload(payload: str) -> tuple[str, str] | None:
    if not isinstance(payload, str):
        return None
    nl = payload.find("\n")
    if nl <= 0 or nl == len(payload) - 1:
        return None
    event_id = payload[:nl].strip()
    access_key = payload[nl + 1 :].strip()
    if not event_id or not access_key:
        return None
    return event_id, access_key


def make_qr_payload(event_id: str, access_key: str) -> str:
    return f"gkp:{event_id}:{access_key}"


def parse_qr_payload(text: str) -> tuple[str, str] | None:
    if not text.startswith("gkp:"):
        return None
    rest = text[4:]
    sep = rest.find(":")
    if sep <= 0 or sep == len(rest) - 1:
        return None
    event_id = rest[:sep].strip()
    access_key = rest[sep + 1 :].strip()
    if not event_id or not access_key:
        return None
    return event_id, access_key


REJECT_RE_ENCODE = (
    "This looks like a re-encoded copy of a card — the hidden key was lost to "
    "compression, but the QR printed on the card still works. Scan it and paste "
    "the gkp: text, or share the original PNG as a file."
)
REJECT = {
    "png": (
        "This looks like a gatekeyp card, but no key could be read from it — "
        "the card may have been altered or re-encoded. Share the original PNG as "
        "a file, or paste the gkp: text with ⌘V."
    ),
    "jpeg": REJECT_RE_ENCODE,
    "webp": REJECT_RE_ENCODE,
    "gif": "That's a GIF — invite cards are PNGs. Share the original PNG as a "
    "file, or paste the gkp: text with ⌘V.",
    "bmp": "That's a BMP — invite cards are PNGs. Share the original PNG as a "
    "file, or paste the gkp: text with ⌘V.",
    "other": "That doesn't look like an invite card. Drop the card PNG here, or "
    "paste the gkp: text with ⌘V.",
}


def classify_invite(data: bytes) -> str:
    """Magic-byte sniffing for the door — mirrors ``web/stego.js`` classifyInvite."""
    if not isinstance(data, (bytes, bytearray)) or len(data) < 12:
        return "other"
    if data[:8] == PNG_SIG:
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:4] == b"GIF8" and data[4] in (0x37, 0x39):
        return "gif"
    if data[:2] == b"BM":
        return "bmp"
    return "other"


def invite_reject_reason(kind: str) -> str:
    """User-facing rejection message — mirrors ``web/stego.js`` inviteRejectReason."""
    return REJECT.get(kind, REJECT["other"])


def build_container(payload: str) -> bytes:
    payload_bytes = payload.encode("utf-8")
    if len(payload_bytes) > MAX_PAYLOAD_LEN:
        raise StegoError(StegoError.MSG_PAYLOAD_BIG)
    head = CONTAINER_MAGIC + bytes([CONTAINER_VERSION]) + struct.pack(">I", len(payload_bytes))
    return head + payload_bytes + struct.pack(">I", crc32(head + payload_bytes))


def parse_container(container: bytes) -> str | None:
    if container is None or len(container) < 13:
        return None
    if container[:4] != CONTAINER_MAGIC or container[4] != CONTAINER_VERSION:
        return None
    (plen,) = struct.unpack(">I", container[5:9])
    if plen > MAX_PAYLOAD_LEN or len(container) != 13 + plen:
        return None
    stored = struct.unpack(">I", container[9 + plen : 13 + plen])[0]
    if crc32(container[: 9 + plen]) != stored:
        return None
    return container[9 : 9 + plen].decode("utf-8")


def _embed_bits(rgba: bytearray, next_pos, bitstream: bytes, n_bits: int) -> None:
    for i in range(n_bits):
        bit = (bitstream[i >> 3] >> (7 - (i & 7))) & 1
        base = next_pos() * 4
        for c in range(3):
            rgba[base + c] = (rgba[base + c] & 0xFE) | bit


def _read_bits_vote(rgba: bytes, next_pos, n_bits: int) -> bytearray:
    out = bytearray((n_bits + 7) // 8)
    for i in range(n_bits):
        base = next_pos() * 4
        ones = (rgba[base] & 1) + (rgba[base + 1] & 1) + (rgba[base + 2] & 1)
        if ones >= 2:
            out[i >> 3] |= 1 << (7 - (i & 7))
    return out


def _read_bits_channel(rgba: bytes, next_pos, n_bits: int, ch: int) -> bytearray:
    out = bytearray((n_bits + 7) // 8)
    for i in range(n_bits):
        base = next_pos() * 4
        if rgba[base + ch] & 1:
            out[i >> 3] |= 1 << (7 - (i & 7))
    return out


def embed(png: bytes, payload: str) -> bytes:
    width, height, rgba = parse_png(png)
    rgba = bytearray(rgba)
    container = build_container(payload)
    compressed = zlib.compress(container)
    total_bits = HEADER_BITS + len(compressed) * 8
    if total_bits > width * height:
        raise StegoError(StegoError.MSG_IMAGE_SMALL)
    header = EMBED_MAGIC + bytes([EMBED_VERSION]) + struct.pack(">I", len(compressed))
    next_pos = make_position_iter(width * height)
    _embed_bits(rgba, next_pos, header, HEADER_BITS)
    _embed_bits(rgba, next_pos, compressed, len(compressed) * 8)
    return write_png(width, height, bytes(rgba))


def extract(png: bytes) -> str | None:
    width, height, rgba = parse_png(png)
    capacity = width * height
    attempts = [
        ("vote", lambda np, n: _read_bits_vote(rgba, np, n)),
        ("ch0", lambda np, n: _read_bits_channel(rgba, np, n, 0)),
        ("ch1", lambda np, n: _read_bits_channel(rgba, np, n, 1)),
        ("ch2", lambda np, n: _read_bits_channel(rgba, np, n, 2)),
    ]
    for _kind, read in attempts:
        next_pos = make_position_iter(capacity)
        header = bytes(read(next_pos, HEADER_BITS))
        if len(header) < 8 or header[:3] != EMBED_MAGIC or header[3] != EMBED_VERSION:
            continue
        (clen,) = struct.unpack(">I", header[4:8])
        if clen < 1 or clen > MAX_PAYLOAD_LEN:
            continue
        bits = bytes(read(next_pos, clen * 8))
        try:
            container = zlib.decompress(bits[:clen])
        except zlib.error:
            continue
        payload = parse_container(container)
        if payload is not None:
            return payload
    return None


def _make_carrier(width: int = 800, height: int = 1200) -> bytes:
    """Deterministic poster-like carrier for the committed fixture.

    Paper-grey ground, an ink band, a bottom keyline block and a dotted
    "tooth" — an echo of the invite-card art, drawn with no external image
    library so the fixture stays reproducible.
    """
    rgba = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            di = (y * width + x) * 4
            v = 244 - int((x / width) * 36)  # faint horizontal paper gradient
            if 140 <= x <= 170:  # ink band (hatch stripe echo)
                v = int(v * 0.35)
            if y >= height - 220:  # bottom keyline block
                v = int(v * 0.6)
            if ((x * 2654435761 + y * 40503) & 0xFFFF) % 41 == 0:  # dotted tooth
                v = max(0, v - 55)
            rgba[di] = rgba[di + 1] = rgba[di + 2] = v
            rgba[di + 3] = 255
    return write_png(width, height, bytes(rgba))


def _main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="gatekeyp stego reference codec tools")
    parser.add_argument(
        "--write-fixture",
        action="store_true",
        help=f"(re)write {FIXTURE_PATH}",
    )
    parser.add_argument(
        "--decode",
        metavar="PNG",
        help="decode an invite-card PNG and print its payload",
    )
    args = parser.parse_args()
    if args.write_fixture:
        png = embed(_make_carrier(), FIXTURE_PAYLOAD)
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_PATH.write_bytes(png)
        sys.stdout.write(f"wrote {FIXTURE_PATH} ({len(png)} bytes)\n")
        return
    if args.decode:
        png = Path(args.decode).read_bytes()
        payload = extract(png)
        if payload is None:
            sys.stderr.write("no invite key found in that PNG\n")
            raise SystemExit(1)
        parsed = parse_payload(payload)
        sys.stdout.write(f"payload: {payload}\n")
        sys.stdout.write(f"event_id: {parsed[0] if parsed else '?'}\n")
        sys.stdout.write(f"access_key: {parsed[1] if parsed else '?'}\n")
        return
    parser.print_help()


if __name__ == "__main__":
    _main()
