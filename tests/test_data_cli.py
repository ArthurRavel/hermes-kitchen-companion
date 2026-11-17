from __future__ import annotations

import json
from pathlib import Path

import pytest

from kitchen_companion.data import (
    add_recipe,
    add_shopping_item,
    list_shopping_items,
    search_recipes,
)


def test_recipe_requires_explicit_add_and_searches_case_insensitively(tmp_path: Path) -> None:
    assert search_recipes(tmp_path, "lentil") == []
    add_recipe(tmp_path, "Lentil soup", "Red lentils and cumin")
    assert search_recipes(tmp_path, "CUMIN")[0]["title"] == "Lentil soup"
    assert (tmp_path / "recipes.json").exists()


def test_recipe_rejects_empty_fields(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        add_recipe(tmp_path, " ", "method")


def test_shopping_list_deduplicates_case_insensitively(tmp_path: Path) -> None:
    add_shopping_item(tmp_path, "Carrots")
    add_shopping_item(tmp_path, " carrots ")
    assert list_shopping_items(tmp_path) == ["Carrots"]


def test_corrupt_local_data_has_safe_actionable_error(tmp_path: Path) -> None:
    (tmp_path / "shopping.json").write_text("not-json")
    with pytest.raises(ValueError, match="Could not read local data"):
        list_shopping_items(tmp_path)


def test_cli_offline_dry_run_emits_plan_without_prompt(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from kitchen_companion import cli

    monkeypatch.setattr(cli.getpass, "getpass", lambda *_: pytest.fail("should not prompt"))
    assert cli.main(["discord", "setup", "--guild-id", str(10**17 + 2), "--dry-run"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["dry_run"] is True
    assert len(result["planned"]) == 6


def test_noninteractive_setup_refuses_echoed_credential(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from kitchen_companion import cli

    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.setattr(
        cli.getpass, "getpass", lambda *_args, **_kwargs: pytest.fail("must not prompt")
    )
    assert cli.main(["discord", "setup", "--guild-id", str(10**17 + 4)]) == 2
    assert "environment" in capsys.readouterr().err
