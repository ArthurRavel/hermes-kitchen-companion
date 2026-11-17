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


def test_scan_detects_credentials_split_across_lines_without_returning_secret(
    tmp_path: Path,
) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    credential = "secret-value-123456789"
    (tmp_path / "candidate.py").write_text(f'api_key =\n    "{credential}"\n')

    findings = violations(tmp_path)

    assert findings == [("candidate.py:1", "credential-assignment")]
    assert all(
        credential not in location and credential not in label for location, label in findings
    )


def test_scan_detects_private_channel_and_server_ids_in_common_formats(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "candidate.yaml").write_text(
        'channel_id:\n  "123456789012345678"\nserverId = 234567890123456789\n'
    )

    findings = violations(tmp_path)

    assert findings == [
        ("candidate.yaml:1", "private-reference-marker"),
        ("candidate.yaml:3", "private-reference-marker"),
    ]


def test_scan_allows_placeholders_and_fake_dry_run_ids_in_documentation(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text(
        'api_key: "YOUR_API_KEY_HERE"\n'
        'guild_id: "<SERVER_ID>"\n'
        "kitchen-companion discord setup --guild-id 100000000000000002 --dry-run\n"
    )

    assert violations(tmp_path) == []
