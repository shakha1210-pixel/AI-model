from workspace.providers import get_provider, list_providers


EXPECTED_PROVIDER_IDS = {
    "openai", "anthropic", "google", "openrouter", "custom_openai",
    "mistral", "groq", "deepseek", "xai", "together", "fireworks",
    "cerebras", "perplexity", "sambanova", "huggingface", "nvidia",
    "deepinfra", "moonshot", "qwen", "novita", "nebius", "minimax",
    "zai", "ai21", "baseten",
}


def test_provider_registry_contains_native_and_openai_compatible_options():
    providers = {item["id"]: item for item in list_providers()}

    assert EXPECTED_PROVIDER_IDS <= set(providers)
    assert providers["openrouter"]["api_style"] == "openai"
    assert providers["anthropic"]["api_style"] == "anthropic"
    assert providers["google"]["api_style"] == "google"
    assert providers["custom_openai"]["accepts_custom_base_url"] is True

    for provider_id in EXPECTED_PROVIDER_IDS - {"anthropic", "google"}:
        assert providers[provider_id]["api_style"] == "openai"


def test_provider_lookup_returns_definition_and_default_endpoint():
    assert get_provider("openai").name == "OpenAI"
    assert get_provider("groq").default_base_url == "https://api.groq.com/openai/v1"
    assert get_provider("deepseek").default_base_url == "https://api.deepseek.com/v1"


def test_unknown_provider_is_rejected():
    try:
        get_provider("not-a-provider")
    except ValueError as exc:
        assert "Unsupported provider" in str(exc)
    else:
        raise AssertionError("Unknown provider must be rejected")
