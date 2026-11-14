"""Authenticated provider connection management API."""
from __future__ import annotations

import datetime
from typing import Generator

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.orm import Session

from auth import get_current_user
from database import Agent, ProviderConnection, SessionLocal, User
from workspace.adapters.base import GenerationRequest, ModelMessage, ProviderAdapterError
from workspace.adapters.factory import get_provider_adapter
from workspace.credentials.encryption import (
    CredentialEncryptionError,
    decrypt_api_key,
    encrypt_api_key,
)
from workspace.credentials.endpoint import (
    ProviderEndpointError,
    validate_public_https_base_url,
)
from workspace.model_catalog import (
    ModelCatalogError,
    ModelCatalogUnsupported,
    list_provider_models,
)
from workspace.providers import get_provider


router = APIRouter(
    prefix="/api/workspace/connections",
    tags=["workspace-connections"],
)


class ConnectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=80)
    api_key: SecretStr
    base_url: str | None = Field(default=None, max_length=2048)


class ConnectionTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = Field(min_length=1, max_length=160)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _safe_connection(connection: ProviderConnection) -> dict:
    provider = get_provider(connection.provider_id)
    return {
        "id": connection.id,
        "provider_id": connection.provider_id,
        "provider_name": provider.name,
        "display_name": connection.display_name,
        "base_url": connection.base_url,
        "created_at": connection.created_at.isoformat() if connection.created_at else None,
        "updated_at": connection.updated_at.isoformat() if connection.updated_at else None,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_connection(
    payload: ConnectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        provider = get_provider(payload.provider_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Unsupported provider") from None

    display_name = payload.display_name.strip()
    api_key = payload.api_key.get_secret_value().strip()
    if not display_name:
        raise HTTPException(status_code=422, detail="Display name must not be empty")
    if not api_key:
        raise HTTPException(status_code=422, detail="API key must not be empty")

    base_url = None
    if provider.accepts_custom_base_url:
        try:
            base_url = validate_public_https_base_url(payload.base_url or "")
        except ProviderEndpointError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
    elif payload.base_url:
        raise HTTPException(
            status_code=422,
            detail="This provider does not accept a custom base URL",
        )

    try:
        encrypted = encrypt_api_key(api_key)
    except CredentialEncryptionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None

    connection = ProviderConnection(
        user_id=current_user.id,
        provider_id=provider.id,
        display_name=display_name,
        encrypted_api_key=encrypted,
        base_url=base_url,
        encryption_key_version="v1",
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return _safe_connection(connection)


@router.get("")
def list_connections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    rows = (
        db.query(ProviderConnection)
        .filter(ProviderConnection.user_id == current_user.id)
        .order_by(ProviderConnection.created_at.desc())
        .all()
    )
    return {"connections": [_safe_connection(row) for row in rows]}


@router.delete("/{connection_id}")
def delete_connection(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    connection = (
        db.query(ProviderConnection)
        .filter(
            ProviderConnection.id == connection_id,
            ProviderConnection.user_id == current_user.id,
        )
        .first()
    )
    if connection is None:
        raise HTTPException(status_code=404, detail="Provider connection not found")
    if db.query(Agent).filter(Agent.provider_connection_id == connection_id).first():
        raise HTTPException(
            status_code=409,
            detail="Delete or reassign agents using this connection before deleting it",
        )
    db.delete(connection)
    db.commit()
    return {"status": "deleted"}


@router.get("/{connection_id}/models")
async def discover_connection_models(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    connection = (
        db.query(ProviderConnection)
        .filter(
            ProviderConnection.id == connection_id,
            ProviderConnection.user_id == current_user.id,
        )
        .first()
    )
    if connection is None:
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

    try:
        models = await list_provider_models(
            connection.provider_id,
            api_key=api_key,
            base_url=base_url,
        )
    except ModelCatalogUnsupported as exc:
        return {
            "provider_id": connection.provider_id,
            "catalog_supported": False,
            "manual_entry_supported": True,
            "message": str(exc),
            "models": [],
        }
    except ModelCatalogError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": str(exc),
                "provider": exc.provider,
                "status_code": exc.status_code,
                "retryable": exc.retryable,
            },
        ) from None

    return {
        "provider_id": connection.provider_id,
        "catalog_supported": True,
        "manual_entry_supported": True,
        "models": [model.public_dict() for model in models],
    }


@router.post("/{connection_id}/test")
async def test_connection(
    connection_id: str,
    payload: ConnectionTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    connection = (
        db.query(ProviderConnection)
        .filter(
            ProviderConnection.id == connection_id,
            ProviderConnection.user_id == current_user.id,
        )
        .first()
    )
    if connection is None:
        raise HTTPException(status_code=404, detail="Provider connection not found")

    try:
        api_key = decrypt_api_key(connection.encrypted_api_key)
    except CredentialEncryptionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None

    # Revalidate custom endpoints before every outbound test request. This
    # reduces SSRF exposure; production still needs an outbound egress policy
    # to prevent DNS rebinding between validation and the HTTP connection.
    base_url = connection.base_url
    if connection.provider_id == "custom_openai":
        try:
            base_url = validate_public_https_base_url(base_url or "")
        except ProviderEndpointError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    adapter = get_provider_adapter(connection.provider_id)
    request = GenerationRequest(
        model=payload.model,
        messages=[
            ModelMessage(
                role="user",
                content="Reply with OK. This is a short provider connectivity test.",
            )
        ],
        temperature=0,
        max_tokens=8,
    )
    try:
        await adapter.generate(request, api_key=api_key, base_url=base_url)
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

    return {
        "ok": True,
        "provider_id": connection.provider_id,
        "model": payload.model,
        "message": "Provider connection successful",
    }
