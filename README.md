<!-- Apeiron repository landing page -->
<p align="center">
  <img src="frontend/app_logo.jfif" alt="Apeiron logo" width="112" />
</p>

<h1 align="center">Apeiron — AI Workspace</h1>

<p align="center">
  <strong>One workspace. Your models. Your agents. Your projects.</strong>
</p>

<p align="center">
  Build a personal AI workspace with configurable agents and multiple model providers.
  <br />
  Ko'p providerli AI agentlar va loyihalar uchun yagona ish muhiti.
</p>

<p align="center">
  <a href="https://github.com/shakha1210-pixel/AI-model/actions/workflows/tests.yml"><img src="https://github.com/shakha1210-pixel/AI-model/actions/workflows/tests.yml/badge.svg?branch=feat/agent-workspace" alt="Tests" /></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Frontend-Vanilla%20JS-F7DF1E?logo=javascript&logoColor=111" alt="Vanilla JavaScript" />
  <img src="https://img.shields.io/badge/Status-Active%20Development-orange" alt="Active development" />
</p>

<p align="center">
  <a href="#ozbekcha">O'zbekcha</a> · <a href="#english">English</a> ·
  <a href="docs/WORKSPACE_ARCHITECTURE.md">Architecture & roadmap</a> ·
  <a href="CONTRIBUTING.md">Contributing</a> ·
  <a href="SECURITY.md">Security</a>
</p>

---

## O'zbekcha

### Apeiron nima?

Apeiron — foydalanuvchi o'z AI providerlarini ulashi, o'z agentlarini yaratishi va ularni loyihalar ustida ishlatishi uchun mo'ljallangan AI Workspace. Loyiha mavjud chat ilovasidan agentlar, fayllar, vazifalar va natijalarni bir joyda boshqaradigan ish muhitiga bosqichma-bosqich o'tmoqda.

> **Hozirgi holat:** faol ishlab chiqilmoqda. Workspace migratsiyasi tugamagan. Mavjud chat funksiyasi saqlanadi; yangi imkoniyatlar kichik bosqichlarda qo'shiladi.

### Mahsulot yo'nalishi

| Yo'nalish | Maqsad |
|---|---|
| **Multi-provider** | OpenAI, Anthropic, Gemini, OpenRouter va OpenAI-compatible API'lar |
| **API Manager** | Foydalanuvchining API kalitlarini serverda shifrlab saqlash |
| **Agent Builder** | Provider, model, system prompt va ruxsatlarni foydalanuvchi belgilaydigan agentlar |
| **Workspace** | Loyihalar, fayllar, editor, agentlar va tasklar |
| **Orchestration** | Vazifalarni rejalashtirish, agentlararo topshirish va kuzatiladigan run'lar |
| **Cross-platform UI** | Desktop, planshet va mobil ekranlarga mos interfeys |

### Providerlar holati

| Provider | Registry | API adapter |
|---|---:|---:|
| OpenAI | Mavjud | Rejada |
| Anthropic | Mavjud | Rejada |
| Google Gemini | Mavjud | Rejada |
| OpenRouter | Mavjud | Rejada |
| Custom OpenAI-compatible | Mavjud | Rejada |

**Eslatma:** registry — provider metadata ro'yxati, ishlaydigan integratsiya degani emas. API kalitini ulash, model discovery va real provider so'rovlari hali yakunlanmagan.

### Texnologiyalar

- **Backend:** Python, FastAPI, SQLAlchemy, Pydantic, HTTPX
- **Frontend:** HTML, CSS, Vanilla JavaScript
- **Database:** SQLite (default) / PostgreSQL orqali SQLAlchemy
- **Tests:** pytest, pytest-asyncio

### Tezkor boshlash

Talablar: Python 3.10+, Git.

<pre><code>git clone https://github.com/shakha1210-pixel/AI-model.git
cd AI-model
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
uvicorn main:app --reload</code></pre>

