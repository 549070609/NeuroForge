# Repository Guidelines

## Project Structure & Module Organization
This repository is a Python monorepo. Most contributor-facing code lives in `main/`:
- `main/agentforge-engine/`: core agent engine, providers, plugins, built-in tools, and the largest test suite.
- `main/Service/`: FastAPI gateway and service layer (`gateway/`, `services/`, `schemas/`, `tests/`).
- `main/Long-memory/`: memory plugins (`embeddings/`, `long-memory/`) and related tests.
- `main/Agent/`: agent metadata and plan assets (`public/`, `plans/`, `namespaces/`).
- `Docs/` and root markdown files are reference docs. Treat `Learncode/` as imported examples/snapshots unless a task explicitly targets it.

## Build, Test, and Development Commands
- Install core dev environment: `cd main/agentforge-engine && pip install -e ".[dev]"`
- Run agentforge-engine tests: `cd main/agentforge-engine && pytest -v --tb=short`
- Run agentforge-engine coverage: `cd main/agentforge-engine && pytest --cov=pyagentforge --cov-report=term-missing`
- Build package artifact: `cd main/agentforge-engine && python -m build`
- Run Service API locally: `cd main/Service && pip install -e ".[dev]" && uvicorn Service.gateway.app:create_app --factory --reload --port 8000`
- Run Service tests: `cd main/Service && pytest tests/ -v --cov=Service --cov-report=html`
- Run Long-memory tests: `cd main/Long-memory/long-memory && pytest`

## Coding Style & Naming Conventions
- Target Python 3.11+ where possible; use 4-space indentation and explicit type hints for new/changed code.
- Naming: modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE_CASE`.
- Test files should follow `test_*.py`; keep test names behavior-focused (for example, `test_tool_registry_rejects_duplicates`).
- In `main/agentforge-engine`, lint and import ordering are enforced by Ruff (`line-length = 100`), with strict mypy settings.

## Testing Guidelines
- Use `pytest` across all modules; async tests should use `@pytest.mark.asyncio`.
- Add or update tests with every behavior change; prefer unit tests first, then integration tests for cross-module flows.
- Maintain solid coverage on touched areas; use `--cov` for non-trivial changes.

## Commit & Pull Request Guidelines
- Follow observed commit style: `feat:`, `fix:`, `test:`, `chore:`, `refactor:` (optional scope, e.g., `feat(ast-grep):`).
- Keep commits focused and imperative; avoid mixing refactors with feature work.
- PRs should include: concise summary, affected paths, test commands/results, linked issue/task, and API examples when endpoints/contracts change.

## Security & Configuration Tips
- Do not commit API keys or local secrets. Use environment variables (for example, `SERVICE_*` settings and provider keys).
- Keep generated runtime data in `data/` and avoid committing local caches or model artifacts unless explicitly required.
