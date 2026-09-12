#!/usr/bin/env python3
"""Offline utility: generate PANTRYPILOT_ADMIN_PASSWORD_HASH.

Usage:
    python scripts/hash_admin_password.py

Prompts for the password interactively (getpass -- never echoed to the
terminal, never taken as a CLI argument where it would land in shell
history/process listings) and prints only the resulting hash string.
The plaintext password is never written to disk, logged, or printed by
this script or by the application at any point.
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.admin.security import hash_password  # noqa: E402


def main() -> int:
    password = getpass.getpass("Admin password: ")
    if not password:
        print("Password must not be empty.", file=sys.stderr)
        return 1
    confirm = getpass.getpass("Confirm admin password: ")
    if password != confirm:
        print("Passwords did not match.", file=sys.stderr)
        return 1

    print(hash_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
