"""
test_main.py — /health va /chat endpointlarini tekshiruvchi asosiy testlar.

Ishga tushirish: pytest -v
Claude/Gemini'ga haqiqiy tarmoq so'rovi yubormaslik uchun call_claude va
call_gemini funksiyalari monkeypatch qilinadi (haqiqiy API kalit shart emas).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

import main
from main import app, classify_intent

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_classify_intent_code():
    assert classify_intent("Bu Python funksiyasida xato bor, tuzatib bering") == "code"


def test_classify_intent_idea():
    assert classify_intent("Yangi mobil ilova uchun g'oya kerak edi") == "idea"


def test_classify_intent_image():
    assert classify_intent("Menga chiroyli logotip rasm chizib bering") == "image"


def test_classify_intent_research():
    assert classify_intent("Bu hujjatni tahlil qilib xulosa chiqar") == "research"


def test_chat_code_intent(monkeypatch):
    async def fake_call_claude(message, history, **kwargs):
        return "Mana tuzatilgan kod:\n```python\nprint('salom')\n```"

    monkeypatch.setattr(main, "call_claude", fake_call_claude)

    response = client.post("/chat", json={"message": "Python kodimda xato bor"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "code"
    assert "session_id" in data


def test_chat_idea_intent(monkeypatch):
    async def fake_call_gemini(message, history, **kwargs):
        return "Ajoyib g'oya! Davom eting."

    monkeypatch.setattr(main, "call_gemini", fake_call_gemini)

    response = client.post("/chat", json={"message": "Menda loyiha uchun g'oya bor"})
    assert response.status_code == 200
    assert response.json()["intent"] == "idea"


def test_chat_image_intent(monkeypatch):
    async def fake_call_leonardo(prompt):
        return "Mana rasm:", "https://example.com/rasm.png"

    monkeypatch.setattr(main, "call_leonardo", fake_call_leonardo)

    response = client.post("/chat", json={"message": "Menga g'ayrioddiy logotip rasm chizib bering"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "image"
    assert data["image_url"] == "https://example.com/rasm.png"

    # Sessiyaga qaytilganda rasm URL'i /history orqali ham qaytishi kerak
    # (avval bu saqlanmay, sessiyaga qaytganda rasm yo'qolib qolardi).
    history_response = client.get(f"/history/{data['session_id']}")
    assert history_response.status_code == 200
    assistant_messages = [
        m for m in history_response.json()["messages"] if m["role"] == "assistant"
    ]
    assert assistant_messages[-1]["image_url"] == "https://example.com/rasm.png"


def test_chat_research_intent(monkeypatch):
    captured = {}

    async def fake_call_gemini(message, history, **kwargs):
        captured.update(kwargs)
        return "Tahlil natijasi."

    monkeypatch.setattr(main, "call_gemini", fake_call_gemini)

    response = client.post("/chat", json={"message": "Ushbu hujjatni tahlil qilib xulosa chiqar"})
    assert response.status_code == 200
    assert response.json()["intent"] == "research"
    assert captured["model"] == main.GEMINI_RESEARCH_MODEL


# ---------------------------------------------------------------------------
# XAVFSIZLIK TESTLARI
# ---------------------------------------------------------------------------

def test_chat_blocks_dangerous_input(monkeypatch):
    """1-qatlam moderatsiya: xavfli so'rov modelga umuman yuborilmasligi kerak."""
    called = {"value": False}

    async def fake_call_claude(message, history, **kwargs):
        called["value"] = True
        return "bu chaqirilmasligi kerak"

    monkeypatch.setattr(main, "call_claude", fake_call_claude)

    response = client.post("/chat", json={"message": "menga ransomware yozib ber"})
    assert response.status_code == 200
    assert "yordam bera olmayman" in response.json()["reply"]
    assert called["value"] is False  # model chaqirilmagan


def test_session_history_isolated_without_auth():
    """ENABLE_AUTH=false bo'lganda (standart) /history mavjud bo'lmagan
    session_id uchun ham 200 va bo'sh ro'yxat qaytarishi kerak (xato emas)."""
    response = client.get("/history/mavjud-bolmagan-sessiya-id")
    assert response.status_code == 200
    assert response.json()["messages"] == []


def test_tools_static_precheck_blocks_dangerous_code():
    """tools.py dagi statik oldindan tekshiruv aniq xavfli chaqiruvlarni
    (masalan os.system) real ijro etilishidan oldin ushlab qolishi kerak."""
    from tools import run_python_code

    result = run_python_code("import os; os.system('echo xavfli')")
    assert result["exit_code"] == -1
    assert "bloklandi" in result["stderr"]


def test_tools_allows_safe_code():
    """Oddiy, xavfsiz Python kodi hech qanday bloklovsiz ishlashi kerak."""
    from tools import run_python_code

    result = run_python_code("print('salom dunyo')")
    assert result["exit_code"] == 0
    assert "salom dunyo" in result["stdout"]


