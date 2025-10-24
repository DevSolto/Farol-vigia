"""Caso de uso responsável pela coleta completa de artigos."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from logging import Logger

from farol_core.domain.contracts import (
    ArticleInput,
    ArticleWriter,
    Clock,
    DateNormalizer,
    Deduper,
    TextCleaner,
    UrlNormalizer,
)
from farol_core.domain.errors import FarolError


@dataclass(slots=True)
class ScrapedItem:
    """Representa o conteúdo cru retornado pelo scraper de páginas."""

    url: str
    title: str | None
    content_html: str
    summary_html: str | None = None
    tags: Sequence[str] = field(default_factory=tuple)
    published_at: str | None = None
    metadata: MutableMapping[str, object] = field(default_factory=dict)


class RequestsSoupScraper:
    """Protocolo simplificado para scrapers baseados em ``requests + bs4``."""

    def fetch_page(self, page: Mapping[str, object]) -> Iterable[ScrapedItem]:  # pragma: no cover - protocolo
        """Retorna itens extraídos da página configurada."""
        raise NotImplementedError


class CollectUseCase:
    """Orquestra o fluxo de coleta com deduplicação e métricas."""

    def __init__(
        self,
        scraper: RequestsSoupScraper,
        *,
        pages: Sequence[Mapping[str, object]],
        url_normalizer: UrlNormalizer,
        date_normalizer: DateNormalizer,
        text_cleaner: TextCleaner,
        deduper: Deduper,
        writer: ArticleWriter,
        clock: Clock,
        logger: Logger,
    ) -> None:
        self._scraper = scraper
        self._pages = tuple(pages)
        self._url_normalizer = url_normalizer
        self._date_normalizer = date_normalizer
        self._text_cleaner = text_cleaner
        self._deduper = deduper
        self._writer = writer
        self._clock = clock
        self._logger = logger

    def execute(self) -> Mapping[str, object]:
        """Executa o fluxo de coleta retornando métricas e itens persistidos."""

        seen_urls: set[str] = set()
        metrics: dict[str, object] = {
            "processed": 0,
            "skipped": defaultdict(int),
            "pages": {"total": len(self._pages), "fetched": 0},
        }
        persisted: list[Mapping[str, object]] = []

        self._logger.info(
            "scrape.start",
            extra={
                "extra": {
                    "at": self._clock.now().isoformat(),
                    "pages": len(self._pages),
                }
            },
        )

        for page_index, page in enumerate(self._pages, start=1):
            page_url = str(page.get("url"))
            page_metadata = self._to_metadata(page.get("metadata"))
            try:
                items = list(self._scraper.fetch_page(page))
            except FarolError:
                self._logger.exception(
                    "scrape.page_error",
                    extra={"extra": {"url": page_url, "index": page_index}},
                )
                raise
            except Exception as exc:  # noqa: BLE001
                self._logger.exception(
                    "scrape.page_unexpected",
                    extra={"extra": {"url": page_url, "index": page_index}},
                )
                raise FarolError("Erro inesperado durante a coleta", cause=exc) from exc

            metrics["pages"]["fetched"] += 1
            self._logger.info(
                "scrape.page_fetched",
                extra={
                    "extra": {
                        "url": page_url,
                        "index": page_index,
                        "count": len(items),
                    }
                },
            )

            for position, item in enumerate(items, start=1):
                normalized_url = self._url_normalizer.to_absolute(item.url, page_url)
                if normalized_url in seen_urls:
                    metrics["skipped"]["url"] += 1
                    self._logger.info(
                        "scrape.item_skipped_dedup",
                        extra={
                            "extra": {
                                "url": normalized_url,
                                "reason": "url",
                                "page_index": page_index,
                                "position": position,
                            }
                        },
                    )
                    continue

                seen_urls.add(normalized_url)

                try:
                    article = self._build_article(
                        item,
                        normalized_url=normalized_url,
                        page_metadata=page_metadata,
                    )
                except FarolError as exc:
                    metrics["skipped"]["invalid"] += 1
                    self._logger.error(
                        "scrape.item_failed",
                        extra={
                            "extra": {
                                "url": normalized_url,
                                "reason": exc.__class__.__name__,
                                "page_index": page_index,
                                "position": position,
                            }
                        },
                    )
                    continue

                fingerprint = self._deduper.fingerprint(article)
                if not self._deduper.is_new(fingerprint):
                    metrics["skipped"]["fingerprint"] += 1
                    self._logger.info(
                        "scrape.item_skipped_dedup",
                        extra={
                            "extra": {
                                "url": normalized_url,
                                "reason": "fingerprint",
                                "page_index": page_index,
                                "position": position,
                            }
                        },
                    )
                    continue

                try:
                    article_id = self._writer.write(article)
                except FarolError as exc:
                    metrics["skipped"]["write"] += 1
                    self._logger.error(
                        "scrape.item_failed",
                        extra={
                            "extra": {
                                "url": normalized_url,
                                "reason": exc.__class__.__name__,
                                "page_index": page_index,
                                "position": position,
                            }
                        },
                    )
                    continue

                metrics["processed"] += 1
                processed_at = self._clock.now().isoformat()
                persisted.append(
                    {
                        "url": article.url,
                        "article_id": article_id,
                        "fingerprint": fingerprint,
                        "processed_at": processed_at,
                    }
                )
                self._logger.info(
                    "scrape.item_persisted",
                    extra={
                        "extra": {
                            "url": article.url,
                            "article_id": article_id,
                            "fingerprint": fingerprint,
                            "page_index": page_index,
                            "position": position,
                        }
                    },
                )

        metrics["skipped"] = dict(metrics["skipped"])
        result = {"metrics": metrics, "items": persisted}
        self._logger.info(
            "scrape.finish",
            extra={
                "extra": {
                    "at": self._clock.now().isoformat(),
                    "processed": metrics["processed"],
                    "skipped": metrics["skipped"],
                }
            },
        )
        return result

    def _build_article(
        self,
        item: ScrapedItem,
        *,
        normalized_url: str,
        page_metadata: Mapping[str, object],
    ) -> ArticleInput:
        content_html = item.content_html or ""
        if not content_html:
            raise FarolError("Artigo sem conteúdo")

        sanitized_html = self._text_cleaner.sanitize_html(content_html)
        summary_source = item.summary_html if item.summary_html is not None else content_html
        summary_text = self._text_cleaner.clean_html_to_text(summary_source)

        title = item.title or summary_text or "Sem título"

        published_at = None
        if item.published_at:
            published_at = self._date_normalizer.parse(item.published_at, reference=None)

        combined_metadata: dict[str, object] = {**page_metadata, **item.metadata}
        combined_metadata.setdefault("normalized_at", self._clock.now().isoformat())

        article = ArticleInput(
            url=normalized_url,
            title=title,
            content=sanitized_html,
            summary=summary_text,
            tags=tuple(item.tags),
            published_at=published_at,
            metadata=combined_metadata,
        )
        return article

    @staticmethod
    def _to_metadata(value: object) -> Mapping[str, object]:
        if isinstance(value, Mapping):
            return dict(value)
        return {}
