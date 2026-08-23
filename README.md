Kod Yozish Agenti
O'zining "Replit-agent"ga o'xshash, AI asosidagi dasturlash yordamchisini yaratish loyihasi. Foydalanuvchi chat orqali savol yozadi, server savol turini ("kod" yoki "g'oya") aniqlaydi va mos AI modeliga (Claude yoki Gemini) yo'naltiradi.

To'ldirilishi kerak bo'lgan barcha narsalar ro'yxati uchun bir papka yuqoridagi TOLDIRILISHI-KERAK-BOLGAN-ROYXAT.txt fayliga qarang.

Tezkor boshlash
Python 3.10 yoki undan yuqori versiyani o'rnating.
(Tavsiya etiladi) virtual muhit yarating:
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

Kutubxonalarni o'rnating:
pip install -r requirements.txt

.env.example faylidan nusxa olib .env nomli fayl yarating, so'ng uni ochib ANTHROPIC_API_KEY, GEMINI_API_KEY qiymatlarini kiriting:
cp .env.example .env

Serverni ishga tushiring:
uvicorn main:app --reload

Brauzerda http://localhost:8000 manzilini oching.
Docker bilan ishga tushirish
docker compose up --build

Testlarni ishga tushirish
pytest -v

Loyiha tuzilishi
agent-project/
├── main.py               — server "yuragi": /chat, /health, intent klassifikatsiya
├── database.py           — ma'lumotlar bazasi (ENABLE_DATABASE=true bo'lsa)
├── auth.py               — ro'yxatdan o'tish/kirish (ENABLE_AUTH=true bo'lsa)
├── rate_limiter.py       — so'rovlarni cheklash (ENABLE_RATE_LIMIT=true bo'lsa)
├── tools.py              — Claude uchun kod ijro etish (ENABLE_TOOLS=true bo'lsa)
├── requirements.txt
├── .env / .env.example
├── Dockerfile / docker-compose.yml
├── tests/test_main.py
├── .github/workflows/deploy.yml
└── frontend/
    ├── index.html / style.css / chat.js / voice.js
    ├── login.html / register.html
    ├── history.html
    └── settings.html

Bosqichma-bosqich reja
Bosqich	Nima qilish kerak	Qachon
1	.env to'ldirish, dasturni ishga tushirish, backend+frontendni ulab sinash	Hozir
1	Domen + hosting tanlash	1-hafta oxiri
2	ENABLE_TOOLS=true (kod ijro etish)	2-hafta
2	ENABLE_DATABASE=true (doimiy saqlash)	2-hafta
3	ENABLE_AUTH=true (login/register), agar kerak bo'lsa	3-hafta
3	ENABLE_RATE_LIMIT=true	3-hafta
3	Ovozli xabar (voice.js allaqachon tayyor)	3-hafta
4	Testlar + CI/CD	4-hafta
4	Hujjatlar (hujjatlar/ papkasiga qarang)	4-hafta
Muhim eslatma — xavfsizlik
tools.py orqali kod ijro etish funksiyasi hozircha faqat DEMO darajasida xavfsiz. Productionga chiqarishdan oldin TOLDIRILISHI-KERAK-BOLGAN-ROYXAT.txt faylidagi tegishli bo'limni albatta o'qing.