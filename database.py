"""
database.py — Suhbat tarixini doimiy saqlash (SQLite yoki PostgreSQL)

Standart holatda main.py xotirada (RAM) ishlaydi. Bu modulni yoqish uchun
main.py yoki .env faylida ENABLE_DATABASE=true qiling.

Jadvallar: users, sessions, messages (loyiha hujjatida ko'rsatilganidek).
"""

import datetime
import os
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ism = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=False)
    # Google orqali ro'yxatdan o'tgan foydalanuvchida parol bo'lmaydi, shuning
    # uchun bu maydon endi ixtiyoriy (nullable=True).
    parol_hash = Column(String, nullable=True)
    google_id = Column(String, unique=True, nullable=True)
    yaratilgan_vaqt = Column(DateTime, default=datetime.datetime.utcnow)

    sessions = relationship("ChatSession", back_populates="user")


class ChatSession(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    boshlangan_vaqt = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="sessions")
    messages = relationship(
        "ChatMessage", back_populates="session", order_by="ChatMessage.vaqt"
    )


class ChatMessage(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" yoki "assistant"
    content = Column(Text, nullable=False)
    vaqt = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_or_create_session(session_id: str | None, user_id: str | None = None) -> str:
    with SessionLocal() as db:
        if session_id:
            existing = db.get(ChatSession, session_id)
            if existing:
                return existing.id
        new_session = ChatSession(id=session_id or str(uuid.uuid4()), user_id=user_id)
        db.add(new_session)
        db.commit()
        return new_session.id


def get_session_owner(session_id: str) -> str | None:
    """Sessiya kimga tegishli ekanini qaytaradi (egasi yo'q bo'lsa None —
    anonim/mehmon sessiyasi). main.py bu yordamida IDOR (boshqa
    foydalanuvchi sessiyasini o'qish/o'chirish) hujumlarining oldini oladi.
    """
    with SessionLocal() as db:
        session = db.get(ChatSession, session_id)
        return session.user_id if session else None


def save_message(session_id: str, role: str, content: str) -> None:
    with SessionLocal() as db:
        db.add(ChatMessage(session_id=session_id, role=role, content=content))
        db.commit()


def list_messages(session_id: str) -> list[dict]:
    with SessionLocal() as db:
        rows = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.vaqt)
            .all()
        )
        return [{"role": r.role, "content": r.content} for r in rows]


def list_sessions(user_id: str | None = None) -> list[dict]:
    """Sessiyalarni (eng yangisi birinchi) va har biri uchun qisqa preview
    matnini qaytaradi. user_id berilsa, FAQAT o'sha foydalanuvchiga tegishli
    sessiyalar qaytariladi — aks holda (ENABLE_AUTH=false) barcha anonim
    sessiyalar ko'rinadi, bu faqat demo/mehmon rejimida qabul qilinadi."""
    with SessionLocal() as db:
        query = db.query(ChatSession)
        if user_id is not None:
            query = query.filter(ChatSession.user_id == user_id)
        sessions = query.order_by(ChatSession.boshlangan_vaqt.desc()).all()
        result = []
        for s in sessions:
            first_user_msg = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == s.id, ChatMessage.role == "user")
                .order_by(ChatMessage.vaqt)
                .first()
            )
            preview = (first_user_msg.content[:60] if first_user_msg else "Bo'sh suhbat")
            result.append({"id": s.id, "preview": preview})
        return result


def delete_session(session_id: str) -> None:
    with SessionLocal() as db:
        db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        db.query(ChatSession).filter(ChatSession.id == session_id).delete()
        db.commit()


if __name__ == "__main__":
    # Qo'lda ishga tushirish: python database.py — jadvallarni yaratadi.
    init_db()
    print(f"Ma'lumotlar bazasi tayyor: {DATABASE_URL}")
