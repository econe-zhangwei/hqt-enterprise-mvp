from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

_SMS_CODES: dict[str, str] = {}
_TOKEN_STORE: dict[str, dict] = {}
_TOKEN_TTL_HOURS = 24

# 开发默认账户，后续可迁移到数据库/统一认证
_DEFAULT_USERS = {
    "admin": "123456",
    "enterprise": "123456",
}


def _issue_token(subject: str, login_type: str) -> dict:
    token = secrets.token_urlsafe(24)
    expires_at = datetime.now(UTC) + timedelta(hours=_TOKEN_TTL_HOURS)
    _TOKEN_STORE[token] = {
        "subject": subject,
        "login_type": login_type,
        "expires_at": expires_at,
    }
    return {
        "token": token,
        "token_type": "bearer",
        "expires_at": expires_at.isoformat(),
        "subject": subject,
        "login_type": login_type,
    }


def send_code(mobile: str) -> dict:
    # MVP: 固定验证码，真实通道后续替换
    code = "000000"
    _SMS_CODES[mobile] = code
    return {"request_id": f"mock-{mobile[-4:]}", "mock_code": code}


def login_with_code(mobile: str, code: str) -> dict:
    if _SMS_CODES.get(mobile) != code:
        raise ValueError("invalid code")
    return _issue_token(subject=mobile, login_type="sms")


def login_with_password(username: str, password: str) -> dict:
    expected = _DEFAULT_USERS.get(username)
    if not expected or expected != password:
        raise ValueError("invalid username or password")
    return _issue_token(subject=username, login_type="password")


def verify_authorization_header(authorization: str | None) -> dict | None:
    if not authorization:
        return None
    if not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    data = _TOKEN_STORE.get(token)
    if not data:
        return None
    if data["expires_at"] < datetime.now(UTC):
        _TOKEN_STORE.pop(token, None)
        return None
    return data
