"""Secret handling: never let an API key reach logs, reports or model context."""

from __future__ import annotations

import re
from typing import Iterable

_PATTERNS = [
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)[\"']?[A-Za-z0-9._\-]{6,}"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{6,}\b"),
]
_MASK = "***REDACTED***"


class SecretRedactor:
    """Replaces registered secrets and common key shapes in arbitrary text."""

    def __init__(self, extra_secrets: Iterable[str] = ()) -> None:
        self._secrets: set[str] = set()
        for secret in extra_secrets:
            self.add(secret)

    def add(self, secret: str | None) -> None:
        if secret and len(secret) >= 6:
            self._secrets.add(secret)

    def redact(self, text: object) -> str:
        if text is None:
            return ""
        value = str(text)
        for secret in sorted(self._secrets, key=len, reverse=True):
            value = value.replace(secret, _MASK)
        for pattern in _PATTERNS:
            value = pattern.sub(lambda m: (m.group(1) if m.lastindex else "") + _MASK, value)
        return value

    def scrub_mapping(self, data: dict) -> dict:
        clean: dict = {}
        for key, value in data.items():
            lowered = str(key).lower()
            if any(token in lowered for token in ("api_key", "apikey", "authorization", "token", "secret")):
                clean[key] = _MASK if value else ""
            elif isinstance(value, dict):
                clean[key] = self.scrub_mapping(value)
            elif isinstance(value, list):
                clean[key] = [self.scrub_mapping(v) if isinstance(v, dict) else self.redact(v) for v in value]
            else:
                clean[key] = self.redact(value)
        return clean


def mask_key(key: str) -> str:
    """Display form for the GUI: sk-ab...wxyz."""

    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:5]}...{key[-4:]}"
