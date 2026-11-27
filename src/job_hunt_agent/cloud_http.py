"""Dependency-free JSON API contract for the hosted Worker boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlsplit

from .cloud_api import CloudService, TenantContext
from .cloud_auth import SessionStore


@dataclass(frozen=True)
class ApiResponse:
    status: int
    body: dict


class CloudApi:
    """Small framework-neutral router used by a future Cloudflare Worker."""

    def __init__(self, connection):
        self.connection = connection
        self.sessions = SessionStore(connection)

    def _identity(self, headers: dict[str, str]):
        authorization = headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        return self.sessions.resolve(token)

    def handle(self, method: str, path: str, headers: dict[str, str], body: bytes = b"") -> ApiResponse:
        identity = self._identity(headers)
        if not identity:
            return ApiResponse(401, {"error": "authentication required"})
        service = CloudService(self.connection, TenantContext(identity.tenant_id, identity.user_id))
        route = urlsplit(path).path.rstrip("/") or "/"
        if method == "GET" and route == "/api/jobs":
            return ApiResponse(200, {"jobs": [dict(row) for row in service.jobs()]})
        if method == "POST" and route == "/api/jobs":
            try:
                payload = json.loads(body.decode("utf-8"))
                service.create_job(payload)
            except (ValueError, json.JSONDecodeError):
                return ApiResponse(400, {"error": "invalid job payload"})
            return ApiResponse(201, {"job_id": payload["job_id"], "created": True})
        prefix = "/api/jobs/"
        if method == "GET" and route.startswith(prefix) and route.endswith("/timeline"):
            job_id = route[len(prefix):-len("/timeline")].strip("/")
            rows = service.timeline("job", job_id)
            return ApiResponse(200, {"job_id": job_id, "events": [dict(row) for row in rows]})
        if method == "POST" and route == "/api/session/revoke":
            authorization = headers.get("authorization", "")
            _, _, token = authorization.partition(" ")
            self.sessions.revoke(token)
            return ApiResponse(200, {"revoked": True})
        return ApiResponse(404, {"error": "not found"})
