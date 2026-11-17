#!/usr/bin/env python3
"""Scan tracked and unignored candidate files for private paths and common credentials."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

FINGERPRINT_FILE = Path(__file__).with_name("private_fingerprints.json")
PRIVATE_FINGERPRINTS = set(json.loads(FINGERPRINT_FILE.read_text(encoding="utf-8")))
IDENTIFIER = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]{3,}|\d{15,20}")
HANDLE = re.compile(r"(?<!\w)@?([A-Za-z][A-Za-z0-9_]{2,})(?!\w)")
PLACEHOLDER = re.compile(
    r"(?i)^(?:your[_ -].*|<[^>]+>|placeholder|example|replace[_ -]?me|changeme)$"
)
DISCORD_ID_CONTEXT = re.compile(
    r"(?i)\b(?:guild|server|channel|forum|category)"
    r"(?:[_ -]?(?:snowflake|id))?\s*[:=]\s*[\"']?(\d{17,20})"
)
PATTERNS = {
    "home-path": re.compile(r"(?i)(?:/home/|/users/)[a-z0-9._-]+"),
    "discord-token": re.compile(
        r"(?i)(?:mfa\.[A-Za-z0-9_-]{20,}|[A-Za-z0-9_-]{23,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{20,})"
    ),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    "credential-assignment": re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|password|passwd)\s*[:=]\s*[\x22\x27]([A-Za-z0-9/+=._-]{12,})[\x22\x27]"
    ),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    "provider-key": re.compile(r"\b(?:AIza[0-9A-Za-z_-]{30,}|sk_(?:live|test)_[0-9A-Za-z]{20,})\b"),
    "personal-email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "private-reference-marker": re.compile(r"(?i)discord\.com/api/webhooks/"),
}


def candidate_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
    )
    return [
        root / name.decode("utf-8", errors="surrogateescape")
        for name in result.stdout.split(b"\0")
        if name and (root / name.decode("utf-8", errors="surrogateescape")).is_file()
    ]


def _location(root: Path, path: Path, content: str, offset: int) -> str:
    line_number = content.count("\n", 0, offset) + 1
    return f"{path.relative_to(root)}:{line_number}"


def violations(root: Path) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in candidate_files(root):
        try:
            content = path.read_bytes().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(content):
                if label == "credential-assignment" and PLACEHOLDER.fullmatch(match.group(1)):
                    continue
                found.append((_location(root, path, content, match.start()), label))
        for match in DISCORD_ID_CONTEXT.finditer(content):
            if PLACEHOLDER.fullmatch(match.group(1)):
                continue
            found.append(
                (_location(root, path, content, match.start()), "private-reference-marker")
            )

        for line_number, line in enumerate(content.splitlines(), start=1):
            location = f"{path.relative_to(root)}:{line_number}"
            identifiers = set(IDENTIFIER.findall(line)) | set(HANDLE.findall(line))
            for identifier in identifiers:
                digest = hashlib.sha256(identifier.casefold().encode("utf-8")).hexdigest()
                if digest in PRIVATE_FINGERPRINTS:
                    found.append((location, "private-reference-fingerprint"))
                    break
    return found


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    files = candidate_files(root)
    problems = violations(root)
    if problems:
        for location, label in problems:
            print(f"privacy scan: {location}: matched {label}; content withheld", file=sys.stderr)
        return 1
    print(f"privacy scan: clean ({len(files)} candidate files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
