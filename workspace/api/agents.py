"""Tenant-scoped CRUD for user-configured workspace agents."""
from __future__ import annotations

import datetime
from typing import Generator

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from auth import get_current_user
from database import Agent, ProviderConnection, SessionLocal, User
from workspace.adapters.base import GenerationRequest, ModelMessage, ProviderAdapterError
from workspace.adapters.factory import get_provider_adapter
from workspace.credentials.encryption import CredentialEncryptionError, decrypt_api_key
from workspace.credentials.endpoint import ProviderEndpointError, validate_public_https_base_url

router = APIRouter(prefix="/api/workspace/agents", tags=["workspace-agents"])

ALLOWED_PERMISSIONS = {
    "project_files.read",
    "project_files.write",
    "web.search",
    "git.read",
    "git.write",
    "code.execute",
}


class AgentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    system_prompt: str = Field(min_length=1, max_length=12000)
    provider_connection_id: str = Field(min_length=1, max_length=64)
    model_id: str = Field(min_length=1, max_length=160)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=2048, ge=1, le=32768)
    permissions: list[str] = Field(default_factory=list, max_length=6)
    is_active: bool = True

    @field_validator("name", "system_prompt", "model_id")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field must not be blank")
        return value

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or any(item not in ALLOWED_PERMISSIONS for item in value):
            raise ValueError("Unsupported or duplicate permission")
        return value


class AgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=12000)

    @field_validator("message")
    @classmethod
    def require_nonblank_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message must not be blank")
        return value


class AgentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=12000)
    provider_connection_id: str | None = Field(default=None, min_length=1, max_length=64)
    model_id: str | None = Field(default=None, min_length=1, max_length=160)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=32768)
    permissions: list[str] | None = Field(default=None, max_length=6)
    is_active: bool | None = None

    @field_validator("name", "system_prompt", "model_id")
    @classmethod
    def require_nonblank_when_set(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Field must not be blank")
        return value

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if len(value) != len(set(value)) or any(item not in ALLOWED_PERMISSIONS for item in value):
            raise ValueError("Unsupported or duplicate permission")
        return value

    @model_validator(mode="after")
    def reject_explicit_nulls(self):
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Fields cannot be null; omit fields that should remain unchanged")
        return self


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _owned_connection(db: Session, connection_id: str, user_id: str) -> ProviderConnection:
    connection = (
        db.query(ProviderConnection)
        .filter(
            ProviderConnection.id == connection_id,
            ProviderConnection.user_id == user_id,
        )
        .first()
    )
    if connection is None:
        raise HTTPException(status_code=422, detail="Provider connection not found")
    return connection


def _owned_agent(db: Session, agent_id: str, user_id: str) -> Agent:
    agent = (
        db.query(Agent)
        .filter(Agent.id == agent_id, Agent.user_id == user_id)
        .first()
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


def _public_agent(agent: Agent) -> dict:
    connection = agent.provider_connection
    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "system_prompt": agent.system_prompt,
        "provider_connection_id": agent.provider_connection_id,
        "provider_id": connection.provider_id,
        "provider_name": connection.display_name,
        "model_id": agent.model_id,
        "temperature": agent.temperature,
        "max_tokens": agent.max_tokens,
        "permissions": agent.permissions or [],
        "is_active": agent.is_active,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
        "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _owned_connection(db, payload.provider_connection_id, current_user.id)
    data = payload.model_dump()
    data["name"] = data["name"].strip()
    data["description"] = data["description"].strip()
    agent = Agent(user_id=current_user.id, **data)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return _public_agent(agent)


@router.get("")
def list_agents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    agents = (
        db.query(Agent)
        .filter(Agent.user_id == current_user.id)
        .order_by(Agent.created_at.desc())
        .all()
    )
    return {"agents": [_public_agent(agent) for agent in agents]}


@router.get("/{agent_id}")
def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return _public_agent(_owned_agent(db, agent_id, current_user.id))


@router.patch("/{agent_id}")
def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    agent = _owned_agent(db, agent_id, current_user.id)
    changes = payload.model_dump(exclude_unset=True)
    if "provider_connection_id" in changes:
        _owned_connection(db, changes["provider_connection_id"], current_user.id)
    for key, value in changes.items():
        if key == "name" and value is not None:
            value = value.strip()
        elif key == "description" and value is not None:
            value = value.strip()
        setattr(agent, key, value)
    agent.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(agent)
    return _public_agent(agent)


@router.delete("/{agent_id}")
def delete_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    agent = _owned_agent(db, agent_id, current_user.id)
    db.delete(agent)
    db.commit()
    return {"status": "deleted"}


@router.post("/{agent_id}/run")
async def run_agent(
    agent_id: str,
    payload: AgentRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Run a single text generation using the agent's configured model.

    This endpoint intentionally does not execute tools, even when the agent
    has permission flags saved. Tool execution requires the future isolated
    execution and approval layer.
    """
    agent = _owned_agent(db, agent_id, current_user.id)
    if not agent.is_active:
        raise HTTPException(status_code=409, detail="Agent is inactive")

    connection = agent.provider_connection
    if connection is None or connection.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Provider connection not found")

    try:
        api_key = decrypt_api_key(connection.encrypted_api_key)
    except CredentialEncryptionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None

    base_url = connection.base_url
    if connection.provider_id == "custom_openai":
        try:
            base_url = validate_public_https_base_url(base_url or "")
        except ProviderEndpointError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    request = GenerationRequest(
        model=agent.model_id,
        messages=[ModelMessage(role="user", content=payload.message)],
        system=agent.system_prompt,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
    )
    try:
        result = await get_provider_adapter(connection.provider_id).generate(
            request, api_key=api_key, base_url=base_url
        )
    except ProviderAdapterError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": str(exc),
                "provider": exc.provider,
                "status_code": exc.status_code,
                "retryable": exc.retryable,
            },
        ) from None

    usage = None
    if result.usage is not None:
        usage = {
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "total_tokens": result.usage.total_tokens,
        }
    return {
        "agent_id": agent.id,
        "text": result.text,
        "model": result.model,
        "provider": result.provider,
        "finish_reason": result.finish_reason,
        "usage": usage,
    }
