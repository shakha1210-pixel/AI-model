# Apeiron — AI Workspace

**O'zbekcha | English below**

Apeiron foydalanuvchi o'z AI providerlarini ulaydigan, agentlar yaratadigan va loyihalar ustida ular bilan ishlaydigan AI Workspace'ga aylanmoqda. Hozir loyiha chat-first ilovadan workspace arxitekturasiga bosqichma-bosqich migratsiya qilinmoqda.

> **Holat:** faol ishlab chiqilmoqda. Migratsiya tugamagan; mavjud chat ilovasi saqlanadi.

## Maqsad

- Multi-provider: OpenAI, Anthropic, Google Gemini, OpenRouter va boshqa OpenAI-compatible endpointlar.
- API Manager: foydalanuvchi o'z API kalitini ulaydi; serverda shifrlangan holda saqlanadi.
- Agent Builder: foydalanuvchi agent yaratadi va provider, model, system prompt hamda vositalarni belgilaydi.
- Workspace: loyihalar, fayllar, editor, agentlar, tasklar va natijalar.
- Orchestration: agentlar vazifalarni rejalashtiradi va kerak bo'lsa bir-biriga topshiradi.
- Desktop, planshet va telefon uchun responsive UI.

**Arxitektura, reja, status, bajarilgan va qolgan ishlar uchun yagona doimiy hujjat:** [docs/WORKSPACE_ARCHITECTURE.md](docs/WORKSPACE_ARCHITECTURE.md). Har bir muhim o'zgarishdan keyin aynan shu fayl yangilanadi.

## Providerlar

| Provider | Hozirgi holat |
|---|---|
| OpenAI | Registry qo'shilgan |
| Anthropic | Registry qo'shilgan |
| Google Gemini | Registry qo'shilgan |
| OpenRouter | Registry qo'shilgan |
| Custom OpenAI-compatible | Registry qo'shilgan |

Muhim: hozircha bu provider metadata registri. API kalitini ulash, model discovery va real API adapterlari hali tayyor emas.

## Texnologiyalar

- Backend: Python, FastAPI
- Frontend: HTML, CSS, Vanilla JavaScript
- Tests: pytest

Migratsiyada mavjud backend va frontendni birdaniga almashtirmaymiz. Yangi workspace imkoniyatlari bosqichma-bosqich qo'shiladi.

## Tezkor boshlash

Talablar: Python 3.10+, Git.

```bash
git clone https://github.com/shakha1210-pixel/AI-model.git
cd AI-model
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
.venv/Scripts/Activate.ps1
pip install -r requirements.txt
```

`.env.example` faylidan `.env` yarating va kerakli qiymatlarni kiriting. API kalitlarini Git'ga commit qilmang.

```bash
uvicorn main:app --reload
```

Brauzer: http://localhost:8000

Docker: `docker compose up --build`

Testlar: `pytest -v`

## Muhim fayllar

- `main.py` — FastAPI ilovasi va legacy chat endpointlari.
- `workspace/providers.py` — provider metadata registri.
- `docs/WORKSPACE_ARCHITECTURE.md` — doimiy arxitektura va loyiha holati.
- `tests/test_workspace_providers.py` — provider registry testlari.
- `frontend/` — mavjud HTML/CSS/JS interfeysi.

## Ishlash qoidalari

1. Ishni kichik, tushunarli commitlarga ajratamiz.
2. `docs/WORKSPACE_ARCHITECTURE.md` — arxitektura va statusning yagona manbasi.
3. Test bajarilmagan bo'lsa, o'tdi deb yozmaymiz.
4. API kalitlari frontend storage, log yoki API response ichiga chiqmasligi kerak.
5. Legacy endpointlar yangi oqim tayyor bo'lmaguncha o'chirilmaydi.

---

# English

Apeiron is evolving into an AI Workspace where users connect their own AI providers, build configurable agents, and collaborate with them inside projects. The repository is migrating incrementally from a chat-first application to a workspace architecture.

> **Status:** under active development. The migration is not complete; the existing chat application remains available.

## Product direction

- Multi-provider support: OpenAI, Anthropic, Google Gemini, OpenRouter, and other OpenAI-compatible endpoints.
- API Manager: users connect their own API keys; secrets are encrypted server-side.
- Agent Builder: users configure agents, providers, models, system prompts, and tools.
- Workspace: projects, files, editor, agents, tasks, and artifacts.
- Orchestration: agents plan tasks and hand work to other agents when appropriate.
- Responsive desktop, tablet, and mobile UI.

**Canonical living architecture, roadmap, status, completed work, and open tasks:** [docs/WORKSPACE_ARCHITECTURE.md](docs/WORKSPACE_ARCHITECTURE.md). Keep that exact file updated after every meaningful change.

## Providers

| Provider | Current status |
|---|---|
| OpenAI | Registry added |
| Anthropic | Registry added |
| Google Gemini | Registry added |
| OpenRouter | Registry added |
| Custom OpenAI-compatible | Registry added |

Note: this is currently provider metadata only. API key connections, model discovery, and live API adapters are not implemented yet.

## Technology

- Backend: Python, FastAPI
- Frontend: HTML, CSS, Vanilla JavaScript
- Tests: pytest

The migration is incremental. Existing backend and frontend functionality will not be replaced in a big-bang rewrite.

## Quick start

Requirements: Python 3.10+, Git.

```bash
git clone https://github.com/shakha1210-pixel/AI-model.git
cd AI-model
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
.venv/Scripts/Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure the required values. Never commit API keys.

```bash
uvicorn main:app --reload
```

Open http://localhost:8000

Docker: `docker compose up --build`

Tests: `pytest -v`

## Key files

- `main.py` — FastAPI application and legacy chat endpoints.
- `workspace/providers.py` — provider metadata registry.
- `docs/WORKSPACE_ARCHITECTURE.md` — canonical living architecture and status.
- `tests/test_workspace_providers.py` — provider registry tests.
- `frontend/` — current HTML/CSS/JS client.

## Engineering rules

1. Work in small, clearly scoped commits.
2. `docs/WORKSPACE_ARCHITECTURE.md` is the single source of truth for architecture and status.
3. Never report tests as passing unless they have actually been run.
4. API keys must never leak into frontend storage, logs, or API responses.
5. Keep legacy endpoints until their replacements are implemented and verified.
