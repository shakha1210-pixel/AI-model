"""
safety.py — Kirish/chiqish xabarlarini tekshiruvchi minimal moderatsiya qatlami

MUHIM CHEKLOV: bu yerdagi kalit-so'z asosidagi tekshiruv FAQAT birinchi
himoya qatlami (defense-in-depth) sifatida mo'ljallangan — u professional
moderatsiya xizmatining (masalan, OpenAI Moderation API, Perspective API,
yoki Anthropic'ning tavsiya etilgan usullari) o'rnini bosa olmaydi.
Productionga chiqishdan oldin buni haqiqiy moderatsiya API'siga almashtirish
tavsiya etiladi — tafsilot uchun TOLDIRILISHI-KERAK-BOLGAN-ROYXAT.txt.

Ishlash tamoyili:
  1) check_input()  — foydalanuvchi xabari modelga yuborilishidan OLDIN
     tekshiriladi. Aniq xavfli so'rov (masalan, zararli dastur yozish,
     o'zini yoki boshqani zararlash bo'yicha ko'rsatma) aniqlansa, model
     umuman chaqirilmaydi — xavfsiz rad javobi darhol qaytariladi.
  2) check_output() — modeldan qaytgan javob foydalanuvchiga yuborilishidan
     OLDIN tekshiriladi (ikkinchi qatlam — model o'zi xato qilishi mumkin).
  3) Har ikkala holatda ham hodisa log qilinadi (audit) — lekin xabar matni
     to'liq emas, faqat qisqa parcha va sabab log qilinadi (haddan tashqari
     hissiy/shaxsiy ma'lumotni log fayllarida saqlamaslik uchun).
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("agent.safety")

REFUSAL_MESSAGE = (
    "Kechirasiz, bu so'rovga yordam bera olmayman, chunki u xavfsizlik "
    "siyosatimizga zid keladi (zararli/xavfli kontent kategoriyasi)."
)

# O'zini yoki boshqani zararlash haqidagi xabarlar UMUMAN BOSHQACHA
# munosabatni talab qiladi — bu "xavfsizlik siyosati buzilishi" emas,
# balki odam yordamga muhtoj bo'lishi mumkin bo'lgan holat. Shuning uchun
# bunday xabarlarga oddiy REFUSAL_MESSAGE emas, balki qo'llab-quvvatlovchi
# javob va resurslar beriladi, va bu ALOHIDA kategoriya sifatida
# belgilanadi (pastdagi ModerationResult.category maydoniga qarang).
SUPPORT_MESSAGE = (
    "Bu yerda o'qiganlarim meni tashvishga soldi — sizga yaxshi tilayman. "
    "Men kod yozish bo'yicha yordamchiman va bu mavzuda malakali yordam "
    "bera olmayman, lekin gaplashish uchun ishonchli odam yoki mutaxassis "
    "topish juda muhim. O'zbekistonda ishonch telefoni: 1050 (bepul, "
    "kecha-kunduz). Agar xavf ostida bo'lsangiz, 103 (tez yordam)ga qo'ng'iroq qiling."
)

# Diqqat: bu ro'yxatlar to'liq emas va faqat DEMO/boshlang'ich daraja uchun.
# Naqshlar juda keng bo'lmasligi kerak (aks holda haqiqiy savollarni ham
# bloklab qo'yishi mumkin — "false positive"), shu bilan birga jiddiy
# kategoriyalarni o'tkazib yubormasligi kerak.
_DANGEROUS_PATTERNS = [
    # Zararli dastur / kiberhujum ishlab chiqish so'rovlari
    r"\bransomware\b",
    r"\bkeylogger\b",
    r"\bddos\s*(hujum|attack|skript)",
    r"zarar(li)?\s*dastur\s*(yoz|ishlab chiq)",
    r"\bexploit\b.*(yoz|ishlab chiq)",
    r"boshqa(ning)?\s*(parol|hisob)\w*\s*(o'g'irla|hack|buz)",
]
_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _DANGEROUS_PATTERNS]

# O'zini/boshqani zararlash — ALOHIDA ro'yxat, ALOHIDA javob bilan.
_SELF_HARM_PATTERNS = [
    r"o'zimni\s*(o'ldir|zararla)",
    r"boshqani\s*(o'ldir|zararla)",
]
_COMPILED_SELF_HARM = [re.compile(p, re.IGNORECASE) for p in _SELF_HARM_PATTERNS]


@dataclass
class ModerationResult:
    allowed: bool
    reason: str | None = None
    category: str | None = None  # "danger" | "self_harm"


def _scan(text: str) -> ModerationResult:
    for pattern in _COMPILED_SELF_HARM:
        if pattern.search(text):
            return ModerationResult(allowed=False, reason=pattern.pattern, category="self_harm")
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            return ModerationResult(allowed=False, reason=pattern.pattern, category="danger")
    return ModerationResult(allowed=True)


def check_input(session_id: str, message: str) -> ModerationResult:
    result = _scan(message)
    if not result.allowed:
        logger.warning(
            "Kirish bloklandi | session=%s | sabab_pattern=%s | uzunlik=%d",
            session_id, result.reason, len(message),
        )
    return result


def check_output(session_id: str, reply: str) -> ModerationResult:
    result = _scan(reply)
    if not result.allowed:
        logger.warning(
            "Model javobi bloklandi (ikkinchi qatlam) | session=%s | sabab_pattern=%s",
            session_id, result.reason,
        )
    return result
