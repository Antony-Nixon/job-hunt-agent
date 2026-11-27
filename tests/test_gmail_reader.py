import base64

from job_hunt_agent.gmail_reader import message_to_job


def test_alert_message_becomes_provenance_tracked_job():
    body = base64.urlsafe_b64encode(b"Apply here: https://careers.example.com/jobs/1").decode()
    message = {"id": "m1", "internalDate": "1763164800000", "payload": {"headers": [{"name": "Subject", "value": "Automation Engineer job alert"}], "body": {"data": body}}}
    job = message_to_job(message)
    assert job is not None
    assert job.job_id == "gmail:m1"
    assert job.source_name == "gmail-alert"


def test_alert_without_job_link_is_ignored():
    message = {"id": "m2", "payload": {"headers": [], "body": {"data": "SGVsbG8="}}}
    assert message_to_job(message) is None


def test_unrelated_linkedin_security_email_is_ignored():
    body = base64.urlsafe_b64encode(b"Confirm your account: https://www.linkedin.com/comm/psettings/email/confirm").decode()
    message = {"id": "m3", "payload": {"headers": [{"name": "Subject", "value": "Verify your email address"}], "body": {"data": body}}}
    assert message_to_job(message) is None


def test_job_alert_prefers_job_link_over_tracking_link():
    body = base64.urlsafe_b64encode(
        b"View job: https://example.com/unsubscribe?x=1 https://example.com/careers/jobs/42"
    ).decode()
    message = {"id": "m4", "payload": {"headers": [{"name": "Subject", "value": "Jobs matching your profile"}], "body": {"data": body}}}
    job = message_to_job(message)
    assert job is not None
    assert job.source_url == "https://example.com/careers/jobs/42"


def test_alert_confirmation_is_ignored():
    body = base64.urlsafe_b64encode(b"View job: https://www.linkedin.com/comm/jobs/view/42").decode()
    message = {"id": "m5", "payload": {"headers": [{"name": "Subject", "value": "Your job alert for Python Automation has been created"}], "body": {"data": body}}}
    assert message_to_job(message) is None


def test_alert_attributes_supported_source_from_public_url():
    body = base64.urlsafe_b64encode(b"View job: https://www.indeed.com/viewjob?jk=abc123").decode()
    message = {"id": "m6", "payload": {"headers": [{"name": "Subject", "value": "Automation Engineer jobs"}], "body": {"data": body}}}
    job = message_to_job(message)
    assert job is not None
    assert job.source_name == "gmail-alert:indeed"

