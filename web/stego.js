/* gatekeyp — stego.js: zero-dependency PNG low-bit codec for invite keys.
 *
 * Phase 3.6 (2026-08). Client-side only: invite cards are encoded and
 * decoded entirely in the browser, so raw access keys never leave a
 * visitor's tab and the server surface is unchanged.
 *
 * Format (v1) — deliberately small and deterministic so it can be mirrored
 * exactly in `tests/stego_ref.py` (the test oracle):
 *
 *   carrier   : 8-bit PNG, any of colour types 0/2/3/4/6, non-interlaced.
 *               Parsed manually (chunk walk + zlib inflate + unfilter) so
 *               browser canvas colour-management can never corrupt the bits.
 *   payload   : `event_id` + "\n" + `access_key` (UTF-8), wrapped in a
 *               container:
 *                 GKP1 | version(1) | payload_len(4 BE) | payload | crc32(4 BE)
 *               crc32 covers the 9-byte prefix + payload.
 *   bitstream : the container is zlib-compressed ('deflate'), prefixed by an
 *               8-byte plaintext header:
 *                 "GKP"(3) | version(1) | compressed_len(4 BE)
 *   embedding : each bit is replicated into the LSB of the R, G and B byte
 *               of one pixel; pixels are visited in a deterministic
 *               xorshift64-scrambled order (seed 0x9e3779b97f4a7c15, deduped)
 *               so the decoder re-derives the same positions. Decode reads a
 *               majority vote across the three channels and, if the container
 *               CRC fails, falls back to each single channel.
 *
 * StegX-informed choices (Delta-Sec/StegX, MIT): magic sentinel, compression,
 * scrambled non-linear embedding order, ±1 LSB placement, versioning. The
 * Argon2id/AES-GCM layers are deliberately omitted — the payload is already a
 * 128-bit random key and the card is a passwordless bearer credential.
 */

"use strict";

