import pytest

from app.core.security import create_token, decode_token, hash_password, verify_password


def test_password_hash_round_trip() -> None:
    hashed = hash_password("very-secure-password")
    assert verify_password("very-secure-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_token_type_is_enforced() -> None:
    access_token = create_token("user-id", "access")
    assert decode_token(access_token, "access")["sub"] == "user-id"
    with pytest.raises(ValueError):
        decode_token(access_token, "refresh")
