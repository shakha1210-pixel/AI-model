"""
project_tool.py — Claude uchun loyiha (project) papkasidagi fayllar bilan
ishlash tool'lari: ro'yxat, o'qish, yozish/yangilash.

Yoqish: .env faylida ENABLE_PROJECT_FILES_TOOL=true (ENABLE_DATABASE=true
ham SHART — loyihalar ma'lumotlar bazasida saqlanadi, main.py'dagi
fail-safe tekshiruviga qarang).

Bu tool FAQAT joriy suhbat (session_id) biriktirilgan loyiha papkasi
bilan ishlaydi — Claude'dan project_id so'ralmaydi, u avtomatik
aniqlanadi. Agar suhbat hech qanday loyihaga bog'lanmagan bo'lsa, tool
xato qaytaradi. Rasm generatsiya (Leonardo) domeni bu tool'dan
mustasno — u tool-use aylanishida umuman ishtirok etmaydi.
"""

import os

from database import (
    count_project_files,
    get_session_project_id,
    list_project_files,
    upsert_project_file,
)

MAX_PROJECT_FILES = int(os.getenv("MAX_PROJECT_FILES", "10"))
# Agent yozadigan fayl matni ham cheklanadi — cheksiz o'sib ketmasligi
# uchun (xuddi foydalanuvchi yuklagan fayllar /files.py'da cheklangani kabi).
MAX_PROJECT_FILE_CONTENT_CHARS = 20000

PROJECT_TOOLS = [
    {
        "name": "project_list_files",
        "description": "Joriy suhbat biriktirilgan loyiha papkasidagi fayllar ro'yxatini qaytaradi.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "project_read_file",
        "description": "Loyiha papkasidagi bitta faylning to'liq matnini o'qiydi.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Fayl nomi (project_list_files natijasidagi nomlardan biri)",
                },
            },
            "required": ["filename"],
        },
    },
    {
        "name": "project_write_file",
        "description": (
            "Loyiha papkasiga yangi fayl yozadi yoki xuddi shu nomdagi mavjud "
            "faylni to'liq yangi matn bilan almashtiradi."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "content": {"type": "string", "description": "Faylning to'liq yangi matni"},
            },
            "required": ["filename", "content"],
        },
    },
]


def _no_project_error() -> dict:
    return {"error": "Bu suhbat hech qanday loyiha papkasiga biriktirilmagan."}


async def project_list_files(session_id: str) -> dict:
    project_id = get_session_project_id(session_id)
    if not project_id:
        return _no_project_error()
    files = list_project_files(project_id)
    return {"files": [{"filename": f["filename"], "size_bytes": f["size_bytes"]} for f in files]}


async def project_read_file(session_id: str, filename: str) -> dict:
    project_id = get_session_project_id(session_id)
    if not project_id:
        return _no_project_error()
    for file in list_project_files(project_id):
        if file["filename"] == filename:
            return {"filename": file["filename"], "content": file["content"]}
    return {"error": f"'{filename}' nomli fayl loyiha papkasida topilmadi."}


async def project_write_file(session_id: str, filename: str, content: str) -> dict:
    project_id = get_session_project_id(session_id)
    if not project_id:
        return _no_project_error()

    existing_names = {f["filename"] for f in list_project_files(project_id)}
    if filename not in existing_names and count_project_files(project_id) >= MAX_PROJECT_FILES:
        return {
            "error": (
                f"Loyiha fayllar chegarasiga yetgan ({MAX_PROJECT_FILES} ta). "
                "Yangi fayl yozishdan oldin birini o'chiring."
            )
        }

    saved = upsert_project_file(project_id, filename, content[:MAX_PROJECT_FILE_CONTENT_CHARS])
    return {"status": "ok", "filename": saved["filename"]}


_HANDLERS = {
    "project_list_files": project_list_files,
    "project_read_file": project_read_file,
    "project_write_file": project_write_file,
}


async def dispatch(name: str, tool_input: dict, session_id: str = "noma'lum") -> dict:
    handler = _HANDLERS.get(name)
    if not handler:
        return {"error": f"Noma'lum loyiha tool: {name}"}
    try:
        return await handler(session_id=session_id, **tool_input)
    except TypeError as exc:
        return {"error": f"Noto'g'ri parametrlar: {exc}"}
