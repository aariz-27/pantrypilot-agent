"""Module F 4.10/4.5: lightweight secret-pattern scan for tracked files.

Scans every git-tracked file (respects .gitignore automatically via
`git ls-files`) for high-confidence secret patterns: cloud provider
key formats, common "key/token/secret = <long-opaque-value>" literal
assignments, and PEM private-key headers. This is a pattern scanner,
not a full entropy/history scanner (e.g. gitleaks/trufflehog) -- it
intentionally stays dependency-free and fast enough to run on every
CI push, matching this repo's existing plain-script convention
(scripts/validate_governance.py).

A line can be explicitly allow-listed with a trailing
`# secret-scan: allow` comment, for a documented, reviewed false
positive (e.g. a placeholder in .env.example) -- use sparingly, never
to hide a real credential.

Exit code 0 = no findings. Exit code 1 = at least one finding
(prints file:line and the matched pattern name, never the secret
value itself).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ALLOW_MARKER = "secret-scan: allow"

# (pattern name, compiled regex). Regexes match the *shape* of a real
# secret, not just the word "key"/"secret" -- so ".env.example"
# placeholders like "your-anthropic-api-key-here" or "changeme" do not
# match (they are not the value shape of a real key).
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key_id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("anthropic_api_key", re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}")),
    ("generic_sk_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("pem_private_key", re.compile(r"-----BEGIN (RSA|EC|DSA|OPENSSH|PRIVATE) KEY-----")),
    (
        "assigned_opaque_secret",
        re.compile(
            r"(?i)\b(api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*"
            r"['\"][A-Za-z0-9_\-/+]{20,}['\"]"
        ),
    ),
]

# Extensions unlikely to contain a real secret literal and prone to
# binary/false-positive noise; text-based config/code files are the
# actual target.
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2",
    ".ttf", ".eot", ".pdf", ".lock", ".db", ".sqlite", ".sqlite3",
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    )
    return [Path(p) for p in result.stdout.splitlines() if p]


def scan_file(path: Path) -> list[str]:
    findings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except (UnicodeDecodeError, OSError):
        return findings

    for lineno, line in enumerate(text.splitlines(), start=1):
        if ALLOW_MARKER in line:
            continue
        for name, pattern in PATTERNS:
            if pattern.search(line):
                findings.append(f"{path}:{lineno}: possible {name}")
    return findings


def main() -> int:
    all_findings: list[str] = []
    for path in tracked_files():
        if path.suffix.lower() in SKIP_SUFFIXES or not path.exists():
            continue
        all_findings.extend(scan_file(path))

    if all_findings:
        print("Secret-pattern scan found possible secrets:")
        for finding in all_findings:
            print(f"  {finding}")
        print(
            "\nIf a finding is a reviewed false positive (e.g. a placeholder), "
            f"add a trailing comment containing '{ALLOW_MARKER}' on that line."
        )
        return 1

    print("Secret-pattern scan: no findings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
