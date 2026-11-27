"""Read-only Gmail job-alert ingestion for one local profile."""

import base64
import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urlparse

from .gmail_local import GMAIL_READONLY_SCOPE, SERVICE_NAME, credential_name
from .schemas import JobRecord
from .sources import _clean_html


JOB_URL = re.compile(r"https?://[^\s<>\"']+")
JOB_SUBJECT = re.compile(
    r"\b(job(?:s)?|hiring|career(?:s)?|vacanc(?:y|ies)|opportunit(?:y|ies)|role(?:s)?)\b",
    re.IGNORECASE,
)
NON_JOB_SUBJECT = re.compile(
    r"(?:job alert|alert).*\b(?:created|confirmed|confirmation)\b|"
    r"\b(?:verify|verification|security alert|profile photo|people viewed your profile|you may know)\b",
    re.IGNORECASE,
)
JOB_LINK_HINT = re.compile(r"/(?:jobs?|careers?|apply|vacanc(?:y|ies)|job-search|jobseeker)/|/comm/jobs/|job|viewjob", re.IGNORECASE)


def _alert_source(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "indeed." in host:
        return "gmail-alert:indeed"
    if "naukri.com" in host:
        return "gmail-alert:naukri"
    if "greenhouse.io" in host:
        return "gmail-alert:greenhouse"
    if "lever.co" in host:
        return "gmail-alert:lever"
    if "ashbyhq.com" in host:
        return "gmail-alert:ashby"
    return "gmail-alert"


def _header(message: dict, name: str) -> str:
    for item in message.get("payload", {}).get("headers", []):
        if item.get("name", "").lower() == name.lower():
            return item.get("value", "")
    return ""


def _body(part: dict) -> str:
    data = part.get("body", {}).get("data")
    if data:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")
    return "\n".join(_body(child) for child in part.get("parts", []))


def _is_job_alert(subject: str, body: str) -> bool:
    """Reject unrelated account/network emails from broad mailbox scans."""
    if NON_JOB_SUBJECT.search(subject) or not JOB_SUBJECT.search(subject):
        return False
    return bool(JOB_LINK_HINT.search(body))


def message_to_job(message: dict) -> JobRecord | None:
    subject = _header(message, "Subject")
    raw_body = _body(message.get("payload", {}))
    body = _clean_html(raw_body)
    if not _is_job_alert(subject, raw_body):
        return None
    urls = [url.rstrip(".,)") for url in JOB_URL.findall(raw_body)]
    urls.sort(key=lambda url: (not bool(JOB_LINK_HINT.search(url)), len(url)))
    if not urls or not body:
        return None
    message_id = message.get("id", "unknown")
    timestamp = datetime.fromtimestamp(int(message.get("internalDate", "0")) / 1000, tz=timezone.utc) if message.get("internalDate") else datetime.now(timezone.utc)
    source_url = urls[0]
    return JobRecord(f"gmail:{message_id}", subject or "Job alert", "Alert email", _alert_source(source_url), source_url, timestamp, body)


def _service(profile_id: str):
    try:
        import keyring
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as error:
        raise RuntimeError('Install Gmail support with: python -m pip install -e ".[gmail]"') from error
    raw = keyring.get_password(SERVICE_NAME, credential_name(profile_id))
    if not raw:
        raise RuntimeError(f"Gmail is not authorized for profile: {profile_id}")
    credentials = Credentials.from_authorized_user_info({"token": None, **__import__("json").loads(raw)}, [GMAIL_READONLY_SCOPE])
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        keyring.set_password(SERVICE_NAME, credential_name(profile_id), credentials.to_json())
    return build("gmail", "v1", credentials=credentials)


def scan_alerts(profile_id: str, repository, query: str, max_messages: int = 50) -> tuple[int, int]:
    service = _service(profile_id)
    response = service.users().messages().list(userId="me", q=query, maxResults=max_messages).execute()
    messages = response.get("messages", [])
    imported = 0
    for summary in messages:
        message = service.users().messages().get(userId="me", id=summary["id"], format="full").execute()
        job = message_to_job(message)
        if job and repository.save_job(job):
            imported += 1
    repository.event("gmail_alert_scan", profile_id, fetched=len(messages), imported=imported, query=query)
    return len(messages), imported
