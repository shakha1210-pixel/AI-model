"""
main.py — Kod Yozish Agenti backend serveri

Bu FastAPI ilovasi loyihaning "yuragi": foydalanuvchi xabarlarini qabul
qiladi, xabar "kod"ga oidmi yoki "g'oya/suhbat"ga oidmi aniqlaydi
(classify_intent), va mos AI modeliga (Claude yoki Gemini) yuboradi.

Ishga tushirish:
    uvicorn main:app --reload
    So'ngra brauzerda http://localhost:8000 manzilini oching.

Talab qilinadigan Python versiyasi: 3.10+
"""

import asyncio
import json
import logging
import os
from typing import AsyncIterator, Literal

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent")

from safety import REFUSAL_MESSAGE, SUPPORT_MESSAGE, check_input, check_output  # noqa: E402

# ---------------------------------------------------------------------------
# BOSQICHLARNI YOQISH/O'CHIRISH
# ---------------------------------------------------------------------------
# Quyidagi fayllar TAYYOR va ISHLAYDI, lekin standart holatda o'chirilgan —
# loyihangiz bosqichiga qarab .env faylida (yoki shu yerda) "true" qiling.
# Batafsil: bir papka tepadagi TOLDIRILISHI-KERAK-BOLGAN-ROYXAT.txt fayliga
# qarang.

# database.py: suhbatlarni doimiy saqlash (standart: xotirada/RAM saqlanadi)
ENABLE_DATABASE = os.getenv("ENABLE_DATABASE", "false").lower() == "true"

# auth.py: ro'yxatdan o'tish/kirish tizimi (ENABLE_DATABASE ham kerak)
ENABLE_AUTH = os.getenv("ENABLE_AUTH", "false").lower() == "true"

# rate_limiter.py: bir foydalanuvchidan kelayotgan so'rovlarni cheklash
ENABLE_RATE_LIMIT = os.getenv("ENABLE_RATE_LIMIT", "false").lower() == "true"

if ENABLE_AUTH and not ENABLE_DATABASE:
    raise RuntimeError(
        "Noto'g'ri konfiguratsiya: ENABLE_AUTH=true uchun ENABLE_DATABASE=true "
        "ham bo'lishi SHART (foydalanuvchi va sessiya egaligi ma'lumotlari "
        "doimiy bazada saqlanishi kerak). .env faylida ENABLE_DATABASE=true "
        "qiling."
    )

# tools.py: Claude'ga kod yozish VA ijro etish imkoniyatini berish
# DIQQAT: yoqishdan oldin tools.py dagi xavfsizlik ogohlantirishini o'qing!
ENABLE_TOOLS = os.getenv("ENABLE_TOOLS", "false").lower() == "true"

# FAIL-SAFE: pentest sinovida tools.py dagi statik filtr bir necha soniyada
# (obfuskatsiya orqali: getattr/chr/__builtins__/importlib) TO'LIQ chetlab
# o'tildi — bu YAGONA himoya bo'lganda amalda deyarli foydasiz. Shuning
# uchun ENABLE_TOOLS=true qilinganda, haqiqiy izolyatsiya (Docker/E2B/
# gVisor) qo'llanganini ONGLI ravishda tasdiqlamasangiz, server ATAYLAB
# ishga tushmaydi.
CODE_EXECUTION_SANDBOX_CONFIRMED = (
    os.getenv("CODE_EXECUTION_SANDBOX_CONFIRMED", "false").lower() == "true"
)
if ENABLE_TOOLS and not CODE_EXECUTION_SANDBOX_CONFIRMED:
    raise RuntimeError(
        "XAVFSIZLIK XATOSI: ENABLE_TOOLS=true, lekin CODE_EXECUTION_SANDBOX_"
        "CONFIRMED=true qilinmagan. tools.py dagi statik filtr (pentest bilan "
        "tasdiqlangan) getattr/chr/__builtins__/importlib kabi oddiy usullar "
        "bilan TO'LIQ chetlab o'tiladi — bu YAGONA himoya bo'lganda amalda "
        "foydasiz. Kod ijrosini Docker konteynerida (tarmoqsiz), E2B.dev kabi "
        "hostlangan sandbox xizmatida, yoki gVisor/Firecracker orqali "
        "izolyatsiya qilganingizga ishonch hosil qilgandan so'ng, buni ONGLI "
        "ravishda .env faylida CODE_EXECUTION_SANDBOX_CONFIRMED=true qilib "
        "belgilang. Batafsil: tools.py va TOLDIRILISHI-KERAK-BOLGAN-ROYXAT.txt."
    )

# github_tool.py: Claude'ga GitHub repositoriy bilan ishlash imkoniyatini
# berish (fayl o'qish/yozish, PR ochish). run_python_code'dan farqli — bu
# server ichida kod ijro etmaydi, shuning uchun sandbox tasdiqlash talab
# qilinmaydi. DIQQAT: github_tool.py dagi xavfsizlik ogohlantirishini
# (token huquqlarini cheklash, prompt injection xavfi) albatta o'qing.
ENABLE_GITHUB_TOOL = os.getenv("ENABLE_GITHUB_TOOL", "false").lower() == "true"

# google_docs_tool.py: Claude'ga Google Docs hujjatlari bilan ishlash
# imkoniyatini berish (o'qish, yaratish). Sessiya darajasida OAuth orqali
# ulanadi (GET /google-docs/connect/{session_id}) — ENABLE_AUTH/DATABASE
# talab qilinmaydi. DIQQAT: google_docs_tool.py dagi ogohlantirishni o'qing
# — GOOGLE_CLIENT_ID/SECRET auth.py bilan bir xil OAuth client'dan qayta
# ishlatiladi, lekin Cloud Console'da yangi redirect URI qo'shish kerak.
ENABLE_GOOGLE_DOCS_TOOL = os.getenv("ENABLE_GOOGLE_DOCS_TOOL", "false").lower() == "true"

