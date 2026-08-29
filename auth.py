"""
auth.py — Ro'yxatdan o'tish, kirish va JWT token boshqaruvi

Yoqish uchun main.py yoki .env faylida ENABLE_AUTH=true qiling. Bu modul
database.py dagi User jadvalidan foydalanadi — shuning uchun ENABLE_DATABASE
ham yoqilgan bo'lishi kerak.
"""

import datetime
import logging
import os
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from database import SessionLocal, User, init_db
from rate_limiter import RateLimitExceeded, check_auth_rate_limit

# TODO: bu maxfiy kalitni albatta o'zgartiring va faqat .env faylida saqlang!
_DEFAULT_JWT_SECRET = "CHANGE_ME_random_secret_key"
JWT_SECRET = os.getenv("JWT_SECRET", _DEFAULT_JWT_SECRET)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 kun

# FAIL-SAFE: agar ENABLE_AUTH=true bo'lsa-yu, JWT_SECRET hali standart
# (o'zgartirilmagan) qiymatda qolgan bo'lsa, server sukut bilan ishga
# tushmasligi kerak — aks holda har kim o'zi token soxtalashtira oladi.
# Faqat aniq ravishda ALLOW_INSECURE_JWT_SECRET=true qilingandagina (masalan
# lokal sinov uchun) bu tekshiruv chetlab o'tiladi.
_jwt_secret_insecure = (not JWT_SECRET) or JWT_SECRET == _DEFAULT_JWT_SECRET or len(JWT_SECRET) < 32
if _jwt_secret_insecure and os.getenv("ALLOW_INSECURE_JWT_SECRET", "false").lower() != "true":
    raise RuntimeError(
        "XAVFSIZLIK XATOSI: JWT_SECRET yo'q, standart qiymatda qolgan yoki "
        "juda qisqa (kamida 32 belgi bo'lishi kerak). Terminalda "
        "`openssl rand -hex 32` buyrug'i bilan tasodifiy qiymat yarating va "
        "uni .env faylidagi JWT_SECRET ga yozing. (Faqat lokal sinov uchun, "
        "xavfni tushungan holda, ALLOW_INSECURE_JWT_SECRET=true qo'yib bu "
        "tekshiruvni vaqtincha chetlab o'tishingiz mumkin.)"
    )

# ---------------------------------------------------------------------------
# Google OAuth sozlamalari — console.cloud.google.com'dan olinadi
# ---------------------------------------------------------------------------
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/auth/google/callback"
)
# Google login muvaffaqiyatli bo'lgach foydalanuvchi shu sahifaga qaytariladi
FRONTEND_LOGIN_SUCCESS_URL = os.getenv(
    "FRONTEND_LOGIN_SUCCESS_URL", "http://127.0.0.1:8000/login.html"
)

logger = logging.getLogger("agent.auth")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

router = APIRouter()

# ---------------------------------------------------------------------------
# XAVFSIZLIK: Google login yakunida to'liq JWT tokenni URL orqali (?token=)
# yuborish xavfli — u brauzer tarixida, server (proxy) loglarida va Referer
# headerda qolib ketishi mumkin. Shuning uchun URL orqali FAQAT qisqa
# muddatli, bir martalik "almashish kodi" yuboriladi; frontend keyin uni
# POST /auth/google/exchange orqali haqiqiy tokenga almashtiradi.
# Eslatma: bu xotirada saqlanadi — bir nechta server nusxasi (replika)
# ishlatilsa, Redis kabi umumiy xotiraga o'tkazish tavsiya etiladi.
# ---------------------------------------------------------------------------
_EXCHANGE_CODE_TTL_SECONDS = 60
_pending_exchange_codes: dict[str, tuple[str, datetime.datetime]] = {}


def _create_exchange_code(access_token: str) -> str:
    import secrets

    code = secrets.token_urlsafe(32)
    expires = datetime.datetime.utcnow() + datetime.timedelta(seconds=_EXCHANGE_CODE_TTL_SECONDS)
    _pending_exchange_codes[code] = (access_token, expires)
    return code


class ExchangeRequest(BaseModel):
    code: str


class RegisterRequest(BaseModel):
    ism: str
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: str) -> str:
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Avtorizatsiyadan o'tilmagan"
    )
    if not token:
        raise unauthorized
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise unauthorized
    except JWTError:
        raise unauthorized

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            raise unauthorized
        return user


