"""Google Gemini GenerateContent API adapter.

The API key is sent in the x-goog-api-key header rather than a query parameter,
so it does not become part of request URLs or ordinary access logs.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from workspace.adapters.base import (
    GenerationRequest,
    GenerationResult,
    ProviderAdapterError,
    StreamEvent,
    Usage,
)
from workspace.providers import get_provider


class GoogleGeminiAdapter:
    """Adapter for the Google Gemini GenerateContent API."""

    def __init__(
        self,
        *,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        provider = get_provider("google")
        self.provider_id = provider.id
        self.default_base_url = provider.default_base_url
        self.timeout = timeout
        self._transport = transport

    def _endpoint(self, model: str, base_url: str | None, *, stream: bool) -> str:
        root = (base_url or self.default_base_url or "").strip()
        parsed = urlsplit(root)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ProviderAdapterError(
                "The provider base URL is invalid",
                provider=self.provider_id,
            )
        action = "streamGenerateContent" if stream else "generateContent"
        endpoint = f"{root.rstrip('/')}/models/{quote(model, safe='')}:"
        endpoint += action
        if stream:
            endpoint += "?alt=sse"
        return endpoint

    def _headers(self, api_key: str, *, stream: bool = False) -> dict[str, str]:
        if not api_key or not api_key.strip():
            raise ProviderAdapterError(
                "An API key is required",
                provider=self.provider_id,
            )
        return {
            "x-goog-api-key": api_key.strip(),
            "content-type": "application/json",
            "accept": "text/event-stream" if stream else "application/json",
        }

    @staticmethod
    def _payload(request: GenerationRequest) -> dict[str, Any]:
        contents: list[dict[str, Any]] = []
        system_parts = [{"text": request.system}] if request.system else []
        for message in request.messages:
            if message.role == "system":
                if message.content:
                    system_parts.append({"text": message.content})
                continue
            role = "model" if message.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": message.content}]})

        payload: dict[str, Any] = {"contents": contents}
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}

        generation_config: dict[str, Any] = {}
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        if request.max_tokens is not None:
            generation_config["maxOutputTokens"] = request.max_tokens
        if request.top_p is not None:
            generation_config["topP"] = request.top_p
        if request.stop:
            generation_config["stopSequences"] = request.stop
        if generation_config:
            payload["generationConfig"] = generation_config
        return payload

    def _raise_for_status(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise ProviderAdapterError(
                f"Provider request failed (HTTP {status})",
                provider=self.provider_id,
                status_code=status,
                retryable=status in {408, 409, 425, 429} or status >= 500,
            ) from None

    @staticmethod
    def _usage(data: Any) -> Usage | None:
        if not isinstance(data, dict):
            return None
        input_tokens = data.get("promptTokenCount")
        output_tokens = data.get("candidatesTokenCount")
        total = data.get("totalTokenCount")
        if input_tokens is None and output_tokens is None and total is None:
            return None
        return Usage(
            input_tokens=input_tokens if isinstance(input_tokens, int) else None,
            output_tokens=output_tokens if isinstance(output_tokens, int) else None,
            total_tokens=total if isinstance(total, int) else None,
        )

    @staticmethod
    def _candidate(data: dict[str, Any]) -> dict[str, Any]:
        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return {}
        return candidates[0] if isinstance(candidates[0], dict) else {}

    @staticmethod
    def _text(candidate: dict[str, Any]) -> str:
        content = candidate.get("content")
        if not isinstance(content, dict):
            return ""
        parts = content.get("parts")
        if not isinstance(parts, list):
            return ""
        return "".join(
            part.get("text", "")
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )

    def _normalize_result(
        self, data: dict[str, Any], requested_model: str
    ) -> GenerationResult:
        candidate = self._candidate(data)
        return GenerationResult(
            text=self._text(candidate),
            model=requested_model,
            provider=self.provider_id,
            finish_reason=candidate.get("finishReason"),
            usage=self._usage(data.get("usageMetadata")),
        )

    async def generate(
        self,
        request: GenerationRequest,
        *,
        api_key: str,
        base_url: str | None = None,
    ) -> GenerationResult:
        url = self._endpoint(request.model, base_url, stream=False)
        headers = self._headers(api_key)
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    url, headers=headers, json=self._payload(request)
                )
            self._raise_for_status(response)
            try:
                data = response.json()
            except ValueError:
                raise ProviderAdapterError(
                    "Provider returned an invalid JSON response",
                    provider=self.provider_id,
                ) from None
            if not isinstance(data, dict):
                raise ProviderAdapterError(
                    "Provider returned an invalid completion",
                    provider=self.provider_id,
                )
            return self._normalize_result(data, request.model)
        except ProviderAdapterError:
            raise
        except httpx.TimeoutException:
            raise ProviderAdapterError(
                "Provider request timed out",
                provider=self.provider_id,
                retryable=True,
            ) from None
        except httpx.RequestError:
            raise ProviderAdapterError(
                "Could not connect to the provider",
                provider=self.provider_id,
                retryable=True,
            ) from None

    async def stream(
        self,
        request: GenerationRequest,
        *,
        api_key: str,
        base_url: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        url = self._endpoint(request.model, base_url, stream=True)
        headers = self._headers(api_key, stream=True)
        final_sent = False

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self._transport
            ) as client:
                async with client.stream(
                    "POST", url, headers=headers, json=self._payload(request)
                ) as response:
                    self._raise_for_status(response)
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        raw_data = line[5:].strip()
                        if not raw_data or raw_data == "[DONE]":
                            continue
                        try:
                            data = json.loads(raw_data)
                        except json.JSONDecodeError:
                            raise ProviderAdapterError(
                                "Provider returned an invalid streaming event",
                                provider=self.provider_id,
                            ) from None
                        if not isinstance(data, dict):
                            continue
                        candidate = self._candidate(data)
                        text = self._text(candidate)
                        finish_reason = candidate.get("finishReason")
                        usage = self._usage(data.get("usageMetadata"))
                        if text or finish_reason is not None or usage is not None:
                            is_final = finish_reason is not None
                            yield StreamEvent(
                                text_delta=text,
                                finish_reason=finish_reason,
                                usage=usage,
                                is_final=is_final,
                            )
                            final_sent = final_sent or is_final

            if not final_sent:
                yield StreamEvent(is_final=True)
        except ProviderAdapterError:
            raise
        except httpx.TimeoutException:
            raise ProviderAdapterError(
                "Provider stream timed out",
                provider=self.provider_id,
                retryable=True,
            ) from None
        except httpx.RequestError:
            raise ProviderAdapterError(
                "Provider stream connection failed",
                provider=self.provider_id,
                retryable=True,
            ) from None
