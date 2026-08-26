"""
database.py — Suhbat tarixini doimiy saqlash (SQLite yoki PostgreSQL)

Standart holatda main.py xotirada (RAM) ishlaydi. Bu modulni yoqish uchun
main.py yoki .env faylida ENABLE_DATABASE=true qiling.

Jadvallar: users, sessions, messages (loyiha hujjatida ko'rsatilganidek).
"""

import datetime
import os
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, create_engine, inspect, text
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
    project_id = Column(String, ForeignKey("projects.id"), nullable=True)
    boshlangan_vaqt = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="sessions")
    project = relationship("Project", back_populates="sessions")
    messages = relationship(
        "ChatMessage", back_populates="session", order_by="ChatMessage.vaqt"
    )


class Project(Base):
    """Loyiha (project) — suhbatlarni va fayllarni guruhlaydigan papka.
    Har bir loyiha bitta foydalanuvchiga tegishli (ENABLE_AUTH+ENABLE_DATABASE
    talab qilinadi — main.py'dagi ENABLE_PROJECTS bayrog'iga qarang)."""

    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    nomi = Column(String, nullable=False)
    yaratilgan_vaqt = Column(DateTime, default=datetime.datetime.utcnow)

    sessions = relationship("ChatSession", back_populates="project")
    files = relationship(
        "ProjectFile", back_populates="project", order_by="ProjectFile.yuklangan_vaqt",
        cascade="all, delete-orphan",
    )


class ProjectFile(Base):
    """Loyiha papkasiga yuklangan (yoki agent tomonidan yozilgan) fayl —
    xotira tejash uchun asl bayt emas, o'qiladigan MATN saqlanadi (xuddi
    /files/extract kabi)."""

    __tablename__ = "project_files"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    nomi = Column(String, nullable=False)
    matn = Column(Text, nullable=False)
    hajm_bayt = Column(Integer, nullable=False)
    yuklangan_vaqt = Column(DateTime, default=datetime.datetime.utcnow)

    project = relationship("Project", back_populates="files")


class ChatMessage(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" yoki "assistant"
    content = Column(Text, nullable=False)
    image_url = Column(String, nullable=True)  # Leonardo AI rasm javoblari uchun
    vaqt = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_add_missing_columns()


def _migrate_add_missing_columns() -> None:
    """Yengil "migratsiya": create_all() faqat YO'Q jadvallarni yaratadi,
    ESKI (loyihalar funksiyasidan oldin yaratilgan) jadvallarga yangi
    ustun qo'shmaydi. Shu sabab sessions.project_id ustunini qo'lda
    qo'shamiz (agar hali yo'q bo'lsa) — aks holda avvalgi versiyada
    yaratilgan ma'lumotlar bazasi bilan server ishga tushganda BARCHA
    sessiyaga oid so'rovlar "no such column" xatosi bilan yiqilardi."""
    inspector = inspect(engine)
    if "sessions" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("sessions")}
    if "project_id" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE sessions ADD COLUMN project_id VARCHAR"))


def get_or_create_session(
    session_id: str | None, user_id: str | None = None, project_id: str | None = None
) -> str:
    with SessionLocal() as db:
        if session_id:
            existing = db.get(ChatSession, session_id)
            if existing:
                return existing.id
        new_session = ChatSession(
            id=session_id or str(uuid.uuid4()), user_id=user_id, project_id=project_id
        )
        db.add(new_session)
        db.commit()
        return new_session.id


def count_sessions(user_id: str) -> int:
    """Foydalanuvchining jami sessiyalar soni — per-user xotira chegarasini
    (MAX_SESSIONS_PER_USER, main.py) tekshirish uchun ishlatiladi."""
    with SessionLocal() as db:
        return db.query(ChatSession).filter(ChatSession.user_id == user_id).count()


def get_session_project_id(session_id: str) -> str | None:
    with SessionLocal() as db:
        session = db.get(ChatSession, session_id)
        return session.project_id if session else None


def set_session_project(session_id: str, project_id: str | None) -> None:
    """Mavjud sessiyani loyiha papkasiga biriktiradi (yoki project_id=None
    bilan ajratadi)."""
    with SessionLocal() as db:
        session = db.get(ChatSession, session_id)
        if session:
            session.project_id = project_id
            db.commit()


def get_session_owner(session_id: str) -> str | None:
    """Sessiya kimga tegishli ekanini qaytaradi (egasi yo'q bo'lsa None —
    anonim/mehmon sessiyasi). main.py bu yordamida IDOR (boshqa
    foydalanuvchi sessiyasini o'qish/o'chirish) hujumlarining oldini oladi.
    """
    with SessionLocal() as db:
        session = db.get(ChatSession, session_id)
        return session.user_id if session else None


def save_message(session_id: str, role: str, content: str, image_url: str | None = None) -> None:
    with SessionLocal() as db:
        db.add(ChatMessage(session_id=session_id, role=role, content=content, image_url=image_url))
        db.commit()


def list_messages(session_id: str) -> list[dict]:
    with SessionLocal() as db:
        rows = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.vaqt)
            .all()
        )
        return [{"role": r.role, "content": r.content, "image_url": r.image_url} for r in rows]


