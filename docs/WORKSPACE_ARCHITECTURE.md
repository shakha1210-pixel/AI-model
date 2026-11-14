# Apeiron Workspace — System Architecture & Living Status

> **Canonical project document.** This exact file must be updated after every
> meaningful architecture or implementation change. Do not create competing
> status documents. README files link here.

- Project: Apeiron / AI-model
- Working branch: `feat/agent-workspace`
- Last updated: 2026-11-14
- Status: Living RFC + implementation tracker

---

## 1. What are we building?

We are evolving Apeiron from a chat-first AI application into a multi-provider,
multi-agent development workspace.

Users will be able to create workspaces and projects, connect personal model
providers, discover or manually enter models, create/configure agents, assign
tasks, inspect agent activity and artifacts, edit files, and run work in a
controlled environment. The UI must work on desktop, tablet, and mobile.

Users choose the provider/model for each agent. The platform must not silently
bind fixed providers to hard-coded agent roles.

## 2. Product principles

- User-configured agents, not fixed role-to-model routing.
- Provider-independent orchestration through a common model gateway.
- Explicit tool permissions and approval for side effects.
- Encrypted, tenant-scoped API credentials.
- Observable task runs, events, errors, and artifacts.
- Incremental migration with legacy functionality preserved until replacement.
- Responsive desktop/tablet/mobile experience.

## 3. Target system architecture

```text
┌──────────────────────────────────────────────────────────────────┐
│ CLIENT: Workspace UI · Agent Builder · API Manager · Editor      │
│                  Desktop / Tablet / Mobile                        │
└──────────────────────────────┬───────────────────────────────────┘
                               │ HTTPS / SSE
┌──────────────────────────────▼───────────────────────────────────┐
│ FASTAPI: Auth · Tenant ownership · Validation · API policies     │
├──────────────────────────────────────────────────────────────────┤
│ WORKSPACE DOMAIN: Projects · Files · Agents · Connections · Runs │
├──────────────────────────────────────────────────────────────────┤
│ ORCHESTRATOR: Planner · Task graph · Handoffs · Retry · Approval │
├──────────────────────────────────────────────────────────────────┤
│ MODEL GATEWAY: Common request / response / stream / tool contract│
├───────────────┬────────────────┬────────────────┬────────────────┤
│ OpenAI        │ Anthropic      │ Google Gemini  │ OpenRouter     │
│ adapter       │ adapter        │ adapter        │ adapter        │
└───────────────┴────────────────┴────────────────┴────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│ TOOLS: Workspace FS · Git · Search · Browser · Isolated Sandbox  │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│ DATA: Users · Encrypted Secrets · Agents · Projects · Runs       │
└──────────────────────────────────────────────────────────────────┘
```

### Backend module target

```text
workspace/
  __init__.py
  providers.py              # public provider metadata [ADDED]
  api/                      # versioned routes and schemas
  adapters/
    __init__.py             # adapter package [ADDED]
    base.py                 # shared adapter contract [ADDED]
    openai_compatible.py    # OpenAI, OpenRouter, compatible vendors
    anthropic.py
    google.py
  credentials/              # encrypted per-user connections
  agents/                   # agent schema, service, repository
  projects/                 # workspace and file operations
  orchestration/             # task planning, runs, handoffs
  execution/                 # sandbox and artifacts
```

The repository currently uses FastAPI and a static HTML/CSS/JavaScript client.
Keep them during migration. Introduce a frontend framework only after a separate
technical evaluation; a big-bang rewrite is not a prerequisite.

## 4. Provider and model strategy

| Provider ID | Name | Adapter family | Registry status |
|---|---|---|---|
| `openai` | OpenAI | OpenAI-compatible | Added |
| `anthropic` | Anthropic | Anthropic Messages | Added |
| `google` | Google Gemini | Google Generative Language | Added |
| `openrouter` | OpenRouter | OpenAI-compatible | Added |
| `custom_openai` | Custom OpenAI-compatible | OpenAI-compatible | Added |

The registry is metadata only; it does not mean live connections are working.

A user connection will include owner ID, provider ID, display name, encrypted
API key, optional validated base URL, status, safe diagnostics, timestamps,
and encryption-key version. The raw key is write-only and must never be returned.

An agent references a connection ID and model ID, plus system instructions,
generation settings, enabled tools, and permission policy. Fetch model catalogs
where supported and allow manual model IDs as a fallback.

## 5. Security invariants

1. Never store API keys in localStorage/sessionStorage, frontend bundles, logs,
   source control, analytics, or API responses.
2. Encrypt credentials at rest with a deployment-managed key; document rotation.
3. Scope every connection, agent, project, file, run, and artifact to an
   authenticated owner; check ownership on every operation.
4. Validate custom base URLs and block localhost, private, loopback, link-local,
   and cloud metadata targets; revalidate redirects and resolved addresses.
5. Run agent tools in an isolated sandbox with CPU, memory, time, filesystem,
   and network limits. Existing demo execution is not a production sandbox.
6. Require approval for destructive actions, external publishing, and commands
   with side effects.
7. Sanitize provider errors and preserve input/output safety checks.

## 6. Current repository reality

- Backend: FastAPI/Python; main routes are concentrated in `main.py`.
- Frontend: static HTML/CSS/Vanilla JavaScript.
- Existing features include chat, SSE, auth, session history, projects,
  file extraction, and feature-flagged tools.
- Legacy routing has fixed Claude/Gemini/Leonardo paths.
- Responsive sidebar behavior exists, but a full workspace UI does not.
- Working branch: `feat/agent-workspace`.

Do not describe planned functionality as implemented.

## 7. Implementation tracker

