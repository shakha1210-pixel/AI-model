import asyncio

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import workspace.api.connections as connections_api
from auth import get_current_user
from database import Base, ProviderConnection, User
from workspace.adapters.base import GenerationResult, Usage
from workspace.credentials.encryption import decrypt_api_key
from workspace.model_catalog import ModelCatalogUnsupported, ModelInfo


@pytest.fixture
def api_context(monkeypatch):
    monkeypatch.setenv(
        "PROVIDER_CREDENTIALS_ENCRYPTION_KEY",
        Fernet.generate_key().decode("ascii"),
    )
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    user = User(id="user-1", email="user@example.test")
    with TestingSession() as db:
        db.add(user)
        db.commit()

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(connections_api.router)
    app.dependency_overrides[connections_api.get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    yield client, TestingSession, user, app
    engine.dispose()


def _create_openai_connection(client):
    return client.post(
        "/api/workspace/connections",
        json={
            "provider_id": "openai",
            "display_name": "Personal OpenAI",
            "api_key": "sk-private-test-value",
        },
    )


def test_create_and_list_never_return_api_key_or_ciphertext(api_context):
    client, TestingSession, user, _ = api_context

    created = _create_openai_connection(client)
    assert created.status_code == 201
    payload = created.json()
    assert payload["provider_id"] == "openai"
    assert payload["display_name"] == "Personal OpenAI"
    assert "api_key" not in payload
    assert "encrypted_api_key" not in payload

    with TestingSession() as db:
        row = db.query(ProviderConnection).filter_by(user_id=user.id).one()
        assert row.encrypted_api_key != "sk-private-test-value"
        assert decrypt_api_key(row.encrypted_api_key) == "sk-private-test-value"

    listed = client.get("/api/workspace/connections")
    assert listed.status_code == 200
    assert len(listed.json()["connections"]) == 1
    assert "encrypted_api_key" not in listed.text
    assert "sk-private-test-value" not in listed.text


def test_custom_provider_requires_a_safe_base_url(api_context):
    client, _, _, _ = api_context
    response = client.post(
        "/api/workspace/connections",
        json={
            "provider_id": "custom_openai",
            "display_name": "Local endpoint",
            "api_key": "custom-secret",
            "base_url": "https://localhost/v1",
        },
    )
    assert response.status_code == 422


def test_delete_is_scoped_to_authenticated_owner(api_context):
    client, TestingSession, user, app = api_context
    created = _create_openai_connection(client)
    connection_id = created.json()["id"]

    other_user = User(id="user-2", email="other@example.test")
    app.dependency_overrides[get_current_user] = lambda: other_user
    deleted = client.delete(f"/api/workspace/connections/{connection_id}")

    assert deleted.status_code == 404
    with TestingSession() as db:
        assert db.query(ProviderConnection).filter_by(id=connection_id).one()
        assert db.query(ProviderConnection).filter_by(user_id=user.id).count() == 1


def test_connection_test_uses_decrypted_key_but_never_returns_it(api_context, monkeypatch):
    client, _, _, _ = api_context
    created = _create_openai_connection(client)
    connection_id = created.json()["id"]
    captured = {}

    class FakeAdapter:
        async def generate(self, request, *, api_key, base_url=None):
            captured["api_key"] = api_key
            captured["base_url"] = base_url
            return GenerationResult(
                text="OK",
                model=request.model,
                provider="openai",
                finish_reason="stop",
                usage=Usage(input_tokens=3, output_tokens=1, total_tokens=4),
            )

    monkeypatch.setattr(
        connections_api, "get_provider_adapter", lambda provider_id: FakeAdapter()
    )
    response = client.post(
        f"/api/workspace/connections/{connection_id}/test",
        json={"model": "gpt-test"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert captured["api_key"] == "sk-private-test-value"
    assert "sk-private-test-value" not in response.text
    assert "encrypted_api_key" not in response.text


def test_unknown_provider_is_rejected(api_context):
    client, _, _, _ = api_context
    response = client.post(
        "/api/workspace/connections",
        json={
            "provider_id": "unknown",
            "display_name": "Unknown",
            "api_key": "secret",
        },
    )
    assert response.status_code == 422



def test_model_discovery_returns_normalized_models_without_credentials(api_context, monkeypatch):
    client, _, _, _ = api_context
    created = _create_openai_connection(client)
    connection_id = created.json()["id"]

    async def fake_catalog(provider_id, *, api_key, base_url=None):
        assert provider_id == "openai"
        assert api_key == "sk-private-test-value"
        return [ModelInfo("gpt-test", "GPT Test", "OpenAI")]

    monkeypatch.setattr(connections_api, "list_provider_models", fake_catalog)
    response = client.get(f"/api/workspace/connections/{connection_id}/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["catalog_supported"] is True
    assert payload["models"] == [
        {"id": "gpt-test", "name": "GPT Test", "owned_by": "OpenAI"}
    ]
    assert "sk-private-test-value" not in response.text
    assert "encrypted_api_key" not in response.text


def test_model_discovery_supports_manual_fallback(api_context, monkeypatch):
    client, _, _, _ = api_context
    created = client.post(
        "/api/workspace/connections",
        json={
            "provider_id": "perplexity",
            "display_name": "Perplexity",
            "api_key": "perplexity-test-key",
        },
    )
    connection_id = created.json()["id"]

    async def unsupported(*args, **kwargs):
        raise ModelCatalogUnsupported("Enter a model ID manually.")

    monkeypatch.setattr(connections_api, "list_provider_models", unsupported)
    response = client.get(f"/api/workspace/connections/{connection_id}/models")

    assert response.status_code == 200
    assert response.json()["catalog_supported"] is False
    assert response.json()["manual_entry_supported"] is True
    assert response.json()["models"] == []


def test_model_discovery_is_scoped_to_connection_owner(api_context):
    client, _, _, app = api_context
    created = _create_openai_connection(client)
    connection_id = created.json()["id"]
    app.dependency_overrides[get_current_user] = lambda: User(
        id="another-user", email="another@example.test"
    )

    response = client.get(f"/api/workspace/connections/{connection_id}/models")

    assert response.status_code == 404