def get_current_user_optional(token: str = Depends(oauth2_scheme)) -> User | None:
    """get_current_user()ga o'xshaydi, lekin token bo'lmasa yoki yaroqsiz
    bo'lsa xato chiqarish o'rniga None qaytaradi. /chat kabi mehmon
    foydalanuvchilarga ham ochiq endpointlarda, lekin token bo'lsa uni
    tanib, sessiyani egasiga bog'lash uchun ishlatiladi."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
    except JWTError:
        return None

    with SessionLocal() as db:
        return db.get(User, user_id)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "noma'lum"


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, request: Request) -> TokenResponse:
    try:
        check_auth_rate_limit(_client_ip(request))
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    init_db()
    with SessionLocal() as db:
        existing = db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Bu email allaqachon ro'yxatdan o'tgan")

        user = User(ism=payload.ism, email=payload.email, parol_hash=hash_password(payload.password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    # Brute-force himoyasi: bir IP manzil belgilangan vaqt oynasida cheklangan
    # sondagina login urinishi qila oladi — ENABLE_AUTH yoqilgan bo'lsa HAR
    # DOIM faol (ENABLE_RATE_LIMIT bayrog'iga bog'liq emas).
    try:
        check_auth_rate_limit(_client_ip(request))
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == form_data.username).first()
        if not user or not user.parol_hash:
            # Foydalanuvchi topilmadi, yoki Google orqali ro'yxatdan o'tgan
            # (demak parol umuman qo'yilmagan) — shu sabab bir xil xabar
            # qaytariladi (email mavjudligini oshkor qilmaslik uchun).
            raise HTTPException(status_code=401, detail="Email yoki parol noto'g'ri")
        if not verify_password(form_data.password, user.parol_hash):
            raise HTTPException(status_code=401, detail="Email yoki parol noto'g'ri")
        return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me")
def me(current_user: User = Depends(get_current_user)) -> dict:
    return {"id": current_user.id, "ism": current_user.ism, "email": current_user.email}


# ---------------------------------------------------------------------------
# Google orqali kirish
# ---------------------------------------------------------------------------

@router.get("/google/login")
def google_login() -> RedirectResponse:
    """Foydalanuvchini Google'ning o'z login sahifasiga yo'naltiradi."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_CLIENT_ID sozlanmagan. .env faylini to'ldiring.",
        )
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/google/callback")
async def google_callback(code: str | None = None, error: str | None = None):
    """Google foydalanuvchini shu manzilga qaytaradi (?code=... bilan)."""
    if error or not code:
        raise HTTPException(status_code=400, detail=f"Google kirish bekor qilindi: {error}")

    init_db()

    async with httpx.AsyncClient(timeout=20) as client:
        # 1) 'code'ni haqiqiy tokenga almashtiramiz
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if token_response.status_code != 200:
            # Google'ning aniq sababini (masalan "redirect_uri_mismatch",
            # "invalid_client") loglab qo'yamiz — foydalanuvchiga umumiy
            # xabar ko'rsatiladi, lekin Render Logs'da haqiqiy sabab
            # ko'rinadi (redirect_uri quyida ham loglanadi — Google
            # Console'dagi ro'yxat bilan solishtirish uchun).
            logger.error(
                "Google token almashinuvi xato: %s %s | redirect_uri=%s",
                token_response.status_code, token_response.text, GOOGLE_REDIRECT_URI,
            )
            raise HTTPException(
                status_code=502, detail="Google token olishda xatolik yuz berdi."
            )
        google_token = token_response.json()["access_token"]

        # 2) Token orqali foydalanuvchi ma'lumotlarini (ism, email) olamiz
        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {google_token}"},
        )
        if userinfo_response.status_code != 200:
            logger.error(
                "Google userinfo xato: %s %s",
                userinfo_response.status_code, userinfo_response.text,
            )
            raise HTTPException(
                status_code=502, detail="Google foydalanuvchi ma'lumotini olib bo'lmadi."
            )
        info = userinfo_response.json()

    google_id = info["sub"]
    email = info.get("email", "")
    ism = info.get("name", email.split("@")[0] if email else "Google foydalanuvchi")

    with SessionLocal() as db:
        user = db.query(User).filter(User.google_id == google_id).first()
        if not user:
            # Google email bilan avval oddiy ro'yxatdan o'tgan bo'lsa, hisoblarni
            # bog'laymiz (bir xil emailga ikkita alohida foydalanuvchi bo'lmasin)
            user = db.query(User).filter(User.email == email).first()
            if user:
                user.google_id = google_id
            else:
                user = User(ism=ism, email=email, google_id=google_id, parol_hash=None)
                db.add(user)
            db.commit()
            db.refresh(user)

        access_token = create_access_token(user.id)

    # To'liq tokenni URL'ga qo'shish o'rniga qisqa muddatli bir martalik
    # kod yuboramiz — login.html buni POST /auth/google/exchange orqali
    # haqiqiy tokenga almashtiradi (pastdagi login.html o'zgarishiga qarang).
    exchange_code = _create_exchange_code(access_token)
    redirect_url = f"{FRONTEND_LOGIN_SUCCESS_URL}?exchange_code={exchange_code}"
    return RedirectResponse(redirect_url)


@router.post("/google/exchange", response_model=TokenResponse)
def exchange_google_code(payload: ExchangeRequest) -> TokenResponse:
    """login.html shu endpointga bir martalik kodni yuborib, haqiqiy JWT
    tokenni oladi. Kod faqat bir marta va TTL ichida ishlaydi."""
    entry = _pending_exchange_codes.pop(payload.code, None)
    if not entry:
        raise HTTPException(status_code=400, detail="Kod yaroqsiz yoki muddati o'tgan")
    access_token, expires = entry
    if datetime.datetime.utcnow() > expires:
        raise HTTPException(status_code=400, detail="Kod muddati o'tgan")
    return TokenResponse(access_token=access_token)
