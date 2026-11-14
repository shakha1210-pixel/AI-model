# Apeiron Workspace — System Architecture & Living Status

> **Canonical project document.** Update this exact file after every meaningful
> architecture or implementation change. Do not create competing status files.

- Project: Apeiron / AI-model
- Working branch: `main`
- Last updated: 2026-11-14
- Status: Living RFC + implementation tracker

## 1. Product goal

Apeiron is evolving from a chat-first AI application into a multi-provider,
multi-agent workspace. Users will connect their own model providers, create
configurable agents, organize projects and files, assign tasks, and inspect
agent runs and artifacts. The experience must support desktop, tablet, and
mobile.

Provider/model selection belongs to the user. Do not bind fixed providers to
hard-coded agent roles.

## 2. Product and engineering principles

- User-configured agents, not fixed role-to-model routing.
- Provider-independent model gateway and normalized request/response/stream types.
- Encrypted, tenant-scoped API credentials; raw keys are write-only.
- Explicit tool permissions and approval for side effects.
- Observable task runs, events, errors, and artifacts.
- Incremental migration; preserve legacy chat until replacements are verified.
- Responsive desktop/tablet/mobile experience.
- Do not describe planned functionality as implemented.

## 3. Target architecture

```text
CLIENT: Workspace UI · API Manager · Agent Builder · Editor
                         │ HTTPS / SSE
FASTAPI: Auth · Tenant ownership · Validation · Workspace API
                         │
WORKSPACE DOMAIN: Projects · Files · Agents · Connections · Runs
                         │
ORCHESTRATOR: Planner · Task graph · Handoffs · Retry · Approval
                         │
MODEL GATEWAY: normalized generation and streaming contract
       ┌─────────────────┼────────────────────┐
  OpenAI-compatible   Anthropic Messages   Google Gemini
  OpenAI/OpenRouter/   adapter              adapter
  custom endpoints
                         │
TOOLS: Workspace FS · Git · Search · Browser · Isolated Sandbox
                         │
DATA: Users · Encrypted Provider Connections · Agents · Projects · Runs
```

### Backend modules

```text
workspace/
  providers.py                 # public provider metadata
  adapters/
    base.py                    # normalized provider contract
    openai_compatible.py       # OpenAI, OpenRouter, custom compatible
    anthropic.py               # Anthropic Messages
    google.py                  # Gemini GenerateContent
    factory.py                 # provider ID -> adapter
  credentials/
    encryption.py              # Fernet credential encryption
    endpoint.py                 # public HTTPS custom endpoint validation
  api/
    connections.py              # authenticated provider connection API
    agents.py                   # tenant-scoped agent CRUD API
  orchestration/                # planned task/run orchestration
  execution/                    # planned isolated execution
```

The current frontend remains static HTML/CSS/Vanilla JavaScript. A framework
migration is not required and must be evaluated separately.

## 4. Provider strategy

| Provider ID | Adapter | Status |
|---|---|---|
| `openai`, `openrouter` | Shared OpenAI-compatible adapter | Implemented |
| `anthropic` | Anthropic Messages | Implemented |
| `google` | Gemini GenerateContent | Implemented |
| 20 additional vendors | Mistral, Groq, DeepSeek, xAI, Together, Fireworks, Cerebras, Perplexity, SambaNova, Hugging Face, NVIDIA NIM, DeepInfra, Moonshot, Qwen, Novita, Nebius, MiniMax, Z.AI, AI21, Baseten | Implemented via OpenAI-compatible adapter |
| `custom_openai` | Shared adapter + custom public HTTPS URL | Implemented |

All adapters support normalized generation and streaming interfaces and have
mocked HTTP coverage. Real provider credentials are not required by CI.

## 5. Security invariants and current limits

1. API keys must never be stored in browser storage, frontend bundles, logs,
   source control, analytics, or API responses.
2. Provider credentials are encrypted at rest using
   `PROVIDER_CREDENTIALS_ENCRYPTION_KEY` (Fernet). Losing this deployment key
   makes stored credentials unrecoverable; back it up securely.
3. All provider connections are scoped to an authenticated user. Every list,
   delete, and test query filters by owner ID.
4. Raw keys are write-only. List/create/delete/test responses expose metadata
   only; the test route decrypts a key only in server memory for the outbound call.
5. Custom provider URLs require HTTPS and reject local/private/link-local/
   reserved targets after DNS resolution. DNS can change between validation
   and connection time; production deployment MUST also enforce outbound
   network/egress rules. This application-level check alone is not a complete
   DNS-rebinding defense.
