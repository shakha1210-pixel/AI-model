import pytest

from workspace.adapters.anthropic import AnthropicAdapter
from workspace.adapters.factory import get_provider_adapter
from workspace.adapters.google import GoogleGeminiAdapter
from workspace.adapters.openai_compatible import OpenAICompatibleAdapter


OPENAI_COMPATIBLE_PROVIDER_IDS = [
    "openai", "openrouter", "custom_openai", "mistral", "groq", "deepseek",
    "xai", "together", "fireworks", "cerebras", "perplexity", "sambanova",
    "huggingface", "nvidia", "deepinfra", "moonshot", "qwen", "novita",
    "nebius", "minimax", "zai", "ai21", "baseten",
]


@pytest.mark.parametrize("provider_id", OPENAI_COMPATIBLE_PROVIDER_IDS)
def test_factory_resolves_openai_compatible_providers(provider_id):
    assert isinstance(get_provider_adapter(provider_id), OpenAICompatibleAdapter)


def test_factory_resolves_native_provider_adapters():
    assert isinstance(get_provider_adapter("anthropic"), AnthropicAdapter)
    assert isinstance(get_provider_adapter("google"), GoogleGeminiAdapter)


def test_factory_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported provider"):
        get_provider_adapter("unknown-provider")