# ---------------------------------------------------------------------------
# LOYIHALAR (PROJECTS) — suhbatlarni va fayllarni guruhlaydigan papkalar.
# Har bir loyiha bitta foydalanuvchiga tegishli bo'lgani uchun ENABLE_AUTH
# (demak ENABLE_DATABASE ham) SHART.
# ---------------------------------------------------------------------------
ENABLE_PROJECTS = os.getenv("ENABLE_PROJECTS", "false").lower() == "true"
if ENABLE_PROJECTS and not (ENABLE_AUTH and ENABLE_DATABASE):
    raise RuntimeError(
        "Noto'g'ri konfiguratsiya: ENABLE_PROJECTS=true uchun ENABLE_AUTH=true "
        "VA ENABLE_DATABASE=true ham bo'lishi SHART (loyihalar foydalanuvchiga "
        "bog'langan holda ma'lumotlar bazasida saqlanadi)."
    )

# project_tool.py: Claude'ga joriy suhbat biriktirilgan loyiha papkasidagi
# fayllarni o'qish/yozish imkonini beradi. ENABLE_PROJECTS ham SHART.
ENABLE_PROJECT_FILES_TOOL = os.getenv("ENABLE_PROJECT_FILES_TOOL", "false").lower() == "true"
if ENABLE_PROJECT_FILES_TOOL and not ENABLE_PROJECTS:
    raise RuntimeError(
        "Noto'g'ri konfiguratsiya: ENABLE_PROJECT_FILES_TOOL=true uchun "
        "ENABLE_PROJECTS=true ham bo'lishi SHART."
    )

# Har bir foydalanuvchi uchun xotira (sessiya) chegarasi — "cheklangan
# xotira": chegaraga yetgan foydalanuvchi yangi suhbat boshlay olmaydi (403),
# frontend shu vaqtda eski suhbatlardan birini o'chirishni yoki (kelajakda)
# Pro rejasiga o'tishni taklif qiladi. Faqat ENABLE_AUTH=true bo'lganda
# ma'noga ega (mehmon/anonim rejimda per-user tushunchasi yo'q).
MAX_SESSIONS_PER_USER = int(os.getenv("MAX_SESSIONS_PER_USER", "30"))


# ---------------------------------------------------------------------------
# FOYDALANUVCHI ANIQLASH (IDOR himoyasi + mehmon rejimi yo'q)
# ---------------------------------------------------------------------------
# ENABLE_AUTH=true bo'lsa, /chat, /chat/stream, /history, /sessions,
# /files kabi barcha "ishlaydigan" endpointlar TOKEN TALAB QILADI — token
# bo'lmasa yoki yaroqsiz bo'lsa 401 qaytadi (get_current_user shuni qiladi).
# Bu "mehmon sifatida davom etish" imkoniyati olib tashlanganini aks
# ettiradi: avvalgi versiyada token ixtiyoriy edi (anonim so'rovlar ham
# ishlardi), bu esa botlar/skriptlar login qilmasdan ham serverga cheksiz
# so'rov (va shu orqali AI API xarajati) yubora olishiga yo'l qo'yardi.
# ENABLE_AUTH=false bo'lganda (faqat lokal sinov/demo uchun) hech qanday
# token talab qilinmaydi — bu holatda egalik tushunchasi ham yo'q.
if ENABLE_AUTH:
    from auth import get_current_user
    from database import get_session_owner

    def current_user_id(user=Depends(get_current_user)) -> str:
        return user.id
else:
    def current_user_id() -> str | None:
        return None

    def get_session_owner(session_id: str) -> str | None:  # noqa: ARG001
        return None


# ---------------------------------------------------------------------------
# SUHBAT TARIXI (SESSIYA) SAQLASH
# ---------------------------------------------------------------------------
if ENABLE_DATABASE:
    from database import (
        count_sessions,
        delete_session,
        get_or_create_session,
        init_db,
        list_messages,
        list_sessions,
        save_message,
    )

    init_db()
else:
    # Oddiy xotirada saqlash (RAM). Server qayta ishga tushganda suhbat
    # tarixi o'chib ketadi — MVP uchun yetarli. Doimiy saqlash uchun
    # ENABLE_DATABASE=true qiling.
    import uuid

    _memory_sessions: dict[str, list[dict]] = {}
    _memory_session_order: list[str] = []  # eng yangisi oxirida

    def get_or_create_session(
        session_id: str | None, user_id: str | None = None, project_id: str | None = None
    ) -> str:
        sid = session_id or str(uuid.uuid4())
        if sid not in _memory_sessions:
            _memory_sessions[sid] = []
            _memory_session_order.append(sid)
        return sid

    def count_sessions(user_id: str) -> int:  # noqa: ARG001
        return 0

    def save_message(session_id: str, role: str, content: str, image_url: str | None = None) -> None:
        _memory_sessions.setdefault(session_id, []).append(
            {"role": role, "content": content, "image_url": image_url}
        )

    def list_messages(session_id: str) -> list[dict]:
        return _memory_sessions.get(session_id, [])

    def list_sessions() -> list[dict]:
        result = []
        for sid in reversed(_memory_session_order):
            msgs = _memory_sessions.get(sid, [])
            first_user = next((m["content"] for m in msgs if m["role"] == "user"), None)
            preview = (first_user[:60] if first_user else "Bo'sh suhbat")
            result.append({"id": sid, "preview": preview})
        return result

    def delete_session(session_id: str) -> None:
        _memory_sessions.pop(session_id, None)
        if session_id in _memory_session_order:
            _memory_session_order.remove(session_id)


