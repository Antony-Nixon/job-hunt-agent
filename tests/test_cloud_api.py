import sqlite3
from pathlib import Path

from job_hunt_agent.cloud_api import CloudService, TenantContext


def test_cloud_service_scopes_jobs_and_records_discovery(tmp_path):
    db = sqlite3.connect(tmp_path / "cloud.db")
    db.row_factory = sqlite3.Row
    db.executescript(Path("08_DEPLOYMENT/migrations/001_cloud_foundation.sql").read_text())
    db.executemany("INSERT INTO tenants VALUES (?, ?, 'active')", [("t1", "now"), ("t2", "now")])
    db.commit()
    service = CloudService(db, TenantContext("t1", "u1"))
    service.create_job({"job_id":"j1","title":"Automation Engineer","company_name":"Example","source_name":"fixture","source_url":"https://example.com/j1","description":"Python","raw_content_hash":"abc"})
    assert [row["job_id"] for row in service.jobs()] == ["j1"]
    assert service.timeline("job", "j1")[0]["event_type"] == "discovered"
    assert CloudService(db, TenantContext("t2", "u2")).jobs() == []