6. Provider connection testing performs a short generation request (maximum
   8 output tokens) and may incur a small provider charge.
7. Agent tools must run in a genuinely isolated sandbox with CPU, memory, time,
   filesystem, and network limits. The existing demo execution is not a
   production sandbox.
8. Require approval for destructive actions, external publishing, and commands
   with side effects.

The API Manager routes are mounted only when both `ENABLE_AUTH=true` and
`ENABLE_DATABASE=true`.

## 6. Current repository reality

- Backend: FastAPI/Python; legacy routes are concentrated in `main.py`.
- Frontend: static HTML/CSS/Vanilla JavaScript; chat UI exists, full Workspace UI
  and API Manager screens are not implemented yet.
- Existing features include chat, SSE, auth, session history, projects, file
  extraction, and feature-flagged tools.
- Legacy routing still contains fixed Claude/Gemini/Leonardo paths; the new
  provider gateway is implemented separately and is not yet wired into legacy
  chat routing.
- Provider registry (25 IDs), adapter contract, expanded OpenAI-compatible vendor catalog, adapter factory, model catalog discovery,
  encrypted credential persistence, owner-scoped connection CRUD, connection testing, and owner-scoped Agent CRUD API are implemented.
- Agent records bind to a connection owned by the same user and store model ID, system prompt, generation limits, active state, and a deny-by-default capability allow-list. Capability execution is not yet wired to the orchestrator.
- Custom endpoint DNS validation is implemented; production egress controls
  remain a deployment requirement.

## 7. Implementation tracker

Status key: DONE = implemented and CI-verified; IN PROGRESS = being implemented;
HARDENING REQUIRED = implemented with a documented production dependency;
TODO = not started.

| Area | Status | Notes |
|---|---|---|
| Migration branch | DONE | `feat/agent-workspace` |
| Provider registry | DONE | `workspace/providers.py` |
| Provider adapter contract | DONE | `workspace/adapters/base.py` |
| OpenAI / OpenRouter / custom adapter | DONE | Generation + SSE |
| Anthropic adapter | DONE | Messages + SSE |
| Gemini adapter | DONE | GenerateContent + SSE |
| Adapter factory | DONE | All five provider IDs |
| ProviderConnection DB model | DONE | Owner FK, encrypted key, base URL, key version, timestamps |
| Credential encryption | DONE | Fernet; deployment-managed key; fail closed |
| Connection create/list/delete API | DONE | Authenticated, owner-scoped, no key disclosure |
| Connection test API | DONE | Short generation test, safe diagnostics |
| Custom endpoint validation | HARDENING REQUIRED | HTTPS + DNS/IP checks; production egress firewall still required |
| API Manager UI | ADDED / NOT VERIFIED | Localized responsive form, list, model discovery, test/delete actions; syntax CI only, manual device review pending |
| Model discovery | DONE | OpenAI-compatible, Anthropic, and Gemini catalogs; manual fallback for unsupported providers; first-page pagination |
| Agent CRUD | DONE | Authenticated create/list/read/update/delete API; same-user provider binding; CI run #43608288861 passed |
| Agent Builder UI | ADDED / NOT VERIFIED | Responsive create/edit/list/delete panel in Settings → Integrations; localized in six languages; CI run #43608673434 passed; syntax/static checks only, browser review pending |
| Tool permissions | IN PROGRESS | Deny-by-default allow-list validation/storage; runtime enforcement and approvals not yet wired |
| Workspace UI shell | TODO | Responsive panel layout |
| File tree/editor | TODO | Project file operations |
| Agent text execution | DONE | Authenticated one-turn generation through configured provider/model; CI run #43608889817 passed; tools intentionally not executed |
| Agent run UI | DONE | Per-agent prompt/run/output panel; provider usage notice; CI run #43609153008 passed; manual browser review pending |
| Orchestrator | TODO | Task graph, handoffs, run lifecycle |
| Run event stream | TODO | SSE initially |
| Isolated execution | TODO | Production-grade sandbox |
| Preview/artifacts | TODO | Output and generated files |
| Mobile/tablet polish | TODO | Breakpoint and touch testing |
| Regression/CI | VERIFIED | Provider model discovery PR run #43606741602 passed Python 3.10–3.12 and frontend syntax; 138 tests passed on Python 3.11. |
| GitHub project presentation | DONE | Bilingual README, templates, contribution/security/community docs |
| Deployment workflow | MANUAL ONLY | No hosting target is configured; tests.yml is the automatic CI workflow |

## 8. Change log

### 2026-11-14 — Agent run panel