# ---------------------------------------------------------------------------
# INTENT KLASSIFIKATSIYA — xabar "kod"ga oidmi yoki "g'oya"ga oidmi?
# ---------------------------------------------------------------------------
CODE_KEYWORDS = [
    "kod", "kodni", "kod yoz", "funksiya", "funksiyani", "dastur", "dasturni",
    "bug", "xato", "xatoni", "debug", "python", "javascript", "typescript",
    "java", "c++", "c#", "html", "css", "sql", "api", "algoritm", "class",
    "method", "kompilyatsiya", "compile", "error", "exception", "refactor",
    "optimallashtir", "test yoz", "repository", "git", "regex", "docker",
]

# Rasm generatsiya so'rovlari (Leonardo AI'ga yo'naltiriladi)
IMAGE_KEYWORDS = [
    "rasm chiz", "rasm yarat", "rasm generatsiya", "surat chiz", "surat yarat",
    "logotip", "banner yarat", "illyustratsiya", "chizib ber", "poster yarat",
    "ai rasm", "image generate", "draw a picture", "generate an image",
]

# Qidiruv/hujjat tahlili so'rovlari (kuchliroq Gemini modeliga yo'naltiriladi)
RESEARCH_KEYWORDS = [
    "hujjatni tahlil", "hujjat tahlili", "maqolani tahlil", "referatni tahlil",
    "qisqacha bayon qil", "xulosa chiqar", "tahlil qilib ber", "izlab top",
    "qidirib ber", "manba top", "adabiyotlar sharhi", "tadqiqot qil",
    "chuqur tahlil",
]


def classify_intent(message: str) -> Literal["code", "idea", "image", "research"]:
    """
    Xabar matnida qaysi domenga oid kalit so'zlar bo'lsa, shunga mos
    natija qaytaradi: "image" (Leonardo), "research" (Gemini Pro),
    "code" (Claude), aks holda "idea" (Gemini, standart suhbat).

    TODO (kelajakda yaxshilash mumkin): oddiy kalit-so'z qidirish o'rniga
    kichik LLM chaqiruvi yoki embedding-based klassifikatsiya ishlatish
    mumkin — hozirgi yechim tezkor va bepul.
    """
    text = message.lower()
    if any(keyword in text for keyword in IMAGE_KEYWORDS):
        return "image"
    if any(keyword in text for keyword in RESEARCH_KEYWORDS):
        return "research"
    if any(keyword in text for keyword in CODE_KEYWORDS):
        return "code"
    return "idea"


# ---------------------------------------------------------------------------
# AI MODELLARI BILAN ISHLASH
# ---------------------------------------------------------------------------
# Domenlar bir nechta ixtisoslashgan agentga bo'lingan (kod/rasm/qidiruv).
# Har biri o'z sohasidan tashqari so'rov kelsa, uni bajarishga urinmay,
# foydalanuvchiga qaysi bo'limga o'tish kerakligini taklif qiladi — bu
# keyword-based klassifikatsiyadagi xatolarni ham yumshatadi (masalan
# "auto" rejimida noto'g'ri agentga tushib qolgan so'rov).
OFF_TOPIC_SUFFIX = (
    " Agar foydalanuvchining birinchi xabari shunchaki salomlashish yoki "
    "suhbatni umumiy tarzda boshlash bo'lsa (masalan 'salom'), uzun "
    "tushuntirish bermang — iliq javob bering va BIR QISQA JUMLA bilan "
    "nima ish qila olishingizni ayting (masalan: 'Salom! Men hujjatlar va "
    "matnlarni chuqur tahlil qilishda yordam beraman.'). Faqat foydalanuvchi "
    "keyingi xabarida ANIQ ravishda boshqa sohaga oid topshiriq bersa "
    "(sizning ixtisosligingizga umuman aloqador bo'lmasa), uni bajarishga "
    "urinmang — o'shanda qisqa qilib qaysi bo'lim (masalan 'Kod yozish', "
    "'Rasm chizish', 'Qidiruv/hujjat tahlili' yoki 'G'oya/erkin suhbat') "
    "mos kelishini taklif qiling."
)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
CLAUDE_SYSTEM_PROMPT = (
    "Siz tajribali dasturchi yordamchisisiz. Foydalanuvchiga aniq, ishlaydigan "
    "kod va tushunarli tushuntirish bilan javob bering. Javobingizni "
    "foydalanuvchi yozgan tilda bering (masalan, ruscha yozsa ruscha, "
    "inglizcha yozsa inglizcha javob bering); til aniq bo'lmasa, o'zbek "
    "tilida javob bering. Kod bloklarini uchta qiyshiq chiziq (```) bilan "
    "belgilang." + OFF_TOPIC_SUFFIX
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_SYSTEM_PROMPT = (
    "Siz do'stona va ijodiy suhbatdoshsiz. Foydalanuvchi bilan g'oyalar, "
    "rejalar va umumiy savollar haqida erkin va tushunarli suhbatlashing. "
    "Foydalanuvchi yozgan tilda javob bering (masalan, ruscha yozsa ruscha, "
    "inglizcha yozsa inglizcha javob bering); til aniq bo'lmasa, o'zbek "
    "tilida javob bering."
)

# "Qidiruv/hujjat tahlili" domeni — kuchliroq Gemini modelidan foydalanadi
# (yangi API kalit talab qilinmaydi, xuddi shu GEMINI_API_KEY ishlatiladi).
GEMINI_RESEARCH_MODEL = os.getenv("GEMINI_RESEARCH_MODEL", "gemini-3.5-flash")
GEMINI_RESEARCH_SYSTEM_PROMPT = (
    "Siz chuqur tahlil va qidiruv bo'yicha ixtisoslashgan yordamchisiz. "
    "Foydalanuvchi biriktirgan hujjat/matn yoki mavzuni sinchiklab tahlil "
    "qiling, asosiy fikrlarni ajratib, tuzilgan va manbaga tayangan javob "
    "bering. Javobingizni foydalanuvchi yozgan tilda bering (masalan, ruscha "
    "yozsa ruscha, inglizcha yozsa inglizcha javob bering); til aniq "
    "bo'lmasa, o'zbek tilida javob bering." + OFF_TOPIC_SUFFIX
)

# --- Leonardo AI (rasm generatsiya) ---------------------------------------
LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY", "")
LEONARDO_MODEL_ID = os.getenv("LEONARDO_MODEL_ID", "b24e16ff-06e3-43eb-8d33-4416c2d75876")
LEONARDO_POLL_INTERVAL_SECONDS = 2
LEONARDO_POLL_MAX_ATTEMPTS = 30


CLAUDE_DEEP_THINKING_SUFFIX = (
    " Bu safar 'chuqur o'ylash' rejimi yoqilgan: javob berishdan oldin "
    "muammoni bosqichma-bosqich tahlil qiling, kamida 2-3 ta yechim "
    "variantini ko'rib chiqing, va faqat shundan keyin eng yaxshi "
    "yechimni tanlab, uni tushuntirib bering."
)


async def call_claude(message: str, history: list[dict], deep_thinking: bool = False) -> str:
    """Claude (Anthropic) API'ga so'rov yuboradi — kod bilan bog'liq savollar uchun."""
    if not ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY sozlanmagan. .env faylini to'ldiring.",
        )

    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": message})

    system_prompt = CLAUDE_SYSTEM_PROMPT + (CLAUDE_DEEP_THINKING_SUFFIX if deep_thinking else "")

    async with httpx.AsyncClient(timeout=90.0 if deep_thinking else 60.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": 4096 if deep_thinking else 2048,
                "system": system_prompt,
                "messages": messages,
            },
        )

    if response.status_code != 200:
        logger.error("Claude API xatosi: %s %s", response.status_code, response.text)
        raise HTTPException(status_code=502, detail="Claude API bilan bog'lanib bo'lmadi.")

    data = response.json()
    return "".join(block.get("text", "") for block in data.get("content", []))


