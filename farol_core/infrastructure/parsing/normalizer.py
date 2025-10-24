"""Normalizador simples para artigos."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime

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

        title = article.title or str(
            article.metadata.get("title") or self._fallback_title
        )
        summary_value = article.metadata.get("summary")
        summary_text = (
            str(summary_value) if summary_value is not None else article.body[:280]
        )

        published_at = self._extract_datetime(article)

        tags: Sequence[str] = self._extract_tags(article)

        metadata = dict(article.metadata)
        now = datetime.utcnow()
        metadata.setdefault("normalized_at", now.isoformat())

        portal_name = str(metadata.get("portal_name", ""))
        published_at_raw = metadata.get("published_at_raw")
        if not isinstance(published_at_raw, str):
            published_at_raw = None

        return ArticleInput(
            url=article.url,
            title=title,
            portal_name=portal_name,
            summary=summary_text,
            content_html=article.body,
            content_text=article.body,
            tags=tags,
            published_at_raw=published_at_raw,
            published_at=published_at,
            collected_at=now,
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
        if isinstance(value, list):
            return tuple(str(tag) for tag in value)
        if isinstance(value, tuple):
            return tuple(str(tag) for tag in value)
        return self._default_tags
