"""Provider registry for the multi-provider Workspace.

This module intentionally contains public provider metadata only. User API keys
must never be placed in this registry, returned by its API, or stored in the
browser. Credential persistence/encryption belongs in the per-user secrets
repository introduced with the API Manager.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


ApiStyle = Literal["openai", "anthropic", "google"]


@dataclass(frozen=True)
class ProviderDefinition:
    id: str
    name: str
    api_style: ApiStyle
    description: str
    default_base_url: str | None
    docs_url: str
    supports_streaming: bool = True
    supports_tools: bool = False
    supports_vision: bool = False
    supports_json_mode: bool = False
    accepts_custom_base_url: bool = False

    def public_dict(self) -> dict:
        """Safe metadata for clients; never includes credentials."""
        return asdict(self)


_PROVIDERS: tuple[ProviderDefinition, ...] = (
    ProviderDefinition(
        id="openai",
        name="OpenAI",
        api_style="openai",
        description="GPT modellari va OpenAI API.",
        default_base_url="https://api.openai.com/v1",
        docs_url="https://platform.openai.com/docs",
        supports_tools=True,
        supports_vision=True,
        supports_json_mode=True,
    ),
    ProviderDefinition(
        id="anthropic",
        name="Anthropic",
        api_style="anthropic",
        description="Claude modellari va Anthropic Messages API.",
        default_base_url="https://api.anthropic.com/v1",
        docs_url="https://docs.anthropic.com/",
        supports_tools=True,
        supports_vision=True,
    ),
    ProviderDefinition(
        id="google",
        name="Google Gemini",
        api_style="google",
        description="Gemini modellari va Google Generative Language API.",
        default_base_url="https://generativelanguage.googleapis.com/v1beta",
        docs_url="https://ai.google.dev/gemini-api/docs",
        supports_tools=True,
        supports_vision=True,
        supports_json_mode=True,
    ),
    ProviderDefinition(
        id="openrouter",
        name="OpenRouter",
        api_style="openai",
        description="Bitta API orqali ko'plab model provayderlariga ulanish.",
        default_base_url="https://openrouter.ai/api/v1",
        docs_url="https://openrouter.ai/docs",
        supports_tools=True,
        supports_vision=True,
        supports_json_mode=True,
    ),
    ProviderDefinition(
        id="custom_openai",
        name="Custom OpenAI-compatible",
        api_style="openai",
        description="OpenAI-compatible API endpointiga ega boshqa provayderlar.",
        default_base_url=None,
        docs_url="https://platform.openai.com/docs/api-reference",
        supports_tools=True,
        supports_vision=True,
        supports_json_mode=True,
        accepts_custom_base_url=True,
    ),
)

PROVIDER_BY_ID = {provider.id: provider for provider in _PROVIDERS}


def list_providers() -> list[dict]:
    """Return stable, public provider metadata for the Workspace UI."""
    return [provider.public_dict() for provider in _PROVIDERS]


def get_provider(provider_id: str) -> ProviderDefinition:
    """Resolve a provider or raise ValueError for an unknown identifier."""
    try:
        return PROVIDER_BY_ID[provider_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported provider: {provider_id}") from exc
