# Copyright (c) 2026 gatekeyp contributors
"""Concurrency regression test for DatabaseHandler shared-connection access.

The API layer (FastAPI threadpool) calls into one shared DatabaseHandler from
several worker threads at once — e.g. the organizer RSVP tab fires its list +
settings requests via Promise.all. Concurrent multi-statement operations were
observed to fail with "sqlite3.ProgrammingError: Recursive use of cursors not
allowed" and "sqlite3.InterfaceError: bad parameter or other API misuse";
the handler now serializes method calls behind a re-entrant lock. This test
pins that behavior with real threads hammering the same handler.
"""

from __future__ import annotations

import threading

from tests.helpers import TEST_ORGANIZER_KEY


class _Collector(threading.Thread):
    """Run calls in a loop, collecting any exception instead of raising."""

    def __init__(self, calls: object, rounds: int) -> None:
        super().__init__()
        self._calls = calls  # type: ignore[assignment]
        self._rounds = rounds
        self.errors: list[str] = []

    def run(self) -> None:
        for _ in range(self._rounds):
            try:
                self._calls()
            except Exception as err:  # noqa: BLE001 - the point is to observe
                self.errors.append(f"{type(err).__name__}: {err}")


def test_concurrent_threads_share_handler_without_misuse() -> None:
    import src.db.database_handler as mod

    db = mod.DatabaseHandler(db_path=":memory:", organizer_key=TEST_ORGANIZER_KEY)
    db.add_event("probe_event", "Probe", "", "probe")
    for i in range(20):
        db.add_rsvp(f"rsvp-{i}", "probe_event", f"guest-{i}", None, None)

    def rsvp_pair() -> None:
        # The exact pair the organizer RSVP tab fires via Promise.all
        db.list_rsvps("probe_event")
        assert db.get_event("probe_event") is not None

    threads = [_Collector(rsvp_pair, 40) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    errors = [e for t in threads for e in t.errors]
    # Concurrent threads may take turns but must never corrupt each other.
    snowed_out = [e for e in errors if "ProgrammingError" in e or "InterfaceError" in e]
    assert not snowed_out, snowed_out[:5]
