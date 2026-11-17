# Hermes Kitchen Companion

A self-hosted household kitchen assistant for Hermes Agent and Discord. The repository is a reusable Hermes profile distribution with a small Python CLI for setting up Discord channels and managing portable local recipe and shopping data.

## Quick start

Requirements: Python 3.11+, a Discord server where you can add a bot, and Hermes Agent for the profile. The bootstrap uses only Python's standard library. From a checkout of the repository, run:

    cd hermes-kitchen-companion
    uv sync --no-dev
    read -r -p "Discord server ID: " SERVER_ID
    uv run kitchen-companion discord setup --guild-id "$SERVER_ID" --dry-run
    uv run kitchen-companion discord setup --guild-id "$SERVER_ID"

The first command is offline and prints the planned resources. The real setup asks for the bot credential in a masked prompt unless the DISCORD_BOT_TOKEN environment variable is already available to that process. The credential is never accepted as a command-line argument, written to disk, or printed. You can also install the package in a standard virtual environment:

    python3 -m venv .venv
    . .venv/bin/activate
    python -m pip install .
    read -r -p "Discord server ID: " SERVER_ID
    kitchen-companion discord setup --guild-id "$SERVER_ID"

The setup prints JSON with created/existing IDs, the local state file path, and next steps. That file contains only server, category, and channel IDs. Review and protect it as local household configuration.

## Create the Discord bot

Create an application and bot in the Discord Developer Portal, then add the bot to your server. Grant **Manage Channels** (required to create channels and set their positions) and **View Channels** on the managed category and its channels so setup can discover existing resources safely. The guild channel-list endpoint omits channels the bot cannot view. Send Messages is needed for normal participation; for the forum notebook, also grant Send Messages in Threads and Create Public Threads. Avoid Administrator. The bot needs access to the selected server. Copy the server ID using Discord's Developer Mode. See the [Discord guild channel endpoints](https://docs.discord.com/developers/resources/guild) for current API permission and channel-type behavior.

## Exact channel result

By default, setup creates one category with these five channels in order:

1. 🍳 Chez Dobby
   1. 💬・discussion — text
   2. 💡・idées-repas — text
   3. 🎬・reels — text
   4. 📖・carnet — forum
   5. 🛒・courses — text

The category name is configurable (--category). Channel names can use the English template with --language en; French is --language fr. Existing resources are matched by exact name, type, and category. Duplicate matches stop setup with an actionable error. Unrelated channels are never deleted. Setup does not configure a Discord gateway or post messages.

--dry-run makes no API requests and does not prompt for a credential. It reports the local plan only. Re-run setup safely to pick up missing channels. Existing positions are left alone by default; pass --sync-order to set the managed category and channel positions.

## Install the Hermes profile

Hermes profile installation installs the Hermes distribution only; it does **not** install this repository's Python CLI. To install the public CLI with uv:

    uv tool install git+https://github.com/ArthurRavel/hermes-kitchen-companion.git

