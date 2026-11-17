# Contributing

Contributions should keep the project self-hosted, English-first, and usable without optional video extraction or external household services. Do not add credentials, real server identifiers, private preferences, generated state, or personal paths.

## Local workflow

- Use Python 3.11 or newer and uv sync --group dev (or a virtual environment with pytest and Ruff installed).
- Keep Discord API behavior isolated behind the Transport protocol; tests must use a fake transport or local fake server, never the real API.
- Run ruff format --check ., ruff check ., pytest, and python scripts/privacy_scan.py before submitting.
- Use focused Conventional Commit messages (feat:, fix:, docs:, test:, chore:).
- Update user-facing docs when CLI behavior or the Hermes profile changes.

## Pull requests

Explain the user-visible behavior, privacy implications, and checks run. Keep changes focused. Do not add telemetry, outreach, cloud dependencies, or destructive cleanup behavior.
