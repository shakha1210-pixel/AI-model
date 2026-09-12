"""
collab_tool.py — Claude uchun boshqa modellarga (Gemini, Leonardo) murojaat
qilish imkonini beruvchi "hamkorlik" tool'lari.

Bu bilan Claude (kod yozish domenida) endi yolg'iz ishlamaydi — kerak
bo'lganda tezkor fikr/g'oya uchun Gemini'ga ("ask_gemini"), loyihaga kerakli
tasvir uchun Leonardo'ga ("generate_image") murojaat qilib, natijani o'z
javobiga qo'shib beradi. Bir domendan ikkinchisiga qo'lda o'tish o'rniga,
agentning o'zi qaysi vaziyatda qaysi modeldan yordam so'rashni hal qiladi.

Yoqish uchun .env faylida ENABLE_COLLAB_TOOL=true qiling. GEMINI_API_KEY va
LEONARDO_API_KEY main.py bilan bir xil (mustaqil o'qiladi — aylanma
import'dan qochish uchun, boshqa tool modullaridagi kabi).
"""

import asyncio
import os

import httpx

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY", "")
LEONARDO_MODEL_ID = os.getenv("LEONARDO_MODEL_ID", "b24e16ff-06e3-43eb-8d33-4416c2d75876")
LEONARDO_POLL_INTERVAL_SECONDS = 2
LEONARDO_POLL_MAX_ATTEMPTS = 30

ASK_GEMINI_SYSTEM_PROMPT = (
    "Siz boshqa AI agentga (Claude'ga) yordam beryapsiz — u kod yozish "
    "ustida ishlayotib sizdan tezkor fikr, g'oya yoki tushuntirish so'radi. "
    "Qisqa, aniq va amaliy javob bering (bir necha jumla yoki ro'yxat "
    "yetarli, uzoq insho kerak emas)."
)

COLLAB_TOOLS = [
    {
        "name": "ask_gemini",
        "description": (
            "Boshqa AI model (Gemini)dan tezkor fikr, g'oya yoki tushuntirish "
            "so'raydi — masalan o'zgaruvchi/funksiya nomlari uchun variantlar, "
            "UX matni g'oyalari, murakkab tushunchani sodda tushuntirish. "
            "Faqat qisqa maslahat kerak bo'lganda ishlating, asosiy kod "
            "yozish vazifasini o'zingiz bajaring."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Gemini'ga beriladigan qisqa savol",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "generate_image",
        "description": (
            "Boshqa AI model (Leonardo) orqali tasvir (rasm, ikonka, "
            "illyustratsiya) generatsiya qiladi — masalan yozayotgan loyihangiz "
            "uchun placeholder logotip yoki banner kerak bo'lsa ishlating. "
            "MUHIM: 'prompt' parametrini FAQAT ingliz tilida yozing (boshqa "
            "tilda mutlaqo aloqasiz rasm chiqishi mumkin). Natijada olingan "
            "URL'ni javobingizga markdown rasm sintaksisi bilan "
            "(![tavsif](URL)) qo'shing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": (
                        "Qanday tasvir kerakligini FAQAT INGLIZ tilida, aniq va "
                        "tasvirlovchi tarzda yozing — rasm generatsiya modeli "
                        "boshqa tillarni yaxshi tushunmaydi va so'rovga aloqasi "
                        "yo'q rasm qaytarishi mumkin."
                    ),
                },
            },
            "required": ["prompt"],
        },
    },
]


async def _ask_gemini(question: str) -> dict:
    if not GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY sozlanmagan."}

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            json={
                "system_instruction": {"parts": [{"text": ASK_GEMINI_SYSTEM_PROMPT}]},
                "contents": [{"role": "user", "parts": [{"text": question}]}],
            },
        )
    if response.status_code != 200:
        return {"error": f"Gemini bilan bog'lanib bo'lmadi ({response.status_code})."}

    data = response.json()
    try:
        candidate = data["candidates"][0]
        answer = "".join(part.get("text", "") for part in candidate["content"]["parts"])
    except (KeyError, IndexError):
        return {"error": "Gemini javobini o'qib bo'lmadi."}
    return {"answer": answer}


async def _generate_image(prompt: str) -> dict:
    if not LEONARDO_API_KEY:
        return {"error": "LEONARDO_API_KEY sozlanmagan."}

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
            return {"error": "Leonardo AI bilan bog'lanib bo'lmadi."}

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
                    return {"image_url": images[0]["url"]}
                break
            if generation.get("status") == "FAILED":
                break

    return {"error": "Rasm generatsiyasi vaqt chegarasidan oshdi."}


async def dispatch(name: str, tool_input: dict) -> dict:
    if name == "ask_gemini":
        question = tool_input.get("question", "").strip()
        if not question:
            return {"error": "Savol bo'sh bo'lishi mumkin emas."}
        return await _ask_gemini(question)
    if name == "generate_image":
        prompt = tool_input.get("prompt", "").strip()
        if not prompt:
            return {"error": "Tasvir tavsifi bo'sh bo'lishi mumkin emas."}
        return await _generate_image(prompt)
    return {"error": f"Noma'lum hamkorlik tool'i: {name}"}
