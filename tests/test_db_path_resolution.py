"""DatabaseHandler DB-path resolution: explicit arg > GATEKEYP_DB_PATH > keys.db."""

import os
from pathlib import Path

from src.db.database_handler import DatabaseHandler


def test_db_path_env_override(monkeypatch, tmp_path):
    override = tmp_path / "e2e-keys.db"
    monkeypatch.setenv("GATEKEYP_DB_PATH", str(override))
    handler = DatabaseHandler()
    try:
        assert os.fspath(override) == handler.cursor.execute("PRAGMA database_list").fetchone()[2]
    finally:
        handler.connection.close()


def test_db_path_explicit_argument_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("GATEKEYP_DB_PATH", str(tmp_path / "ignored.db"))
    explicit = tmp_path / "explicit.db"
    handler = DatabaseHandler(db_path=str(explicit))
    try:
        assert os.fspath(explicit) == handler.cursor.execute("PRAGMA database_list").fetchone()[2]
    finally:
        handler.connection.close()


def test_db_path_default_without_env(monkeypatch, tmp_path):
    monkeypatch.delenv("GATEKEYP_DB_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    handler = DatabaseHandler()
    try:
        resolved = handler.cursor.execute("PRAGMA database_list").fetchone()[2]
        assert Path(resolved).name == "keys.db"
    finally:
        handler.connection.close()
