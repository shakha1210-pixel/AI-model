# Workspace architecture (RFC)

## Product direction

Move Apeiron from a chat-first application to a project workspace. A workspace
contains projects, files, agent definitions, provider connections, task runs
and execution artifacts. Users create and configure agents; the platform does
not silently assign fixed models to hard-coded roles.

## Provider strategy

The first-class providers are OpenAI, Anthropic, Google Gemini and OpenRouter.
The registry also exposes a Custom OpenAI-compatible option so additional
vendors can be configured without changing agent orchestration.

An agent references a model connection by identifier and stores a model name,
system instructions, tools/capabilities and optional generation settings.
Provider-specific HTTP details stay behind adapters:

- OpenAI-compatible adapter: OpenAI, OpenRouter and custom endpoints.
- Anthropic adapter: Claude Messages API.
- Google adapter: Gemini API.

Provider model catalogs should be loaded from provider APIs when supported,
with a manually-entered model ID as a fallback. Do not hard-code a model list
as the source of truth.

## Target modules

```text
workspace/
  providers.py       # public provider registry (added first)
  adapters/          # provider-specific request/response translation
  credentials/       # encrypted per-user API key storage
  agents/            # agent schema, CRUD and validation
  projects/          # workspace/project and virtual file tree
  orchestration/     # task graph, agent handoff and run lifecycle
  execution/         # isolated command execution and artifact handling
```

FastAPI remains the API server during the migration. The existing HTML/CSS/JS
client remains operational while the new workspace screens are introduced
incrementally. A frontend framework migration is a separate, reversible step,
not a prerequisite for the backend domain split.

## Security invariants

1. API keys are write-only secrets: never return them from an API, log them,
   include them in errors, or store them in localStorage/sessionStorage.
2. Encrypt credentials at rest with an application-managed encryption key
   supplied by the deployment environment. Support key rotation.
3. Every credential, agent, project, file and run is scoped to an authenticated
   user; enforce ownership checks on every read/write.
4. Validate provider IDs and custom base URLs. Block localhost, link-local,
   private-network and cloud metadata destinations to prevent SSRF.
5. Agent tool execution must use an isolated sandbox with resource and network
   limits. The current demo code runner is not a production sandbox.
6. Keep user approval gates for destructive actions, external publishing and
   commands with side effects.

## Migration sequence

1. Provider registry and provider adapter contract.
2. Encrypted API connections and model discovery.
3. Agent CRUD and per-agent model/connection selection.
4. Workspace/project file tree and editor shell.
5. Task orchestration, streaming run events and agent handoffs.
6. Sandboxed execution, preview and artifacts.
7. Responsive desktop/tablet/mobile UI and regression tests.

## Compatibility

The existing `/chat`, history, auth and project endpoints remain available
during the migration. New Workspace endpoints are versioned/namespaced and
can be enabled independently. Legacy fixed-provider routing is removed only
after the new agent-run path has feature parity and regression coverage.
