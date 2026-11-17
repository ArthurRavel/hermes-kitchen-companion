"""Portable JSON-backed recipe notebook and shared shopping list helpers."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Could not read local data file {path}: {exc.__class__.__name__}."
        ) from None


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as temporary:
        temporary.write(payload)
        temporary_path = Path(temporary.name)
    try:
        temporary_path.chmod(0o600)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def add_recipe(directory: Path, title: str, body: str) -> dict[str, str]:
    title = title.strip()
    body = body.strip()
    if not title or not body:
        raise ValueError("Recipe title and instructions must not be empty.")
    path = directory / "recipes.json"
    recipes = _read(path, [])
    if not isinstance(recipes, list) or any(
        not isinstance(row, dict)
        or not isinstance(row.get("title"), str)
        or not isinstance(row.get("body"), str)
        for row in recipes
    ):
        raise ValueError("Recipe notebook must contain objects with text titles and bodies.")
    recipe = {"id": datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"), "title": title, "body": body}
    recipes.append(recipe)
    _write(path, recipes)
    return recipe


def search_recipes(directory: Path, query: str) -> list[dict[str, str]]:
    recipes = _read(directory / "recipes.json", [])
    if not isinstance(recipes, list) or any(
        not isinstance(row, dict)
        or not isinstance(row.get("title"), str)
        or not isinstance(row.get("body"), str)
        for row in recipes
    ):
        raise ValueError("Recipe notebook must contain objects with text titles and bodies.")
    needle = query.strip().casefold()
    if not needle:
        return recipes
    return [
        row
        for row in recipes
        if needle in (row.get("title", "") + " " + row.get("body", "")).casefold()
    ]


def add_shopping_item(directory: Path, item: str) -> list[str]:
    item = re.sub(r"\s+", " ", item).strip()
    if not item:
        raise ValueError("Shopping item must not be empty.")
    path = directory / "shopping.json"
    items = _read(path, [])
    if not isinstance(items, list) or not all(isinstance(value, str) for value in items):
        raise ValueError("Shopping list must contain a JSON list of text items.")
    if item.casefold() not in {value.casefold() for value in items}:
        items.append(item)
        _write(path, items)
    return items


def list_shopping_items(directory: Path) -> list[str]:
    items = _read(directory / "shopping.json", [])
    if not isinstance(items, list) or not all(isinstance(value, str) for value in items):
        raise ValueError("Shopping list must contain a JSON list of text items.")
    return items
