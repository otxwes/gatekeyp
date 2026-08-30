// gatekeyp — JXA (JavaScriptCore) harness to cross-check web/stego.js against
// the Python oracle (tests/stego_ref.py). Node is unavailable in this
// environment, so this is how the *shipped* JS gets parsed and its
// format-critical internals pinned to Python-derived golden values.
//
// This file is a template: the driver (tests/jxa_stego_check.py) substitutes
// the STEGO_MODULE_SOURCE placeholder with the hooked web/stego.js source (its
// return object extended with a __test member exposing the internals) and the
// EXPECTED_JSON placeholder with the golden values, then runs the result via
// `osascript -l JavaScript`.

ObjC.import("Foundation");

function readFile(path) {
    return $.NSString.stringWithContentsOfFileEncodingError(path, $.NSUTF8StringEncoding, null).js;
}

// --- Minimal TextEncoder/TextDecoder shims (JavaScriptCore in JXA lacks them) ---
function TextEncoder() {}
TextEncoder.prototype.encode = function (s) {
    var out = [];
    for (var i = 0; i < s.length; i++) {
        var cp = s.codePointAt(i);
        if (cp > 0xffff) i++;
        if (cp < 0x80) out.push(cp);
        else if (cp < 0x800) out.push(0xc0 | (cp >> 6), 0x80 | (cp & 63));
        else if (cp < 0x10000) out.push(0xe0 | (cp >> 12), 0x80 | ((cp >> 6) & 63), 0x80 | (cp & 63));
        else out.push(0xf0 | (cp >> 18), 0x80 | ((cp >> 12) & 63), 0x80 | ((cp >> 6) & 63), 0x80 | (cp & 63));
    }
    return Uint8Array.from(out);
};
function TextDecoder() {}
TextDecoder.prototype.decode = function (bytes) {
    var out = "";
    for (var i = 0; i < bytes.length; i++) {
        var b = bytes[i];
        var cp;
        if (b < 0x80) cp = b;
        else if ((b & 0xe0) === 0xc0) { cp = ((b & 31) << 6) | (bytes[i + 1] & 63); i += 1; }
        else if ((b & 0xf0) === 0xe0) { cp = ((b & 15) << 12) | ((bytes[i + 1] & 63) << 6) | (bytes[i + 2] & 63); i += 2; }
        else { cp = ((b & 7) << 18) | ((bytes[i + 1] & 63) << 12) | ((bytes[i + 2] & 63) << 6) | (bytes[i + 3] & 63); i += 3; }
        out += String.fromCodePoint(cp);
    }
    return out;
};

// --- The shipped codec, hooked to expose its internals via gkpStego.__test ---
var window = {};
__STEGO_MODULE_SOURCE__

// --- Vendored encoder + decoder for the QR fallback round-trip ---
var self = {};
__QR_ENCODER_SOURCE__
__JSQR_SOURCE__

var T = window.gkpStego.__test;
var exp = JSON.parse(readFile("__EXPECTED_JSON__"));
var failures = [];

// CRC32 vs Python's zlib.crc32
exp.crc32.forEach(function (c) {
    var got = T.crc32(Uint8Array.from(c.bytes));
    if (got !== c.value) failures.push("crc32 mismatch: got " + got + " want " + c.value + " (hex " + c.hex + ")");
});

// xorshift64 raw stream vs Python mirror. JXA's JavaScriptCore has a broken
// BigInt `%` (and `/`), so we pin the raw stream here and re-derive the
// scrambled positions below with bitwise long division; the shipped `%` path
// is exercised by the browser E2E, where the engine is a real one.
function bigintMod(x, c) {
    var r = 0n;
    for (var i = 63; i >= 0; i--) {
        r = (r << 1n) | ((x >> BigInt(i)) & 1n);
        if (r >= c) r = r - c;
    }
    return r;
}
(function () {
    var rng = T.makeRng();
    for (var i = 0; i < exp.rngRaw.length; i++) {
        var got = rng();
        var want = BigInt("0x" + exp.rngRaw[i]);
        if (got !== want) failures.push("rng raw " + i + ": got " + got + " want " + exp.rngRaw[i]);
    }
})();
(function () {
    var rng = T.makeRng();
    var seen = {};
    for (var i = 0; i < exp.rng.positions.length; i++) {
        var p;
        for (;;) {
            var raw = rng();
            p = Number(bigintMod(raw, BigInt(exp.rng.capacity)));
            if (!(p in seen)) { seen[p] = true; break; }
        }
        if (p !== exp.rng.positions[i]) failures.push("rng position " + i + ": got " + p + " want " + exp.rng.positions[i]);
    }
})();

