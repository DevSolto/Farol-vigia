"""Implementação concreta de ``Clock`` baseada no relógio do sistema."""

from __future__ import annotations

from datetime import UTC, datetime

from farol_core.domain.contracts import Clock


class SystemClock(Clock):
    """Retorna instantes no fuso UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)