Brauzerda http://localhost:8000 manzilini oching. Kerakli integratsiyalar uchun muhit o'zgaruvchilarini lokal .env faylida sozlang; maxfiy kalitlarni hech qachon Git'ga qo'shmang.

Testlarni ishga tushirish:

<pre><code>python -m pytest -v</code></pre>

### Muhim hujjatlar

- [Workspace arxitekturasi, roadmap va jonli status](docs/WORKSPACE_ARCHITECTURE.md) — loyiha holatining yagona manbasi.
- [Hissa qo'shish qoidalari](CONTRIBUTING.md)
- [Xavfsizlik siyosati](SECURITY.md)

### Muhim tamoyillar

1. Mavjud chat yo'llari yangi oqim tekshirilmaguncha saqlanadi.
2. Providerga xos kod adapter ichida qoladi.
3. API kalitlari browser storage, log yoki API javobiga chiqmaydi.
4. Har bir foydalanuvchi resursi egalik tekshiruvi bilan himoyalanadi.
5. Custom endpointlar SSRF hujumlariga qarshi tekshiriladi.
6. Agent kodini ishga tushirish haqiqiy izolyatsiyalangan sandbox talab qiladi.
7. Test o'tkazilmagan bo'lsa, muvaffaqiyatli deb belgilanmaydi.

---

## English

### What is Apeiron?

Apeiron is evolving into a personal AI Workspace where users connect their own model providers, build configurable agents, and work with them across projects. The goal is to bring agents, files, tasks, and outputs into one coherent environment while preserving the existing chat application during the migration.

> **Current status:** under active development. The Workspace migration is not complete. Existing chat functionality remains available while new capabilities are introduced incrementally.

### Product direction

| Area | Goal |
|---|---|
| **Multi-provider** | OpenAI, Anthropic, Gemini, OpenRouter, and OpenAI-compatible APIs |
| **API Manager** | Encrypt and store user-owned API credentials server-side |
| **Agent Builder** | User-configured provider, model, instructions, and permissions |
| **Workspace** | Projects, files, editor, agents, and tasks |
| **Orchestration** | Task planning, agent handoffs, and observable runs |
| **Cross-platform UI** | Responsive desktop, tablet, and mobile experience |

### Provider status

| Provider | Registry | API adapter |
|---|---:|---:|
| OpenAI | Added | Planned |
| Anthropic | Added | Planned |
| Google Gemini | Added | Planned |
| OpenRouter | Added | Planned |
| Custom OpenAI-compatible | Added | Planned |

**Important:** the registry contains public provider metadata only. It does not mean live integrations are available yet. Credential connections, model discovery, and real provider requests are still being implemented.

### Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy, Pydantic, HTTPX
- **Frontend:** HTML, CSS, Vanilla JavaScript
- **Database:** SQLite by default / PostgreSQL via SQLAlchemy
- **Tests:** pytest, pytest-asyncio

### Quick start

Requirements: Python 3.10+, Git.

<pre><code>git clone https://github.com/shakha1210-pixel/AI-model.git
cd AI-model
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
uvicorn main:app --reload</code></pre>

Open http://localhost:8000. Configure required integrations through environment variables in a local .env file. Never commit secrets.

Run tests:

<pre><code>python -m pytest -v</code></pre>

### Project documentation

- [Architecture, roadmap, and living implementation status](docs/WORKSPACE_ARCHITECTURE.md) — the single source of truth for project status.
- [Contribution guidelines](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

### Engineering principles

1. Preserve legacy chat routes until replacement paths are verified.
2. Keep provider-specific behavior inside adapters.
3. Never expose API keys in browser storage, logs, or API responses.
4. Enforce ownership checks for every user-owned resource.
5. Protect custom endpoints against SSRF.
6. Run agent code only in a genuinely isolated sandbox.
7. Never report tests as passing unless they were actually run.

---

<p align="center">
  <sub>Built incrementally · Security first · Provider independent</sub>
</p>
