"""
rate_limiter.py — Foydalanuvchi so'rovlarini cheklash (xarajatni nazorat qilish
VA login'ga brute-force hujumlardan himoya)

Sodda "sliding window" (siljiydigan oyna) algoritmi — xotirada ishlaydi.

Ikki xil rejim bor:
  1) check_rate_limit()      — /chat uchun, faqat ENABLE_RATE_LIMIT=true
     bo'lganda main.py orqali ishga tushiriladi (xarajatni nazorat qilish).
  2) check_auth_rate_limit() — /auth/login va /auth/register uchun, ENABLE_AUTH
     yoqilgan bo'lsa HAR DOIM faol (ENABLE_RATE_LIMIT'ga bog'liq emas) —
     chunki login brute-force himoyasi ixtiyoriy "cost control" emas,
     balki asosiy xavfsizlik talabi.

DIQQAT: bu xotirada ishlagani uchun (1) server qayta ishga tushsa hisoblagich
nolga tushadi, (2) bir nechta server nusxasi (masalan Docker'da 2+ replika)
ishlatilsa har biri o'z hisobini yuritadi. Katta loyihalar uchun Redis
asosidagi cheklovchi (masalan `slowapi` yoki `redis` kutubxonasi bilan)
ishlatish tavsiya etiladi.
"""

import os
import time
from collections import defaultdict, deque

MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "20"))
WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

# Login/register uchun ancha qattiqroq standart chegara — oddiy foydalanuvchi
# 5 daqiqada 8 martadan ortiq kirish urinishi qilmaydi, lekin brute-force
# skript (soniyasiga o'nlab urinish) darhol to'xtatiladi.
AUTH_MAX_REQUESTS = int(os.getenv("AUTH_RATE_LIMIT_MAX_REQUESTS", "8"))
AUTH_WINDOW_SECONDS = int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "300"))

_buckets: dict[str, dict[str, deque]] = defaultdict(lambda: defaultdict(deque))


class RateLimitExceeded(Exception):
    pass


def _check(bucket: str, client_key: str, max_requests: int, window_seconds: int) -> None:
    now = time.monotonic()
    window = _buckets[bucket][client_key]

    while window and now - window[0] > window_seconds:
        window.popleft()

    if len(window) >= max_requests:
        raise RateLimitExceeded(
            f"Juda ko'p so'rov yubordingiz. {window_seconds} soniyada "
            f"ko'pi bilan {max_requests} ta so'rov yuborish mumkin."
        )

    window.append(now)


def check_rate_limit(client_key: str) -> None:
    """client_key limitdan oshib ketgan bo'lsa RateLimitExceeded chiqaradi.
    /chat endpointi uchun — faqat ENABLE_RATE_LIMIT=true bo'lsa chaqiriladi."""
    _check("chat", client_key, MAX_REQUESTS, WINDOW_SECONDS)


def get_status(client_key: str) -> dict:
    """client_key uchun joriy holatni qaytaradi (so'rov yubormasdan) —
    frontend'dagi cheklov ko'rsatkichi (rate-limit-badge) shu orqali
    ishlaydi. Eski (window_seconds'dan chiqib ketgan) yozuvlarni
    tozalab, keyin qolgan/limit sonlarini hisoblaydi."""
    now = time.monotonic()
    window = _buckets["chat"][client_key]
    while window and now - window[0] > WINDOW_SECONDS:
        window.popleft()
    used = len(window)
    return {
        "remaining": max(0, MAX_REQUESTS - used),
        "max_requests": MAX_REQUESTS,
        "window_seconds": WINDOW_SECONDS,
    }


def check_auth_rate_limit(client_key: str) -> None:
    """Login/register uchun brute-force himoyasi — ENABLE_AUTH yoqilgan
    bo'lsa HAR DOIM faol, ENABLE_RATE_LIMIT bayrog'iga bog'liq emas."""
    _check("auth", client_key, AUTH_MAX_REQUESTS, AUTH_WINDOW_SECONDS)
