"""Authentication, project authorization, rate limiting, and security audit helpers."""

import hashlib
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Request
from jwt import PyJWKClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from assureai_api.config import Settings
from assureai_api.models import (
    AuditEvent,
    Project,
    ProjectMembership,
    ProjectRole,
    User,
)

_PROJECT_PATH = re.compile(r"^/api/v1/projects/([^/]+)(?:/|$)")


class AuthenticationError(PermissionError):
    pass


class AuthorizationError(PermissionError):
    pass


class RateLimitExceededError(PermissionError):
    pass


@dataclass(frozen=True)
class Identity:
    subject: str
    email: str | None
    display_name: str | None


def create_development_token(settings: Settings, identity: Identity) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": identity.subject,
            "email": identity.email,
            "name": identity.display_name,
            "iss": "assureai-development",
            "aud": "assureai",
            "iat": now,
            "exp": now + timedelta(seconds=settings.session_ttl_seconds),
            "jti": str(uuid.uuid4()),
        },
        settings.session_secret.get_secret_value(),
        algorithm="HS256",
    )


def _decode_development_token(settings: Settings, token: str) -> dict[str, Any]:
    return dict(
        jwt.decode(
            token,
            settings.session_secret.get_secret_value(),
            algorithms=["HS256"],
            issuer="assureai-development",
            audience="assureai",
        )
    )


def _decode_oidc_token(settings: Settings, token: str) -> dict[str, Any]:
    assert settings.oidc_jwks_url is not None
    assert settings.oidc_audience is not None
    assert settings.oidc_issuer is not None
    signing_key = PyJWKClient(settings.oidc_jwks_url).get_signing_key_from_jwt(token)
    return dict(
        jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    )


def authenticate_request(request: Request, settings: Settings) -> Identity:
    token = request.cookies.get(settings.session_cookie_name)
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    if not token:
        raise AuthenticationError("Authentication is required.")
    try:
        claims = (
            _decode_oidc_token(settings, token)
            if settings.auth_mode == "oidc"
            else _decode_development_token(settings, token)
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError("The authentication session is invalid or expired.") from exc
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise AuthenticationError("The identity token is missing a subject.")
    email = claims.get("email")
    name = claims.get("name")
    return Identity(
        subject=subject,
        email=email if isinstance(email, str) else None,
        display_name=name if isinstance(name, str) else None,
    )


def upsert_user(session: Session, identity: Identity) -> User:
    user = session.scalar(select(User).where(User.external_subject == identity.subject))
    if user is None:
        user = User(
            external_subject=identity.subject,
            email=identity.email,
            display_name=identity.display_name,
        )
        session.add(user)
        session.flush()
    else:
        user.email = identity.email or user.email
        user.display_name = identity.display_name or user.display_name
    return user


def bootstrap_orphan_projects_for_development(session: Session, user: User) -> None:
    """Give the first demo login ownership of pre-M6 projects; never used for OIDC."""

    orphan_projects = session.scalars(
        select(Project).where(
            ~select(ProjectMembership.project_id)
            .where(ProjectMembership.project_id == Project.id)
            .exists()
        )
    ).all()
    for project in orphan_projects:
        session.add(
            ProjectMembership(project_id=project.id, user_id=user.id, role=ProjectRole.OWNER)
        )


def project_id_from_path(path: str) -> str | None:
    match = _PROJECT_PATH.match(path)
    return match.group(1) if match else None


def required_role(request: Request) -> ProjectRole:
    path = request.url.path
    if (
        "/members" in path
        or "/security/config" in path
        or (request.method == "DELETE" and path.rstrip("/").count("/") == 4)
    ):
        return ProjectRole.OWNER
    if request.method in {"GET", "HEAD"}:
        return ProjectRole.VIEWER
    return ProjectRole.EDITOR


def authorize_project(session: Session, user: User, project_id: str, role: ProjectRole) -> None:
    membership = session.scalar(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user.id,
        )
    )
    if membership is None:
        if session.get(Project, project_id) is None:
            return
        raise AuthorizationError("Project access is not permitted.")
    rank = {ProjectRole.VIEWER: 1, ProjectRole.EDITOR: 2, ProjectRole.OWNER: 3}
    if rank[membership.role] < rank[role]:
        raise AuthorizationError("This project role does not permit the requested action.")


def record_audit(
    session: Session,
    *,
    project_id: str | None,
    event_type: str,
    actor_user_id: str | None,
    request_id: str | None,
    trace_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    document_id: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        project_id=project_id,
        document_id=document_id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        target_type=target_type,
        target_id=target_id,
        request_id=request_id,
        trace_id=trace_id,
        event_metadata=metadata or {},
    )
    session.add(event)
    return event


class RateLimiter:
    """Redis fixed-window limiter with a process-local development fallback."""

    def __init__(self, settings: Settings, redis_client: Any | None) -> None:
        self.limit = settings.rate_limit_requests
        self.window = settings.rate_limit_window_seconds
        self.redis = redis_client
        self._local: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        bucket = int(time.time() // self.window)
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        redis_key = f"assureai:rate:{digest}:{bucket}"
        if self.redis is not None:
            count = int(self.redis.incr(redis_key))
            if count == 1:
                self.redis.expire(redis_key, self.window + 1)
        else:
            now = time.monotonic()
            with self._lock:
                count, expires = self._local.get(redis_key, (0, now + self.window))
                if now >= expires:
                    count, expires = 0, now + self.window
                count += 1
                self._local[redis_key] = (count, expires)
        if count > self.limit:
            raise RateLimitExceededError("Too many requests. Try again later.")


def owner_count(session: Session, project_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(ProjectMembership)
            .where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.role == ProjectRole.OWNER,
            )
        )
        or 0
    )
