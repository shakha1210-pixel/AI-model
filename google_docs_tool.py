"""
google_docs_tool.py — Claude uchun Google Docs bilan ishlash tool'i va
unga bog'liq OAuth ulanish oqimi.

Bu tool ENABLE_AUTH/ENABLE_DATABASE'ga BOG'LIQ EMAS — sessiya (session_id)
darajasida ishlaydi: har bir brauzer sessiyasi o'z Google hisobini
GET /google-docs/connect/{session_id} orqali bir marta ulaydi, so'ng shu
sessiyada Claude google_docs_* tool'laridan foydalana oladi.

Yoqish: .env faylida ENABLE_GOOGLE_DOCS_TOOL=true qiling. GOOGLE_CLIENT_ID
va GOOGLE_CLIENT_SECRET auth.py bilan BIR XIL OAuth client'dan qayta
ishlatiladi (Google Cloud Console'da alohida client yaratish shart emas).
DIQQAT: shu OAuth client'ning Cloud Console > Clients > Authorized redirect
URIs ro'yxatiga quyidagi GOOGLE_DOCS_REDIRECT_URI qiymatini QO'SHISH kerak —
mavjud login redirect URI'ni o'chirmang, ikkalasi ham kerak bo'ladi.

Tokenlar xotirada (RAM) saqlanadi — server qayta ishga tushsa, foydalanuvchi
qayta ulanishi kerak bo'ladi. Ko'p nusxali (replika) deploy uchun Redis
kabi umumiy xotiraga o'tkazish tavsiya etiladi.
"""

import datetime
import os
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

# auth.py dagi bilan bir xil OAuth client (aylanma import'dan qochish uchun
# .env orqali mustaqil o'qiladi).
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_DOCS_REDIRECT_URI = os.getenv(
    "GOOGLE_DOCS_REDIRECT_URI", "http://127.0.0.1:8000/google-docs/callback"
)
FRONTEND_DOCS_SUCCESS_URL = os.getenv(
    "FRONTEND_DOCS_SUCCESS_URL", "http://127.0.0.1:8000/settings.html"
)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
DOCS_API_URL = "https://docs.googleapis.com/v1/documents"
DOCS_SCOPE = "https://www.googleapis.com/auth/documents"

router = APIRouter()

GOOGLE_DOCS_TOOLS = [
    {
        "name": "google_docs_read",
        "description": "Google Docs hujjatining matnini o'qiydi (document_id orqali).",
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "Google Docs hujjat ID'si (hujjat URL'idagi /d/...../edit orasidagi qism)",
                },
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "google_docs_create",
        "description": (
            "Yangi Google Docs hujjatini beriladigan sarlavha va matn bilan "
            "yaratadi va hujjat havolasini qaytaradi."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Hujjat sarlavhasi"},
                "content": {"type": "string", "description": "Hujjatga yoziladigan matn"},
            },
            "required": ["title", "content"],
        },
    },
]

# session_id -> {"access_token", "expires_at", "refresh_token"(ixtiyoriy)}
_session_tokens: dict[str, dict] = {}


def is_connected(session_id: str) -> bool:
    return session_id in _session_tokens


@router.get("/google-docs/connect/{session_id}")
def google_docs_connect(session_id: str) -> RedirectResponse:
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID sozlanmagan. .env faylini to'ldiring.")
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_DOCS_REDIRECT_URI,
        "response_type": "code",
        "scope": DOCS_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": session_id,
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/google-docs/status/{session_id}")
def google_docs_status(session_id: str) -> dict:
    return {"connected": is_connected(session_id)}


