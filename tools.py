"""
tools.py — Claude uchun "tool use" (funksiya chaqirish) imkoniyati

Bu fayl loyihani "Replit-agent"ga o'xshatuvchi eng muhim kengaytma: Claude'ga
kod yozish VA uni ijro etish imkoniyatini beradi. Yoqish uchun main.py yoki
.env faylida ENABLE_TOOLS=true qiling.

!!! XAVFSIZLIK OGOHLANTIRISHI !!!
Quyidagi run_python_code() funksiyasi hozircha faqat DEMO/O'QUV maqsadida
yozilgan — u kodni to'g'ridan-to'g'ri shu serverning o'zida ishga tushiradi.
Bu ISHLAB CHIQARISH (production) uchun XAVFSIZ EMAS: foydalanuvchi
serverning fayllarini o'chirishi, tarmoqqa so'rov yuborishi yoki boshqa
zararli amallarni bajarishi mumkin.

Productionga chiqarishdan oldin quyidagilardan birini TANLASHINGIZ SHART:
  1. Docker konteynerida tarmoqsiz, vaqtinchalik muhitda ishga tushirish
  2. Hostlangan sandbox xizmati (masalan E2B.dev, Modal, Piston)
  3. gVisor / Firecracker kabi izolyatsiya texnologiyasi

Qaysi variantni tanlaganingizni shu faylga izoh qilib yozib qo'ying —
batafsil: bir papka tepadagi TOLDIRILISHI-KERAK-BOLGAN-ROYXAT.txt.
"""

import json
import logging
import os
import re
import subprocess
import sys

import httpx

logger = logging.getLogger("agent.tools")
audit_logger = logging.getLogger("agent.tools.audit")

CODE_EXECUTION_TIMEOUT_SECONDS = int(os.getenv("CODE_EXECUTION_TIMEOUT_SECONDS", "5"))

# Xotira chegarasi (baytda) — bitta ijro uchun. Standart: 128 MB.
CODE_EXECUTION_MEMORY_LIMIT_BYTES = int(
    os.getenv("CODE_EXECUTION_MEMORY_LIMIT_BYTES", str(128 * 1024 * 1024))
)

# 2-QATLAM HIMOYA: aniq zararli/xavfli chaqiruvlarni oldindan bloklovchi
# oddiy naqsh-ro'yxati. BU YAGONA HIMOYA EMAS — sandbox/konteyner ASOSIY
# himoya bo'lishi kerak (fayl boshidagi ogohlantirishga qarang). Bu faqat
# aniq va shubhasiz xavfli chaqiruvlarni ("qo'shimcha to'siq" sifatida)
# ushlab qoladi; ataylab yashiringan (obfuskatsiya) chetlab o'tishlarga
# qarshi kafolat bermaydi.
_BLOCKED_PATTERNS = [
    r"\bos\.system\s*\(",
    r"\bsubprocess\.",
    r"\bshutil\.rmtree\s*\(",
    r"\bsocket\.",
    r"__import__\s*\(\s*['\"]os['\"]\s*\)\s*\.\s*(remove|rmdir|system)",
    r"\bctypes\.",
    r"\bopen\s*\([^)]*['\"]\/etc\/",
    r"\bopen\s*\([^)]*['\"]\.\.[\\/]",
]
_COMPILED_BLOCKED = [re.compile(p) for p in _BLOCKED_PATTERNS]


def _static_precheck(code: str) -> str | None:
    """Kod ishga tushirilishidan oldin aniq xavfli naqshlarni qidiradi.
    Muammo topilsa — sabab satrini, aks holda None qaytaradi."""
    for pattern in _COMPILED_BLOCKED:
        if pattern.search(code):
            return pattern.pattern
    return None

# main.py dagi bilan bir xil sozlamalar (aylanma import'dan qochish uchun
# takrorlangan — kelajakda umumiy config.py fayliga chiqarish mumkin).
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
CLAUDE_SYSTEM_PROMPT = (
    "Siz tajribali dasturchi yordamchisisiz. Kerak bo'lganda run_python_code "
    "tool'idan foydalanib yozgan kodingizni sinab ko'ring, github_* tool'lari "
    "orqali (agar mavjud bo'lsa) GitHub repositoriylari bilan, google_docs_* "
    "tool'lari orqali (agar mavjud bo'lsa) Google Docs hujjatlari bilan, "
    "project_* tool'lari orqali (agar mavjud bo'lsa) joriy suhbat biriktirilgan "
    "loyiha papkasidagi fayllar bilan ishlang, va natijasini foydalanuvchiga "
    "o'zbek tilida tushuntiring."
)

RUN_PYTHON_TOOL = [
    {
        "name": "run_python_code",
        "description": (
            "Berilgan Python kodini ishga tushiradi va uning konsol chiqishini "
            "(stdout/stderr) qaytaradi. Foydalanuvchi kodni sinab ko'rishni "
            "so'raganda yoki natijani tekshirish kerak bo'lganda ishlating."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Ishga tushiriladigan Python kodi"},
            },
            "required": ["code"],
        },
    }
]

