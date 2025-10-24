"""Writer que persiste artigos em uma coleção MongoDB."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from farol_core.domain.contracts import ArticleInput, ArticleWriteResult, ArticleWriter
from farol_core.domain.errors import WriteError


class MongoArticleWriter(ArticleWriter):
    """Implementação de ``ArticleWriter`` para MongoDB."""

    def __init__(self, collection: Any) -> None:
        self._collection = collection

    def write(self, article: ArticleInput, fingerprint: str) -> ArticleWriteResult:
        document = self._to_document(article, fingerprint)
        try:
            result = self._collection.update_one(
                {"url": article.url},
                {"$set": document},
                upsert=True,
            )
        except Exception as exc:  # noqa: BLE001
            if exc.__class__.__name__ != "DuplicateKeyError":
                raise WriteError("Falha ao escrever artigo no MongoDB", cause=exc) from exc

            try:
                fallback_result = self._collection.update_one(
                    {"fingerprint": fingerprint},
                    {"$set": document},
                    upsert=False,
                )
            except Exception as inner_exc:  # noqa: BLE001
                raise WriteError(
                    "Falha ao atualizar artigo duplicado por fingerprint no MongoDB",
                    cause=inner_exc,
                ) from inner_exc

            if getattr(fallback_result, "matched_count", 0) == 0:
                raise WriteError(
                    "Fingerprint existente não encontrado para atualização no MongoDB",
                    cause=exc,
                ) from exc

            return ArticleWriteResult(status="updated")

        if getattr(result, "upserted_id", None) is not None:
            return ArticleWriteResult(status="inserted", article_id=str(result.upserted_id))

        return ArticleWriteResult(status="updated")

    def _to_document(self, article: ArticleInput, fingerprint: str) -> Mapping[str, Any]:
        document = {
            "url": article.url,
            "portal_name": article.portal_name,
            "title": article.title,
            "summary": article.summary,
            "content_html": article.content_html,
            "content_text": article.content_text,
            "tags": list(article.tags),
            "published_at_raw": article.published_at_raw,
            "published_at": self._to_utc(article.published_at),
            "collected_at": self._to_utc(article.collected_at),
            "fingerprint": fingerprint,
            "raw_meta": dict(article.metadata),
        }
        return document

    @staticmethod
    def _to_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
