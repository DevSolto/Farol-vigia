"""Normalização de URLs relativas em absolutas."""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urljoin, urlsplit, urlunsplit

from farol_core.domain.contracts import UrlNormalizer


class SimpleUrlNormalizer(UrlNormalizer):
    """Normaliza URLs relativas usando ``urllib.parse.urljoin``."""

    def __init__(self, *, default_base_url: str | None = None) -> None:
        self._default_base = self._normalize_default_base(default_base_url)

    def to_absolute(self, url: str, base_url: str | None = None) -> str:
        candidate = (url or "").strip()
        if not candidate:
            raise ValueError("URL não pode ser vazia para normalização")

        base_candidate = (base_url or "").strip()
        if base_candidate:
            return urljoin(base_candidate, candidate)
        if self._default_base:
            return urljoin(self._default_base, candidate)
        return candidate

    def _normalize_default_base(self, value: str | None) -> str | None:
        if not value:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        parts = urlsplit(cleaned)
        if parts.scheme and parts.netloc:
            return urlunsplit((parts.scheme, parts.netloc, "/", "", ""))
        return cleaned


def build_url_normalizer(options: Mapping[str, object] | None = None) -> SimpleUrlNormalizer:
    """Factory auxiliar compatível com configurações JSON."""

    options = options or {}
    default_base = options.get("default_base_url")
    return SimpleUrlNormalizer(default_base_url=str(default_base) if default_base else None)