# main.py dagi bilan bir xil bayroqlar (aylanma import'dan qochish uchun
# takrorlangan) — qaysi tool'lar Claude'ga taqdim etilishini belgilaydi.
ENABLE_TOOLS = os.getenv("ENABLE_TOOLS", "false").lower() == "true"
ENABLE_GITHUB_TOOL = os.getenv("ENABLE_GITHUB_TOOL", "false").lower() == "true"
ENABLE_GOOGLE_DOCS_TOOL = os.getenv("ENABLE_GOOGLE_DOCS_TOOL", "false").lower() == "true"
ENABLE_PROJECT_FILES_TOOL = os.getenv("ENABLE_PROJECT_FILES_TOOL", "false").lower() == "true"


def _active_tools() -> list[dict]:
    """Joriy sozlamalarga qarab Claude'ga taqdim etiladigan tool'lar
    ro'yxatini yig'adi — har biri mustaqil yoqiladi/o'chiriladi."""
    active: list[dict] = []
    if ENABLE_TOOLS:
        active += RUN_PYTHON_TOOL
    if ENABLE_GITHUB_TOOL:
        from github_tool import GITHUB_TOOLS

        active += GITHUB_TOOLS
    if ENABLE_GOOGLE_DOCS_TOOL:
        from google_docs_tool import GOOGLE_DOCS_TOOLS

        active += GOOGLE_DOCS_TOOLS
    if ENABLE_PROJECT_FILES_TOOL:
        from project_tool import PROJECT_TOOLS

        active += PROJECT_TOOLS
    return active


def _limit_resources() -> None:
    """subprocess ichida (bola jarayonda) chaqiriladi — CPU/xotira/fayl
    va process sonini cheklaydi. Faqat Unix (Linux/macOS)da ishlaydi;
    Windows'da bu funksiya jim o'tkazib yuboriladi (resource moduli yo'q).
    Bu ham TO'LIQ SANDBOX EMAS — faqat "runaway" kodning (cheksiz xotira/
    CPU yeyish) serverni yiqitishining oldini oladigan qo'shimcha chegara.
    """
    try:
        import resource

        cpu_seconds = CODE_EXECUTION_TIMEOUT_SECONDS + 1
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        resource.setrlimit(
            resource.RLIMIT_AS,
            (CODE_EXECUTION_MEMORY_LIMIT_BYTES, CODE_EXECUTION_MEMORY_LIMIT_BYTES),
        )
        resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))
        resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
    except ImportError:
        pass  # Windows — resource moduli mavjud emas


