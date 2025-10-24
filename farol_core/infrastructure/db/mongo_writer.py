"""Writer que persiste artigos em uma coleção MongoDB."""

from __future__ import annotations

from typing import Any, Mapping

from farol_core.domain.contracts import ArticleInput, ArticleWriter
from farol_core.domain.errors import WriteError


class MongoArticleWriter(ArticleWriter):
    """Implementação de ``ArticleWriter`` para MongoDB."""

    def __init__(self, collection) -> None:
        self._collection = collection

    def write(self, article: ArticleInput) -> str | None:
        document = self._to_document(article)
        try:
            result = self._collection.update_one(
                {"url": article.url},
                {"$set": document},
                upsert=True,
            )
        except Exception as exc:  # noqa: BLE001
            raise WriteError("Falha ao escrever artigo no MongoDB", cause=exc) from exc

        if getattr(result, "upserted_id", None) is not None:
            return str(result.upserted_id)
        return None

    def _to_document(self, article: ArticleInput) -> Mapping[str, Any]:
        document = {
            "url": article.url,
            "title": article.title,
            "content": article.content,
            "summary": article.summary,
            "tags": list(article.tags),
            "published_at": article.published_at,
            "metadata": dict(article.metadata),
        }
        return document
