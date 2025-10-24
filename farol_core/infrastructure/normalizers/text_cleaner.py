"""Rotinas utilitárias para higienizar HTML e extrair texto limpo."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from farol_core.domain.contracts import TextCleaner
from farol_core.infrastructure.parsing.html_tree import HTMLDocument

_RE_WHITESPACE = re.compile(r"\s+")


class SoupTextCleaner(TextCleaner):
    """Limpa HTML utilizando um parser leve baseado em ``html.parser``."""

    def __init__(self, *, allowed_tags: Iterable[str] | None = None) -> None:
        self._allowed_tags = tuple(allowed_tags or ("p", "br", "strong", "em", "ul", "ol", "li", "a", "blockquote"))

    def clean_html_to_text(self, html: str) -> str:
        soup = HTMLDocument.from_html(html or "")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.root.get_text(" ", strip=True)
        text = _RE_WHITESPACE.sub(" ", text).strip()
        return re.sub(r"\s+([!?.,;:])", r"\1", text)

    def sanitize_html(self, html: str) -> str:
        soup = HTMLDocument.from_html(html or "")
        for tag in soup.find_all(True):
            if tag.name not in self._allowed_tags:
                tag.unwrap()
                continue
            if tag.name == "a":
                href = tag.get("href")
                if href and href.lower().startswith("javascript:"):
                    del tag["href"]
            # remove atributos potencialmente perigosos
            for attribute in list(tag.attrs):
                if attribute not in {"href", "title"}:
                    del tag[attribute]
        for dangerous in soup(["script", "style"]):
            dangerous.decompose()
        sanitized = str(soup)
        return sanitized.strip()


def build_text_cleaner(options: Mapping[str, object] | None = None) -> SoupTextCleaner:
    """Factory compatível com opções em configurações JSON."""

    options = options or {}
    allowed = options.get("allowed_tags")
    if isinstance(allowed, Iterable) and not isinstance(allowed, (str, bytes)):
        allowed_tags = tuple(str(tag) for tag in allowed)
    else:
        allowed_tags = None
    return SoupTextCleaner(allowed_tags=allowed_tags)
