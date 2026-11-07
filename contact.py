"""
contact.py — Landing sahifadagi aloqa formasi uchun POST /contact.

Xabar Telegram botga (asosiy yo'l) va/yoki emailga (SMTP) yuboriladi.
Qaysi kanal sozlangan bo'lsa, o'sha ishlaydi; kamida bittasi muvaffaqiyatli
bo'lsa foydalanuvchiga "ok" qaytadi. Hech biri sozlanmagan bo'lsa 503 —
frontend shunda mailto: zaxira yo'liga o'tadi.

.env / Render Environment:
  TELEGRAM_BOT_TOKEN   — @BotFather bergan token (FAQAT env'da, kodda EMAS)
  TELEGRAM_CHAT_ID     — xabarlar keladigan chat (shaxsiy chat yoki guruh) ID'si
  CONTACT_EMAIL_TO     — (ixtiyoriy) email qabul qiluvchi; SMTP_* auth.py bilan bir xil
"""

import asyncio
import logging
import os
import re
import smtplib
import time
from collections import defaultdict, deque
from email.mime.text import MIMEText
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("agent.contact")
router = APIRouter()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "") or SMTP_USER
CONTACT_EMAIL_TO = os.getenv("CONTACT_EMAIL_TO", "") or SMTP_USER

# Spamdan himoya: har IP uchun va umumiy (IP soxtalashtirilsa ham ishlaydi)
PER_IP_MAX, PER_IP_WINDOW = 5, 3600
GLOBAL_MAX, GLOBAL_WINDOW = 30, 3600
_hits: dict[str, deque] = defaultdict(deque)

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ContactRequest(BaseModel):
    topic: Literal["Savol", "Hamkorlik so'rovi", "Pro navbat"] = "Savol"
    name: str = Field(..., min_length=1, max_length=80)
    contact: str = Field(..., min_length=3, max_length=120)
    message: str = Field(..., min_length=1, max_length=2000)
    website: str = ""  # honeypot: odam ko'rmaydi, botlar to'ldiradi


def _clean(text: str) -> str:
    return _CTRL.sub("", text).strip()


def _allow(key: str, limit: int, window: int) -> bool:
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


async def _send_telegram(text: str) -> bool:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": True},
            )
        if res.status_code != 200:
            logger.error("Telegram xatosi: %s %s", res.status_code, res.text[:200])
            return False
        return True
    except httpx.HTTPError as exc:
        # exc matnida URL (demak TOKEN) bo'lishi mumkin — faqat turini log qilamiz
        logger.error("Telegram ulanish xatosi: %s", type(exc).__name__)
        return False


def _smtp_send(subject: str, body: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM_EMAIL
    msg["To"] = CONTACT_EMAIL_TO
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM_EMAIL, [CONTACT_EMAIL_TO], msg.as_string())


async def _send_email(subject: str, body: str) -> bool:
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD and CONTACT_EMAIL_TO):
        return False
    try:
        await asyncio.to_thread(_smtp_send, subject, body)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Email yuborilmadi: %s", type(exc).__name__)
        return False


def _channels_configured() -> bool:
    return bool(
        (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
        or (SMTP_HOST and SMTP_USER and SMTP_PASSWORD and CONTACT_EMAIL_TO)
    )


@router.post("/contact")
async def contact(payload: ContactRequest, request: Request) -> dict:
    if payload.website:  # honeypot to'ldirilgan — botga "ok" deymiz, hech narsa yubormaymiz
        return {"status": "ok"}

    ip = request.client.host if request.client else "noma'lum"
    if not (_allow(f"ip:{ip}", PER_IP_MAX, PER_IP_WINDOW) and _allow("global", GLOBAL_MAX, GLOBAL_WINDOW)):
        raise HTTPException(status_code=429, detail="Juda ko'p so'rov. Keyinroq urinib ko'ring.")

    if not _channels_configured():
        raise HTTPException(status_code=503, detail="Aloqa kanali sozlanmagan.")

    topic, name = payload.topic, _clean(payload.name)
    contact_info, message = _clean(payload.contact), _clean(payload.message)
    text = f"📩 Apeiron: {topic}\nIsm: {name}\nAloqa: {contact_info}\n\n{message}"

    results = await asyncio.gather(
        _send_telegram(text), _send_email(f"Apeiron: {topic}", text)
    )
    if not any(results):
        raise HTTPException(status_code=502, detail="Xabarni yuborib bo'lmadi.")
    return {"status": "ok"}