- Added a per-agent text prompt, Run action, and response output panel to Agent Builder.
- The UI calls the authenticated single-turn run endpoint and renders model output with `textContent` (no HTML interpretation).
- Added provider usage/possible charge notice. Tool execution remains disabled; permission flags do not authorize runtime actions yet.
- Added localized run controls and usage notice in six languages. CI run #43609153008 passed on Python 3.10–3.12 with 156 tests per version; frontend smoke check also passed.


### 2026-11-14 — Safe single-turn Agent execution API

- Added `POST /api/workspace/agents/{id}/run` for one-turn text generation using the agent's configured provider connection, model, system prompt, temperature, and token limit.
- Agent ownership and connection ownership are checked before decrypting credentials; credentials remain server-side and are not included in responses.
- Inactive agents cannot run. Custom provider URLs are revalidated before outbound requests.
- Tool permissions are deliberately NOT executed by this endpoint. Tool calls remain blocked until an isolated execution and approval system is implemented.
- Added mocked adapter tests for request configuration, secret non-disclosure, and inactive-agent rejection. CI run #43608889817 passed on Python 3.10–3.12 with 156 tests per version; frontend smoke check also passed.


### 2026-11-14 — Agent Builder UI

- Added an Agent Builder panel under Settings → Integrations with create, edit, list, and delete flows.
- The UI loads the signed-in user's provider connections and binds each agent to one of them; model IDs remain manually editable.
- Added system prompt, description, temperature, output token limit, active toggle, and six allow-list permission toggles.
- Added responsive single-column mobile layout and translations for Uzbek, Russian, English, Turkish, Arabic, and Karakalpak.
- Added UI wiring/localization tests and Node syntax checking for `agent-manager.js`. CI run #43608673434 passed Python 3.10–3.12 with 154 tests per version and the frontend syntax smoke checks. Actual browser/device visual verification remains pending.


### 2026-11-14 — Agent Builder API foundation

- Added the `workspace_agents` table with user ownership, provider connection binding, model ID, system prompt, generation settings, active state, and JSON capability allow-list.
- Added authenticated tenant-scoped agent create/list/read/update/delete endpoints under `/api/workspace/agents`.
- Agent creation and reassignment require a provider connection owned by the current user; foreign agent IDs return 404.
- Capabilities are deny-by-default and restricted to a fixed allow-list. Runtime tool execution and approval enforcement are not implemented yet.
- Provider connections referenced by agents cannot be deleted until agents are deleted or reassigned.
- Added API tests for CRUD, validation, tenant isolation, foreign connection binding, null update rejection, and connection deletion safeguards. CI run #43608288861 passed on Python 3.10, 3.11, and 3.12; 151 tests passed on each version, including explicit-null update rejection.


### 2026-11-14 — Provider model discovery

- Added normalized model catalog discovery for OpenAI-compatible vendors, Anthropic, and Google Gemini.
- Added owner-scoped `GET /api/workspace/connections/{id}/models`; API keys are decrypted only server-side and never returned.
- Gemini catalog filters out non-generation models; model names are normalized into IDs and display names.
- Providers without a catalog endpoint (currently Perplexity) return a manual-entry fallback rather than failing the connection.
- Added model discovery actions and datalist suggestions to the Provider Manager UI.
- Added mocked HTTP, ownership, and manual-fallback tests.
- CI run #43606741602 passed Python 3.10, 3.11, and 3.12 plus the Node frontend syntax check; Python 3.11 reported 138 passed.

### 2026-11-14 — Expanded provider catalog

- Expanded the provider registry from 5 to 25 IDs while reusing the existing OpenAI-compatible adapter for vendors that share the Chat Completions API.
- Added Mistral, Groq, DeepSeek, xAI, Together AI, Fireworks AI, Cerebras, Perplexity, SambaNova, Hugging Face, NVIDIA NIM, DeepInfra, Moonshot AI, Qwen/DashScope, Novita, Nebius Token Factory, MiniMax, Z.AI/GLM, AI21 Labs, and Baseten.
- Added the expanded catalog to the Provider Manager selector and registry/factory tests. Model IDs remain manually entered until model discovery is implemented.

### 2026-11-14 — Provider API Manager UI

- Added a provider connection form to Settings → Integrations for all five provider IDs.
- Added connection list, manual model ID, short connection test, and delete actions.
- API keys are entered in a password field, sent only in the authenticated POST body, and cleared from the form after submission; they are never written to browser storage.
- Added responsive layout styles and translations for Uzbek, Russian, English, Turkish, Arabic, and Karakalpak.
- Added a Node.js syntax-check job for the provider manager and i18n scripts. Manual visual checks on desktop and mobile remain outstanding.
- Automatic deployment was disabled until a hosting target is selected; the separate test workflow remains automatic on pushes and pull requests.

