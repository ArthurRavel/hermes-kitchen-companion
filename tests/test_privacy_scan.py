from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.privacy_scan import violations


def test_scan_rejects_private_home_path_and_common_token_shape(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    candidate = tmp_path / "candidate.txt"
    fake_token = "ghp_" + "a" * 36
    private_path = "/" + "home/" + "example-user/private-data"
    candidate.write_text(f"{private_path}\n{fake_token}\n")
    subprocess.run(["git", "add", "candidate.txt"], cwd=tmp_path, check=True)

    findings = violations(tmp_path)

    assert {kind for _, kind in findings} == {"home-path", "github-token"}
    assert all(fake_token not in location for location, _ in findings)
