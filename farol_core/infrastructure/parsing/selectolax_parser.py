"""Parser baseado em selectolax para converter HTML em ``RawArticle``."""

from __future__ import annotations

from typing import Mapping

from farol_core.domain.contracts import Parser, RawArticle, RawListingItem
from farol_core.domain.errors import ParseError

try:  # pragma: no cover - dependência opcional em tempo de execução
    from selectolax.parser import HTMLParser
except Exception:  # noqa: BLE001 - degradar para import tardio
    HTMLParser = None  # type: ignore


class SelectolaxParser(Parser):
    """Extrai dados de HTML usando seletores CSS."""

    def __init__(
        self,
        selectors: Mapping[str, str],
        *,
        required_fields: frozenset[str] | None = None,
    ) -> None:
        if HTMLParser is None:
            raise ImportError("selectolax não está disponível")
        self._selectors = dict(selectors)
        self._required = required_fields or frozenset({"title", "body"})

    def parse(self, item: RawListingItem) -> RawArticle:
        try:
            parser = HTMLParser(item.content)
        except Exception as exc:  # noqa: BLE001
            raise ParseError("Não foi possível inicializar o parser HTML", cause=exc) from exc

        extracted: dict[str, str | None] = {}
        for field, selector in self._selectors.items():
            node = parser.css_first(selector)
            extracted[field] = node.text(separator=" ").strip() if node else None

        missing = [field for field in self._required if not extracted.get(field)]
        if missing:
            raise ParseError(f"Campos obrigatórios ausentes no parsing: {', '.join(missing)}")

        metadata = dict(item.metadata)
        metadata.update({k: v for k, v in extracted.items() if k not in {"title", "body"}})

        return RawArticle(
            url=item.url,
            title=extracted.get("title"),
            body=extracted.get("body") or "",
            metadata=metadata,
        )
