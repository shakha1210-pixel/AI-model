import json

import httpx
import pytest

from workspace.adapters.base import GenerationRequest, ModelMessage, ProviderAdapterError
from workspace.adapters.google import GoogleGeminiAdapter


def _request():
    return GenerationRequest(
        model="gemini-test",
        messages=[
            ModelMessage(role="user", content="Hi"),
            ModelMessage(role="assistant", content="Hello"),
        ],
        system="Be helpful",
        temperature=0.3,
        max_tokens=128,
        top_p=0.85,
        stop=["STOP"],
    )


@pytest.mark.asyncio
async def test_generate_maps_request_and_normalizes_response():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": "Gemini says "}, {"text": "hello"}],
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 5,
                    "totalTokenCount": 15,
                },
            },
        )

    adapter = GoogleGeminiAdapter(transport=httpx.MockTransport(handler))
    result = await adapter.generate(_request(), api_key="gemini-test-key")

    assert captured["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-test:generateContent"
    )
    assert captured["headers"]["x-goog-api-key"] == "gemini-test-key"
    assert "gemini-test-key" not in captured["url"]
    assert captured["payload"]["systemInstruction"] == {
        "parts": [{"text": "Be helpful"}]
    }
    assert captured["payload"]["contents"] == [
        {"role": "user", "parts": [{"text": "Hi"}]},
        {"role": "model", "parts": [{"text": "Hello"}]},
    ]
    assert captured["payload"]["generationConfig"]["maxOutputTokens"] == 128
    assert captured["payload"]["generationConfig"]["stopSequences"] == ["STOP"]
    assert result.text == "Gemini says hello"
    assert result.finish_reason == "STOP"
    assert result.usage.total_tokens == 15
    assert result.provider == "google"


@pytest.mark.asyncio
async def test_stream_uses_sse_endpoint_and_normalizes_candidate():
    body = (
        'data: {"candidates":[{"content":{"parts":[{"text":"Gem"}]}}]}\n\n'
        'data: {"candidates":[{"content":{"parts":[{"text":"ini"}]},"finishReason":"STOP"}],'
        '"usageMetadata":{"promptTokenCount":2,"candidatesTokenCount":1,"totalTokenCount":3}}\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models/gemini-test:streamGenerateContent")
        assert request.url.query == "alt=sse"
        assert request.headers["accept"] == "text/event-stream"
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=body,
        )

    adapter = GoogleGeminiAdapter(transport=httpx.MockTransport(handler))
    events = [
        event
        async for event in adapter.stream(_request(), api_key="stream-gemini-key")
    ]

    assert "".join(event.text_delta for event in events) == "Gemini"
    assert any(event.finish_reason == "STOP" for event in events)
    assert events[-1].is_final is True


@pytest.mark.asyncio
async def test_http_errors_are_sanitized():
    secret = "gemini-private-key"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": secret}})

    adapter = GoogleGeminiAdapter(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderAdapterError) as raised:
        await adapter.generate(_request(), api_key=secret)

    assert raised.value.status_code == 401
    assert raised.value.retryable is False
    assert secret not in str(raised.value)


@pytest.mark.asyncio
async def test_invalid_base_url_is_rejected():
    adapter = GoogleGeminiAdapter()
    with pytest.raises(ProviderAdapterError, match="base URL is invalid"):
        await adapter.generate(
            _request(),
            api_key="test-key",
            base_url="file:///tmp",
        )
