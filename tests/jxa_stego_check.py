# Copyright (c) 2026 gatekeyp contributors
"""Cross-check the shipped ``web/stego.js`` against the Python oracle via JXA.

Node is unavailable in this environment, so the browser codec is validated by
parsing it and running its pure functions inside the macOS JavaScriptCore
engine (``osascript -l JavaScript``), comparing against golden values computed
by ``tests/stego_ref.py``. The browser E2E pass covers the remaining
embed/PNG/decompress paths. Requires macOS (JXA) — skipped otherwise.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from tests import stego_ref

_HERE = Path(__file__).resolve().parent
_HARNESS = _HERE / "jxa_stego_check.js"
_STEGO_JS = _HERE.parent / "web" / "stego.js"
_EXPECTED_JSON = _HERE / ".jxa_expected.json"
_SCRIPT_PATH = _HERE / ".jxa_script.js"


def _rng_positions(capacity: int, count: int) -> list[int]:
    next_pos = stego_ref.make_position_iter(capacity)
    return [next_pos() for _ in range(count)]


def _build_expected() -> dict:
    payloads = [
        ("event_ab12cd34", "local:0123456789abcdef"),
        ("event_" + "9" * 30, "local:" + "c0ffee" * 10),
        ("event_b3c9", "local:" + "ab" * 32),
    ]
    containers = []
    bad_containers = []
    rng_raw = stego_ref.make_rng()
    for event_id, key in payloads:
        pair = stego_ref.make_payload(event_id, key)
        container = stego_ref.build_container(pair)
        containers.append({"payload": pair, "hex": container.hex(), "bytes": list(container)})
        flipped = bytearray(container)
        flipped[len(flipped) // 2] ^= 0xFF
        bad_containers.append(bytes(flipped).hex())
    return {
        "crc32": [
            {"bytes": list(b"GKP1"), "value": stego_ref.crc32(b"GKP1"), "hex": "GKP1"},
            {"bytes": [], "value": stego_ref.crc32(b""), "hex": "empty"},
            {
                "bytes": list(b"event_id\nlocal:abc"),
                "value": stego_ref.crc32(b"event_id\nlocal:abc"),
                "hex": "payload",
            },
            {"bytes": [0] * 512, "value": stego_ref.crc32(b"\x00" * 512), "hex": "zeros512"},
        ],
        "rng": {
            "capacity": 1000,
            "positions": _rng_positions(1000, 40),
        },
        "rngRaw": [f"{rng_raw():016x}" for _ in range(40)],
        "payloads": [
            {
                "eventId": event_id,
                "key": key,
                "pair": stego_ref.make_payload(event_id, key),
                "qr": stego_ref.make_qr_payload(event_id, key),
            }
            for event_id, key in payloads
        ],
        "containers": containers,
        "badContainers": bad_containers,
    }


def main() -> int:
    if shutil.which("osascript") is None:
        sys.stderr.write("osascript (JXA) not available — skipping JS cross-check\n")
        return 0
    expected = _build_expected()
    # Hook the shipped codec: expose its internals as a __test member of the
    # returned module so the harness can pin them against the Python oracle.
    target = "    return { embed, extract, makePayload, parsePayload, qrPayload, parseQrPayload };"
    hooked = (
        "    return { embed, extract, makePayload, parsePayload, qrPayload, parseQrPayload, "
        "__test: { crc32, makeRng, makePositionIter, makePayload, parsePayload, qrPayload, "
        "parseQrPayload, buildContainer, parseContainer } };"
    )
    module_src = _STEGO_JS.read_text(encoding="utf-8")
    if target not in module_src:
        sys.stderr.write("could not hook web/stego.js (return line changed?) — check the codec\n")
        return 1
    module_src = module_src.replace(target, hooked)
    harness = _HARNESS.read_text(encoding="utf-8")
    script = harness.replace("__STEGO_MODULE_SOURCE__", module_src).replace(
        "__EXPECTED_JSON__", str(_EXPECTED_JSON)
    )
    _EXPECTED_JSON.write_text(json.dumps(expected), encoding="utf-8")
    _SCRIPT_PATH.write_text(script, encoding="utf-8")
    osascript = shutil.which("osascript")
    try:
        proc = subprocess.run(  # noqa: S603 - fixed command list, no shell
            [osascript, "-l", "JavaScript", str(_SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    finally:
        _EXPECTED_JSON.unlink(missing_ok=True)
        _SCRIPT_PATH.unlink(missing_ok=True)
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    combined = proc.stdout + proc.stderr
    if proc.returncode != 0 or "JXA-OK" not in combined:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
