import json

import httpx
import pytest

from workspace.adapters.base import GenerationRequest, ModelMessage, ProviderAdapterError
from workspace.adapters.openai_compatible import OpenAICompatibleAdapter


def _request():
    return GenerationRequest(
        model="gpt-test",
        messages=[ModelMessage(role="user", content="Hello")],
        system="Be concise",
        temperature=0.25,
        max_tokens=64,
        top_p=0.9,
        stop=["END"],
    )


@pytest.mark.asyncio
async def test_generate_normalizes_response_and_request():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "gpt-test",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "Hello back"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 8,
                    "completion_tokens": 3,
                    "total_tokens": 11,
                },
            },
        )

    adapter = OpenAICompatibleAdapter(
        transport=httpx.MockTransport(handler)
    )
    result = await adapter.generate(_request(), api_key="test-secret")

    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["headers"]["authorization"] == "Bearer test-secret"
    assert captured["payload"]["model"] == "gpt-test"
    assert captured["payload"]["messages"] == [
        {"role": "system", "content": "Be concise"},
        {"role": "user", "content": "Hello"},
    ]
    assert captured["payload"]["temperature"] == 0.25
    assert captured["payload"]["max_tokens"] == 64
    assert captured["payload"]["top_p"] == 0.9
    assert captured["payload"]["stop"] == ["END"]
    assert result.text == "Hello back"
    assert result.finish_reason == "stop"
    assert result.usage.total_tokens == 11
    assert result.provider == "openai"


@pytest.mark.asyncio
async def test_openrouter_uses_its_default_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith("https://openrouter.ai/api/v1/")
        return httpx.Response(
            200,
            json={
                "model": "router/model",
                "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
            },
        )

    adapter = OpenAICompatibleAdapter(
        "openrouter", transport=httpx.MockTransport(handler)
    )
    result = await adapter.generate(
        GenerationRequest(
            model="router/model",
            messages=[ModelMessage(role="user", content="Hi")],
        ),
        api_key="router-test-key",
    )

    assert result.provider == "openrouter"
    assert result.text == "OK"


@pytest.mark.asyncio
async def test_custom_provider_requires_a_base_url():
    adapter = OpenAICompatibleAdapter("custom_openai")
    request = GenerationRequest(
        model="local-model",
        messages=[ModelMessage(role="user", content="Hi")],
    )

    with pytest.raises(ProviderAdapterError, match="base URL is required"):
        await adapter.generate(request, api_key="local-test-key")


@pytest.mark.asyncio
async def test_invalid_base_url_is_rejected_without_network_access():
    adapter = OpenAICompatibleAdapter("custom_openai")
    request = GenerationRequest(
        model="local-model",
        messages=[ModelMessage(role="user", content="Hi")],
    )

    with pytest.raises(ProviderAdapterError, match="base URL is invalid"):
        await adapter.generate(
            request,
            api_key="test-key",
            base_url="file:///etc/passwd",
        )


@pytest.mark.asyncio
async def test_http_errors_are_normalized_and_do_not_leak_credentials():
    secret = "super-secret-test-key"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": secret}})

    adapter = OpenAICompatibleAdapter(
        transport=httpx.MockTransport(handler)
    )
    with pytest.raises(ProviderAdapterError) as raised:
        await adapter.generate(_request(), api_key=secret)

    assert raised.value.status_code == 429
    assert raised.value.retryable is True
    assert secret not in str(raised.value)


@pytest.mark.asyncio
async def test_stream_normalizes_text_finish_and_done_events():
    body = (
        'data: {"choices":[{"delta":{"content":"Hel"},"finish_reason":null}]}\n\n'
        'data: {"choices":[{"delta":{"content":"lo"},"finish_reason":null}]}\n\n'
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
        "data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept"] == "text/event-stream"
        payload = json.loads(request.content)
        assert payload["stream"] is True
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=body,
        )

    adapter = OpenAICompatibleAdapter(
        transport=httpx.MockTransport(handler)
    )
    events = [
        event
        async for event in adapter.stream(_request(), api_key="stream-test-key")
    ]

    assert "".join(event.text_delta for event in events) == "Hello"
    assert any(event.finish_reason == "stop" for event in events)
    assert events[-1].is_final is True
