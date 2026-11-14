import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import get_current_user
from database import Agent, Base, ProviderConnection, User
import workspace.api.agents as agents_api
import workspace.api.connections as connections_api


@pytest.fixture
def agent_context():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    user = User(id="agent-owner", email="owner@example.test")
    other = User(id="agent-other", email="other@example.test")
    with TestingSession() as db:
        db.add_all([user, other])
        db.commit()
        db.add(
            ProviderConnection(
                id="connection-owner",
                user_id=user.id,
                provider_id="openai",
                display_name="My OpenAI",
                encrypted_api_key="ciphertext-never-exposed",
            )
        )
        db.add(
            ProviderConnection(
                id="connection-other",
                user_id=other.id,
                provider_id="openai",
                display_name="Other OpenAI",
                encrypted_api_key="other-ciphertext",
            )
        )
        db.commit()

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(agents_api.router)
    app.include_router(connections_api.router)
    app.dependency_overrides[agents_api.get_db] = override_db
    app.dependency_overrides[connections_api.get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    yield client, TestingSession, user, other, app
    engine.dispose()


def _agent_payload(**overrides):
    payload = {
        "name": "Research helper",
        "description": "Helps with research",
        "system_prompt": "You are a careful research assistant.",
        "provider_connection_id": "connection-owner",
        "model_id": "gpt-test-model",
        "temperature": 0.4,
        "max_tokens": 4096,
        "permissions": [],
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def test_agent_crud_and_safe_serialization(agent_context):
    client, TestingSession, user, _, _ = agent_context
    created = client.post("/api/workspace/agents", json=_agent_payload())
    assert created.status_code == 201
    data = created.json()
    assert data["name"] == "Research helper"
    assert data["provider_id"] == "openai"
    assert data["provider_name"] == "My OpenAI"
    assert data["permissions"] == []
    assert "encrypted_api_key" not in created.text
    assert "ciphertext-never-exposed" not in created.text

    agent_id = data["id"]
    listed = client.get("/api/workspace/agents")
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()["agents"]] == [agent_id]

    updated = client.patch(
        f"/api/workspace/agents/{agent_id}",
        json={"name": "Updated helper", "temperature": 1.1, "permissions": ["web.search"]},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated helper"
    assert updated.json()["temperature"] == 1.1
    assert updated.json()["permissions"] == ["web.search"]

    fetched = client.get(f"/api/workspace/agents/{agent_id}")
    assert fetched.status_code == 200
    assert fetched.json()["system_prompt"] == "You are a careful research assistant."

    deleted = client.delete(f"/api/workspace/agents/{agent_id}")
    assert deleted.status_code == 200
    assert client.get(f"/api/workspace/agents/{agent_id}").status_code == 404
    with TestingSession() as db:
        assert db.query(Agent).filter_by(user_id=user.id).count() == 0


def test_agent_cannot_bind_another_users_connection(agent_context):
    client, _, _, _, _ = agent_context
    response = client.post(
        "/api/workspace/agents",
        json=_agent_payload(provider_connection_id="connection-other"),
    )
    assert response.status_code == 422


def test_agent_crud_is_tenant_scoped(agent_context):
    client, _, user, other, app = agent_context
    created = client.post("/api/workspace/agents", json=_agent_payload())
    agent_id = created.json()["id"]
    app.dependency_overrides[get_current_user] = lambda: other

    assert client.get("/api/workspace/agents").json()["agents"] == []
    assert client.get(f"/api/workspace/agents/{agent_id}").status_code == 404
    assert client.patch(f"/api/workspace/agents/{agent_id}", json={"name": "Hijack"}).status_code == 404
    assert client.delete(f"/api/workspace/agents/{agent_id}").status_code == 404


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "   "},
        {"system_prompt": " "},
        {"model_id": ""},
        {"temperature": 2.1},
        {"max_tokens": 0},
        {"permissions": ["unknown.capability"]},
        {"permissions": ["web.search", "web.search"]},
    ],
)
def test_agent_rejects_invalid_configuration(agent_context, overrides):
    client, _, _, _, _ = agent_context
    response = client.post("/api/workspace/agents", json=_agent_payload(**overrides))
    assert response.status_code == 422


def test_agent_update_rejects_explicit_null_values(agent_context):
    client, _, _, _, _ = agent_context
    created = client.post("/api/workspace/agents", json=_agent_payload())
    agent_id = created.json()["id"]
    response = client.patch(
        f"/api/workspace/agents/{agent_id}",
        json={"name": None, "provider_connection_id": None},
    )
    assert response.status_code == 422


def test_provider_connection_cannot_be_deleted_while_agent_uses_it(agent_context):
    client, _, _, _, _ = agent_context
    created = client.post("/api/workspace/agents", json=_agent_payload())
    assert created.status_code == 201
    response = client.delete("/api/workspace/connections/connection-owner")
    assert response.status_code == 409
    assert "agents" in response.json()["detail"].lower()


def test_agent_update_rejects_foreign_connection(agent_context):
    client, _, _, _, _ = agent_context
    created = client.post("/api/workspace/agents", json=_agent_payload())
    agent_id = created.json()["id"]
    response = client.patch(
        f"/api/workspace/agents/{agent_id}",
        json={"provider_connection_id": "connection-other"},
    )
    assert response.status_code == 422
