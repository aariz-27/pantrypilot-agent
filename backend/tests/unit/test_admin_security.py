from __future__ import annotations

from app.admin.security import (
    build_session_cookie_value,
    constant_time_username_equals,
    hash_password,
    parse_session_cookie_value,
    verify_password,
)


def test_hash_password_roundtrip_verifies():
    encoded = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", encoded) is True


def test_hash_password_rejects_wrong_password():
    encoded = hash_password("correct horse battery staple")
    assert verify_password("wrong password", encoded) is False


def test_hash_password_never_stores_plaintext():
    encoded = hash_password("my-secret-password")
    assert "my-secret-password" not in encoded


def test_hash_password_produces_different_salts_each_time():
    first = hash_password("same password")
    second = hash_password("same password")
    assert first != second
    assert verify_password("same password", first)
    assert verify_password("same password", second)


def test_verify_password_fails_closed_on_malformed_hash():
    assert verify_password("anything", "not-a-valid-hash") is False
    assert verify_password("anything", "") is False
    assert verify_password("anything", "scrypt$bad$format") is False


def test_verify_password_fails_closed_on_wrong_scheme():
    assert verify_password("anything", "bcrypt$1$2$3$abcd$abcd") is False


def test_constant_time_username_equals():
    assert constant_time_username_equals("founder", "founder") is True
    assert constant_time_username_equals("founder", "Founder") is False
    assert constant_time_username_equals("", "founder") is False


def test_session_cookie_roundtrip():
    cookie_value = build_session_cookie_value("session-abc-123", "my-secret")
    session_id = parse_session_cookie_value(cookie_value, "my-secret")
    assert session_id == "session-abc-123"


def test_session_cookie_rejects_tampered_signature():
    cookie_value = build_session_cookie_value("session-abc-123", "my-secret")
    tampered = cookie_value[:-1] + ("0" if cookie_value[-1] != "0" else "1")
    assert parse_session_cookie_value(tampered, "my-secret") is None


def test_session_cookie_rejects_wrong_secret():
    cookie_value = build_session_cookie_value("session-abc-123", "my-secret")
    assert parse_session_cookie_value(cookie_value, "different-secret") is None


def test_session_cookie_rejects_malformed_values():
    assert parse_session_cookie_value("", "my-secret") is None
    assert parse_session_cookie_value("no-dot-here", "my-secret") is None
    assert parse_session_cookie_value(".", "my-secret") is None
    assert parse_session_cookie_value("id.", "my-secret") is None
    assert parse_session_cookie_value(".sig", "my-secret") is None
