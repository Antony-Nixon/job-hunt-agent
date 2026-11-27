from datetime import datetime, timedelta, timezone

import pytest

from job_hunt_agent.retention import RetentionPolicy, expires_at, should_expire


def test_raw_source_expires_but_verified_facts_do_not():
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert should_expire("raw_source", created, created + timedelta(days=31))
    assert expires_at("verified_fact", created) is None
    assert not should_expire("verified_fact", created, created + timedelta(days=3650))


def test_retention_rejects_unknown_kind_and_negative_duration():
    with pytest.raises(ValueError, match="unknown retention"):
        expires_at("password", datetime.now(timezone.utc))
    with pytest.raises(ValueError, match="negative"):
        RetentionPolicy(raw_source_days=-1).validate()

