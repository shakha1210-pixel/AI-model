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
    ProviderDefinition(
        id="mistral",
        name="Mistral AI",
        api_style="openai",
        description="Mistral va Codestral modellari.",
        default_base_url="https://api.mistral.ai/v1",
        docs_url="https://docs.mistral.ai/",
    ),
    ProviderDefinition(
        id="groq",
        name="Groq",
        api_style="openai",
        description="Groq tezkor inference platformasi.",
        default_base_url="https://api.groq.com/openai/v1",
        docs_url="https://console.groq.com/docs",
    ),
    ProviderDefinition(
        id="deepseek",
        name="DeepSeek",
        api_style="openai",
        description="DeepSeek chat va reasoning modellari.",
        default_base_url="https://api.deepseek.com/v1",
        docs_url="https://api-docs.deepseek.com/",
    ),
    ProviderDefinition(
        id="xai",
        name="xAI",
        api_style="openai",
        description="Grok modellari va xAI API.",
        default_base_url="https://api.x.ai/v1",
        docs_url="https://docs.x.ai/",
    ),
    ProviderDefinition(
        id="together",
        name="Together AI",
        api_style="openai",
        description="Ochiq modellar uchun Together AI inference.",
        default_base_url="https://api.together.ai/v1",
        docs_url="https://docs.together.ai/",
    ),
    ProviderDefinition(
        id="fireworks",
        name="Fireworks AI",
        api_style="openai",
        description="Fireworks AI serverless model inference.",
        default_base_url="https://api.fireworks.ai/inference/v1",
        docs_url="https://docs.fireworks.ai/",
    ),
    ProviderDefinition(
        id="cerebras",
        name="Cerebras",
        api_style="openai",
        description="Cerebras inference API.",
        default_base_url="https://api.cerebras.ai/v1",
        docs_url="https://inference-docs.cerebras.ai/",
    ),
    ProviderDefinition(
        id="perplexity",
        name="Perplexity",
        api_style="openai",
        description="Sonar qidiruvga yo'naltirilgan modellar.",
        default_base_url="https://api.perplexity.ai",
        docs_url="https://docs.perplexity.ai/",
    ),
    ProviderDefinition(
        id="sambanova",
        name="SambaNova",
        api_style="openai",
        description="SambaNova Cloud inference API.",
        default_base_url="https://api.sambanova.ai/v1",
        docs_url="https://docs.sambanova.ai/",
    ),
    ProviderDefinition(
        id="huggingface",
        name="Hugging Face",
        api_style="openai",
        description="Hugging Face Inference Router.",
        default_base_url="https://router.huggingface.co/v1",
        docs_url="https://huggingface.co/docs/api-inference/",
    ),
    ProviderDefinition(
        id="nvidia",
        name="NVIDIA NIM",
        api_style="openai",
        description="NVIDIA hosted NIM inference endpoints.",
        default_base_url="https://integrate.api.nvidia.com/v1",
        docs_url="https://docs.api.nvidia.com/nim/",
    ),
    ProviderDefinition(
        id="deepinfra",
        name="DeepInfra",
        api_style="openai",
        description="DeepInfra serverless model inference.",
        default_base_url="https://api.deepinfra.com/v1/openai",
        docs_url="https://deepinfra.com/docs",
    ),
    ProviderDefinition(
        id="moonshot",
        name="Moonshot AI",
        api_style="openai",
        description="Kimi modellari uchun OpenAI-compatible API.",
        default_base_url="https://api.moonshot.ai/v1",
        docs_url="https://platform.moonshot.ai/docs",
    ),
    ProviderDefinition(
        id="qwen",
        name="Qwen / DashScope",
        api_style="openai",
        description="Alibaba Cloud Model Studio OpenAI-compatible API.",
        default_base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        docs_url="https://www.alibabacloud.com/help/en/model-studio/",
    ),
    ProviderDefinition(
        id="novita",
        name="Novita AI",
        api_style="openai",
        description="Novita AI OpenAI-compatible inference.",
        default_base_url="https://api.novita.ai/openai/v1",
        docs_url="https://novita.ai/docs",
    ),
    ProviderDefinition(
        id="nebius",
        name="Nebius Token Factory",
        api_style="openai",
        description="Nebius Token Factory model inference.",
        default_base_url="https://api.tokenfactory.nebius.com/v1",
        docs_url="https://docs.tokenfactory.nebius.com/",
    ),
    ProviderDefinition(
        id="minimax",
        name="MiniMax",
        api_style="openai",
        description="MiniMax model API.",
        default_base_url="https://api.minimax.io/v1",
        docs_url="https://platform.minimax.io/docs",
    ),
    ProviderDefinition(
        id="zai",
        name="Z.AI / GLM",
        api_style="openai",
        description="GLM models via Z.AI OpenAI-compatible API.",
        default_base_url="https://api.z.ai/api/paas/v4",
        docs_url="https://docs.z.ai/",
    ),
    ProviderDefinition(
        id="ai21",
        name="AI21 Labs",
        api_style="openai",
        description="AI21 Jamba models and API.",
        default_base_url="https://api.ai21.com/studio/v1",
        docs_url="https://docs.ai21.com/",
    ),
    ProviderDefinition(
        id="baseten",
        name="Baseten",
        api_style="openai",
        description="Baseten hosted model inference.",
        default_base_url="https://inference.baseten.co/v1",
        docs_url="https://docs.baseten.co/",
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
