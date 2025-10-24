"""Componentes de apoio para testar a orquestração da CLI."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from farol_core.application.collect_usecase import RequestsSoupScraper, ScrapedItem
from farol_core.domain.contracts import ArticleInput, ArticleWriteResult

CREATED_COMPONENTS: dict[str, dict[str, object]] = {}


def reset_components() -> None:
    """Limpa o registro de componentes criados."""

    CREATED_COMPONENTS.clear()


def _register(portal_name: str, component: str, instance: object) -> object:
    CREATED_COMPONENTS.setdefault(portal_name, {})[component] = instance
    return instance


class _ConfigurableScraper(RequestsSoupScraper):
    def __init__(
        self,
        items: Mapping[str, Iterable[Mapping[str, Any]]],
        *,
        pages: Iterable[Mapping[str, Any]],
        portal_name: str,
        since: str | None = None,
    ) -> None:
        self._items = {
            url: [self._to_scraped(item) for item in items_list]
            for url, items_list in items.items()
        }
        self.pages = tuple(pages)
        self.portal_name = portal_name
        self.since = since
        self.calls: list[Mapping[str, Any]] = []

    def _to_scraped(self, item: Mapping[str, Any]) -> ScrapedItem:
        data = dict(item)
        return ScrapedItem(
            url=str(data.get("url", "")),
            title=data.get("title"),
            content_html=str(data.get("content_html", "")),
            summary_html=data.get("summary_html"),
            tags=tuple(data.get("tags", ())),
            published_at=data.get("published_at"),
            metadata=dict(data.get("metadata", {})),
        )

    def fetch_page(self, page: Mapping[str, Any]) -> Iterable[ScrapedItem]:
        self.calls.append(dict(page))
        url = str(page.get("url", ""))
        return list(self._items.get(url, []))


class _SimpleUrlNormalizer:
    def to_absolute(self, url: str, base_url: str | None = None) -> str:
        if base_url and url.startswith("/"):
            return f"{base_url.rstrip('/')}{url}"
        return url


class _SimpleDateNormalizer:
    def parse(self, value: str, reference: datetime | None = None) -> datetime | None:
        return datetime.fromisoformat(value)


class _SimpleTextCleaner:
    def clean_html_to_text(self, html: str) -> str:
        return html.replace("<", "").replace(">", "").strip()

    def sanitize_html(self, html: str) -> str:
        return html.strip()


class _RecordingDeduper:
    def __init__(
        self,
        *,
        portal_name: str,
        fingerprint_field: str | None = None,
    ) -> None:
        self.portal_name = portal_name
        self.fingerprint_field = fingerprint_field
        self.seen: set[str] = set()

    def fingerprint(self, article: ArticleInput) -> str:
        if self.fingerprint_field == "title":
            return f"{self.portal_name}:{article.title}"
        return f"{self.portal_name}:{article.url}"

    def is_new(self, fingerprint: str) -> bool:
        if fingerprint in self.seen:
            return False
        self.seen.add(fingerprint)
        return True


@dataclass
class _RecordingWriter:
    portal_name: str
    writes: list[tuple[ArticleInput, str]] = field(default_factory=list)

    def write(self, article: ArticleInput, fingerprint: str) -> ArticleWriteResult:
        self.writes.append((article, fingerprint))
        return ArticleWriteResult(
            status="inserted",
            article_id=f"{self.portal_name}:{len(self.writes)}",
        )


def build_scraper(
    *,
    portal,
    pages,
    items: Mapping[str, Iterable[Mapping[str, Any]]],
    since: str | None = None,
    **_: Any,
) -> RequestsSoupScraper:
    scraper = _ConfigurableScraper(
        items,
        pages=pages,
        portal_name=portal.name,
        since=since,
    )
    return _register(portal.name, "scraper", scraper)


def build_url_normalizer(*, portal, **_: Any) -> _SimpleUrlNormalizer:
    return _register(portal.name, "url_normalizer", _SimpleUrlNormalizer())


def build_date_normalizer(*, portal, **_: Any) -> _SimpleDateNormalizer:
    return _register(portal.name, "date_normalizer", _SimpleDateNormalizer())


def build_text_cleaner(*, portal, **_: Any) -> _SimpleTextCleaner:
    return _register(portal.name, "text_cleaner", _SimpleTextCleaner())


def build_deduper(
    *, portal, fingerprint_field: str | None = None, **_: Any
) -> _RecordingDeduper:
    return _register(
        portal.name,
        "deduper",
        _RecordingDeduper(
            portal_name=portal.name,
            fingerprint_field=fingerprint_field,
        ),
    )


def build_writer(*, portal, **_: Any) -> _RecordingWriter:
    return _register(portal.name, "writer", _RecordingWriter(portal_name=portal.name))

