"""OpenAI Chat Completions adapter shared by compatible providers.

Credentials are supplied per request and are never retained on this adapter.
Custom endpoint network policy (including SSRF protection) must be enforced by
the API Manager before a base URL reaches this module.
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


class OpenAICompatibleAdapter:
    """Adapter for OpenAI Chat Completions-compatible HTTP APIs."""

    def __init__(
        self,
        provider_id: str = "openai",
        *,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        provider = get_provider(provider_id)
        if provider.api_style != "openai":
            raise ValueError(
                f"Provider {provider_id!r} does not use the OpenAI API style"
            )
        self.provider_id = provider.id
        self.default_base_url = provider.default_base_url
        self.timeout = timeout
        # Transport injection supports deterministic tests; it carries no user
        # credential and can be omitted in production.
        self._transport = transport

    def _endpoint(self, base_url: str | None) -> str:
        root = (base_url or self.default_base_url or "").strip()
        if not root:
            raise ProviderAdapterError(
                "A base URL is required for this provider",
                provider=self.provider_id,
            )

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
        return root.rstrip("/") + "/chat/completions"

    def _headers(self, api_key: str) -> dict[str, str]:
        if not api_key or not api_key.strip():
            raise ProviderAdapterError(
                "An API key is required",
                provider=self.provider_id,
            )
        return {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _payload(self, request: GenerationRequest, *, stream: bool) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.extend(
            {"role": message.role, "content": message.content}
            for message in request.messages
        )

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "stream": stream,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.stop:
            payload["stop"] = request.stop
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
        prompt = data.get("prompt_tokens")
        completion = data.get("completion_tokens")
        total = data.get("total_tokens")
        if prompt is None and completion is None and total is None:
            return None
        return Usage(
            input_tokens=prompt if isinstance(prompt, int) else None,
            output_tokens=completion if isinstance(completion, int) else None,
            total_tokens=total if isinstance(total, int) else None,
        )

    @staticmethod
    def _text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            ]
            return "".join(parts)
        return ""

    def _normalize_result(self, data: dict[str, Any], requested_model: str) -> GenerationResult:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderAdapterError(
                "Provider returned an empty completion",
                provider=self.provider_id,
            )
        choice = choices[0] if isinstance(choices[0], dict) else {}
        message = choice.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        return GenerationResult(
            text=self._text(content),
            model=data.get("model") or requested_model,
            provider=self.provider_id,
            finish_reason=choice.get("finish_reason"),
            usage=self._usage(data.get("usage")),
        )

    async def generate(
        self,
        request: GenerationRequest,
        *,
        api_key: str,
        base_url: str | None = None,
    ) -> GenerationResult:
        """Send a non-streaming chat completion request."""
        url = self._endpoint(base_url)
        headers = self._headers(api_key)
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=self._payload(request, stream=False),
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
        """Stream Server-Sent Events and normalize text/finish/usage events."""
        url = self._endpoint(base_url)
        headers = self._headers(api_key)
        headers["Accept"] = "text/event-stream"
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
                        if not line or line.startswith(":") or not line.startswith("data:"):
                            continue
                        raw_data = line[5:].strip()
                        if raw_data == "[DONE]":
                            yield StreamEvent(is_final=True)
                            final_sent = True
                            break
                        try:
                            data = json.loads(raw_data)
                        except json.JSONDecodeError:
                            raise ProviderAdapterError(
                                "Provider returned an invalid streaming event",
                                provider=self.provider_id,
                            ) from None
                        if not isinstance(data, dict):
                            continue

                        choices = data.get("choices") or []
                        choice = choices[0] if choices and isinstance(choices[0], dict) else {}
                        delta = choice.get("delta") or {}
                        content = self._text(delta.get("content")) if isinstance(delta, dict) else ""
                        finish_reason = choice.get("finish_reason")
                        usage = self._usage(data.get("usage"))
                        if content or finish_reason is not None or usage is not None:
                            is_final = finish_reason is not None
                            yield StreamEvent(
                                text_delta=content,
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
