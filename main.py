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
import logging
import os
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
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


# ---------------------------------------------------------------------------
# SESSIYA EGALIGI (IDOR himoyasi)
# ---------------------------------------------------------------------------
# ENABLE_AUTH=true bo'lsa, /history, /sessions, DELETE /sessions
# endpointlari FAQAT joriy foydalanuvchiga tegishli sessiyalarni ko'rsatadi
# — aks holda har qanday kishi boshgan session_id (UUID) ni topib olib
# boshqa foydalanuvchining suhbatini o'qishi/o'chirishi mumkin edi.
# ENABLE_AUTH=false bo'lganda (demo/mehmon rejimi) egalik tushunchasi yo'q —
# bu faqat lokal sinov/demo uchun maqsadga muvofiq.
if ENABLE_AUTH:
    from auth import get_current_user_optional
    from database import get_session_owner

    def current_user_id_optional(user=Depends(get_current_user_optional)) -> str | None:
        return user.id if user else None
else:
    def current_user_id_optional() -> str | None:
        return None

    def get_session_owner(session_id: str) -> str | None:  # noqa: ARG001
        return None


# ---------------------------------------------------------------------------
# SUHBAT TARIXI (SESSIYA) SAQLASH
# ---------------------------------------------------------------------------
if ENABLE_DATABASE:
    from database import (
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

    def get_or_create_session(session_id: str | None, user_id: str | None = None) -> str:
        sid = session_id or str(uuid.uuid4())
        if sid not in _memory_sessions:
            _memory_sessions[sid] = []
            _memory_session_order.append(sid)
        return sid

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
    "kod va tushunarli tushuntirish bilan javob bering. Javobingizni o'zbek "
    "tilida yozing, kod bloklarini uchta qiyshiq chiziq (```) bilan belgilang."
    + OFF_TOPIC_SUFFIX
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_SYSTEM_PROMPT = (
    "Siz do'stona va ijodiy suhbatdoshsiz. Foydalanuvchi bilan g'oyalar, "
    "rejalar va umumiy savollar haqida erkin va tushunarli o'zbek tilida "
    "suhbatlashing."
)

# "Qidiruv/hujjat tahlili" domeni — kuchliroq Gemini modelidan foydalanadi
# (yangi API kalit talab qilinmaydi, xuddi shu GEMINI_API_KEY ishlatiladi).
GEMINI_RESEARCH_MODEL = os.getenv("GEMINI_RESEARCH_MODEL", "gemini-3.5-flash")
GEMINI_RESEARCH_SYSTEM_PROMPT = (
    "Siz chuqur tahlil va qidiruv bo'yicha ixtisoslashgan yordamchisiz. "
    "Foydalanuvchi biriktirgan hujjat/matn yoki mavzuni sinchiklab tahlil "
    "qiling, asosiy fikrlarni ajratib, tuzilgan va manbaga tayangan javob "
    "bering. Javobingizni o'zbek tilida yozing." + OFF_TOPIC_SUFFIX
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
        if request.url.path == "/chat":
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


@app.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest, user_id: str | None = Depends(current_user_id_optional)
) -> ChatResponse:
    # session_id boshqa foydalanuvchiga tegishli bo'lsa, unga yozib
    # qo'yishga yo'l qo'ymaymiz — shu o'rniga yangi (o'ziga tegishli)
    # sessiya ochiladi.
    existing_owner = get_session_owner(payload.session_id) if payload.session_id else None
    if existing_owner is not None and existing_owner != user_id:
        session_id = get_or_create_session(None, user_id=user_id)
    else:
        session_id = get_or_create_session(payload.session_id, user_id=user_id)

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
        if ENABLE_TOOLS:
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


def _assert_session_access(session_id: str, user_id: str | None) -> None:
    """ENABLE_AUTH yoqilganda: sessiya boshqa foydalanuvchiga tegishli
    bo'lsa 403 qaytaradi. ENABLE_AUTH o'chirilganda hech narsa qilmaydi
    (demo/mehmon rejimi — eski xatti-harakat saqlanadi)."""
    if not ENABLE_AUTH:
        return
    owner = get_session_owner(session_id)
    if owner is not None and owner != user_id:
        raise HTTPException(status_code=403, detail="Bu sessiyaga kirish huquqingiz yo'q")


@app.get("/history/{session_id}")
async def history(
    session_id: str, user_id: str | None = Depends(current_user_id_optional)
) -> dict:
    _assert_session_access(session_id, user_id)
    return {"session_id": session_id, "messages": list_messages(session_id)}


@app.get("/sessions")
async def sessions(user_id: str | None = Depends(current_user_id_optional)) -> dict:
    # ENABLE_AUTH yoqilgan bo'lsa, faqat joriy foydalanuvchining o'z
    # sessiyalari qaytariladi (login qilinmagan bo'lsa — bo'sh ro'yxat).
    if ENABLE_AUTH:
        return {"sessions": list_sessions(user_id=user_id) if user_id else []}
    return {"sessions": list_sessions()}


@app.delete("/sessions/{session_id}")
async def delete_session_endpoint(
    session_id: str, user_id: str | None = Depends(current_user_id_optional)
) -> dict:
    _assert_session_access(session_id, user_id)
    delete_session(session_id)
    return {"status": "ok"}


if ENABLE_AUTH:
    from auth import router as auth_router

    app.include_router(auth_router, prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# FRONTENDNI XIZMAT KO'RSATISH (qulaylik uchun, ixtiyoriy)
# ---------------------------------------------------------------------------
# Bu qator ENG OXIRIDA turishi SHART — aks holda yuqoridagi API yo'llarini
# "yutib" qo'yishi mumkin.
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