async def _iter_sse_json(response: httpx.Response) -> AsyncIterator[dict]:
    """Anthropic/Gemini SSE oqimidagi "data: {...}" qatorlarini JSON
    obyektiga aylantirib beradi (bo'sh yoki JSON bo'lmagan qatorlar
    e'tiborsiz qoldiriladi)."""
    async for line in response.aiter_lines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload:
            continue
        try:
            yield json.loads(payload)
        except json.JSONDecodeError:
            continue


async def stream_claude(
    message: str, history: list[dict], deep_thinking: bool = False
) -> AsyncIterator[dict]:
    """call_claude()ning oqim (streaming) varianti — matn bo'lak-bo'lak
    tayyor bo'lgani sayin {"type": "text", "text": ...} qaytaradi."""
    if not ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY sozlanmagan. .env faylini to'ldiring.",
        )

    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": message})

    system_prompt = CLAUDE_SYSTEM_PROMPT + (CLAUDE_DEEP_THINKING_SUFFIX if deep_thinking else "")

    async with httpx.AsyncClient(timeout=90.0 if deep_thinking else 60.0) as client:
        async with client.stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": 4096 if deep_thinking else 2048,
                "system": system_prompt,
                "messages": messages,
                "stream": True,
            },
        ) as response:
            if response.status_code != 200:
                body = await response.aread()
                logger.error("Claude API xatosi: %s %s", response.status_code, body)
                raise HTTPException(status_code=502, detail="Claude API bilan bog'lanib bo'lmadi.")

            async for event in _iter_sse_json(response):
                if event.get("type") != "content_block_delta":
                    continue
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta" and delta.get("text"):
                    yield {"type": "text", "text": delta["text"]}


GEMINI_DEEP_THINKING_SUFFIX = (
    " Bu safar 'chuqur o'ylash' rejimi yoqilgan: javob berishdan oldin "
    "muammoni turli tomondan ko'rib chiqing, ortiqcha shoshilmang, va "
    "yakuniy javobingizni yanada chuqurroq tahlil bilan bering."
)


async def call_gemini(
    message: str,
    history: list[dict],
    deep_thinking: bool = False,
    model: str | None = None,
    system_prompt: str | None = None,
) -> str:
    """Gemini (Google) API'ga so'rov yuboradi — g'oya/erkin suhbat uchun
    (yoki `model`/`system_prompt` berilsa, masalan qidiruv/hujjat tahlili
    domeni uchun kuchliroq model bilan)."""
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY sozlanmagan. .env faylini to'ldiring.",
        )

    contents = [
        {
            "role": "model" if m["role"] == "assistant" else "user",
            "parts": [{"text": m["content"]}],
        }
        for m in history
    ]
    contents.append({"role": "user", "parts": [{"text": message}]})

    base_prompt = system_prompt or GEMINI_SYSTEM_PROMPT
    full_system_prompt = base_prompt + (GEMINI_DEEP_THINKING_SUFFIX if deep_thinking else "")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model or GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )

    async with httpx.AsyncClient(timeout=90.0 if deep_thinking else 60.0) as client:
        response = await client.post(
            url,
            json={
                "system_instruction": {"parts": [{"text": full_system_prompt}]},
                "contents": contents,
            },
        )

    if response.status_code != 200:
        logger.error("Gemini API xatosi: %s %s", response.status_code, response.text)
        raise HTTPException(status_code=502, detail="Gemini API bilan bog'lanib bo'lmadi.")

    data = response.json()
    try:
        candidate = data["candidates"][0]
        return "".join(part.get("text", "") for part in candidate["content"]["parts"])
    except (KeyError, IndexError):
        logger.error("Gemini javobi kutilmagan formatda: %s", data)
        raise HTTPException(status_code=502, detail="Gemini javobini o'qib bo'lmadi.")


