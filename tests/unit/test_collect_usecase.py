from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime

import pytest

from farol_core.application.collect_usecase import CollectUseCase, RequestsSoupScraper, ScrapedItem
from farol_core.domain.contracts import ArticleInput, ArticleWriteResult
from farol_core.domain.errors import FarolError
from farol_core.infrastructure.logging.logger import configure_logger


@dataclass
class _ClockStub:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


class _WriterStub:
    def __init__(self) -> None:
        self.received: list[tuple[ArticleInput, str]] = []
        self.next_result = ArticleWriteResult(status="inserted", article_id="article-id")

    def write(self, article: ArticleInput, fingerprint: str) -> ArticleWriteResult:
        self.received.append((article, fingerprint))
        return self.next_result


class _ScraperStub(RequestsSoupScraper):
    def __init__(self, pages: Mapping[str, list[ScrapedItem]]) -> None:
        self._pages = pages
        self.called_with: list[Mapping[str, object]] = []

    def fetch_page(self, page: Mapping[str, object]) -> Iterable[ScrapedItem]:
        self.called_with.append(page)
        url = str(page.get("url"))
        return list(self._pages.get(url, []))


class _UrlNormalizerStub:
    def to_absolute(self, url: str, base_url: str | None = None) -> str:
        if base_url and url.startswith("/"):
            return f"{base_url}{url}"
        return url


class _DateNormalizerStub:
    def parse(self, value: str, reference: datetime | None = None) -> datetime | None:
        return datetime.fromisoformat(value)


class _TextCleanerStub:
    def clean_html_to_text(self, html: str) -> str:
        return html.replace("<p>", "").replace("</p>", "").strip()

    def sanitize_html(self, html: str) -> str:
        return html.strip()


class _DeduperStub:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def fingerprint(self, article: ArticleInput) -> str:
        return article.title.lower()

    def is_new(self, fingerprint: str) -> bool:
        if fingerprint in self._seen:
            return False
        self._seen.add(fingerprint)
        return True


def _build_use_case(
    *,
    scraper: RequestsSoupScraper,
    pages: Iterable[Mapping[str, object]],
    writer: _WriterStub | None = None,
    clock: _ClockStub | None = None,
    logger_name: str = "test.collect",
    logger: logging.Logger | None = None,
) -> tuple[CollectUseCase, _WriterStub, _ClockStub, logging.Logger]:
    writer = writer or _WriterStub()
    clock = clock or _ClockStub(datetime(2024, 1, 1, 12, 0, 0))
    logger = logger or configure_logger(logger_name)

    use_case = CollectUseCase(
        scraper,
        pages=tuple(pages),
        url_normalizer=_UrlNormalizerStub(),
        date_normalizer=_DateNormalizerStub(),
        text_cleaner=_TextCleanerStub(),
        deduper=_DeduperStub(),
        writer=writer,
        clock=clock,
        logger=logger,
    )
    return use_case, writer, clock, logger


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[tuple[str, dict[str, object]]] = []

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - trivial
        message = record.getMessage()
        extra_value = getattr(record, "extra", {})
        if isinstance(extra_value, str):
            try:
                extra_value = json.loads(extra_value)
            except json.JSONDecodeError:
                extra_value = {"value": extra_value}
        elif not isinstance(extra_value, dict):
            extra_value = {"value": extra_value}
        self.records.append((message, extra_value))


def test_collect_usecase_processes_pages_and_apply_dedup() -> None:
    pages = (
        {"url": "https://example.com/page-1", "metadata": {"section": "home"}},
        {"url": "https://example.com/page-2", "metadata": {"section": "tech"}},
    )
    scraper = _ScraperStub(
        {
            "https://example.com/page-1": [
                ScrapedItem(
                    url="/item-1",
                    title="Primeiro",
                    content_html="<p>conteudo 1</p>",
                    summary_html="<p>resumo 1</p>",
                    tags=("news",),
                    published_at="2024-01-01T10:00:00",
                ),
                ScrapedItem(
                    url="/item-1",
                    title="Duplicado por URL",
                    content_html="<p>conteudo 1b</p>",
                ),
            ],
            "https://example.com/page-2": [
                ScrapedItem(
                    url="/item-2",
                    title="Primeiro",
                    content_html="<p>conteudo 2</p>",
                )
            ],
        }
    )
    logger = configure_logger("test.collect.dedup")
    list_handler = _ListHandler()
    logger.addHandler(list_handler)
    use_case, writer, clock, _ = _build_use_case(
        scraper=scraper, pages=pages, logger_name="test.collect.dedup", logger=logger
    )

    result = use_case.execute()

    assert len(scraper.called_with) == 2
    assert writer.received and writer.received[0][0].url == "https://example.com/page-1/item-1"
    assert writer.received[0][0].metadata["section"] == "home"
    assert writer.received[0][1] == "primeiro"

    assert result["metrics"]["processed"] == 1
    assert result["metrics"]["skipped"] == {"url": 1, "fingerprint": 1}
    assert result["metrics"]["pages"] == {"total": 2, "fetched": 2}
    assert result["items"] == [
        {
            "url": "https://example.com/page-1/item-1",
            "article_id": "article-id",
            "fingerprint": "primeiro",
            "status": "inserted",
            "processed_at": clock.instant.isoformat(),
        }
    ]

    dedup_records = [
        extra
        for message, extra in list_handler.records
        if message == "scrape.item_skipped_dedup"
    ]
    assert len(dedup_records) == 2
    assert {extra["reason"] for extra in dedup_records} == {"url", "fingerprint"}


def test_collect_usecase_wraps_unexpected_errors() -> None:
    class _FailingScraper(RequestsSoupScraper):  # pragma: no cover - exceção
        def fetch_page(self, page: Mapping[str, object]) -> Iterable[ScrapedItem]:
            raise ValueError("boom")

    use_case, _, _, _ = _build_use_case(
        scraper=_FailingScraper(),
        pages=({"url": "https://example.com"},),
    )

    with pytest.raises(FarolError):
        use_case.execute()


def test_collect_usecase_propagates_domain_errors() -> None:
    class _DomainErrorScraper(RequestsSoupScraper):  # pragma: no cover - exceção
        def fetch_page(self, page: Mapping[str, object]) -> Iterable[ScrapedItem]:
            raise FarolError("erro fetch")

    use_case, _, _, _ = _build_use_case(
        scraper=_DomainErrorScraper(),
        pages=({"url": "https://example.com"},),
    )

    with pytest.raises(FarolError):
        use_case.execute()
