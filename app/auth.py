from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import Settings


@dataclass(frozen=True)
class AdminSession:
    username: str


def _get_serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key=secret_key, salt="admin-session")


def verify_credentials(username: str, password: str, settings: Settings) -> bool:
    return hmac.compare_digest(username, settings.admin_username) and hmac.compare_digest(
        password, settings.admin_password
    )


def create_session_token(username: str, settings: Settings) -> str:
    serializer = _get_serializer(settings.secret_key)
    return serializer.dumps({"u": username})


def read_session_token(token: str, settings: Settings) -> Optional[AdminSession]:
    serializer = _get_serializer(settings.secret_key)
    try:
        data = serializer.loads(token, max_age=settings.session_ttl_seconds)
    except (BadSignature, SignatureExpired):
        return None
    username = data.get("u")
    if not username:
        return None
    return AdminSession(username=username)
