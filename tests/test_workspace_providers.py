from workspace.providers import get_provider, list_providers


def test_provider_registry_contains_initial_and_compatible_options():
    providers = {item["id"]: item for item in list_providers()}

    assert {"openai", "anthropic", "google", "openrouter", "custom_openai"} <= set(providers)
    assert providers["openrouter"]["api_style"] == "openai"
    assert providers["anthropic"]["api_style"] == "anthropic"
    assert providers["google"]["api_style"] == "google"
    assert providers["custom_openai"]["accepts_custom_base_url"] is True


def test_provider_lookup_returns_definition():
    assert get_provider("openai").name == "OpenAI"


def test_unknown_provider_is_rejected():
    try:
        get_provider("not-a-provider")
    except ValueError as exc:
        assert "Unsupported provider" in str(exc)
    else:
        raise AssertionError("Unknown provider must be rejected")
