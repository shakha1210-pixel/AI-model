"""Resolve provider IDs to their concrete adapter implementation."""
from __future__ import annotations

import httpx

from workspace.adapters.anthropic import AnthropicAdapter
from workspace.adapters.base import ProviderAdapter
from workspace.adapters.google import GoogleGeminiAdapter
from workspace.adapters.openai_compatible import OpenAICompatibleAdapter
from workspace.providers import get_provider


def get_provider_adapter(
    provider_id: str,
    *,
    timeout: float = 60.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ProviderAdapter:
    """Build an adapter from a provider registry ID.

    The factory stores no credentials. Pass the user's decrypted API key only
    to generate()/stream() after authorization and ownership checks.
    """
    provider = get_provider(provider_id)
    if provider.api_style == "openai":
        return OpenAICompatibleAdapter(
            provider_id, timeout=timeout, transport=transport
        )
    if provider.api_style == "anthropic":
        return AnthropicAdapter(timeout=timeout, transport=transport)
    if provider.api_style == "google":
        return GoogleGeminiAdapter(timeout=timeout, transport=transport)
    raise ValueError(f"No adapter registered for provider: {provider_id}")
