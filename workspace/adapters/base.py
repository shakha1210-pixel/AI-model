"""Provider-independent contracts for model adapters.

Adapters translate normalized Workspace requests to provider-specific APIs.
They must not own credentials, persist secrets, or log request headers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol, runtime_checkable


@dataclass(frozen=True)
class ModelMessage:
    role: str
    content: str


@dataclass(frozen=True)
class GenerationRequest:
    model: str
    messages: list[ModelMessage]
    system: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    stop: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class GenerationResult:
    text: str
    model: str
    provider: str
    finish_reason: str | None = None
    usage: Usage | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class StreamEvent:
    """Normalized streaming event; text_delta is the common happy path."""
    text_delta: str = ""
    finish_reason: str | None = None
    usage: Usage | None = None
    is_final: bool = False


class ProviderAdapterError(Exception):
    """Safe, provider-neutral error. Never include API keys in its message."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable


@runtime_checkable
class ProviderAdapter(Protocol):
    """Contract implemented by each provider integration.

    Implementations receive credentials at call time from the server-side
    credential service. They must never retain them on shared adapter objects.
    """

    provider_id: str

    async def generate(
        self, request: GenerationRequest, *, api_key: str, base_url: str | None = None
    ) -> GenerationResult:
        """Generate one complete response."""
        ...

    def stream(
        self, request: GenerationRequest, *, api_key: str, base_url: str | None = None
    ) -> AsyncIterator[StreamEvent]:
        """Stream normalized events from the provider."""
        ...
