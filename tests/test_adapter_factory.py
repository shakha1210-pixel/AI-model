import pytest

from workspace.adapters.anthropic import AnthropicAdapter
from workspace.adapters.factory import get_provider_adapter
from workspace.adapters.google import GoogleGeminiAdapter
from workspace.adapters.openai_compatible import OpenAICompatibleAdapter


@pytest.mark.parametrize(
    ("provider_id", "adapter_type"),
    [
        ("openai", OpenAICompatibleAdapter),
        ("openrouter", OpenAICompatibleAdapter),
        ("custom_openai", OpenAICompatibleAdapter),
        ("anthropic", AnthropicAdapter),
        ("google", GoogleGeminiAdapter),
    ],
)
def test_factory_resolves_every_registered_provider(provider_id, adapter_type):
    adapter = get_provider_adapter(provider_id)

    assert isinstance(adapter, adapter_type)


def test_factory_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported provider"):
        get_provider_adapter("unknown-provider")