def list_sessions(user_id: str | None = None) -> list[dict]:
    """Sessiyalarni (eng yangisi birinchi) va har biri uchun qisqa preview
    matnini qaytaradi. user_id berilsa, FAQAT o'sha foydalanuvchiga tegishli
    sessiyalar qaytariladi — aks holda (ENABLE_AUTH=false) barcha anonim
    sessiyalar ko'rinadi, bu faqat demo/mehmon rejimida qabul qilinadi.
    Loyihaga biriktirilgan sessiyalar uchun project_id/project_name ham
    qaytariladi (yon paneldagi loyiha yorlig'i uchun)."""
    with SessionLocal() as db:
        query = db.query(ChatSession)
        if user_id is not None:
            query = query.filter(ChatSession.user_id == user_id)
        sessions = query.order_by(ChatSession.boshlangan_vaqt.desc()).all()
        project_names = {p.id: p.nomi for p in db.query(Project).all()}
        result = []
        for s in sessions:
            first_user_msg = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == s.id, ChatMessage.role == "user")
                .order_by(ChatMessage.vaqt)
                .first()
            )
            preview = (first_user_msg.content[:60] if first_user_msg else "Bo'sh suhbat")
            result.append({
                "id": s.id,
                "preview": preview,
                "project_id": s.project_id,
                "project_name": project_names.get(s.project_id) if s.project_id else None,
            })
        return result


def delete_session(session_id: str) -> None:
    with SessionLocal() as db:
        db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        db.query(ChatSession).filter(ChatSession.id == session_id).delete()
        db.commit()


# ---------------------------------------------------------------------------
# LOYIHALAR (PROJECTS)
# ---------------------------------------------------------------------------

def create_project(user_id: str, name: str) -> dict:
    with SessionLocal() as db:
        project = Project(user_id=user_id, nomi=name)
        db.add(project)
        db.commit()
        db.refresh(project)
        return {"id": project.id, "name": project.nomi}


def list_projects(user_id: str) -> list[dict]:
    with SessionLocal() as db:
        projects = (
            db.query(Project)
            .filter(Project.user_id == user_id)
            .order_by(Project.yaratilgan_vaqt.desc())
            .all()
        )
        return [{"id": p.id, "name": p.nomi} for p in projects]


def get_project_owner(project_id: str) -> str | None:
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        return project.user_id if project else None


def count_projects(user_id: str) -> int:
    with SessionLocal() as db:
        return db.query(Project).filter(Project.user_id == user_id).count()


def delete_project(project_id: str) -> None:
    """Loyihani va uning fayllarini o'chiradi. Loyihaga biriktirilgan
    sessiyalar O'CHIRILMAYDI — faqat loyihadan ajratiladi (suhbat tarixi
    saqlanib qoladi, shunchaki endi hech qanday papkaga tegishli emas)."""
    with SessionLocal() as db:
        db.query(ChatSession).filter(ChatSession.project_id == project_id).update(
            {"project_id": None}
        )
        db.query(ProjectFile).filter(ProjectFile.project_id == project_id).delete()
        db.query(Project).filter(Project.id == project_id).delete()
        db.commit()


def add_project_file(project_id: str, filename: str, content: str, size_bytes: int) -> dict:
    with SessionLocal() as db:
        file = ProjectFile(
            project_id=project_id, nomi=filename, matn=content, hajm_bayt=size_bytes
        )
        db.add(file)
        db.commit()
        db.refresh(file)
        return {"id": file.id, "filename": file.nomi, "size_bytes": file.hajm_bayt}


def upsert_project_file(project_id: str, filename: str, content: str) -> dict:
    """Agent tool'i (project_write_file) uchun: xuddi shu nomdagi fayl
    mavjud bo'lsa ustiga yozadi, aks holda yangi fayl yaratadi."""
    with SessionLocal() as db:
        existing = (
            db.query(ProjectFile)
            .filter(ProjectFile.project_id == project_id, ProjectFile.nomi == filename)
            .first()
        )
        size_bytes = len(content.encode("utf-8"))
        if existing:
            existing.matn = content
            existing.hajm_bayt = size_bytes
            db.commit()
            return {"id": existing.id, "filename": existing.nomi, "size_bytes": existing.hajm_bayt}
        file = ProjectFile(project_id=project_id, nomi=filename, matn=content, hajm_bayt=size_bytes)
        db.add(file)
        db.commit()
        db.refresh(file)
        return {"id": file.id, "filename": file.nomi, "size_bytes": file.hajm_bayt}


def list_project_files(project_id: str) -> list[dict]:
    with SessionLocal() as db:
        files = (
            db.query(ProjectFile)
            .filter(ProjectFile.project_id == project_id)
            .order_by(ProjectFile.yuklangan_vaqt)
            .all()
        )
        return [
            {"id": f.id, "filename": f.nomi, "content": f.matn, "size_bytes": f.hajm_bayt}
            for f in files
        ]


def count_project_files(project_id: str) -> int:
    with SessionLocal() as db:
        return db.query(ProjectFile).filter(ProjectFile.project_id == project_id).count()


def get_project_file_owner_project(file_id: str) -> str | None:
    """Fayl qaysi loyihaga tegishli ekanini qaytaradi (o'chirishda huquq
    tekshiruvi uchun)."""
    with SessionLocal() as db:
        file = db.get(ProjectFile, file_id)
        return file.project_id if file else None


def delete_project_file(file_id: str) -> None:
    with SessionLocal() as db:
        db.query(ProjectFile).filter(ProjectFile.id == file_id).delete()
        db.commit()


if __name__ == "__main__":
    # Qo'lda ishga tushirish: python database.py — jadvallarni yaratadi.
    init_db()
    print(f"Ma'lumotlar bazasi tayyor: {DATABASE_URL}")