### 2026-11-14 — Provider API Manager foundation

- Added `ProviderConnection` SQLAlchemy model linked to the owning user.
- Added Fernet encryption/decryption for provider API keys. Missing or malformed
  encryption configuration fails closed.
- Added owner-scoped create, list, delete, and connection-test endpoints at
  `/api/workspace/connections`.
- Raw keys and ciphertext are omitted from all API responses.
- Added custom endpoint validation: HTTPS only, no userinfo/query/fragment,
  and reject local/private/link-local/reserved DNS/IP targets.
- Added API and security tests. Initial CI found a detached ORM test fixture;
  the fixture was corrected to keep identity fields loaded. A subsequent syntax
  issue in that fixture was also corrected. Latest run is being rechecked.
- Added `PROVIDER_CREDENTIALS_ENCRYPTION_KEY` to `.env.example` and declared
  `cryptography` directly in requirements.

### 2026-11-14 — Anthropic, Gemini, and adapter factory

- Implemented Anthropic Messages generation and SSE text streaming.
- Implemented Google Gemini GenerateContent and SSE streaming.
- Added provider adapter factory for all five registry IDs.
- CI run #43604875752 passed on Python 3.10, 3.11, and 3.12; 91 tests passed
  on Python 3.11.

### 2026-11-14 — OpenAI-compatible adapter and live CI

- Implemented OpenAI-compatible generation and SSE streaming for OpenAI,
  OpenRouter, and custom compatible providers.
- CI run #43604535329 passed on Python 3.10, 3.11, and 3.12; 77 tests passed
  on Python 3.11.

### 2026-11-14 — Repository presentation and provider contract

- Added normalized provider adapter contracts and tests.
- Added GitHub Actions matrix testing, bilingual README, issue/PR templates,
  contribution guide, security policy, and code of conduct.
- Fixed CI setup to provide a test-only JWT secret without using production keys.

### 2026-11-14 — Initial Workspace foundation

- Created `feat/agent-workspace`.
- Added provider registry and initial provider tests.
- No legacy chat routes have been replaced.

## 9. Roadmap

### Milestone 1 — Provider gateway
- [x] Provider registry and normalized adapter contract.
- [x] OpenAI-compatible, Anthropic, and Gemini adapters.
- [x] Adapter factory and mocked HTTP tests.
- [x] Python 3.10–3.12 CI verification.

### Milestone 2 — API Manager
- [x] Per-user credential model and Fernet encryption.
- [x] Owner-scoped create/list/delete endpoints.
- [x] Connection test endpoint with safe diagnostics.
- [x] Custom HTTPS endpoint validation.
- [ ] Production outbound network/egress restrictions.
- [x] Responsive API Manager UI implementation (manual visual verification pending).

### Milestone 3 — Model discovery and Agent Builder
- [x] Fetch provider model lists where supported (first page).
- [x] Allow manual model IDs and fallback for providers without catalogs.
- [ ] Per-user agent CRUD and connection/model binding.
- [ ] Prompts, capabilities, tools, and permission settings.

### Milestone 4 — Workspace and project files
- [ ] Responsive navigation and workspace panels.
- [ ] Project file tree and safe file operations.
- [ ] Editor and task/run side panel.
- [ ] Mobile navigation and touch verification.

### Milestone 5 — Orchestration and execution
- [ ] Task/run lifecycle, events, planner, handoffs, retries, cancellation.
- [ ] Approval checkpoints.
- [ ] Isolated sandbox, artifacts, and preview.

### Milestone 6 — Stabilization
- [ ] Regression, auth, tenant isolation, and secret-handling review.
- [ ] Desktop, tablet, and mobile verification.
- [ ] Deployment, backup, and encryption-key rotation documentation.
- [ ] Deprecate legacy paths only after feature parity.

**Next concrete task:** review the user's local test results and manually verify Provider Manager, Agent Builder, and Agent run panel on desktop/mobile; then add persistent run history and observable task lifecycle.

## 10. Definition of done

A feature is DONE only when implementation is committed, CI has passed,
authorization and ownership are covered, secrets do not leak, and this document
reflects the real state. UI changes also require responsive checks.

## 11. Maintenance protocol

After every meaningful milestone update this exact file: date, tracker statuses,
change log, immediate next task, and architecture boundaries. This document must
always answer what is being built, how it is structured, what is verified, what
remains, and what happens next.
