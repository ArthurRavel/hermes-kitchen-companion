"""Command-line interface for Discord setup and local kitchen data."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import warnings
from pathlib import Path

from . import __version__
from .bootstrap import BootstrapConfig, bootstrap, save_state
from .data import add_recipe, add_shopping_item, list_shopping_items, search_recipes
from .discord_api import DiscordClient, DiscordError, UrllibTransport


def _default_state() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "hermes-kitchen-companion" / "discord-state.json"


def _default_data() -> Path:
    return Path(
        os.environ.get(
            "KITCHEN_COMPANION_DATA", Path.home() / ".local" / "share" / "hermes-kitchen-companion"
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kitchen-companion", description="Self-hosted kitchen profile tools"
    )
    parser.add_argument("--version", action="version", version=f"kitchen-companion {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    discord = commands.add_parser("discord", help="Set up the managed Discord channels")
    discord_commands = discord.add_subparsers(dest="discord_command", required=True)
    setup = discord_commands.add_parser("setup", help="Create missing channels in a server")
    setup.add_argument("--guild-id", required=True, help="Discord server ID")
    setup.add_argument("--category", default="🍳 Chez Dobby", help="Managed category name")
    setup.add_argument("--language", choices=("en", "fr"), default="fr")
    setup.add_argument("--state-file", type=Path, default=_default_state())
    setup.add_argument(
        "--dry-run", action="store_true", help="Show intended resources without any API request"
    )
    setup.add_argument(
        "--sync-order", action="store_true", help="Set managed category and channel positions"
    )
    recipe = commands.add_parser("recipe", help="Search and save local recipes")
    recipe_commands = recipe.add_subparsers(dest="recipe_command", required=True)
    search = recipe_commands.add_parser("search")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--data-dir", type=Path, default=_default_data())
    add = recipe_commands.add_parser(
        "add", help="Save only a recipe the user explicitly asked to keep"
    )
    add.add_argument("title")
    add.add_argument("body", help="Recipe ingredients and method")
    add.add_argument("--data-dir", type=Path, default=_default_data())
    shopping = commands.add_parser("shopping", help="Manage the local shared shopping list")
    shopping_commands = shopping.add_subparsers(dest="shopping_command", required=True)
    shopping_list = shopping_commands.add_parser("list")
    shopping_list.add_argument("--data-dir", type=Path, default=_default_data())
    shopping_add = shopping_commands.add_parser("add")
    shopping_add.add_argument("item")
    shopping_add.add_argument("--data-dir", type=Path, default=_default_data())
    return parser


def _read_token() -> str:
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if token:
        if not token.strip():
            raise ValueError("The process environment contains an empty credential.")
        return token.strip()
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise ValueError(
            "No interactive terminal is available. Provide the credential through "
            "the process environment."
        )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            token = getpass.getpass("Discord bot token (hidden): ", stream=sys.stderr)
    except (getpass.GetPassWarning, EOFError):
        raise ValueError(
            "Could not read the credential without echo; use the process environment."
        ) from None
    if not token.strip():
        raise ValueError("A bot credential is required for Discord setup.")
    return token.strip()


def _emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "discord":
            if args.dry_run:
                client = DiscordClient(token="", transport=UrllibTransport())
            else:
                token = _read_token()
                client = DiscordClient(token=token, transport=UrllibTransport())
            config = BootstrapConfig(
                guild_id=args.guild_id,
                category_name=args.category,
                language=args.language,
                sync_order=args.sync_order,
            )
            summary = bootstrap(client, config, dry_run=args.dry_run)
            if not args.dry_run:
                save_state(args.state_file, summary)
                summary["state_file"] = str(args.state_file)
                summary["next_steps"] = (
                    "Install the Hermes profile and configure its local data directory."
                )
            _emit(summary)
            return 0
        if args.command == "recipe":
            if args.recipe_command == "add":
                _emit(add_recipe(args.data_dir, args.title, args.body))
            else:
                _emit(search_recipes(args.data_dir, args.query))
            return 0
        if args.shopping_command == "add":
            _emit(add_shopping_item(args.data_dir, args.item))
        else:
            _emit(list_shopping_items(args.data_dir))
        return 0
    except (DiscordError, ValueError, OSError) as exc:
        # API errors are deliberately credential-free; do not echo arbitrary response bodies.
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
