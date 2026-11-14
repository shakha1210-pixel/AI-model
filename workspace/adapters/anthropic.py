"""Anthropic Messages API adapter.

API keys are supplied for each call and are never retained on this object.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlsplit

import httpx

from workspace.adapters.base import (
    GenerationRequest,
    GenerationResult,
    ProviderAdapterError,
    StreamEvent,
    Usage,
)
from workspace.providers import get_provider


class AnthropicAdapter:
    """Adapter for the Anthropic Messages API."""

    API_VERSION = "2023-06-01"

    def __init__(
        self,
        *,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        provider = get_provider("anthropic")
        self.provider_id = provider.id
        self.default_base_url = provider.default_base_url
        self.timeout = timeout
        self._transport = transport

    def _endpoint(self, base_url: str | None) -> str:
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
        return root.rstrip("/") + "/messages"

    def _headers(self, api_key: str) -> dict[str, str]:
        if not api_key or not api_key.strip():
            raise ProviderAdapterError(
                "An API key is required",
                provider=self.provider_id,
            )
        return {
            "x-api-key": api_key.strip(),
            "anthropic-version": self.API_VERSION,
            "content-type": "application/json",
            "accept": "application/json",
        }

    @staticmethod
    def _messages(request: GenerationRequest) -> tuple[str | None, list[dict[str, str]]]:
        system_parts = [request.system] if request.system else []
        messages: list[dict[str, str]] = []
        for message in request.messages:
            if message.role == "system":
                if message.content:
                    system_parts.append(message.content)
                continue
            role = "assistant" if message.role == "assistant" else "user"
            messages.append({"role": role, "content": message.content})
        system = "\n\n".join(system_parts) or None
        return system, messages

    def _payload(self, request: GenerationRequest, *, stream: bool) -> dict[str, Any]:
        system, messages = self._messages(request)
        payload: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens or 1024,
            "messages": messages,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.stop:
            payload["stop_sequences"] = request.stop
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
        input_tokens = data.get("input_tokens")
        output_tokens = data.get("output_tokens")
        if input_tokens is None and output_tokens is None:
            return None
        input_value = input_tokens if isinstance(input_tokens, int) else None
        output_value = output_tokens if isinstance(output_tokens, int) else None
        total = (
            input_value + output_value
            if input_value is not None and output_value is not None
            else None
        )
        return Usage(
            input_tokens=input_value,
            output_tokens=output_value,
            total_tokens=total,
        )

    @staticmethod
    def _text(content: Any) -> str:
        if not isinstance(content, list):
            return ""
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        )

    def _normalize_result(
        self, data: dict[str, Any], requested_model: str
    ) -> GenerationResult:
        return GenerationResult(
            text=self._text(data.get("content")),
            model=data.get("model") or requested_model,
            provider=self.provider_id,
            finish_reason=data.get("stop_reason"),
            usage=self._usage(data.get("usage")),
        )

    async def generate(
        self,
        request: GenerationRequest,
        *,
        api_key: str,
        base_url: str | None = None,
    ) -> GenerationResult:
        url = self._endpoint(base_url)
        headers = self._headers(api_key)
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    url, headers=headers, json=self._payload(request, stream=False)
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
        url = self._endpoint(base_url)
        headers = self._headers(api_key)
        headers["accept"] = "text/event-stream"
        input_tokens: int | None = None
        output_tokens: int | None = None
        final_sent = False

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self._transport
            ) as client:
                async with client.stream(
                    "POST",
                    url,
                    headers=headers,
                    json=self._payload(request, stream=True),
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

                        event_type = data.get("type")
                        if event_type == "message_start":
                            usage_data = (data.get("message") or {}).get("usage", {})
                            value = usage_data.get("input_tokens")
                            if isinstance(value, int):
                                input_tokens = value
                        elif event_type == "content_block_delta":
                            delta = data.get("delta") or {}
                            text = (
                                delta.get("text", "")
                                if delta.get("type") == "text_delta"
                                else ""
                            )
                            if text:
                                yield StreamEvent(text_delta=text)
                        elif event_type == "message_delta":
                            delta = data.get("delta") or {}
                            usage_data = data.get("usage") or {}
                            value = usage_data.get("output_tokens")
                            if isinstance(value, int):
                                output_tokens = value
                            usage = None
                            if input_tokens is not None or output_tokens is not None:
                                total = (
                                    input_tokens + output_tokens
                                    if input_tokens is not None and output_tokens is not None
                                    else None
                                )
                                usage = Usage(
                                    input_tokens=input_tokens,
                                    output_tokens=output_tokens,
                                    total_tokens=total,
                                )
                            finish_reason = delta.get("stop_reason")
                            if finish_reason is not None or usage is not None:
                                yield StreamEvent(
                                    finish_reason=finish_reason,
                                    usage=usage,
                                    is_final=finish_reason is not None,
                                )
                                final_sent = final_sent or finish_reason is not None
                        elif event_type == "message_stop":
                            yield StreamEvent(is_final=True)
                            final_sent = True
                            break

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
