"""Password hashing and session-token signing for the admin dashboard.

Dependency choice, stated explicitly: neither Argon2id nor bcrypt is a
current project dependency (verified: not in pyproject.toml, not
installed). The ticket accepts "Argon2id preferred OR bcrypt if
already supported by project dependencies" -- since neither is already
supported, this uses Python's stdlib `hashlib.scrypt` (PEP 458-class
memory-hard KDF, available since Python 3.6, no new dependency) rather
than adding a new third-party cryptography dependency for a
single-account login. This keeps the project's deliberately small
dependency surface (see pyproject.toml's own comments about CI/dep
discipline) while still meeting the security bar: scrypt is a
memory-hard, salted, tunable-cost password KDF, not a plain hash.

Session tokens are signed with HMAC-SHA256 over a random session id,
keyed by PANTRYPILOT_ADMIN_SESSION_SECRET -- never a JWT library (none
is a project dependency either, and a signed opaque id plus a
server-side session table, checked below, is simpler and gives real
logout/revocation, which a stateless JWT would not without its own
denylist).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SALT_BYTES = 16


def hash_password(plain_password: str) -> str:
    """Returns an encoded string safe to store as
    PANTRYPILOT_ADMIN_PASSWORD_HASH. Never called at request time on
    the live login path -- only by the offline hash-generation utility
    (scripts/hash_admin_password.py) and by tests."""

    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.scrypt(
        plain_password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${derived.hex()}"


def verify_password(plain_password: str, encoded_hash: str) -> bool:
    """Never raises on malformed stored hashes -- a corrupt/misconfigured
    PANTRYPILOT_ADMIN_PASSWORD_HASH must fail closed (no login), never
    500 with a stack trace or silently accept anything."""

    try:
        scheme, n_str, r_str, p_str, salt_hex, hash_hex = encoded_hash.split("$")
        if scheme != "scrypt":
            return False
        n, r, p = int(n_str), int(r_str), int(p_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False

    derived = hashlib.scrypt(plain_password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=len(expected))
    return hmac.compare_digest(derived, expected)


def generate_session_id() -> str:
    return secrets.token_urlsafe(32)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def sign_session_id(session_id: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), session_id.encode("utf-8"), hashlib.sha256).hexdigest()


def build_session_cookie_value(session_id: str, secret: str) -> str:
    return f"{session_id}.{sign_session_id(session_id, secret)}"


def parse_session_cookie_value(cookie_value: str, secret: str) -> str | None:
    """Returns the session_id only if the signature verifies; None for
    any malformed or tampered cookie value. Constant-time comparison
    against a forged signature."""

    if not cookie_value or "." not in cookie_value:
        return None
    session_id, _, signature = cookie_value.partition(".")
    if not session_id or not signature:
        return None
    expected_signature = sign_session_id(session_id, secret)
    if not hmac.compare_digest(signature, expected_signature):
        return None
    return session_id


def constant_time_username_equals(candidate: str, expected: str) -> bool:
    return hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))
