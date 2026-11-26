"""Identity, membership, and safe operational configuration routes."""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from assureai_api.database import get_db
from assureai_api.models import ProjectMembership, ProjectRole
from assureai_api.security import (
    AuthenticationError,
    Identity,
    authenticate_request,
    bootstrap_orphan_projects_for_development,
    create_development_token,
    owner_count,
    record_audit,
    upsert_user,
)

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger(__name__)
DbSession = Annotated[Session, Depends(get_db)]


class DevelopmentLoginRequest(BaseModel):
    subject: str = Field(default="demo-owner", min_length=1, max_length=255)
    email: str | None = Field(default="demo@localhost", max_length=320)
    display_name: str | None = Field(default="Demo Owner", max_length=200)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    external_subject: str
    email: str | None
    display_name: str | None


class MembershipResponse(BaseModel):
    project_id: str
    user: UserResponse
    role: ProjectRole
    created_at: datetime


class MembershipUpsert(BaseModel):
    external_subject: str = Field(min_length=1, max_length=255)
    role: ProjectRole
    email: str | None = Field(default=None, max_length=320)
    display_name: str | None = Field(default=None, max_length=200)


class MembershipRoleUpdate(BaseModel):
    role: ProjectRole


def _membership_response(membership: ProjectMembership) -> MembershipResponse:
    return MembershipResponse(
        project_id=membership.project_id,
        user=UserResponse.model_validate(membership.user),
        role=membership.role,
        created_at=membership.created_at,
    )


@router.post("/auth/development/login", response_model=UserResponse)
def development_login(
    payload: DevelopmentLoginRequest, request: Request, response: Response, session: DbSession
) -> UserResponse:
    settings = request.app.state.settings
    if settings.auth_mode != "development":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    identity = Identity(payload.subject, payload.email, payload.display_name)
    user = upsert_user(session, identity)
    bootstrap_orphan_projects_for_development(session, user)
    record_audit(
        session,
        project_id=None,
        event_type="auth.login",
        actor_user_id=user.id,
        request_id=request.state.request_id,
        trace_id=request.state.trace_id,
        target_type="user",
        target_id=user.id,
    )
    session.commit()
    logger.info("auth.login", extra={"user_id": user.id, "request_id": request.state.request_id})
    token = create_development_token(settings, identity)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )
    return UserResponse.model_validate(user)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, session: DbSession) -> None:
    actor_user_id = None
    try:
        identity = authenticate_request(request, request.app.state.settings)
        actor_user_id = upsert_user(session, identity).id
    except AuthenticationError:
        pass
    record_audit(
        session,
        project_id=None,
        event_type="auth.logout",
        actor_user_id=actor_user_id,
        request_id=request.state.request_id,
        trace_id=request.state.trace_id,
        target_type="session",
    )
    session.commit()
    logger.info("auth.logout", extra={"request_id": request.state.request_id})
    response.delete_cookie(request.app.state.settings.session_cookie_name, path="/")


@router.get("/auth/me", response_model=UserResponse)
def current_user(request: Request) -> UserResponse:
    return UserResponse.model_validate(request.state.user)


@router.get("/projects/{project_id}/members", response_model=list[MembershipResponse])
def list_members(project_id: str, session: DbSession) -> list[MembershipResponse]:
    memberships = session.scalars(
        select(ProjectMembership)
        .options(selectinload(ProjectMembership.user))
        .where(ProjectMembership.project_id == project_id)
        .order_by(ProjectMembership.created_at)
    ).all()
    return [_membership_response(item) for item in memberships]


@router.post(
    "/projects/{project_id}/members",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    project_id: str, payload: MembershipUpsert, request: Request, session: DbSession
) -> MembershipResponse:
    user = upsert_user(
        session, Identity(payload.external_subject, payload.email, payload.display_name)
    )
    existing = session.scalar(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user.id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Member already exists.")
    membership = ProjectMembership(project_id=project_id, user_id=user.id, role=payload.role)
    session.add(membership)
    record_audit(
        session,
        project_id=project_id,
        event_type="membership.added",
        actor_user_id=request.state.user.id,
        request_id=request.state.request_id,
        trace_id=request.state.trace_id,
        target_type="user",
        target_id=user.id,
        metadata={"role": payload.role.value},
    )
    session.commit()
    session.refresh(membership)
    return _membership_response(membership)


@router.patch("/projects/{project_id}/members/{user_id}", response_model=MembershipResponse)
def change_member_role(
    project_id: str,
    user_id: str,
    payload: MembershipRoleUpdate,
    request: Request,
    session: DbSession,
) -> MembershipResponse:
    membership = session.scalar(
        select(ProjectMembership)
        .options(selectinload(ProjectMembership.user))
        .where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")
    if (
        membership.role == ProjectRole.OWNER
        and payload.role != ProjectRole.OWNER
        and owner_count(session, project_id) == 1
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A project must retain an owner."
        )
    previous = membership.role
    membership.role = payload.role
    record_audit(
        session,
        project_id=project_id,
        event_type="membership.changed",
        actor_user_id=request.state.user.id,
        request_id=request.state.request_id,
        trace_id=request.state.trace_id,
        target_type="user",
        target_id=user_id,
        metadata={"from": previous.value, "to": payload.role.value},
    )
    session.commit()
    return _membership_response(membership)


@router.delete("/projects/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(project_id: str, user_id: str, request: Request, session: DbSession) -> None:
    membership = session.scalar(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")
    if membership.role == ProjectRole.OWNER and owner_count(session, project_id) == 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="The final owner cannot be removed."
        )
    session.delete(membership)
    record_audit(
        session,
        project_id=project_id,
        event_type="membership.removed",
        actor_user_id=request.state.user.id,
        request_id=request.state.request_id,
        trace_id=request.state.trace_id,
        target_type="user",
        target_id=user_id,
    )
    session.commit()


@router.get("/projects/{project_id}/security/config")
def security_config(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    return {
        "storage_provider": settings.storage_provider,
        "storage_container": settings.azure_storage_container
        if settings.storage_provider == "azure_blob"
        else None,
        "secret_store_provider": settings.secret_store_provider,
        "malware_scanner": settings.malware_scanner,
        "secret_values_exposed": False,
    }
