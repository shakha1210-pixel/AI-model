# Contributing to Apeiron

Thank you for helping improve Apeiron. The project is evolving from a chat-first
application into a multi-provider AI Workspace, so small, reviewable changes are
preferred over large rewrites.

## Before you start

1. Check the open issues and current roadmap in
   [WORKSPACE_ARCHITECTURE.md](docs/WORKSPACE_ARCHITECTURE.md).
2. For substantial changes, open an issue or discuss the design first.
3. Work on a feature branch; do not commit directly to `main`.
4. Never commit API keys, credentials, user data, local databases, or production
   logs.

## Development setup

Use Python 3.10 or newer, create a virtual environment, and install dependencies:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
```

Run the test suite with:

```bash
pytest -v
```

## Engineering expectations

- Preserve existing chat endpoints and behavior unless a migration is explicitly
  planned and tested.
- Keep provider-specific API details inside adapter modules.
- Normalize provider errors and never expose secrets in errors or logs.
- Enforce authenticated ownership checks for user-owned resources.
- Treat custom provider URLs as untrusted input; prevent SSRF.
- Do not enable code execution without a real isolated sandbox.
- Add tests for new behavior and regression cases.
- Check responsive layouts on desktop and mobile when changing the UI.
- Update the single canonical status/architecture document:
  `docs/WORKSPACE_ARCHITECTURE.md`.

## Pull requests

Use the pull request template. Explain the motivation, implementation, test
commands/results, compatibility impact, and any security considerations. Add
screenshots for visible UI changes. Do not claim tests passed unless they were
actually executed.

## Scope and review

Keep each pull request focused. Avoid unrelated formatting churn, dependency
upgrades, and framework migrations unless they are part of an agreed design.