async def stream_gemini(
    message: str,
    history: list[dict],
    deep_thinking: bool = False,
    model: str | None = None,
    system_prompt: str | None = None,
) -> AsyncIterator[dict]:
    """call_gemini()ning oqim (streaming) varianti."""
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY sozlanmagan. .env faylini to'ldiring.",
        )

    contents = [
        {
            "role": "model" if m["role"] == "assistant" else "user",
            "parts": [{"text": m["content"]}],
        }
        for m in history
    ]
    contents.append({"role": "user", "parts": [{"text": message}]})

    base_prompt = system_prompt or GEMINI_SYSTEM_PROMPT
    full_system_prompt = base_prompt + (GEMINI_DEEP_THINKING_SUFFIX if deep_thinking else "")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model or GEMINI_MODEL}:streamGenerateContent?alt=sse&key={GEMINI_API_KEY}"
    )

    async with httpx.AsyncClient(timeout=90.0 if deep_thinking else 60.0) as client:
        async with client.stream(
            "POST",
            url,
            json={
                "system_instruction": {"parts": [{"text": full_system_prompt}]},
                "contents": contents,
            },
        ) as response:
            if response.status_code != 200:
                body = await response.aread()
                logger.error("Gemini API xatosi: %s %s", response.status_code, body)
                raise HTTPException(status_code=502, detail="Gemini API bilan bog'lanib bo'lmadi.")

            async for event in _iter_sse_json(response):
                try:
                    candidate = event["candidates"][0]
                    parts = candidate["content"]["parts"]
                except (KeyError, IndexError):
                    continue
                for part in parts:
                    text = part.get("text", "")
                    if text:
                        yield {"type": "text", "text": text}


async def call_leonardo(prompt: str) -> tuple[str, str]:
    """Leonardo AI'ga rasm generatsiya so'rovi yuboradi va tayyor bo'lguncha
    natijani so'raydi (poll qiladi). Qaytaradi: (matn javob, rasm URL'i)."""
    if not LEONARDO_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="LEONARDO_API_KEY sozlanmagan. .env faylini to'ldiring.",
        )

    headers = {
        "authorization": f"Bearer {LEONARDO_API_KEY}",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        create_response = await client.post(
            "https://cloud.leonardo.ai/api/rest/v1/generations",
            headers=headers,
            json={"prompt": prompt, "modelId": LEONARDO_MODEL_ID, "num_images": 1},
        )
        if create_response.status_code not in (200, 201):
            logger.error(
                "Leonardo API xatosi (yaratish): %s %s",
                create_response.status_code, create_response.text,
            )
            raise HTTPException(status_code=502, detail="Leonardo AI bilan bog'lanib bo'lmadi.")

        generation_id = create_response.json()["sdGenerationJob"]["generationId"]

        for _ in range(LEONARDO_POLL_MAX_ATTEMPTS):
            await asyncio.sleep(LEONARDO_POLL_INTERVAL_SECONDS)
            status_response = await client.get(
                f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}",
                headers=headers,
            )
            if status_response.status_code != 200:
                continue
            generation = status_response.json().get("generations_by_pk", {})
            if generation.get("status") == "COMPLETE":
                images = generation.get("generated_images", [])
                if images:
                    return "Mana so'ragan rasmingiz:", images[0]["url"]
                break
            if generation.get("status") == "FAILED":
                break

    raise HTTPException(status_code=502, detail="Rasm generatsiyasi vaqt chegarasidan oshdi.")


# ---------------------------------------------------------------------------
# FASTAPI ILOVASI VA ENDPOINTLAR
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Foydalanuvchi xabari")
    session_id: str | None = Field(None, description="Suhbat sessiyasi ID'si")
    mode: Literal["auto", "code", "idea", "image", "research"] = Field(
        "auto",
        description=(
            "Foydalanuvchi tanlagan domen: avto/kod(claude)/g'oya(gemini)/"
            "rasm(leonardo)/qidiruv(gemini pro)"
        ),
    )
    thinking: bool = Field(False, description="'Chuqur o'ylash' rejimi yoqilganmi")
    project_id: str | None = Field(
        None,
        description=(
            "Agar shu qiymat bilan YANGI sessiya ochilsa, sessiya shu loyiha "
            "papkasiga biriktiriladi (ENABLE_PROJECTS=true bo'lganda)."
        ),
    )


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    intent: Literal["code", "idea", "image", "research"]
    image_url: str | None = None


app = FastAPI(title="Kod Yozish Agenti API")

