# SPDX-License-Identifier: LGPL-2.1-or-later

"""Authentication state helpers for VibeCAD.

This module does not validate credentials or make network calls at import time.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
from typing import Any
from urllib import error, request


KEYRING_SERVICE = "FreeCAD VibeCAD"
KEYRING_USERNAME = "openai-api-key"


class AuthStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    CONFIGURED_UNVERIFIED = "configured_unverified"
    VERIFIED = "verified"
    INVALID = "invalid"
    OFFLINE = "offline"


@dataclass(frozen=True)
class AuthState:
    status: AuthStatus
    source: str | None = None
    redacted_key: str | None = None
    message: str = ""

    @property
    def can_call_provider(self) -> bool:
        return self.status in {AuthStatus.CONFIGURED_UNVERIFIED, AuthStatus.VERIFIED}


@dataclass(frozen=True)
class AuthCredential:
    value: str
    source: str


def redact_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "***"
    return f"{value[:3]}...{value[-4:]}"


def read_dotenv_key(path: Path) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() != "OPENAI_API_KEY":
            continue
        value = value.strip().strip('"').strip("'")
        return value or None
    return None


def _keyring_module() -> Any | None:
    try:
        import keyring

        return keyring
    except Exception:
        return None


def keyring_available() -> bool:
    return _keyring_module() is not None


def read_keyring_key() -> str | None:
    keyring = _keyring_module()
    if keyring is None:
        return None
    try:
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME) or None
    except Exception:
        return None


def store_keyring_key(value: str) -> dict[str, str | bool | None]:
    clean = value.strip()
    if not clean:
        return {"stored": False, "error": "API key cannot be empty.", "redacted_key": None}
    keyring = _keyring_module()
    if keyring is None:
        return {
            "stored": False,
            "error": "No OS keyring backend is available.",
            "redacted_key": None,
        }
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, clean)
        return {"stored": True, "error": None, "redacted_key": redact_secret(clean)}
    except Exception as exc:
        return {"stored": False, "error": str(exc), "redacted_key": None}


def delete_keyring_key() -> dict[str, str | bool]:
    keyring = _keyring_module()
    if keyring is None:
        return {"deleted": False, "error": "No OS keyring backend is available."}
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
        return {"deleted": True, "error": ""}
    except Exception as exc:
        return {"deleted": False, "error": str(exc)}


def resolve_auth_credential(
    env: dict[str, str] | None = None,
    dotenv_path: Path | None = None,
) -> AuthCredential | None:
    data = env if env is not None else os.environ
    value = data.get("OPENAI_API_KEY")
    if value:
        return AuthCredential(value=value, source="environment")

    value = read_keyring_key()
    if value:
        return AuthCredential(value=value, source="OS keyring")

    if dotenv_path is not None:
        value = read_dotenv_key(dotenv_path)
        if value:
            return AuthCredential(value=value, source=str(dotenv_path))

    return None


def resolve_auth_state(env: dict[str, str] | None = None, dotenv_path: Path | None = None) -> AuthState:
    credential = resolve_auth_credential(env=env, dotenv_path=dotenv_path)
    if credential is not None:
        return AuthState(
            AuthStatus.CONFIGURED_UNVERIFIED,
            source=credential.source,
            redacted_key=redact_secret(credential.value),
            message=f"OpenAI API key found in {credential.source}.",
        )

    return AuthState(
        AuthStatus.NOT_CONFIGURED,
        message="No OpenAI API key is configured.",
    )


def validate_openai_api_key(
    api_key: str | None,
    *,
    source: str | None = None,
    timeout_seconds: float = 10.0,
    opener: Any | None = None,
) -> AuthState:
    clean = (api_key or "").strip()
    if not clean:
        return AuthState(
            AuthStatus.NOT_CONFIGURED,
            source=source,
            message="No OpenAI API key is configured.",
        )

    http_request = request.Request(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {clean}"},
        method="GET",
    )
    redacted = redact_secret(clean)
    try:
        open_call = opener or request.urlopen
        response = open_call(http_request, timeout=timeout_seconds)
        try:
            status_code = getattr(response, "status", None)
            if status_code is None and hasattr(response, "getcode"):
                status_code = response.getcode()
            if hasattr(response, "read"):
                response.read(512)
        finally:
            if hasattr(response, "close"):
                response.close()
        if status_code is None or 200 <= int(status_code) < 300:
            return AuthState(
                AuthStatus.VERIFIED,
                source=source,
                redacted_key=redacted,
                message="OpenAI API key validated.",
            )
        return AuthState(
            AuthStatus.INVALID,
            source=source,
            redacted_key=redacted,
            message=f"OpenAI credential validation failed with HTTP {status_code}.",
        )
    except error.HTTPError as exc:
        status = AuthStatus.INVALID if exc.code in {401, 403} else AuthStatus.OFFLINE
        return AuthState(
            status,
            source=source,
            redacted_key=redacted,
            message=f"OpenAI credential validation failed with HTTP {exc.code}.",
        )
    except Exception as exc:
        return AuthState(
            AuthStatus.OFFLINE,
            source=source,
            redacted_key=redacted,
            message=f"OpenAI credential validation could not reach the API: {exc}",
        )


def validate_configured_openai_auth(
    *,
    env: dict[str, str] | None = None,
    dotenv_path: Path | None = None,
    timeout_seconds: float = 10.0,
    opener: Any | None = None,
) -> AuthState:
    credential = resolve_auth_credential(env=env, dotenv_path=dotenv_path)
    if credential is None:
        return AuthState(
            AuthStatus.NOT_CONFIGURED,
            message="No OpenAI API key is configured.",
        )
    return validate_openai_api_key(
        credential.value,
        source=credential.source,
        timeout_seconds=timeout_seconds,
        opener=opener,
    )
