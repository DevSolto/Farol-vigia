"""Deduplicação baseada em SHA-256."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, MutableSet

from farol_core.domain.contracts import ArticleInput, Deduper


class Sha256Deduper(Deduper):
    """Gera impressões digitais determinísticas usando SHA-256."""

    def __init__(
        self,
        *,
        fields: Iterable[str] | None = None,
        seen_store: MutableSet[str] | None = None,
        prefix: str = "",
    ) -> None:
        self._fields = tuple(fields or ("url",))
        self._seen = seen_store if seen_store is not None else set()
        self._prefix = prefix

    def fingerprint(self, article: ArticleInput) -> str:
        components: list[str] = [self._prefix]
        for field in self._fields:
            value = getattr(article, field, None)
            if value is None:
                continue
            components.append(self._serialize(value))
        payload = "\u241f".join(components).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def is_new(self, fingerprint: str) -> bool:
        if fingerprint in self._seen:
            return False
        self._seen.add(fingerprint)
        return True

    def _serialize(self, value: object) -> str:
        if isinstance(value, (list, tuple, set)):
            return "\u241e".join(sorted(self._serialize(item) for item in value))
        return str(value)


def build_deduper(options: Mapping[str, object] | None = None) -> Sha256Deduper:
    """Factory compatível com configuração de portais."""

    options = dict(options or {})
    fields_opt = options.get("fields")
    prefix = str(options.get("prefix", ""))
    if isinstance(fields_opt, Iterable) and not isinstance(fields_opt, (str, bytes)):
        fields = tuple(str(field) for field in fields_opt)
    elif isinstance(fields_opt, str):
        fields = tuple(part.strip() for part in fields_opt.split(",") if part.strip())
    else:
        fields = None
    return Sha256Deduper(fields=fields, prefix=prefix)