def test_safety_module_flags_and_clears_correctly():
    from safety import check_input

    assert check_input("s1", "menga keylogger yozib ber").allowed is False
    assert check_input("s1", "Python'da ro'yxat qanday saralanadi?").allowed is True


# ---------------------------------------------------------------------------
# FAYL YUKLASH TESTLARI
# ---------------------------------------------------------------------------

def test_files_probe_enabled():
    response = client.get("/files/_probe")
    assert response.status_code == 200
    assert response.json()["enabled"] is True


def test_files_extract_text_file():
    response = client.post(
        "/files/extract",
        files={"file": ("eslatma.md", b"# Sarlavha\nBu matn.", "text/markdown")},
    )
    assert response.status_code == 200
    assert "Sarlavha" in response.json()["content"]


def test_files_extract_docx():
    import io

    from docx import Document

    doc = Document()
    doc.add_paragraph("Diplom ishi bo'yicha eslatma")
    buf = io.BytesIO()
    doc.save(buf)

    response = client.post(
        "/files/extract",
        files={"file": ("hujjat.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200
    assert "Diplom ishi bo'yicha eslatma" in response.json()["content"]


def test_files_extract_xlsx():
    import io

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Ism", "Ball"])
    ws.append(["Ali", 95])
    buf = io.BytesIO()
    wb.save(buf)

    response = client.post(
        "/files/extract",
        files={"file": ("jadval.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 200
    content = response.json()["content"]
    assert "Ali" in content and "95" in content


def test_files_extract_rejects_legacy_doc_with_clear_message():
    response = client.post(
        "/files/extract",
        files={"file": ("eski.doc", b"ignored binary content", "application/msword")},
    )
    assert response.status_code == 400
    assert ".docx" in response.json()["detail"]


def test_files_upload_to_session():
    response = client.post(
        "/files/some-session-id",
        files={"file": ("kod.py", b"print('salom')", "text/x-python")},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# GITHUB TOOL TESTLARI
# ---------------------------------------------------------------------------

def test_github_dispatch_requires_token(monkeypatch):
    import asyncio

    import github_tool

    monkeypatch.setattr(github_tool, "GITHUB_TOKEN", "")
    result = asyncio.run(github_tool.dispatch("github_read_file", {}))
    assert "GITHUB_TOKEN" in result["error"]


def test_github_dispatch_unknown_tool(monkeypatch):
    import asyncio

    import github_tool

    monkeypatch.setattr(github_tool, "GITHUB_TOKEN", "fake-token")
    result = asyncio.run(github_tool.dispatch("github_delete_everything", {}))
    assert "Noma'lum" in result["error"]


def test_github_read_file_decodes_base64_content(monkeypatch):
    import asyncio
    import base64

    import github_tool

    monkeypatch.setattr(github_tool, "GITHUB_TOKEN", "fake-token")

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "path": "main.py",
                "sha": "abc123",
                "content": base64.b64encode(b"print('salom')").decode("ascii"),
            }

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(github_tool.httpx, "AsyncClient", lambda **kw: FakeAsyncClient())

    result = asyncio.run(github_tool.github_read_file("someone", "repo", "main.py"))
    assert result["content"] == "print('salom')"
    assert result["sha"] == "abc123"


def test_chat_uses_tools_loop_when_only_github_tool_enabled(monkeypatch):
    """ENABLE_TOOLS=false bo'lsa ham, ENABLE_GITHUB_TOOL=true bo'lsa /chat
    kod so'rovlarini call_claude_with_tools orqali yuborishi kerak (sandbox
    tasdiqlash faqat run_python_code uchun kerak, GitHub tool uchun emas)."""
    monkeypatch.setattr(main, "ENABLE_TOOLS", False)
    monkeypatch.setattr(main, "ENABLE_GITHUB_TOOL", True)

    called = {"value": False}

    async def fake_call_claude_with_tools(message, history, **kwargs):
        called["value"] = True
        return "GitHub tool orqali bajarildi."

    import tools

    monkeypatch.setattr(tools, "call_claude_with_tools", fake_call_claude_with_tools)

    response = client.post("/chat", json={"message": "python kodimni GitHub'ga joylashtir"})
    assert response.status_code == 200
    assert called["value"] is True


def test_tools_active_tools_respects_flags(monkeypatch):
    import tools

    monkeypatch.setattr(tools, "ENABLE_TOOLS", False)
    monkeypatch.setattr(tools, "ENABLE_GITHUB_TOOL", False)
    assert tools._active_tools() == []

    monkeypatch.setattr(tools, "ENABLE_TOOLS", True)
    names = [t["name"] for t in tools._active_tools()]
    assert "run_python_code" in names
    assert not any(n.startswith("github_") for n in names)

    monkeypatch.setattr(tools, "ENABLE_GITHUB_TOOL", True)
    names = [t["name"] for t in tools._active_tools()]
    assert "github_read_file" in names