// payload / QR string helpers
exp.payloads.forEach(function (p) {
    if (T.makePayload(p.eventId, p.key) !== p.pair) failures.push("makePayload mismatch for " + p.eventId);
    var parsed = T.parsePayload(p.pair);
    if (!parsed || parsed.eventId !== p.eventId || parsed.accessKey !== p.key) {
        failures.push("parsePayload mismatch for " + p.eventId);
    }
    if (T.qrPayload(p.eventId, p.key) !== p.qr) failures.push("qrPayload mismatch for " + p.eventId);
    var qparsed = T.parseQrPayload(p.qr);
    if (!qparsed || qparsed.eventId !== p.eventId || qparsed.accessKey !== p.key) {
        failures.push("parseQrPayload mismatch for " + p.eventId);
    }
});
// negative QR / payload cases
["", "gkp:", "https://example.com/x", "gkp:event_x"].forEach(function (s) {
    if (T.parseQrPayload(s) !== null) failures.push("parseQrPayload accepted bad input: " + s);
});

// container build/parse vs Python mirror
exp.containers.forEach(function (c) {
    var built = T.buildContainer(c.payload);
    var hex = "";
    for (var i = 0; i < built.length; i++) hex += ("0" + built[i].toString(16)).slice(-2);
    if (hex !== c.hex) failures.push("buildContainer mismatch for " + c.payload);
    var parsed = T.parseContainer(Uint8Array.from(c.bytes));
    if (parsed !== c.payload) failures.push("parseContainer mismatch for " + c.payload);
});
exp.badContainers.forEach(function (hex) {
    var bytes = Uint8Array.from(hex.match(/.{2}/g).map(function (h) { return parseInt(h, 16); }));
    if (T.parseContainer(bytes) !== null) failures.push("parseContainer accepted corrupted bytes: " + hex);
});

// door classifyInvite vs Python oracle (magic-byte sniffing)
exp.classify.forEach(function (c) {
    var got = T.classifyInvite(Uint8Array.from(c.bytes));
    if (got !== c.hex) failures.push("classifyInvite mismatch: got " + got + " want " + c.hex);
});

// inviteRejectReason vs Python oracle (unknown kinds fall back to "other")
Object.keys(exp.rejectReasons).forEach(function (kind) {
    var got = T.inviteRejectReason(kind);
    if (got !== exp.rejectReasons[kind]) failures.push("inviteRejectReason mismatch for " + kind);
});

// QR fallback round-trip: vendored encoder -> RGBA pixel buffer -> vendored jsQR.
// This is exactly what web/door_qr.js does in the browser, minus the canvas.
function qrPixelBuffer(text) {
    var qr = qrcode(0, "M");
    qr.addData(text);
    qr.make();
    var n = qr.getModuleCount();
    var scale = 6, margin = 4;
    var size = (n + margin * 2) * scale;
    var data = new Uint8Array(size * size * 4);
    for (var y = 0; y < size; y++) {
        for (var x = 0; x < size; x++) {
            var mRow = Math.floor(y / scale) - margin;
            var mCol = Math.floor(x / scale) - margin;
            var dark = mRow >= 0 && mRow < n && mCol >= 0 && mCol < n && qr.isDark(mRow, mCol);
            var i = (y * size + x) * 4;
            var v = dark ? 0 : 255;
            data[i] = v; data[i + 1] = v; data[i + 2] = v; data[i + 3] = 255;
        }
    }
    return { data: data, width: size, height: size };
}
exp.qrRoundTrip.forEach(function (text) {
    var c = qrPixelBuffer(text);
    var res = self.jsQR(c.data, c.width, c.height, { inversionAttempts: "attemptBoth" });
    if (!res || res.data !== text) {
        failures.push("QR round-trip failed for " + text + " (got " + (res ? res.data : "null") + ")");
    }
});
// Decoding pure noise must not crash and must yield null (guarded in door_qr.js).
(function () {
    var noise = new Uint8Array(96 * 96 * 4);
    for (var i = 0; i < noise.length; i++) noise[i] = (i * 7 + 3) & 255;
    var res = null;
    try { res = self.jsQR(noise, 96, 96); } catch (e) {}
    if (res !== null) failures.push("jsQR decoded noise (expected null)");
})();

if (failures.length) {
    console.log("JXA-FAIL:\n" + failures.join("\n"));
} else {
    console.log("JXA-OK: web/stego.js internals match the Python oracle");
}
