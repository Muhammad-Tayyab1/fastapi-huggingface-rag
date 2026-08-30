import pytest

from app.core.security import (
    api_key_lookup_prefix,
    api_key_matches,
    create_api_key,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_api_keys_are_random_and_hash_verifiable() -> None:
    raw_key, prefix, key_hash = create_api_key()

    assert raw_key.startswith(f"rag_{prefix}.")
    assert api_key_lookup_prefix(raw_key) == prefix
    assert api_key_matches(raw_key, key_hash)
    assert not api_key_matches(f"{raw_key}changed", key_hash)


def test_password_hash_round_trip() -> None:
    hashed = hash_password("very-secure-password")
    assert verify_password("very-secure-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_token_type_is_enforced() -> None:
    access_token = create_token("user-id", "access")
    assert decode_token(access_token, "access")["sub"] == "user-id"
    with pytest.raises(ValueError):
        decode_token(access_token, "refresh")