# ALLOWED_ORIGINS: vergul bilan ajratilgan domenlar ro'yxati, masalan:
# ALLOWED_ORIGINS=https://mening-domenim.uz,https://www.mening-domenim.uz
# .env da sozlanmasa, standart "*" (faqat local development uchun mos —
# productionda albatta o'z domeningizni ko'rsating).
_allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = (
    ["*"] if _allowed_origins_env.strip() == "*"
    else [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
)
if ALLOWED_ORIGINS == ["*"]:
    logger.warning(
        "ALLOWED_ORIGINS='*' — barcha domenlardan so'rov qabul qilinmoqda. "
        "Productionga chiqishdan oldin .env faylida ALLOWED_ORIGINS ni "
        "o'z domeningiz bilan cheklang."
    )

# GZip: statik fayllar (CSS/JS/HTML) va API javoblarini siqib yuboradi
# (odatda ~8x kichrayadi). minimum_size — shundan kichik javoblarni
# siqishga urinmaydi (foyda bermaydi).
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

if ENABLE_RATE_LIMIT:
    from rate_limiter import RateLimitExceeded, check_rate_limit, get_status

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        if request.url.path in ("/chat", "/chat/stream"):
            client_key = request.client.host if request.client else "unknown"
            try:
                check_rate_limit(client_key)
            except RateLimitExceeded as exc:
                return JSONResponse(status_code=429, content={"detail": str(exc)})
        return await call_next(request)

    # frontend/chat.js shu endpointni chaqirib "N/max so'rov" belgisini
    # ko'rsatadi (rate-limit-badge) — ENABLE_RATE_LIMIT=false bo'lsa,
    # bu route umuman ro'yxatdan o'tmaydi va frontend uni jimgina
    # yashiradi (404 sifatida qabul qilib).
    @app.get("/rate-limit/status")
    async def rate_limit_status(request: Request) -> dict:
        client_key = request.client.host if request.client else "unknown"
        return get_status(client_key)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# FAYL YUKLASH — foydalanuvchi hujjat (.docx/.xlsx) yoki matn/kod fayl
# biriktirsa, agent uni o'qiy oladi (Leonardo/rasm domeniga tegishli emas —
# u faqat matnli so'rov (prompt) bilan ishlaydi).
# ---------------------------------------------------------------------------
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


@app.get("/files/_probe")
async def files_probe() -> dict:
    """Frontend shu orqali fayl biriktirish tugmasini ko'rsatish/yashirishni
    hal qiladi (404 bo'lmasa — yoqilgan)."""
    return {"enabled": True}


@app.post("/files/extract")
async def files_extract(
    file: UploadFile = File(...), user_id: str | None = Depends(current_user_id)
) -> dict:
    """Yuklangan faylni (.docx/.xlsx yoki matn/kod fayl) o'qiladigan matnga
    aylantirib qaytaradi — frontend shu matnni chat xabariga qo'shadi."""
    from files import extract_text

    data = await file.read()
    if len(data) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Fayl juda katta (maksimal 5 MB).")

    content = extract_text(file.filename or "", data)
    return {"filename": file.filename, "content": content}


@app.post("/files/{session_id}")
async def files_upload(
    session_id: str, file: UploadFile = File(...), user_id: str | None = Depends(current_user_id)
) -> dict:
    """Faylni sessiyaga bog'lab qabul qiladi (best-effort — mazmuni allaqachon
    /files/extract orqali xabar matniga qo'shilgan bo'ladi, shuning uchun bu
    yerda muvaffaqiyatsizlik suhbatni to'xtatmaydi)."""
    _assert_session_access(session_id, user_id)
    await file.read()
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest, user_id: str | None = Depends(current_user_id)
) -> ChatResponse:
    session_id = _resolve_session(payload, user_id)

    # 1-QATLAM MODERATSIYA: xavfli so'rov aniqlansa, model UMUMAN
    # chaqirilmaydi — bu ham xarajatni tejaydi, ham xavfsizlikni ta'minlaydi.
    # "self_harm" kategoriyasi uchun qattiq rad javobi EMAS, balki
    # qo'llab-quvvatlovchi javob va resurslar beriladi (safety.py'ga qarang).
    input_check = check_input(session_id, payload.message)
    if not input_check.allowed:
        reply_text = (
            SUPPORT_MESSAGE if input_check.category == "self_harm" else REFUSAL_MESSAGE
        )
        save_message(session_id, "user", payload.message)
        save_message(session_id, "assistant", reply_text)
        return ChatResponse(reply=reply_text, session_id=session_id, intent="idea")

    chat_history = list_messages(session_id)

    # Foydalanuvchi "avto" tanlasa avtomatik aniqlanadi, aks holda uning
    # tanlovi (kod->Claude, g'oya->Gemini, rasm->Leonardo,
    # qidiruv->Gemini Pro) to'g'ridan-to'g'ri ishlatiladi.
    intent = classify_intent(payload.message) if payload.mode == "auto" else payload.mode
    save_message(session_id, "user", payload.message)

    image_url: str | None = None
    if intent == "code":
        if ENABLE_TOOLS or ENABLE_GITHUB_TOOL or ENABLE_GOOGLE_DOCS_TOOL or ENABLE_PROJECT_FILES_TOOL:
            from tools import call_claude_with_tools

            reply = await call_claude_with_tools(payload.message, chat_history, session_id=session_id)
        else:
            reply = await call_claude(payload.message, chat_history, deep_thinking=payload.thinking)
    elif intent == "image":
        reply, image_url = await call_leonardo(payload.message)
    elif intent == "research":
        reply = await call_gemini(
            payload.message,
            chat_history,
            deep_thinking=payload.thinking,
            model=GEMINI_RESEARCH_MODEL,
            system_prompt=GEMINI_RESEARCH_SYSTEM_PROMPT,
        )
    else:
        reply = await call_gemini(payload.message, chat_history, deep_thinking=payload.thinking)

    # 2-QATLAM MODERATSIYA: model javobini foydalanuvchiga yuborishdan oldin
    # ham tekshiramiz (model o'zi xato/xavfli javob berishi mumkin).
    output_check = check_output(session_id, reply)
    if not output_check.allowed:
        reply = REFUSAL_MESSAGE
        image_url = None

    save_message(session_id, "assistant", reply, image_url=image_url)

    return ChatResponse(reply=reply, session_id=session_id, intent=intent, image_url=image_url)


