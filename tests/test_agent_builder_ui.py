from pathlib import Path


def test_agent_builder_ui_is_wired_to_authenticated_api():
    html = Path("frontend/settings.html").read_text(encoding="utf-8")
    script = Path("frontend/agent-manager.js").read_text(encoding="utf-8")

    assert 'id="agent-form"' in html
    assert 'id="agent-list"' in html
    assert 'src="agent-manager.js?v=1"' in html
    assert '"/api/workspace/agents"' in script
    assert '"/api/workspace/connections"' in script
    assert "localStorage" not in script
    assert "textContent" in script
    assert "data-run-agent" in script
    assert '"/run"' in script


def test_agent_builder_permissions_match_backend_allow_list():
    html = Path("frontend/settings.html").read_text(encoding="utf-8")
    for permission in (
        "project_files.read",
        "project_files.write",
        "web.search",
        "git.read",
        "git.write",
        "code.execute",
    ):
        assert f'value="{permission}"' in html


def test_agent_builder_translation_keys_exist_in_all_six_languages():
    translations = Path("frontend/i18n.js").read_text(encoding="utf-8")
    assert translations.count('"settings.agents.title"') == 6
    assert translations.count('"settings.agents.runtimeNotice"') == 6
    assert translations.count('"settings.agents.runPlaceholder"') == 6
    assert translations.count('"settings.agents.runHint"') == 6
