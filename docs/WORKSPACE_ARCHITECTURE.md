# Apeiron Workspace — System Architecture & Living Status

> **Canonical project document.** Update this exact file after every meaningful
> architecture or implementation change. Do not create competing status files.

- Project: Apeiron / AI-model
- Working branch: `feat/provider-api-manager`
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
  agents/                       # planned agent domain
  orchestration/                # planned task/run orchestration
  execution/                    # planned isolated execution
```

The current frontend remains static HTML/CSS/Vanilla JavaScript. A framework
migration is not required and must be evaluated separately.

## 4. Provider strategy

| Provider ID | Adapter | Status |
|---|---|---|
| `openai` | OpenAI-compatible Chat Completions | Implemented |
| `anthropic` | Anthropic Messages | Implemented |
| `google` | Gemini GenerateContent | Implemented |
| `openrouter` | Shared OpenAI-compatible adapter | Implemented |
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
- Provider registry, adapter contract, all five provider IDs, adapter factory,
  encrypted credential persistence, owner-scoped connection CRUD, and
  connection testing are implemented.
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
| API Manager UI | ADDED / NOT VERIFIED | Settings → Integrations panel; localized form, list, test/delete actions, responsive styles; syntax CI only, manual device review pending |
| Model discovery | TODO | Provider catalogs + manual model IDs |
| Agent CRUD | TODO | User-created configurable agents |
| Tool permissions | TODO | Capability validation and approval |
| Workspace UI shell | TODO | Responsive panel layout |
| File tree/editor | TODO | Project file operations |
| Orchestrator | TODO | Task graph, handoffs, run lifecycle |
| Run event stream | TODO | SSE initially |
| Isolated execution | TODO | Production-grade sandbox |
| Preview/artifacts | TODO | Output and generated files |
| Mobile/tablet polish | TODO | Breakpoint and touch testing |
| Regression/CI | VERIFIED | Provider Manager UI PR run #43605971375 passed Python 3.10–3.12 and frontend JavaScript syntax checks. |
| GitHub project presentation | DONE | Bilingual README, templates, contribution/security/community docs |
| Deployment workflow | MANUAL ONLY | No hosting target is configured; tests.yml is the automatic CI workflow |

## 8. Change log

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
- [ ] Fetch provider model lists where supported.
- [ ] Allow manual model IDs.
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

**Next concrete task:** complete the current Python + frontend syntax CI matrix, open a PR, and merge only when green. After merge, implement provider model discovery so users can select models instead of entering IDs manually.

## 10. Definition of done

A feature is DONE only when implementation is committed, CI has passed,
authorization and ownership are covered, secrets do not leak, and this document
reflects the real state. UI changes also require responsive checks.

## 11. Maintenance protocol

After every meaningful milestone update this exact file: date, tracker statuses,
change log, immediate next task, and architecture boundaries. This document must
always answer what is being built, how it is structured, what is verified, what
remains, and what happens next.