@app.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest, user_id: str | None = Depends(current_user_id)
) -> StreamingResponse:
    """`/chat` bilan bir xil ishlaydi, lekin javobni Server-Sent Events (SSE)
    orqali so'z-so'z oqim sifatida qaytaradi ("yozilayotgandek" ko'rinish
    uchun). Xavfsizlik kafolati saqlanadi: har bir yangi bo'lak yuborilishidan
    OLDIN to'plangan matnning HAMMASI check_output() orqali qayta tekshiriladi
    — xavfli deb topilgan bo'lak (yoki undan keyingisi) hech qachon
    foydalanuvchiga yetib bormaydi, "blocked" hodisasi butun javobni
    REFUSAL_MESSAGE bilan almashtirishni buyuradi (frontend allaqachon
    ko'rsatilgan xavfsiz bo'laklarni ham shu bilan almashtiradi)."""
    session_id = _resolve_session(payload, user_id)

    def sse(data: dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def event_stream() -> AsyncIterator[str]:
        input_check = check_input(session_id, payload.message)
        if not input_check.allowed:
            reply_text = (
                SUPPORT_MESSAGE if input_check.category == "self_harm" else REFUSAL_MESSAGE
            )
            save_message(session_id, "user", payload.message)
            save_message(session_id, "assistant", reply_text)
            yield sse({"delta": reply_text})
            yield sse({"done": True, "session_id": session_id, "intent": "idea", "image_url": None})
            return

        chat_history = list_messages(session_id)
        intent = classify_intent(payload.message) if payload.mode == "auto" else payload.mode
        save_message(session_id, "user", payload.message)

        full_text = ""
        image_url: str | None = None
        blocked = False

        try:
            if intent == "code":
                if ENABLE_TOOLS or ENABLE_GITHUB_TOOL or ENABLE_GOOGLE_DOCS_TOOL or ENABLE_PROJECT_FILES_TOOL:
                    from tools import stream_claude_with_tools

                    source = stream_claude_with_tools(
                        payload.message, chat_history, session_id=session_id
                    )
                else:
                    source = stream_claude(payload.message, chat_history, deep_thinking=payload.thinking)

                async for event in source:
                    if event["type"] == "tool_start":
                        yield sse({"tool": event["name"]})
                        continue
                    full_text += event["text"]
                    if not check_output(session_id, full_text).allowed:
                        blocked = True
                        break
                    yield sse({"delta": event["text"]})

            elif intent == "image":
                reply, image_url = await call_leonardo(payload.message)
                full_text = reply
                if not check_output(session_id, full_text).allowed:
                    blocked = True
                else:
                    yield sse({"delta": full_text})

            else:
                if intent == "research":
                    source = stream_gemini(
                        payload.message,
                        chat_history,
                        deep_thinking=payload.thinking,
                        model=GEMINI_RESEARCH_MODEL,
                        system_prompt=GEMINI_RESEARCH_SYSTEM_PROMPT,
                    )
                else:
                    source = stream_gemini(payload.message, chat_history, deep_thinking=payload.thinking)

                async for event in source:
                    full_text += event["text"]
                    if not check_output(session_id, full_text).allowed:
                        blocked = True
                        break
                    yield sse({"delta": event["text"]})
        except HTTPException as exc:
            yield sse({"error": exc.detail})
            return

        if blocked:
            full_text = REFUSAL_MESSAGE
            image_url = None
            yield sse({"blocked": True, "reply": REFUSAL_MESSAGE})

        save_message(session_id, "assistant", full_text, image_url=image_url)
        yield sse({"done": True, "session_id": session_id, "intent": intent, "image_url": image_url})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _assert_session_access(session_id: str, user_id: str | None) -> None:
    """ENABLE_AUTH yoqilganda: sessiya boshqa foydalanuvchiga tegishli
    bo'lsa 403 qaytaradi. ENABLE_AUTH o'chirilganda hech narsa qilmaydi
    (demo/mehmon rejimi — eski xatti-harakat saqlanadi)."""
    if not ENABLE_AUTH:
        return
    owner = get_session_owner(session_id)
    if owner is not None and owner != user_id:
        raise HTTPException(status_code=403, detail="Bu sessiyaga kirish huquqingiz yo'q")


def _check_session_limit(user_id: str | None) -> None:
    """Har-user xotira (sessiya) chegarasini tekshiradi — faqat ENABLE_AUTH
    yoqilgan va foydalanuvchi haqiqatan ANIQLANGAN bo'lsa ma'noga ega."""
    if not (ENABLE_AUTH and user_id is not None):
        return
    used = count_sessions(user_id)
    if used >= MAX_SESSIONS_PER_USER:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "session_limit_reached",
                "message": (
                    f"Sessiya chegarasiga yetdingiz ({used}/{MAX_SESSIONS_PER_USER}). "
                    "Davom etish uchun eski suhbatlardan birini o'chiring."
                ),
                "used": used,
                "limit": MAX_SESSIONS_PER_USER,
            },
        )


def _resolve_session(payload: ChatRequest, user_id: str | None) -> str:
    """/chat va /chat/stream uchun umumiy sessiya-aniqlash mantig'i.
    session_id boshqa foydalanuvchiga tegishli bo'lsa, unga yozib qo'yishga
    yo'l qo'ymaymiz — shu o'rniga yangi (o'ziga tegishli) sessiya ochiladi.
    Har qanday YANGI sessiya ochilishidan oldin xotira chegarasi
    tekshiriladi (_check_session_limit)."""
    existing_owner = get_session_owner(payload.session_id) if payload.session_id else None

    if existing_owner is not None:
        if existing_owner == user_id:
            return get_or_create_session(payload.session_id, user_id=user_id)
        _check_session_limit(user_id)
        return get_or_create_session(None, user_id=user_id)

    _check_session_limit(user_id)
    project_id = payload.project_id
    if project_id and ENABLE_PROJECTS and get_project_owner(project_id) != user_id:
        # Boshqa foydalanuvchining loyihasiga biriktirishga urinish — jim
        # e'tiborsiz qoldiramiz (loyihasiz oddiy sessiya ochiladi).
        project_id = None
    return get_or_create_session(payload.session_id, user_id=user_id, project_id=project_id)


@app.get("/history/{session_id}")
async def history(
    session_id: str, user_id: str | None = Depends(current_user_id)
) -> dict:
    _assert_session_access(session_id, user_id)
    return {"session_id": session_id, "messages": list_messages(session_id)}


@app.get("/sessions")
async def sessions(user_id: str | None = Depends(current_user_id)) -> dict:
    # ENABLE_AUTH yoqilgan bo'lsa, faqat joriy foydalanuvchining o'z
    # sessiyalari qaytariladi (login qilinmagan bo'lsa — bo'sh ro'yxat).
    if ENABLE_AUTH:
        return {"sessions": list_sessions(user_id=user_id) if user_id else []}
    return {"sessions": list_sessions()}


@app.delete("/sessions/{session_id}")
async def delete_session_endpoint(
    session_id: str, user_id: str | None = Depends(current_user_id)
) -> dict:
    _assert_session_access(session_id, user_id)
    delete_session(session_id)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# LOYIHALAR (PROJECTS) — suhbatlarni va fayllarni guruhlaydigan papkalar.
