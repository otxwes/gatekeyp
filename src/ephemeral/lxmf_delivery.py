# Copyright (c) 2026 gatekeyp contributors

"""Optional LXMF (Reticulum) delivery of event organizer keys.

Prototype for mesh key distribution. The organizer's browser posts the
organizer key it was just shown plus the attendee's LXMF address (a
32-character destination hash, as displayed by Sideband or Nomad Network)
to ``POST /api/lite/events/{event_id}/deliver``. The route verifies the key
against the event's stored HMAC first, so the endpoint can only relay a key
that was actually displayed for that event.

Design notes:

- Delivery is end-to-end encrypted by Reticulum; relays only ever see
  ciphertext, and gatekeyp never logs or stores the key.
- The feature is opt-in: ``GATEKEYP_LXMF_ENABLED=1`` plus the ``mesh``
  extra (``uv sync --extra mesh``). RNS/LXMF are imported lazily so a
  default install keeps working without them.
- Messages are handed to LXMF's router, which retries delivery from its
  background job thread; "queued" means "handed to the mesh", not
  "delivered yet".
- ``warmup()`` must run in the server's main thread: ``LXMRouter`` installs
  signal handlers in its constructor, which only works there. uvicorn then
  installs its own handlers when it starts, overriding ours.
"""

from __future__ import annotations

import os
import re
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

LXMF_DEST_RE = re.compile(r"^[0-9a-f]{32}$")

_DEFAULT_STATE_DIR = Path("instance/lxmf")
_ENABLED_FLAGS = {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def _mesh_deps_available() -> bool:
    """Import RNS/LXMF once, caching whether the optional deps are present."""
    try:
        import LXMF  # noqa: F401
        import RNS  # noqa: F401
    except Exception:  # noqa: BLE001 - any import failure means "not installed"
        return False
    return True


def compose_key_message(*, title: str, organizer_key: str, share_url: str, expires_at: str) -> str:
    """Compose the plaintext body sent inside the encrypted LXMF payload."""
    return (
        f"{title}\n\n"
        f"Organizer key: {organizer_key}\n"
        f"Share link: {share_url}\n\n"
        f"This page wipes itself {expires_at}."
    )


class LXMFKeyDeliverer:
    """Relays event organizer keys to attendee LXMF addresses over Reticulum.

    Bound to env config at construction (enabled flag, state directory and
    an optional RNS config directory). One instance per process — RNS allows
    a single stack per process anyway. Sends are serialized by an internal
    lock because RNS/LXMF are not thread-safe.
    """

    _PATH_WAIT_SECONDS = 7.0  # mirrors LXMF's PATH_REQUEST_WAIT

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        state_dir: str | os.PathLike[str] | None = None,
        rns_config: str | None = None,
    ) -> None:
        flag = os.environ.get("GATEKEYP_LXMF_ENABLED", "").strip().lower()
        self.enabled = enabled if enabled is not None else flag in _ENABLED_FLAGS
        self.state_dir = Path(
            state_dir or os.environ.get("GATEKEYP_LXMF_STATE") or _DEFAULT_STATE_DIR
        )
        self.rns_config = rns_config or os.environ.get("GATEKEYP_LXMF_RNS_CONFIG") or None
        self._lock = threading.Lock()
        self._router: Any = None  # LXMF.LXMRouter, built lazily by warmup/send
        self._source: Any = None  # our own lxmf.delivery destination
        self._identity_file = self.state_dir / "identity"
        self._rns_started = False
        self._startup_error: str | None = None

    def available(self) -> bool:
        """True when opted in, deps import and startup has not failed."""
        if not self.enabled or not _mesh_deps_available():
            return False
        return self._startup_error is None

    def warmup(self) -> bool:
        """Build the RNS + LXMF stack ahead of the first send.

        Must be called from the main thread (LXMRouter installs signal
        handlers). Returns True when the stack is ready to send.
        """
        if not self.enabled or not _mesh_deps_available():
            return False
        try:
            self._ensure_router()
        except Exception as err:  # noqa: BLE001 - surface any startup failure
            self._startup_error = str(err)
        return self._startup_error is None

    def send_organizer_key(
        self, destination: str, *, title: str, organizer_key: str, share_url: str, expires_at: str
    ) -> dict[str, str]:
        """Queue the key for an LXMF destination hash (32 hex chars).

        Returns ``{"status": "queued"}`` when handed to the mesh, or
        ``{"status": "failed", "detail": ...}`` when delivery cannot start
        yet. Never raises: the caller maps the status to an HTTP code.
        """
        if not self.enabled or not _mesh_deps_available():
            return {"status": "failed", "detail": "Mesh delivery is not enabled"}
        address = destination.strip().lower()
        if not LXMF_DEST_RE.match(address):
            return {"status": "failed", "detail": "LXMF address must be 32 hex characters"}
        with self._lock:
            try:
                router = self._ensure_router()
                import LXMF
                import RNS

                remote_identity = self._wait_for_identity(bytes.fromhex(address))
                if remote_identity is None:
                    return {
                        "status": "failed",
                        "detail": (
                            "No path to that LXMF address yet — the attendee's "
                            "Sideband/Nomad Network app must be running (and reachable) "
                            "before a key can be delivered"
                        ),
                    }
                out = RNS.Destination(
                    remote_identity,
                    RNS.Destination.OUT,
                    RNS.Destination.SINGLE,
                    "lxmf",
                    "delivery",
                )
                message = LXMF.LXMessage(
                    destination=out,
                    source=self._source,
                    content=compose_key_message(
                        title=title,
                        organizer_key=organizer_key,
                        share_url=share_url,
                        expires_at=expires_at,
                    ),
                    title=title,
                    desired_method=LXMF.LXMessage.DIRECT,
                )
                router.handle_outbound(message)
            except Exception as err:  # noqa: BLE001 - never propagate to HTTP
                return {"status": "failed", "detail": f"Mesh send failed: {err}"}
        return {
            "status": "queued",
            "detail": "Handed to the mesh — it arrives when the attendee is reachable",
        }

    def _ensure_router(self) -> Any:
        """Start RNS, load or create the sender identity and build the router."""
        if self._router is not None:
            return self._router
        import LXMF
        import RNS

        self.state_dir.mkdir(parents=True, exist_ok=True)
        if not self._rns_started:
            # One RNS instance per process; starting a second one is an error.
            RNS.Reticulum(configdir=self.rns_config)
            self._rns_started = True
        if self._identity_file.exists():
            identity = RNS.Identity.from_file(str(self._identity_file))
        else:
            identity = RNS.Identity()
            identity.to_file(str(self._identity_file))
        router = LXMF.LXMRouter(identity=identity, storagepath=str(self.state_dir))
        # Registering our own delivery identity gives the sender a stable
        # source destination (and a reply address for attendees, unused for
        # now). It is the only delivery identity the router accepts.
        self._source = router.register_delivery_identity(identity, display_name="GateKeyP")
        self._router = router
        return router

    def _wait_for_identity(self, dest_hash: bytes, wait: float | None = None) -> Any:
        """Ask Reticulum for a path and poll until the identity can be recalled."""
        import RNS

        deadline = time.monotonic() + (self._PATH_WAIT_SECONDS if wait is None else wait)
        RNS.Transport.request_path(dest_hash)
        while time.monotonic() < deadline:
            identity = RNS.Identity.recall(dest_hash)
            if identity is not None:
                return identity
            time.sleep(0.3)
        return None


@lru_cache(maxsize=1)
def get_deliverer() -> LXMFKeyDeliverer:
    """Process-wide deliverer bound to env config (created on first use)."""
    return LXMFKeyDeliverer()
