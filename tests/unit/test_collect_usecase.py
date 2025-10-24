from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

import pytest

from farol_core.application.collect_usecase import CollectUseCase
from farol_core.domain.contracts import ArticleInput, RawArticle, RawListingItem
from farol_core.domain.errors import FarolError
from farol_core.infrastructure.logging.logger import configure_logger


@dataclass
class _ClockStub:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


class _FetcherStub:
    def __init__(self, items: Iterable[RawListingItem]) -> None:
        self._items = list(items)

    def fetch(self) -> Iterable[RawListingItem]:
        return self._items


class _ParserStub:
    def parse(self, item: RawListingItem) -> RawArticle:
        return RawArticle(
            url=item.url,
            title="Titulo",
            body=item.content,
            metadata=item.metadata,
        )


class _NormalizerStub:
    def normalize(self, article: RawArticle) -> ArticleInput:
        return ArticleInput(
            url=article.url,
            title=article.title or "fallback",
            content=article.body,
            summary=None,
            tags=(),
            published_at=None,
            metadata=article.metadata,
        )


class _WriterStub:
    def __init__(self) -> None:
        self.received: list[ArticleInput] = []

    def write(self, article: ArticleInput) -> str:
        self.received.append(article)
        return "article-id"


class _FailingFetcher:
    def fetch(self) -> Iterable[RawListingItem]:  # pragma: no cover
        raise ValueError("falhou")


class _ErrorFetcher:
    def fetch(self) -> Iterable[RawListingItem]:  # pragma: no cover
        raise FarolError("erro fetch")


def test_collect_usecase_runs_with_dependencies() -> None:
    items = [RawListingItem(url="https://example.com", content="body")]
    fetcher = _FetcherStub(items)
    parser = _ParserStub()
    normalizer = _NormalizerStub()
    writer = _WriterStub()
    clock = _ClockStub(datetime(2024, 1, 1, 12, 0, 0))
    logger = configure_logger("test.collect")

    use_case = CollectUseCase(fetcher, parser, normalizer, writer, clock, logger)

    result = use_case.execute()

    assert writer.received[0].url == "https://example.com"
    assert result == [
        {
            "url": "https://example.com",
            "article_id": "article-id",
            "processed_at": clock.instant.isoformat(),
        }
    ]


def test_collect_usecase_wraps_unexpected_errors() -> None:
    parser = _ParserStub()
    normalizer = _NormalizerStub()
    writer = _WriterStub()
    clock = _ClockStub(datetime(2024, 1, 1, 12, 0, 0))
    logger = configure_logger("test.collect")

    use_case = CollectUseCase(
        _FailingFetcher(),
        parser,
        normalizer,
        writer,
        clock,
        logger,
    )

    with pytest.raises(FarolError):
        use_case.execute()


def test_collect_usecase_propagates_domain_errors() -> None:
    parser = _ParserStub()
    normalizer = _NormalizerStub()
    writer = _WriterStub()
    clock = _ClockStub(datetime(2024, 1, 1, 12, 0, 0))
    logger = configure_logger("test.collect")

    use_case = CollectUseCase(
        _ErrorFetcher(),
        parser,
        normalizer,
        writer,
        clock,
        logger,
    )

    with pytest.raises(FarolError):
        use_case.execute()
