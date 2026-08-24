"""
github_tool.py — Claude uchun GitHub repositoriy bilan ishlash tool'lari
(fayl o'qish/yozish, papka ro'yxati, Pull Request ochish).

Yoqish: .env faylida ENABLE_GITHUB_TOOL=true va GITHUB_TOKEN kiriting.

!!! XAVFSIZLIK OGOHLANTIRISHI !!!
GITHUB_TOKEN uchun albatta "fine-grained personal access token" yarating
(https://github.com/settings/personal-access-tokens) va uni FAQAT kerakli
repo(lar)ga hamda FAQAT quyidagi ruxsatlarga cheklang:
  - Contents: Read and write
  - Pull requests: Read and write
Butun akkountga to'liq kirish beruvchi "classic" tokendan FOYDALANMANG.

Diqqat: agent foydalanuvchi yuborgan (yoki biriktirgan fayldagi) matnga
asoslanib ishlaydi — agar o'sha matn ichida yashirin ko'rsatma bo'lsa
("prompt injection"), agent buni haqiqiy topshiriq deb qabul qilib,
repoga xohlanmagan o'zgartirish kiritishi MUMKIN. Shu sabab:
  - Tokenni ahamiyatsiz/sinov repositoriyga yo'naltiring, yoki
  - `main`/`master` branch'ni himoyalab (branch protection), agentga
    faqat boshqa branch'larga yozish va Pull Request orqali taklif
    qilish huquqini bering — PR'ni birlashtirishdan oldin o'zingiz
    ko'rib chiqing.
"""

import base64
import os

import httpx

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API_URL = "https://api.github.com"

GITHUB_TOOLS = [
    {
        "name": "github_read_file",
        "description": "GitHub repodagi bitta faylning mazmunini o'qiydi.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repo egasi (foydalanuvchi/tashkilot nomi)"},
                "repo": {"type": "string", "description": "Repo nomi"},
                "path": {"type": "string", "description": "Fayl yo'li (masalan: main.py)"},
                "ref": {"type": "string", "description": "Branch yoki commit (ixtiyoriy, standart: asosiy branch)"},
            },
            "required": ["owner", "repo", "path"],
        },
    },
    {
        "name": "github_list_directory",
        "description": "GitHub repodagi papka ichidagi fayl/papkalar ro'yxatini qaytaradi.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "path": {"type": "string", "description": "Papka yo'li (bo'sh qoldirilsa — repo ildizi)"},
                "ref": {"type": "string"},
            },
            "required": ["owner", "repo"],
        },
    },
    {
        "name": "github_create_or_update_file",
        "description": (
            "GitHub repoda fayl yaratadi yoki mavjudini yangilab commit qiladi. "
            "Fayl allaqachon mavjud bo'lsa, avtomatik ravishda uning ustiga yoziladi."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "path": {"type": "string"},
                "content": {"type": "string", "description": "Faylning to'liq yangi matni"},
                "message": {"type": "string", "description": "Commit xabari"},
                "branch": {"type": "string", "description": "Branch nomi (ixtiyoriy, standart: asosiy branch)"},
            },
            "required": ["owner", "repo", "path", "content", "message"],
        },
    },
    {
        "name": "github_create_pull_request",
        "description": "Bitta branch'dagi o'zgarishlarni boshqasiga qo'shish uchun Pull Request ochadi.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "title": {"type": "string"},
                "head": {"type": "string", "description": "O'zgarish turgan branch"},
                "base": {"type": "string", "description": "O'zgarish qo'shiladigan branch (masalan main)"},
                "body": {"type": "string", "description": "PR tavsifi (ixtiyoriy)"},
            },
            "required": ["owner", "repo", "title", "head", "base"],
        },
    },
]


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _error(res: httpx.Response) -> dict:
    try:
        message = res.json().get("message", res.text)
    except Exception:
        message = res.text
    return {"error": f"GitHub API xatosi ({res.status_code}): {message}"}


async def github_read_file(owner: str, repo: str, path: str, ref: str | None = None) -> dict:
    params = {"ref": ref} if ref else {}
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents/{path}", headers=_headers(), params=params
        )
    if res.status_code != 200:
        return _error(res)
    data = res.json()
    if isinstance(data, list):
        return {"error": "Bu yo'l papka, fayl emas — github_list_directory ishlating."}
    content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    return {"path": data["path"], "sha": data["sha"], "content": content[:8000]}


async def github_list_directory(owner: str, repo: str, path: str = "", ref: str | None = None) -> dict:
    params = {"ref": ref} if ref else {}
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents/{path}", headers=_headers(), params=params
        )
    if res.status_code != 200:
        return _error(res)
    data = res.json()
    if not isinstance(data, list):
        return {"error": "Bu yo'l fayl, papka emas — github_read_file ishlating."}
    return {"items": [{"name": i["name"], "type": i["type"], "path": i["path"]} for i in data]}


async def github_create_or_update_file(
    owner: str, repo: str, path: str, content: str, message: str, branch: str | None = None
) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        get_params = {"ref": branch} if branch else {}
        existing = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents/{path}", headers=_headers(), params=get_params
        )
        existing_sha = existing.json().get("sha") if existing.status_code == 200 else None

        payload: dict = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        }
        if branch:
            payload["branch"] = branch
        if existing_sha:
            payload["sha"] = existing_sha

        res = await client.put(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents/{path}", headers=_headers(), json=payload
        )
    if res.status_code not in (200, 201):
        return _error(res)
    data = res.json()
    return {"status": "ok", "commit_sha": data.get("commit", {}).get("sha"), "path": path}


async def github_create_pull_request(
    owner: str, repo: str, title: str, head: str, base: str, body: str = ""
) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.post(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/pulls",
            headers=_headers(),
            json={"title": title, "head": head, "base": base, "body": body},
        )
    if res.status_code not in (200, 201):
        return _error(res)
    data = res.json()
    return {"status": "ok", "pr_url": data.get("html_url"), "number": data.get("number")}


_HANDLERS = {
    "github_read_file": github_read_file,
    "github_list_directory": github_list_directory,
    "github_create_or_update_file": github_create_or_update_file,
    "github_create_pull_request": github_create_pull_request,
}


async def dispatch(name: str, tool_input: dict) -> dict:
    if not GITHUB_TOKEN:
        return {"error": "GITHUB_TOKEN sozlanmagan. .env faylini to'ldiring."}
    handler = _HANDLERS.get(name)
    if not handler:
        return {"error": f"Noma'lum GitHub tool: {name}"}
    try:
        return await handler(**tool_input)
    except TypeError as exc:
        return {"error": f"Noto'g'ri parametrlar: {exc}"}