# Agent (Claude) bu papkadagi fayllarni project_tool.py orqali o'qiy/yoza
# oladi (ENABLE_PROJECT_FILES_TOOL=true bo'lsa) — Leonardo/rasm domeni bu
# tool-use aylanishida umuman ishtirok etmagani uchun avtomatik mustasno.
# ---------------------------------------------------------------------------
if ENABLE_PROJECTS:
    from database import (
        add_project_file,
        count_project_files,
        count_projects,
        create_project,
        delete_project,
        delete_project_file,
        get_project_file_owner_project,
        get_project_owner,
        list_project_files,
        list_projects,
        set_session_project,
    )

    MAX_PROJECTS_PER_USER = int(os.getenv("MAX_PROJECTS_PER_USER", "5"))
    MAX_PROJECT_FILES = int(os.getenv("MAX_PROJECT_FILES", "10"))

    class ProjectCreateRequest(BaseModel):
        name: str = Field(..., min_length=1, max_length=80)

    class ProjectResponse(BaseModel):
        id: str
        name: str

    class SessionProjectRequest(BaseModel):
        project_id: str | None = Field(
            None, description="Biriktiriladigan loyiha ID'si — None bo'lsa, sessiya loyihadan ajratiladi."
        )

    def _assert_project_access(project_id: str, user_id: str | None) -> None:
        owner = get_project_owner(project_id)
        if owner is None:
            raise HTTPException(status_code=404, detail="Loyiha topilmadi")
        if owner != user_id:
            raise HTTPException(status_code=403, detail="Bu loyihaga kirish huquqingiz yo'q")

    @app.post("/projects", response_model=ProjectResponse)
    async def create_project_endpoint(
        payload: ProjectCreateRequest, user_id: str = Depends(current_user_id)
    ) -> ProjectResponse:
        used = count_projects(user_id)
        if used >= MAX_PROJECTS_PER_USER:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "project_limit_reached",
                    "message": (
                        f"Loyihalar chegarasiga yetdingiz ({used}/{MAX_PROJECTS_PER_USER}). "
                        "Davom etish uchun eski loyihalardan birini o'chiring."
                    ),
                    "used": used,
                    "limit": MAX_PROJECTS_PER_USER,
                },
            )
        project = create_project(user_id, payload.name.strip())
        return ProjectResponse(**project)

    @app.get("/projects")
    async def list_projects_endpoint(user_id: str = Depends(current_user_id)) -> dict:
        return {"projects": list_projects(user_id), "limit": MAX_PROJECTS_PER_USER}

    @app.delete("/projects/{project_id}")
    async def delete_project_endpoint(
        project_id: str, user_id: str = Depends(current_user_id)
    ) -> dict:
        _assert_project_access(project_id, user_id)
        delete_project(project_id)
        return {"status": "ok"}

    @app.get("/projects/{project_id}/files")
    async def list_project_files_endpoint(
        project_id: str, user_id: str = Depends(current_user_id)
    ) -> dict:
        _assert_project_access(project_id, user_id)
        files = list_project_files(project_id)
        return {
            "files": [{"id": f["id"], "filename": f["filename"], "size_bytes": f["size_bytes"]} for f in files],
            "limit": MAX_PROJECT_FILES,
        }

    @app.post("/projects/{project_id}/files")
    async def upload_project_file_endpoint(
        project_id: str, file: UploadFile = File(...), user_id: str = Depends(current_user_id)
    ) -> dict:
        _assert_project_access(project_id, user_id)

        used = count_project_files(project_id)
        if used >= MAX_PROJECT_FILES:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "project_file_limit_reached",
                    "message": (
                        f"Loyiha fayllar chegarasiga yetdi ({used}/{MAX_PROJECT_FILES}). "
                        "Yangisini yuklashdan oldin birini o'chiring."
                    ),
                    "used": used,
                    "limit": MAX_PROJECT_FILES,
                },
            )

        from files import extract_text

        data = await file.read()
        if len(data) > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Fayl juda katta (maksimal 5 MB).")
        content = extract_text(file.filename or "", data)
        saved = add_project_file(project_id, file.filename or "fayl", content, len(data))
        return {"id": saved["id"], "filename": saved["filename"], "size_bytes": saved["size_bytes"]}

    @app.delete("/projects/{project_id}/files/{file_id}")
    async def delete_project_file_endpoint(
        project_id: str, file_id: str, user_id: str = Depends(current_user_id)
    ) -> dict:
        _assert_project_access(project_id, user_id)
        if get_project_file_owner_project(file_id) != project_id:
            raise HTTPException(status_code=404, detail="Fayl topilmadi")
        delete_project_file(file_id)
        return {"status": "ok"}

    @app.patch("/sessions/{session_id}/project")
    async def update_session_project_endpoint(
        session_id: str, payload: SessionProjectRequest, user_id: str | None = Depends(current_user_id)
    ) -> dict:
        _assert_session_access(session_id, user_id)
        if payload.project_id is not None:
            _assert_project_access(payload.project_id, user_id)
        set_session_project(session_id, payload.project_id)
        return {"status": "ok"}


if ENABLE_AUTH:
    from auth import router as auth_router

    app.include_router(auth_router, prefix="/auth", tags=["auth"])

if ENABLE_GOOGLE_DOCS_TOOL:
    from google_docs_tool import router as google_docs_router

    app.include_router(google_docs_router, tags=["google-docs"])


# ---------------------------------------------------------------------------
# FRONTENDNI XIZMAT KO'RSATISH (qulaylik uchun, ixtiyoriy)
# ---------------------------------------------------------------------------
# Bu qator ENG OXIRIDA turishi SHART — aks holda yuqoridagi API yo'llarini
# "yutib" qo'yishi mumkin.
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
