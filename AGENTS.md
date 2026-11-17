# Project instructions

## Commands

- uv sync --group dev
- uv run ruff format --check .
- uv run ruff check .
- uv run pytest
- uv run python scripts/privacy_scan.py
- uv run kitchen-companion discord setup --guild-id <SERVER_ID> --dry-run

## Quality and privacy rules

- Python 3.11+; type public interfaces and keep runtime dependencies minimal.
- Use the injected Discord Transport; tests must never call Discord.
- Never accept a bot credential as a CLI argument or include one in output, docs, examples, state, fixtures, or logs.
- Persist only non-secret Discord IDs in setup state. Keep household data local and portable.
- Bootstrap must remain idempotent, detect ambiguous exact matches, and never delete unrelated resources.
- Preserve the exact default category/channel template and offer English and French labels.
- Profile instructions must distinguish agent-driven behavior from implemented CLI behavior.
- Avoid telemetry, cloud dependencies, integrations outside Discord, automatic weekly scheduling, and destructive cleanup.
- Run formatting, lint, tests, privacy scan, and inspect the final diff before committing.