window.gkpStego = (function () {
    /* ----------------------------------------------------------
     * Constants + shared format primitives
     * ---------------------------------------------------------- */
    const SEED = 0x9e3779b97f4a7c15n;           // xorshift64 seed (fixed, exact)
    const EMBED_MAGIC = [0x47, 0x4b, 0x50];     // "GKP"
    const EMBED_VERSION = 0x01;
    const CONTAINER_MAGIC = [0x47, 0x4b, 0x50, 0x31]; // "GKP1"
    const CONTAINER_VERSION = 0x01;
    const HEADER_BITS = 64;                     // magic(24) + version(8) + len(32)
    const MAX_PAYLOAD_LEN = 4096;               // compressed-size sanity cap
    const MASK64 = 0xffffffffffffffffn;

    /* ----------------------------------------------------------
     * CRC32 (standard zlib/PNG polynomial — mirrors Python's zlib.crc32)
     * ---------------------------------------------------------- */
    const CRC_TABLE = (() => {
        const t = new Uint32Array(256);
        for (let n = 0; n < 256; n++) {
            let c = n;
            for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
            t[n] = c >>> 0;
        }
        return t;
    })();

    function crc32(bytes, start = 0, end = bytes.length) {
        let c = 0xffffffff;
        for (let i = start; i < end; i++) {
            c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
        }
        return (c ^ 0xffffffff) >>> 0;
    }

    /* ----------------------------------------------------------
     * Payload helpers
     * ---------------------------------------------------------- */
    function makePayload(eventId, accessKey) {
        return `${eventId}\n${accessKey}`;
    }

    function parsePayload(str) {
        if (typeof str !== "string") return null;
        const nl = str.indexOf("\n");
        if (nl <= 0 || nl === str.length - 1) return null;
        const eventId = str.slice(0, nl).trim();
        const accessKey = str.slice(nl + 1).trim();
        if (!eventId || !accessKey) return null;
        return { eventId, accessKey };
    }

    function qrPayload(eventId, accessKey) {
        return `gkp:${eventId}:${accessKey}`;
    }

    function parseQrPayload(str) {
        if (typeof str !== "string" || !str.startsWith("gkp:")) return null;
        const rest = str.slice(4);
        const sep = rest.indexOf(":");
        if (sep <= 0 || sep === rest.length - 1) return null;
        const eventId = rest.slice(0, sep).trim();
        const accessKey = rest.slice(sep + 1).trim();
        if (!eventId || !accessKey) return null;
        return { eventId, accessKey };
    }

    /* ----------------------------------------------------------
     * zlib helpers (browser-native CompressionStream / DecompressionStream)
     * ---------------------------------------------------------- */
    async function zlibDeflate(bytes) {
        const cs = new CompressionStream("deflate");
        const writer = cs.writable.getWriter();
        writer.write(bytes);
        writer.close();
        return new Uint8Array(await new Response(cs.readable).arrayBuffer());
    }

    async function zlibInflate(bytes) {
        const ds = new DecompressionStream("deflate");
        const writer = ds.writable.getWriter();
        writer.write(bytes);
        writer.close();
        return new Uint8Array(await new Response(ds.readable).arrayBuffer());
    }

    async function toBytes(input) {
        if (input instanceof Uint8Array) return input;
        if (input instanceof ArrayBuffer) return new Uint8Array(input);
        if (input && typeof input.arrayBuffer === "function") return new Uint8Array(await input.arrayBuffer());
        throw new Error("Expected a PNG file, blob or buffer.");
    }

    /* ----------------------------------------------------------
     * PNG parsing (manual — colour-management-safe)
     * ---------------------------------------------------------- */
    const PNG_SIG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

    function readU32(bytes, off) {
        return ((bytes[off] << 24) | (bytes[off + 1] << 16) | (bytes[off + 2] << 8) | bytes[off + 3]) >>> 0;
    }

    function paeth(a, b, c) {
        const p = a + b - c;
        const pa = Math.abs(p - a);
        const pb = Math.abs(p - b);
        const pc = Math.abs(p - c);
        if (pa <= pb && pa <= pc) return a;
        if (pb <= pc) return b;
        return c;
    }

    async function parsePng(buf) {
        const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
        if (bytes.length < 41) throw new Error("Not a PNG image (file too small).");
        for (let i = 0; i < 8; i++) {
            if (bytes[i] !== PNG_SIG[i]) throw new Error("Not a PNG image.");
        }
        let off = 8;
        let width = 0, height = 0, bitDepth = 0, colorType = 0, interlace = 0;
        const idat = [];
        let plte = null, trns = null;
        let sawIhdr = false;
        while (off + 8 <= bytes.length) {
            const len = readU32(bytes, off);
            const type = String.fromCharCode(bytes[off + 4], bytes[off + 5], bytes[off + 6], bytes[off + 7]);
            const dataStart = off + 8;
            const dataEnd = dataStart + len;
            if (dataEnd + 4 > bytes.length) throw new Error("Corrupt PNG (truncated chunk).");
            const stored = readU32(bytes, dataEnd);
            if (crc32(bytes, off + 4, dataEnd) !== stored) throw new Error("Corrupt PNG (chunk checksum mismatch).");
            if (type === "IHDR") {
                if (sawIhdr) throw new Error("Corrupt PNG (duplicate IHDR).");
                sawIhdr = true;
                if (len !== 13) throw new Error("Corrupt PNG (bad IHDR length).");
                width = readU32(bytes, dataStart);
                height = readU32(bytes, dataStart + 4);
                bitDepth = bytes[dataStart + 8];
                colorType = bytes[dataStart + 9];
                interlace = bytes[dataStart + 12];
                if (bitDepth !== 8) throw new Error("Only 8-bit PNGs are supported.");
                if (interlace !== 0) throw new Error("Interlaced PNGs are not supported.");
            } else if (type === "PLTE") {
                plte = bytes.slice(dataStart, dataEnd);
            } else if (type === "tRNS") {
                trns = bytes.slice(dataStart, dataEnd);
            } else if (type === "IDAT") {
                idat.push(bytes.slice(dataStart, dataEnd));
            } else if (type === "IEND") {
                break;
            }
            off = dataEnd + 4;
        }
        if (!sawIhdr || width === 0 || height === 0) throw new Error("Not a PNG image (missing IHDR).");
        if (!idat.length) throw new Error("Corrupt PNG (no image data).");

        const stride = [1, 0, 3, 1, 2, 0, 4][colorType] || 0;
        if (stride === 0) throw new Error(`Unsupported PNG colour type ${colorType}.`);
        if (colorType === 3 && !plte) throw new Error("Corrupt PNG (palette image without PLTE).");

        // Concatenate IDAT and inflate.
        const total = idat.reduce((n, c) => n + c.length, 0);
        const all = new Uint8Array(total);
        let p = 0;
        for (const c of idat) { all.set(c, p); p += c.length; }
        const raw = await zlibInflate(all);

        // Unfilter each scanline, then expand to RGBA.
        const rowLen = stride * width;
        const rgba = new Uint8Array(width * height * 4);
        const prev = new Uint8Array(rowLen);
        let rp = 0;
        for (let y = 0; y < height; y++) {
            if (rp >= raw.length) throw new Error("Corrupt PNG (image data too short).");
            const filter = raw[rp++];
            const line = new Uint8Array(rowLen);
            for (let x = 0; x < rowLen; x++) {
                if (rp >= raw.length) throw new Error("Corrupt PNG (image data too short).");
                const rawByte = raw[rp++];
                const left = x >= stride ? line[x - stride] : 0;
                const up = prev[x];
                const upLeft = x >= stride ? prev[x - stride] : 0;
                let v = rawByte;
                if (filter === 1) v = (v + left) & 0xff;
                else if (filter === 2) v = (v + up) & 0xff;
                else if (filter === 3) v = (v + ((left + up) >> 1)) & 0xff;
                else if (filter === 4) v = (v + paeth(left, up, upLeft)) & 0xff;
                else if (filter !== 0) throw new Error(`Corrupt PNG (unknown filter ${filter}).`);
                line[x] = v;
            }
            for (let x = 0; x < width; x++) {
                const si = x * stride;
                const di = (y * width + x) * 4;
                if (colorType === 0) {
                    const g = line[si];
                    rgba[di] = g; rgba[di + 1] = g; rgba[di + 2] = g;
                    rgba[di + 3] = (trns && line[si] === trns[0]) ? 0 : 255;
                } else if (colorType === 2) {
                    rgba[di] = line[si]; rgba[di + 1] = line[si + 1]; rgba[di + 2] = line[si + 2];
                    rgba[di + 3] = 255;
                } else if (colorType === 3) {
                    const idx = line[si];
                    rgba[di] = plte[idx * 3]; rgba[di + 1] = plte[idx * 3 + 1]; rgba[di + 2] = plte[idx * 3 + 2];
                    rgba[di + 3] = (trns && idx < trns.length) ? trns[idx] : 255;
                } else if (colorType === 4) {
                    const g = line[si];
                    rgba[di] = g; rgba[di + 1] = g; rgba[di + 2] = g;
                    rgba[di + 3] = line[si + 1];
                } else {
                    rgba[di] = line[si]; rgba[di + 1] = line[si + 1];
                    rgba[di + 2] = line[si + 2]; rgba[di + 3] = line[si + 3];
                }
            }
            prev.set(line);
        }
        return { width, height, rgba };
    }

    /* ----------------------------------------------------------
     * PNG writing (always 8-bit RGBA, filter 0)
     * ---------------------------------------------------------- */
    function chunk(type, data) {
        const out = new Uint8Array(12 + data.length);
        out[0] = (data.length >>> 24) & 0xff; out[1] = (data.length >>> 16) & 0xff;
        out[2] = (data.length >>> 8) & 0xff; out[3] = data.length & 0xff;
        for (let i = 0; i < 4; i++) out[4 + i] = type.charCodeAt(i);
        out.set(data, 8);
        const crc = crc32(out, 4, 8 + data.length);
        out[8 + data.length] = (crc >>> 24) & 0xff; out[9 + data.length] = (crc >>> 16) & 0xff;
        out[10 + data.length] = (crc >>> 8) & 0xff; out[11 + data.length] = crc & 0xff;
        return out;
    }

    async function writePng(width, height, rgba) {
        const ihdr = new Uint8Array(13);
        const u32 = (v, o) => {
            ihdr[o] = (v >>> 24) & 0xff; ihdr[o + 1] = (v >>> 16) & 0xff;
            ihdr[o + 2] = (v >>> 8) & 0xff; ihdr[o + 3] = v & 0xff;
        };
        u32(width, 0);
        u32(height, 4);
        ihdr[8] = 8; ihdr[9] = 6; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;

        const rowLen = width * 4;
        const raw = new Uint8Array(height * (1 + rowLen));
        for (let y = 0; y < height; y++) {
            raw[y * (1 + rowLen)] = 0; // filter: None
            raw.set(rgba.subarray(y * rowLen, (y + 1) * rowLen), y * (1 + rowLen) + 1);
        }
        const idatData = await zlibDeflate(raw);

        const sig = new Uint8Array(PNG_SIG);
        const parts = [sig, chunk("IHDR", ihdr), chunk("IDAT", idatData), chunk("IEND", new Uint8Array(0))];
        const outTotal = parts.reduce((n, c) => n + c.length, 0);
        const out = new Uint8Array(outTotal);
        let op = 0;
        for (const c of parts) { out.set(c, op); op += c.length; }
        return new Blob([out], { type: "image/png" });
    }

    /* ----------------------------------------------------------
     * Deterministic scrambled pixel order (xorshift64, fixed seed)
     * ---------------------------------------------------------- */
    function makeRng(seed = SEED) {
        let state = BigInt(seed) & MASK64;
        return function next() {
            let x = state;
            x ^= (x << 13n) & MASK64;
            x ^= x >> 7n;
            x ^= (x << 17n) & MASK64;
            state = x & MASK64;
            return state;
        };
    }

    function makePositionIter(capacity) {
        const rng = makeRng();
        const seen = new Set();
        return function nextPos() {
            for (;;) {
                const p = Number(rng() % BigInt(capacity));
                if (!seen.has(p)) { seen.add(p); return p; }
            }
        };
    }

    /* ----------------------------------------------------------
     * Bit embedding / extraction (LSB of R, G and B per pixel)
     * ---------------------------------------------------------- */
    function embedBits(rgba, nextPos, bytes, nBits) {
        for (let i = 0; i < nBits; i++) {
            const bit = (bytes[i >> 3] >> (7 - (i & 7))) & 1;
            const base = nextPos() * 4;
            for (let c = 0; c < 3; c++) rgba[base + c] = (rgba[base + c] & 0xfe) | bit;
        }
    }

    function readBitsVote(rgba, nextPos, nBits) {
        const out = new Uint8Array(Math.ceil(nBits / 8));
        for (let i = 0; i < nBits; i++) {
            const base = nextPos() * 4;
            const ones = (rgba[base] & 1) + (rgba[base + 1] & 1) + (rgba[base + 2] & 1);
            if (ones >= 2) out[i >> 3] |= 1 << (7 - (i & 7));
        }
        return out;
    }

    function readBitsChannel(rgba, nextPos, nBits, ch) {
        const out = new Uint8Array(Math.ceil(nBits / 8));
        for (let i = 0; i < nBits; i++) {
            const base = nextPos() * 4;
            if (rgba[base + ch] & 1) out[i >> 3] |= 1 << (7 - (i & 7));
        }
        return out;
    }

    /* ----------------------------------------------------------
     * Payload container
     * ---------------------------------------------------------- */
    function buildContainer(payload) {
        const payloadBytes = new TextEncoder().encode(payload);
        if (payloadBytes.length > MAX_PAYLOAD_LEN) throw new Error("Payload too large.");
        const out = new Uint8Array(13 + payloadBytes.length);
        out[0] = CONTAINER_MAGIC[0]; out[1] = CONTAINER_MAGIC[1];
        out[2] = CONTAINER_MAGIC[2]; out[3] = CONTAINER_MAGIC[3];
        out[4] = CONTAINER_VERSION;
        out[5] = (payloadBytes.length >>> 24) & 0xff; out[6] = (payloadBytes.length >>> 16) & 0xff;
        out[7] = (payloadBytes.length >>> 8) & 0xff; out[8] = payloadBytes.length & 0xff;
        out.set(payloadBytes, 9);
        const crc = crc32(out, 0, 9 + payloadBytes.length);
        const o = 9 + payloadBytes.length;
        out[o] = (crc >>> 24) & 0xff; out[o + 1] = (crc >>> 16) & 0xff;
        out[o + 2] = (crc >>> 8) & 0xff; out[o + 3] = crc & 0xff;
        return out;
    }

    function parseContainer(bytes) {
        if (!bytes || bytes.length < 13) return null;
        for (let i = 0; i < 4; i++) if (bytes[i] !== CONTAINER_MAGIC[i]) return null;
        if (bytes[4] !== CONTAINER_VERSION) return null;
        const plen = readU32(bytes, 5);
        if (plen > MAX_PAYLOAD_LEN || bytes.length !== 13 + plen) return null;
        const stored = readU32(bytes, 9 + plen);
        if (crc32(bytes, 0, 9 + plen) !== stored) return null;
        return new TextDecoder().decode(bytes.subarray(9, 9 + plen));
    }

    /* ----------------------------------------------------------
     * Public embed / extract
     * ---------------------------------------------------------- */
    async function embed(pngInput, payload) {
        const png = await toBytes(pngInput);
        const { width, height, rgba } = await parsePng(png);
        const container = buildContainer(payload);
        const compressed = await zlibDeflate(container);
        const totalBits = HEADER_BITS + compressed.length * 8;
        if (totalBits > width * height) {
            throw new Error("This image is too small to carry the invite key.");
        }
        const header = new Uint8Array(8);
        header[0] = EMBED_MAGIC[0]; header[1] = EMBED_MAGIC[1]; header[2] = EMBED_MAGIC[2];
        header[3] = EMBED_VERSION;
        header[4] = (compressed.length >>> 24) & 0xff; header[5] = (compressed.length >>> 16) & 0xff;
        header[6] = (compressed.length >>> 8) & 0xff; header[7] = compressed.length & 0xff;
        const nextPos = makePositionIter(width * height);
        embedBits(rgba, nextPos, header, HEADER_BITS);
        embedBits(rgba, nextPos, compressed, compressed.length * 8);
        return writePng(width, height, rgba);
    }

    async function extract(pngInput) {
        const png = await toBytes(pngInput);
        const { width, height, rgba } = await parsePng(png);
        const capacity = width * height;
        const attempts = [
            { read: (np, n) => readBitsVote(rgba, np, n) },
            { read: (np, n) => readBitsChannel(rgba, np, n, 0) },
            { read: (np, n) => readBitsChannel(rgba, np, n, 1) },
            { read: (np, n) => readBitsChannel(rgba, np, n, 2) },
        ];
        for (const attempt of attempts) {
            const nextPos = makePositionIter(capacity);
            const header = attempt.read(nextPos, HEADER_BITS);
            if (header[0] !== EMBED_MAGIC[0] || header[1] !== EMBED_MAGIC[1] || header[2] !== EMBED_MAGIC[2]) continue;
            if (header[3] !== EMBED_VERSION) continue;
            const clen = readU32(header, 4);
            if (clen < 1 || clen > MAX_PAYLOAD_LEN) continue;
            const bits = attempt.read(nextPos, clen * 8);
            const container = bits.slice(0, clen);
            try {
                const inflated = await zlibInflate(container);
                const payload = parseContainer(inflated);
                if (payload !== null) return payload;
            } catch {
                /* fall through to the next attempt */
            }
        }
        return null;
    }

    return { embed, extract, makePayload, parsePayload, qrPayload, parseQrPayload };
})();