def run_python_code(code: str, session_id: str = "noma'lum") -> dict:
    """DEMO darajadagi kod ijrochisi. Fayl boshidagi ogohlantirishni o'qing.

    Qo'shilgan himoya qatlamlari (lekin bularning HECH biri to'liq sandbox
    o'rnini bosmaydi — productionda Docker/E2B/gVisor ISHLATILISHI SHART):
      1. Statik oldindan tekshiruv — aniq xavfli chaqiruvlarni bloklaydi.
      2. Toza environment — kod ANTHROPIC_API_KEY kabi server sirlariga
         os.environ orqali kira olmaydi.
      3. CPU/xotira/fayl/process chegaralari (Unix'da).
      4. Har bir ijro audit-log qilinadi (kim/qachon/nima ishga tushirdi).
    """
    precheck_issue = _static_precheck(code)
    if precheck_issue:
        audit_logger.warning(
            "Kod ijrosi BLOKLANDI (statik tekshiruv) | session=%s | naqsh=%s",
            session_id, precheck_issue,
        )
        return {
            "stdout": "",
            "stderr": (
                "Bu kod xavfsizlik siyosati bo'yicha bloklandi (potentsial "
                "xavfli tizim chaqiruvi aniqlandi)."
            ),
            "exit_code": -1,
        }

    audit_logger.info(
        "Kod ijrosi boshlandi | session=%s | uzunlik=%d belgi", session_id, len(code)
    )

    # Bola jarayonga faqat minimal PATH beriladi — API kalitlari va boshqa
    # maxfiy .env qiymatlari kod ichidan os.environ orqali o'qib bo'lmaydi.
    minimal_env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}

    try:
        result = subprocess.run(
            [sys.executable, "-I", "-c", code],  # -I: izolyatsiyalangan rejim
            capture_output=True,
            text=True,
            timeout=CODE_EXECUTION_TIMEOUT_SECONDS,
            env=minimal_env,
            preexec_fn=_limit_resources if hasattr(os, "fork") else None,
        )
        audit_logger.info(
            "Kod ijrosi tugadi | session=%s | exit_code=%s", session_id, result.returncode
        )
        return {
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        audit_logger.warning("Kod ijrosi TIMEOUT | session=%s", session_id)
        return {
            "stdout": "",
            "stderr": "Kod bajarilishi vaqt chegarasidan oshib ketdi.",
            "exit_code": -1,
        }


async def _iter_sse_json(response: httpx.Response):
    """main.py dagi bilan bir xil SSE-parser (aylanma import'dan qochish
    uchun takrorlangan — yuqoridagi izohga qarang)."""
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


async def dispatch_tool_call(name: str, tool_input: dict, session_id: str = "noma'lum") -> dict:
    if name == "run_python_code":
        return run_python_code(tool_input.get("code", ""), session_id=session_id)
    if name.startswith("github_"):
        from github_tool import dispatch as github_dispatch

        return await github_dispatch(name, tool_input)
    if name.startswith("google_docs_"):
        from google_docs_tool import dispatch as google_docs_dispatch

        return await google_docs_dispatch(name, tool_input, session_id=session_id)
    if name.startswith("project_"):
        from project_tool import dispatch as project_dispatch

        return await project_dispatch(name, tool_input, session_id=session_id)
    return {"error": f"Noma'lum tool: {name}"}


async def call_claude_with_tools(
    message: str, history: list[dict], session_id: str = "noma'lum"
) -> str:
    """
    call_claude()ga o'xshaydi, lekin Claude'ga run_python_code tool'idan
    foydalanish imkonini beradi va tool natijasini yana Claude'ga qaytarib,
    yakuniy javobni hosil qiladi.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY sozlanmagan.")

    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": message})

    async with httpx.AsyncClient(timeout=60.0) as client:
        for _ in range(5):  # tool-use aylanishlarining maksimal soni
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 2048,
                    "system": CLAUDE_SYSTEM_PROMPT,
                    "tools": _active_tools(),
                    "messages": messages,
                },
            )
            if response.status_code != 200:
                logger.error("Claude API xatosi: %s %s", response.status_code, response.text)
                raise RuntimeError("Claude API bilan bog'lanib bo'lmadi.")

            data = response.json()
            messages.append({"role": "assistant", "content": data["content"]})

            if data.get("stop_reason") != "tool_use":
                return "".join(
                    block.get("text", "") for block in data["content"] if block.get("type") == "text"
                )

            tool_results = []
            for block in data["content"]:
                if block.get("type") == "tool_use":
                    result = await dispatch_tool_call(
                        block["name"], block.get("input", {}), session_id=session_id
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block["id"],
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
            messages.append({"role": "user", "content": tool_results})

    return "Kechirasiz, javobni yakunlab bo'lmadi (juda ko'p tool chaqiruvi)."


async def stream_claude_with_tools(
    message: str, history: list[dict], session_id: str = "noma'lum"
):
    """call_claude_with_tools()ning oqim (streaming) varianti. Matn tayyor
    bo'lgani sayin {"type": "text", "text": ...}, tool chaqirilganda esa
    {"type": "tool_start", "name": ...} qaytaradi (main.py shu ikkinchisini
    frontendga "🔧 <tool> ishlatilmoqda..." belgisi sifatida yuboradi)."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY sozlanmagan.")

    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": message})

    async with httpx.AsyncClient(timeout=60.0) as client:
        for _ in range(5):  # tool-use aylanishlarining maksimal soni
            blocks: dict[int, dict] = {}
            stop_reason: str | None = None

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
                    "max_tokens": 2048,
                    "system": CLAUDE_SYSTEM_PROMPT,
                    "tools": _active_tools(),
                    "messages": messages,
                    "stream": True,
                },
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    logger.error("Claude API xatosi: %s %s", response.status_code, body)
                    raise RuntimeError("Claude API bilan bog'lanib bo'lmadi.")

                async for event in _iter_sse_json(response):
                    etype = event.get("type")
                    if etype == "content_block_start":
                        index = event["index"]
                        block = event["content_block"]
                        if block["type"] == "text":
                            blocks[index] = {"type": "text", "text": ""}
                        elif block["type"] == "tool_use":
                            blocks[index] = {
                                "type": "tool_use",
                                "id": block["id"],
                                "name": block["name"],
                                "json": "",
                            }
                    elif etype == "content_block_delta":
                        index = event["index"]
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            blocks[index]["text"] += text
                            if text:
                                yield {"type": "text", "text": text}
                        elif delta.get("type") == "input_json_delta":
                            blocks[index]["json"] += delta.get("partial_json", "")
                    elif etype == "message_delta":
                        stop_reason = event.get("delta", {}).get("stop_reason")

            content = []
            for index in sorted(blocks):
                block = blocks[index]
                if block["type"] == "text":
                    content.append({"type": "text", "text": block["text"]})
                else:
                    try:
                        tool_input = json.loads(block["json"]) if block["json"] else {}
                    except json.JSONDecodeError:
                        tool_input = {}
                    content.append(
                        {
                            "type": "tool_use",
                            "id": block["id"],
                            "name": block["name"],
                            "input": tool_input,
                        }
                    )
            messages.append({"role": "assistant", "content": content})

            if stop_reason != "tool_use":
                return

            tool_results = []
            for block in content:
                if block["type"] == "tool_use":
                    yield {"type": "tool_start", "name": block["name"]}
                    result = await dispatch_tool_call(
                        block["name"], block["input"], session_id=session_id
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block["id"],
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
            messages.append({"role": "user", "content": tool_results})

    yield {"type": "text", "text": "\n\n(Kechirasiz, javobni yakunlab bo'lmadi — juda ko'p tool chaqiruvi.)"}
