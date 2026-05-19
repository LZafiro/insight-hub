"""JWT creation & validation."""

import pytest

from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_access_token_roundtrip() -> None:
    token = create_access_token(subject="user-123", workspace_id="ws-1")
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "user-123"
    assert payload["wid"] == "ws-1"
    assert payload["type"] == "access"
    assert "jti" in payload


def test_refresh_token_roundtrip() -> None:
    token = create_refresh_token(subject="user-123")
    payload = decode_token(token, expected_type="refresh")
    assert payload["sub"] == "user-123"
    assert payload["type"] == "refresh"


def test_rejects_wrong_token_type() -> None:
    access = create_access_token(subject="user-123")
    with pytest.raises(TokenError, match="Expected refresh"):
        decode_token(access, expected_type="refresh")


def test_rejects_garbage_token() -> None:
    with pytest.raises(TokenError):
        decode_token("not.a.jwt", expected_type="access")


def test_password_hashing_roundtrip() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)
