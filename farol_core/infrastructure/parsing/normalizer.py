"""Normalizador simples para artigos."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from farol_core.domain.contracts import ArticleInput, Normalizer, RawArticle
from farol_core.domain.errors import NormalizeError


class SimpleNormalizer(Normalizer):
    """Transforma ``RawArticle`` em ``ArticleInput`` aplicando defaults."""

    def __init__(
        self,
        *,
        default_tags: Iterable[str] | None = None,
        fallback_title: str = "Sem título",
    ) -> None:
        self._default_tags = tuple(default_tags or ())
        self._fallback_title = fallback_title

    def normalize(self, article: RawArticle) -> ArticleInput:
        if not article.body:
            raise NormalizeError("Artigo sem conteúdo para normalização")

        title = article.title or str(article.metadata.get("title") or self._fallback_title)
        summary = (
            article.metadata.get("summary")  # type: ignore[arg-type]
            if hasattr(article.metadata, "get")
            else None
        )
        summary_text = str(summary) if summary is not None else article.body[:280]

        published_at = self._extract_datetime(article)

        tags: Sequence[str] = self._extract_tags(article)

        metadata = dict(article.metadata)
        metadata.setdefault("normalized_at", datetime.utcnow().isoformat())

        return ArticleInput(
            url=article.url,
            title=title,
            content=article.body,
            summary=summary_text,
            tags=tags,
            published_at=published_at,
            metadata=metadata,
        )

    def _extract_datetime(self, article: RawArticle) -> datetime | None:
        value = article.metadata.get("published_at")
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError as exc:
                raise NormalizeError("Data de publicação em formato inválido") from exc
        return None

    def _extract_tags(self, article: RawArticle) -> Sequence[str]:
        value = article.metadata.get("tags")
        if isinstance(value, (list, tuple)):
            return tuple(str(tag) for tag in value)
        return self._default_tags