For a checkout/virtual environment install, use the [Quick start](#quick-start) commands above. To install the Hermes profile distribution, use its public repository source:

    hermes profile install github.com/ArthurRavel/hermes-kitchen-companion --name kitchen-companion --alias

Then inspect and select the installed profile using your Hermes version's profile commands. The repository root contains distribution.yaml, SOUL.md, config.yaml, and skills/household/kitchen-companion/SKILL.md, following the [Hermes profile distribution](https://hermes-agent.nousresearch.com/docs/user-guide/profile-distributions) and [skill](https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills) layouts. Inspect the installed distribution with hermes profile info kitchen-companion and hermes profile list. Hermes Agent is not bundled, and this project is not affiliated with Hermes Agent or Discord.

The skill describes agent-driven behavior: two or three meal ideas on request, searching saved recipes first, saving only on explicit request, respecting household preferences and allergies, and offering vegetarian alternatives when relevant. These conversation behaviors depend on the installed Hermes model/tools; the Python package does not implement them as deterministic chat logic.

## Connect Hermes to Discord

The channel bootstrap does not configure or start the Hermes messaging gateway. To use the profile in Discord, follow the [official Hermes Discord setup](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/discord) and use Hermes' supported credential setup outside this repository. The bootstrap credential and the gateway credential are not written by this project to its profile files. Enable the required Message Content and Server Members intents, and configure the household members or roles allowed to use the gateway. Hermes normally requires a mention for replies in server channels; this distribution does not set a channel response policy.

The bootstrap writes a local channel-ID mapping. The profile skill can read that file when local file tools are available; it does not hard-code Discord IDs. If you pass a custom `--state-file`, set `kitchen-companion.channel_state_file` in the local Hermes config to that path.

## Local data and architecture

Recipes and shopping items use portable JSON files under ~/.local/share/hermes-kitchen-companion by default. Set KITCHEN_COMPANION_DATA or pass --data-dir to change the location. For example:

    uv run kitchen-companion recipe add "Lentil soup" "Red lentils, onion, stock. Simmer until tender." --data-dir ./household-data
    uv run kitchen-companion recipe search lentil --data-dir ./household-data
    uv run kitchen-companion shopping add "Carrots" --data-dir ./household-data
    uv run kitchen-companion shopping list --data-dir ./household-data
    uv run kitchen-companion shopping remove "Carrots" --data-dir ./household-data

The agent should only store a recipe after someone explicitly asks. The CLI does not sync files to Discord; it provides local helpers the profile can use. Keep the data directory private and back it up as you would other household files.

    Household member
          │ asks in Discord
          ▼
    Discord server ── channel IDs ── Hermes Agent profile
                                          │
                                          ├── bundled kitchen skill (agent-driven behavior)
                                          └── local JSON helpers ── recipes.json / shopping.json

    Local setup CLI ── Discord REST API (channel creation only)
           └────────── local state file (non-secret IDs)

No telemetry, analytics, hosted service, or automatic weekly scheduling is included. Optional social-video extraction is not required and is not implemented by the core package; meal ideas, notebook, and shopping helpers remain usable without it. No Obsidian or other personal infrastructure is required.

## Configuration and privacy

examples/config.yaml documents the non-secret fields with placeholders. The Discord token comes only from the process environment or a hidden interactive prompt. It is not in config, shell command examples, generated files, CLI output, or logs. API errors show safe status messages without response bodies. HTTP requests have a timeout and bounded retries for Discord rate limits.

The generated state file is written to ~/.config/hermes-kitchen-companion/discord-state.json by default (or --state-file). It contains only the selected server ID, category ID, and channel-ID mapping. Recipe and shopping data stay in the configured local data directory. Discord receives only the channel setup requests. The profile's runtime privacy also depends on the Hermes deployment and Discord server access you configure.

## Troubleshooting

- **401:** check that the environment is supplying the bot credential for the correct application; setup never echoes it.
- **403:** confirm the bot is in the selected server and has Manage Channels.
- **404:** verify the server ID and bot access.
- **Duplicate category/channel:** rename or remove the duplicate yourself, then rerun setup. The tool will not guess which one to use.
- **Rate limit or timeout:** retry later; the HTTP client waits on a bounded Retry-After interval and makes a finite number of attempts.
- **Forum unavailable:** use a server where forum channels are enabled and ensure the bot can manage channels.
- **Hermes bot stays offline:** check that Message Content and Server Members intents are enabled in the Developer Portal, and that gateway users or roles are allowed in Hermes configuration.

## Uninstall and rollback

The bootstrap only creates the managed category/channels and writes a local mapping. It never deletes channels or household data. To remove the installed Hermes profile, run `hermes profile delete kitchen-companion`; Hermes removes that profile's own configuration, credentials, memories, and sessions, so back up anything you need first. Then manually delete the bot and any channels you no longer want in Discord. The setup state file and data directory are outside the profile and must be removed manually if desired. The CLI intentionally has no destructive cleanup command.

## Development

    uv sync --group dev
    uv run ruff format --check .
    uv run ruff check .
    uv run pytest
    uv run python scripts/privacy_scan.py

See CONTRIBUTING.md and AGENTS.md for project rules. This project is experimental and community maintained.

This is an experimental test project entirely managed by AI.
