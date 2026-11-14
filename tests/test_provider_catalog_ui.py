from pathlib import Path

from workspace.providers import list_providers


def test_every_registered_provider_is_available_in_provider_manager_ui():
    html = Path("frontend/settings.html").read_text(encoding="utf-8")
    for provider in list_providers():
        assert f'value="{provider["id"]}"' in html
