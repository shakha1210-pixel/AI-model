import json

import httpx
import pytest

from workspace.model_catalog import (
    ModelCatalogError,
    ModelCatalogUnsupported,
    list_provider_models,
)


@pytest.mark.asyncio
async def test_openai_compatible_catalog_normalizes_models_and_auth():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "model-z", "owned_by": "vendor"},
                    {"id": "model-a", "name": "Model A"},
                    {"id": "model-z", "owned_by": "vendor"},
                ]
            },
        )

    models = await list_provider_models(
        "groq",
        api_key="catalog-test-key",
        transport=httpx.MockTransport(handler),
    )

    assert captured["url"] == "https://api.groq.com/openai/v1/models"
    assert captured["authorization"] == "Bearer catalog-test-key"
    assert [model.id for model in models] == ["model-a", "model-z"]
    assert models[0].name == "Model A"


@pytest.mark.asyncio
async def test_anthropic_catalog_uses_native_headers():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = request.headers
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "claude-model",
                        "display_name": "Claude Model",
                        "type": "model",
                    }
                ]
            },
        )

    models = await list_provider_models(
        "anthropic",
        api_key="anthropic-catalog-key",
        transport=httpx.MockTransport(handler),
    )

    assert captured["headers"]["x-api-key"] == "anthropic-catalog-key"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert models[0].id == "claude-model"
    assert models[0].name == "Claude Model"


@pytest.mark.asyncio
async def test_gemini_catalog_filters_non_generation_models():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["api_key"] = request.headers["x-goog-api-key"]
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "models/gemini-flash",
                        "displayName": "Gemini Flash",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/text-embedding",
                        "displayName": "Embedding",
                        "supportedGenerationMethods": ["embedContent"],
                    },
                ]
            },
        )

    models = await list_provider_models(
        "google",
        api_key="google-catalog-key",
        transport=httpx.MockTransport(handler),
    )

    assert captured["url"].endswith("/models?pageSize=100")
    assert captured["api_key"] == "google-catalog-key"
    assert [model.id for model in models] == ["gemini-flash"]


@pytest.mark.asyncio
async def test_perplexity_falls_back_to_manual_model_id_without_network():
    with pytest.raises(ModelCatalogUnsupported, match="manually"):
        await list_provider_models("perplexity", api_key="perplexity-key")


@pytest.mark.asyncio
async def test_catalog_http_errors_are_sanitized():
    secret = "do-not-leak-this-key"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": secret})

    with pytest.raises(ModelCatalogError) as raised:
        await list_provider_models(
            "openai",
            api_key=secret,
            transport=httpx.MockTransport(handler),
        )

    assert raised.value.status_code == 429
    assert raised.value.retryable is True
    assert secret not in str(raised.value)


@pytest.mark.asyncio
async def test_custom_provider_requires_a_base_url():
    with pytest.raises(ModelCatalogError, match="base URL is invalid"):
        await list_provider_models("custom_openai", api_key="custom-key")


@pytest.mark.asyncio
async def test_model_catalog_rejects_missing_api_key():
    with pytest.raises(ModelCatalogError, match="API key is required"):
        await list_provider_models("openai", api_key="")
