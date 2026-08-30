from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
API_KEY_PREFIX = "rag_"


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_context.verify(password, hashed_password)


def create_api_key() -> tuple[str, str, str]:
    lookup_prefix = token_urlsafe(9)
    raw_key = f"{API_KEY_PREFIX}{lookup_prefix}.{token_urlsafe(32)}"
    return raw_key, lookup_prefix, hash_api_key(raw_key)


def hash_api_key(raw_key: str) -> str:
    return sha256(raw_key.encode()).hexdigest()


def api_key_matches(raw_key: str, expected_hash: str) -> bool:
    return compare_digest(hash_api_key(raw_key), expected_hash)


def api_key_lookup_prefix(raw_key: str) -> str | None:
    if not raw_key.startswith(API_KEY_PREFIX) or "." not in raw_key:
        return None
    prefix, _ = raw_key.removeprefix(API_KEY_PREFIX).split(".", 1)
    return prefix or None


def create_token(subject: str, token_type: Literal["access", "refresh"]) -> str:
    now = datetime.now(UTC)
    lifetime = (
        timedelta(minutes=settings.access_token_expire_min)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_expire_days)
    )
    payload = {"sub": subject, "type": token_type, "iat": now, "exp": now + lifetime}
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str, expected_type: Literal["access", "refresh"]) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise ValueError("Invalid token type")
    return payload
