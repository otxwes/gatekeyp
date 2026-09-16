# Copyright (c) 2026 gatekeyp contributors

"""Loopback demo: deliver an event organizer key over LXMF, end to end.

Spawns two independent Reticulum instances in separate processes, connected
through a local TCP interface pair:

- the attendee receiver registers an LXMF delivery identity, announces its
  address (32 hex chars) and decrypts whatever arrives;
- the gatekeyp sender waits for the path, then relays a organizer key with
  ``LXMF.DIRECT`` exactly as ``LXMFKeyDeliverer`` does inside
  ``POST /api/lite/events/{id}/deliver``;
- the parent asserts the receiver decrypted the key text.

Requires the optional ``mesh`` extra:

    uv sync --extra mesh
    uv run python scripts/lxmf_loopback.py
"""

from __future__ import annotations

import multiprocessing
import shutil
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.ephemeral.lxmf_delivery import compose_key_message

WORK_DIR = REPO_ROOT / "tmp" / "lxmf_demo"
PORT = 4965
ORGANIZER_KEY = "demo-organizer-key-goes-to-the-attendee-over-mesh"
KEY_TEXT = compose_key_message(
    title="Mesh Night",
    organizer_key=ORGANIZER_KEY,
    share_url="https://demo.invalid/i/demoevent",
    expires_at="Sep 16, 2026 08:00 UTC",
)
ADDRESS_FILE = WORK_DIR / "attendee_address"


def _rns_config(cfg_dir: Path, *, server: bool, port: int) -> None:
    """Write a minimal RNS config: one TCP interface, no instance sharing."""
    cfg_dir.mkdir(parents=True, exist_ok=True)
    if server:
        iface = (
            "  [[tcp]]\n"
            "    type = TCPServerInterface\n"
            "    interface_enabled = yes\n"
            "    listen_ip = 127.0.0.1\n"
            f"    port = {port}\n"
        )
    else:
        iface = (
            "  [[tcp]]\n"
            "    type = TCPClientInterface\n"
            "    interface_enabled = yes\n"
            "    target_host = 127.0.0.1\n"
            f"    target_port = {port}\n"
        )
    (cfg_dir / "config").write_text(
        "[reticulum]\nenable_transport = False\nshare_instance = No\n\n[interfaces]\n" + iface
    )


def _attendee(state: dict, port: int) -> None:  # pragma: no cover - manual demo
    """Receiver process: register, announce, decrypt, report back."""
    import LXMF
    import RNS

    _rns_config(WORK_DIR / "attendee_cfg", server=True, port=port)
    RNS.Reticulum(configdir=str(WORK_DIR / "attendee_cfg"))
    identity = RNS.Identity()
    router = LXMF.LXMRouter(identity=identity, storagepath=str(WORK_DIR / "attendee_store"))
    delivery = router.register_delivery_identity(identity, display_name="Attendee")
    received: list = []
    router.register_delivery_callback(received.append)
    ADDRESS_FILE.write_text(RNS.hexrep(delivery.hash, delimit=False))
    deadline = time.monotonic() + 75.0
    while time.monotonic() < deadline:
        router.announce(delivery.hash)  # keep the address visible on the wire
        time.sleep(2.0)

    if received:
        state["content"] = received[0].content_as_string()


def _gatekeyp(address_hex: str, state: dict, port: int) -> None:  # pragma: no cover
    """Sender process: mirror the deliverer's send path for one message."""
    import LXMF
    import RNS

    _rns_config(WORK_DIR / "server_cfg", server=False, port=port)
    RNS.Reticulum(configdir=str(WORK_DIR / "server_cfg"))
    identity = RNS.Identity()
    router = LXMF.LXMRouter(identity=identity, storagepath=str(WORK_DIR / "server_store"))
    source = router.register_delivery_identity(identity, display_name="GateKeyP")
    dest_hash = bytes.fromhex(address_hex)
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline and not RNS.Transport.has_path(dest_hash):
        time.sleep(0.5)
    remote = RNS.Identity.recall(dest_hash)
    if remote is None:
        state["error"] = "no identity recalled for the attendee address"
        return
    destination = RNS.Destination(
        remote, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery"
    )
    message = LXMF.LXMessage(
        destination=destination,
        source=source,
        content=KEY_TEXT,
        title="Event organizer key",
        desired_method=LXMF.LXMessage.DIRECT,
    )
    router.handle_outbound(message)
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        if message.state in (
            LXMF.LXMessage.DELIVERED,
            LXMF.LXMessage.FAILED,
            LXMF.LXMessage.CANCELLED,
            LXMF.LXMessage.REJECTED,
        ):
            state["sent_state"] = message.state
            return
        time.sleep(0.5)


def main() -> int:
    """Run both halves of the loopback and report the verdict."""
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    WORK_DIR.mkdir(parents=True)
    with multiprocessing.Manager() as manager:
        state = manager.dict()
        attendee = multiprocessing.Process(target=_attendee, args=(state, PORT))
        attendee.start()
        for _ in range(120):
            if ADDRESS_FILE.exists():
                break
            time.sleep(0.25)
        if not ADDRESS_FILE.exists():
            print("FAIL - the attendee process never announced an address")
            attendee.terminate()
            return 1
        address_hex = ADDRESS_FILE.read_text().strip()
        print(f"attendee LXMF address: {address_hex}")
        sender = multiprocessing.Process(target=_gatekeyp, args=(address_hex, state, PORT))
        sender.start()
        sender.join(90.0)
        attendee.join(90.0)
        if state.get("error"):
            print(f"FAIL - {state['error']}")
            return 1
        content = state.get("content", "")
        if ORGANIZER_KEY not in content:
            print("FAIL - the attendee never decrypted the organizer key")
            return 1
        print(f"sent state: {state.get('sent_state')}")
        print("PASS - organizer key delivered and decrypted over LXMF")
        print(f"received: {content!r}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
