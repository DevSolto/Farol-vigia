"""Caso de uso responsável pela coleta completa de artigos."""

from __future__ import annotations

from farol_core.domain.contracts import (
    ArticleInput,
    ArticleWriter,
    Clock,
    Fetcher,
    Normalizer,
    Parser,
    RawArticle,
    RawListingItem,
)
from farol_core.domain.errors import FarolError


class CollectUseCase:
    """Orquestra o fluxo de coleta: fetch -> parse -> normalize -> write."""

    def __init__(
        self,
        fetcher: Fetcher,
        parser: Parser,
        normalizer: Normalizer,
        writer: ArticleWriter,
        clock: Clock,
        logger,
    ) -> None:
        self._fetcher = fetcher
        self._parser = parser
        self._normalizer = normalizer
        self._writer = writer
        self._clock = clock
        self._logger = logger

    def execute(self) -> list[dict[str, object]]:
        """Executa o fluxo de coleta completo retornando relatórios por item."""

        collected: list[dict[str, object]] = []
        self._logger.info(
            "collect.start", extra={"extra": {"at": self._clock.now().isoformat()}}
        )

        try:
            items = list(self._fetcher.fetch())
        except FarolError:
            self._logger.exception("collect.fetch.error", extra={"extra": {}})
            raise
        except Exception as exc:  # noqa: BLE001
            self._logger.exception("collect.fetch.unexpected", extra={"extra": {}})
            raise FarolError("Erro inesperado durante a busca", cause=exc) from exc

        for position, item in enumerate(items, start=1):
            self._logger.debug(
                "collect.item.received",
                extra={
                    "extra": {
                        "url": item.url,
                        "position": position,
                    }
                },
            )
            try:
                raw_article = self._parse_item(item)
                normalized = self._normalize_article(raw_article)
                article_id = self._write_article(normalized)
            except FarolError as exc:
                self._logger.error(
                    "collect.item.failed",
                    extra={
                        "extra": {
                            "url": item.url,
                            "position": position,
                            "error": exc.__class__.__name__,
                        }
                    },
                )
                continue

            result = {
                "url": normalized.url,
                "article_id": article_id,
                "processed_at": self._clock.now().isoformat(),
            }
            self._logger.info(
                "collect.item.succeeded",
                extra={
                    "extra": {
                        "url": normalized.url,
                        "position": position,
                        "article_id": article_id,
                    }
                },
            )
            collected.append(result)

        self._logger.info(
            "collect.finish",
            extra={
                "extra": {"count": len(collected), "at": self._clock.now().isoformat()}
            },
        )
        return collected

    def _parse_item(self, item: RawListingItem) -> RawArticle:
        raw_article = self._parser.parse(item)
        self._logger.debug(
            "collect.item.parsed", extra={"extra": {"url": raw_article.url}}
        )
        return raw_article

    def _normalize_article(self, raw_article: RawArticle) -> ArticleInput:
        normalized = self._normalizer.normalize(raw_article)
        self._logger.debug(
            "collect.item.normalized", extra={"extra": {"url": normalized.url}}
        )
        return normalized

    def _write_article(self, article: ArticleInput) -> str | None:
        article_id = self._writer.write(article)
        self._logger.debug(
            "collect.item.persisted",
            extra={"extra": {"url": article.url, "article_id": article_id}},
        )
        return article_id
