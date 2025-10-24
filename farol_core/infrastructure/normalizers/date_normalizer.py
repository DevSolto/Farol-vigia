"""Conversão de datas textuais em ``datetime``."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta

from farol_core.domain.contracts import DateNormalizer

_SUPPORTED_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
)


class FlexibleDateNormalizer(DateNormalizer):
    """Interpreta formatos comuns e expressões relativas simples."""

    def __init__(self, *, fallback_to_reference: bool = True) -> None:
        self._fallback_to_reference = fallback_to_reference

    def parse(self, value: str, reference: datetime | None = None) -> datetime | None:
        text = (value or "").strip()
        if not text:
            return None

        text = text.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            pass

        for pattern in _SUPPORTED_FORMATS:
            try:
                return datetime.strptime(text, pattern)
            except ValueError:
                continue

        lower = text.lower()
        if reference and self._fallback_to_reference:
            if lower in {"hoje", "today"}:
                return reference.replace(hour=0, minute=0, second=0, microsecond=0)
            if lower in {"ontem", "yesterday"}:
                day = reference - timedelta(days=1)
                return day.replace(hour=0, minute=0, second=0, microsecond=0)

        return None


def build_date_normalizer(options: Mapping[str, object] | None = None) -> FlexibleDateNormalizer:
    """Factory amigável para configuração externa."""

    options = options or {}
    fallback = options.get("fallback_to_reference", True)
    return FlexibleDateNormalizer(fallback_to_reference=bool(fallback))