Status key: DONE = implemented and verified; ADDED / NOT VERIFIED = committed
but not yet tested; IN PROGRESS = currently being worked on; TODO = not started.

| Area | Status | Notes |
|---|---|---|
| Migration branch | DONE | `feat/agent-workspace` created |
| Provider registry | ADDED / NOT VERIFIED | `workspace/providers.py` |
| Provider registry tests | ADDED / NOT VERIFIED | Test file committed; execution not confirmed |
| Adapter contract tests | ADDED / NOT VERIFIED | `tests/test_workspace_adapter_contract.py` |
| Architecture living document | DONE | This file |
| Bilingual README | DONE | Uzbek + English sections |
| Adapter protocol | ADDED / NOT VERIFIED | Normalized request/result/stream/error contract in `workspace/adapters/base.py` |
| OpenAI adapter | TODO | Requests and streaming |
| Anthropic adapter | TODO | Messages API and streaming |
| Gemini adapter | TODO | GenerateContent and streaming |
| OpenRouter adapter | TODO | OpenAI-compatible integration |
| Encrypted API connections | TODO | Per-user secret persistence |
| Connection test endpoint | TODO | Safe diagnostics, no key disclosure |
| Model discovery | TODO | Catalogs + manual model ID |
| Agent CRUD | TODO | User-created configurable agents |
| Tool permissions | TODO | Capability validation and approval |
| Workspace API | TODO | Namespaced/versioned routes |
| Workspace UI shell | TODO | Responsive panel layout |
| File tree/editor | TODO | Project file operations |
| Orchestrator | TODO | Task graph, handoffs, run lifecycle |
| Run event stream | TODO | SSE initially |
| Isolated execution | TODO | Production-grade sandbox |
| Preview/artifacts | TODO | Output and generated files |
| Mobile/tablet polish | TODO | Breakpoint and touch testing |
| Regression/CI | ADDED / NOT VERIFIED | GitHub Actions pytest workflow for Python 3.10–3.12 |

## 8. Change log — what changed?

### 2026-11-14 — Repository presentation and provider contract

- Added normalized provider adapter contracts for one-shot generation, streaming events, usage, and safe provider errors.
- Added contract tests; execution has not yet been verified.
- Added GitHub Actions test workflow for Python 3.10, 3.11, and 3.12.
- Added contribution and security guidance, issue templates, and a pull request template.
- Reworked README as a bilingual project landing page with product direction, provider status, setup, and project links.

### 2026-11-14 — Initial Workspace foundation

- Created branch `feat/agent-workspace`.
- Added `workspace/__init__.py`.
- Added `workspace/providers.py` with OpenAI, Anthropic, Gemini, OpenRouter,
  and Custom OpenAI-compatible metadata.
- Added `tests/test_workspace_providers.py`.
- Added this living architecture/status document.
- Updated README with Uzbek and English documentation.
- No legacy chat routing has been replaced.
- Provider adapters, API key storage, model discovery, and agent runtime are
  not implemented yet.
- Tests have been committed but have not yet been run in a verified environment.

## 9. Roadmap — what remains and what happens next?

### Milestone 1 — Provider gateway foundation
1. Verify the adapter contract and GitHub Actions workflow by running the test suite.
2. Implement OpenAI-compatible generation and streaming with mocked HTTP tests.
3. Implement Anthropic and Gemini adapters against the same contract.
4. Add adapter-specific error normalization and usage mapping.
5. Keep legacy `/chat` unchanged until the new path is validated.

### Milestone 2 — API Manager
1. Select credential persistence compatible with the existing database.
2. Implement create/list/delete/test connection endpoints.
3. Ensure list responses never reveal raw keys.
4. Add SSRF protection for custom endpoints.
5. Build the provider connection UI.

### Milestone 3 — Model discovery and Agent Builder
1. Fetch provider model lists where supported.
2. Allow manual model IDs.
3. Implement per-user agent CRUD.
4. Bind agents to provider connections and models.
5. Add prompts, capabilities, tools, and permission settings.

### Milestone 4 — Workspace and project files
1. Build responsive navigation and workspace panels.
2. Add project file tree and safe file operations.
3. Integrate editor and task/run side panel.
4. Verify mobile navigation and touch interactions.

### Milestone 5 — Orchestration and execution
1. Add task/run lifecycle and event model.
2. Implement planner, handoffs, retries, and cancellation.
3. Add approval checkpoints.
4. Integrate isolated sandbox and artifacts.
5. Add run output and preview.

### Milestone 6 — Stabilization
1. Run regression tests and CI.
2. Test auth, tenant isolation, and secret handling.
3. Test desktop, tablet, and mobile.
4. Document deployment, backups, and encryption key rotation.
5. Deprecate legacy paths only after feature parity.

**Next concrete task:** execute the new contract and registry tests in a verified environment, fix any failures, then implement the OpenAI-compatible adapter. Database inspection confirms SQLAlchemy 2.x is already a project dependency and the existing `User` model is the likely ownership anchor for the future encrypted-credential table.

## 10. Definition of done

A feature is DONE only when implementation is committed, tests have actually
passed (or manual verification is explicitly documented), authorization and
ownership are covered, errors do not leak secrets, and both README and this
document reflect the real state. UI changes also require responsive checks.

## 11. Document maintenance protocol

After every meaningful milestone update this exact file:
1. Last updated date.
2. Implementation tracker statuses.
3. Dated change log.
4. Immediate next actions and dependencies.
5. Architecture diagrams/module layout when boundaries change.

Record why a plan changes and what replaces it. This document must always answer:
what are we building, how is it structured, what changed, what is verified,
what remains, and what happens next.
