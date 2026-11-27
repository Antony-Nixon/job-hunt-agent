import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from job_hunt_agent.cloud_auth import SessionStore


def test_sessions_are_hashed_tenant_bound_expiring_and_revocable(tmp_path):
    db = sqlite3.connect(tmp_path / "cloud.db")
    db.row_factory = sqlite3.Row
    db.executescript(Path("08_DEPLOYMENT/migrations/001_cloud_foundation.sql").read_text())
    db.execute("INSERT INTO tenants VALUES ('t1', 'now', 'active')")
    db.execute("INSERT INTO users VALUES ('u1', 't1', 'a@example.com', 'now')")
    db.commit()
    store = SessionStore(db)
    token = store.issue("u1", "t1", timedelta(hours=1))
    assert store.resolve(token).tenant_id == "t1"
    assert db.execute("SELECT token_hash FROM sessions").fetchone()[0] != token
    assert store.resolve(token, datetime.now(timezone.utc) + timedelta(hours=2)) is None
    token2 = store.issue("u1", "t1")
    assert store.revoke(token2) is True
    assert store.resolve(token2) is None


def test_unknown_user_cannot_receive_session(tmp_path):
    db = sqlite3.connect(tmp_path / "cloud.db")
    db.executescript(Path("08_DEPLOYMENT/migrations/001_cloud_foundation.sql").read_text())
    store = SessionStore(db)
    try:
        store.issue("missing", "t1")
        raise AssertionError("unknown users must be rejected")
    except ValueError:
        pass