@router.get("/google-docs/callback")
async def google_docs_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    """Google foydalanuvchini shu manzilga qaytaradi (?code=...&state=session_id)."""
    if error or not code or not state:
        raise HTTPException(status_code=400, detail=f"Google Docs ulash bekor qilindi: {error}")

    async with httpx.AsyncClient(timeout=20) as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_DOCS_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
    if token_response.status_code != 200:
        raise HTTPException(status_code=502, detail="Google token olishda xatolik yuz berdi.")
    data = token_response.json()

    expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=data.get("expires_in", 3600))
    entry = {"access_token": data["access_token"], "expires_at": expires_at}
    # Google refresh_token'ni FAQAT birinchi ulanishda (prompt=consent bilan)
    # qaytaradi — keyingi qayta ulanishlarda avvalgisini saqlab qolamiz.
    if data.get("refresh_token"):
        entry["refresh_token"] = data["refresh_token"]
    elif state in _session_tokens and "refresh_token" in _session_tokens[state]:
        entry["refresh_token"] = _session_tokens[state]["refresh_token"]
    _session_tokens[state] = entry

    return RedirectResponse(f"{FRONTEND_DOCS_SUCCESS_URL}?google_docs=connected")


async def _refresh_access_token(session_id: str) -> str | None:
    entry = _session_tokens.get(session_id)
    if not entry or "refresh_token" not in entry:
        return None
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "refresh_token": entry["refresh_token"],
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "grant_type": "refresh_token",
            },
        )
    if res.status_code != 200:
        return None
    data = res.json()
    entry["access_token"] = data["access_token"]
    entry["expires_at"] = datetime.datetime.utcnow() + datetime.timedelta(seconds=data.get("expires_in", 3600))
    return entry["access_token"]


async def _get_access_token(session_id: str) -> str | None:
    entry = _session_tokens.get(session_id)
    if not entry:
        return None
    if datetime.datetime.utcnow() >= entry["expires_at"] - datetime.timedelta(seconds=30):
        return await _refresh_access_token(session_id)
    return entry["access_token"]


def _docs_error(res: httpx.Response) -> dict:
    return {"error": f"Google Docs API xatosi ({res.status_code}): {res.text}"}


async def google_docs_read(session_id: str, document_id: str) -> dict:
    token = await _get_access_token(session_id)
    if not token:
        return {"error": "Google Docs ulanmagan. Avval sozlamalar sahifasidan ulang."}
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.get(f"{DOCS_API_URL}/{document_id}", headers={"Authorization": f"Bearer {token}"})
    if res.status_code != 200:
        return _docs_error(res)
    data = res.json()
    text_parts: list[str] = []
    for element in data.get("body", {}).get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        for run in paragraph.get("elements", []):
            text_run = run.get("textRun")
            if text_run:
                text_parts.append(text_run.get("content", ""))
    return {"title": data.get("title", ""), "content": "".join(text_parts)[:8000]}


async def google_docs_create(session_id: str, title: str, content: str) -> dict:
    token = await _get_access_token(session_id)
    if not token:
        return {"error": "Google Docs ulanmagan. Avval sozlamalar sahifasidan ulang."}
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=20) as client:
        create_res = await client.post(DOCS_API_URL, headers=headers, json={"title": title})
        if create_res.status_code != 200:
            return _docs_error(create_res)
        document_id = create_res.json()["documentId"]

        if content:
            update_res = await client.post(
                f"{DOCS_API_URL}/{document_id}:batchUpdate",
                headers=headers,
                json={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]},
            )
            if update_res.status_code != 200:
                return _docs_error(update_res)

    return {
        "status": "ok",
        "document_id": document_id,
        "url": f"https://docs.google.com/document/d/{document_id}/edit",
    }


_HANDLERS = {
    "google_docs_read": google_docs_read,
    "google_docs_create": google_docs_create,
}


async def dispatch(name: str, tool_input: dict, session_id: str) -> dict:
    handler = _HANDLERS.get(name)
    if not handler:
        return {"error": f"Noma'lum Google Docs tool: {name}"}
    try:
        return await handler(session_id=session_id, **tool_input)
    except TypeError as exc:
        return {"error": f"Noto'g'ri parametrlar: {exc}"}
