import json

import httpx
import pytest

from workspace.adapters.anthropic import AnthropicAdapter
from workspace.adapters.base import GenerationRequest, ModelMessage, ProviderAdapterError


def _request():
    return GenerationRequest(
        model="claude-test",
        messages=[
            ModelMessage(role="system", content="Extra system"),
            ModelMessage(role="user", content="Hello"),
        ],
        system="Be concise",
        temperature=0.2,
        max_tokens=80,
        top_p=0.8,
        stop=["END"],
    )


@pytest.mark.asyncio
async def test_generate_maps_messages_and_normalizes_response():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "claude-test",
                "content": [{"type": "text", "text": "Hello from Claude"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 9, "output_tokens": 4},
            },
        )

    adapter = AnthropicAdapter(transport=httpx.MockTransport(handler))
    result = await adapter.generate(_request(), api_key="anthropic-test-key")

    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "anthropic-test-key"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["payload"]["system"] == "Be concise\n\nExtra system"
    assert captured["payload"]["messages"] == [
        {"role": "user", "content": "Hello"}
    ]
    assert captured["payload"]["max_tokens"] == 80
    assert captured["payload"]["stop_sequences"] == ["END"]
    assert result.text == "Hello from Claude"
    assert result.finish_reason == "end_turn"
    assert result.usage.total_tokens == 13
    assert result.provider == "anthropic"


@pytest.mark.asyncio
async def test_generate_uses_default_max_tokens_when_missing():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "OK"}], "model": "claude-test"},
        )

    adapter = AnthropicAdapter(transport=httpx.MockTransport(handler))
    request = GenerationRequest(
        model="claude-test",
        messages=[ModelMessage(role="user", content="Hi")],
    )
    await adapter.generate(request, api_key="key")

    assert captured["payload"]["max_tokens"] == 1024


@pytest.mark.asyncio
async def test_stream_normalizes_text_finish_and_usage():
    body = (
        'event: message_start\ndata: {"type":"message_start","message":{"usage":{"input_tokens":7}}}\n\n'
        'event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hi"}}\n\n'
        'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":2}}\n\n'
        'event: message_stop\ndata: {"type":"message_stop"}\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept"] == "text/event-stream"
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=body,
        )

    adapter = AnthropicAdapter(transport=httpx.MockTransport(handler))
    events = [
        event
        async for event in adapter.stream(_request(), api_key="stream-key")
    ]

    assert "".join(event.text_delta for event in events) == "Hi"
    assert any(event.finish_reason == "end_turn" for event in events)
    assert any(event.usage and event.usage.total_tokens == 9 for event in events)
    assert events[-1].is_final is True


@pytest.mark.asyncio
async def test_http_errors_are_sanitized_and_retryable():
    secret = "never-show-this-key"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": secret})

    adapter = AnthropicAdapter(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderAdapterError) as raised:
        await adapter.generate(_request(), api_key=secret)

    assert raised.value.status_code == 503
    assert raised.value.retryable is True
    assert secret not in str(raised.value)
