from __future__ import annotations

from datetime import datetime, timezone

import pytest

from farol_core.domain.contracts import ArticleInput
from farol_core.domain.errors import WriteError
from farol_core.infrastructure.db.mongo_writer import MongoArticleWriter


class _UpdateResult:
    def __init__(self, *, upserted_id: str | None = None, matched_count: int = 0) -> None:
        self.upserted_id = upserted_id
        self.matched_count = matched_count


def _build_article() -> ArticleInput:
    return ArticleInput(
        url="https://example.com/artigo",
        title="Título",
        portal_name="Portal Exemplo",
        summary="Resumo do artigo",
        content_html="<p>Conteúdo</p>",
        content_text="Conteúdo",
        tags=("politica",),
        published_at_raw="2024-01-01T00:00:00-03:00",
        published_at=datetime(2024, 1, 1, 3, 0, 0),
        collected_at=datetime(2024, 1, 2, 12, 0, 0),
        metadata={"section": "home"},
    )


def test_to_document_includes_all_expected_fields() -> None:
    writer = MongoArticleWriter(collection=None)
    article = _build_article()

    document = writer._to_document(article, "fingerprint-123")

    assert document == {
        "url": article.url,
        "portal_name": article.portal_name,
        "title": article.title,
        "summary": article.summary,
        "content_html": article.content_html,
        "content_text": article.content_text,
        "tags": ["politica"],
        "published_at_raw": article.published_at_raw,
        "published_at": datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc),
        "collected_at": datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
        "fingerprint": "fingerprint-123",
        "raw_meta": {"section": "home"},
    }


def test_write_returns_inserted_status_when_upserting_new_document() -> None:
    class _CollectionStub:
        def __init__(self) -> None:
            self.calls: list[tuple[dict[str, object], dict[str, object], bool]] = []

        def update_one(self, filter: dict[str, object], update: dict[str, object], *, upsert: bool):
            self.calls.append((filter, update, upsert))
            return _UpdateResult(upserted_id="abc123", matched_count=1)

    collection = _CollectionStub()
    writer = MongoArticleWriter(collection)

    result = writer.write(_build_article(), "fingerprint-123")

    assert result.status == "inserted"
    assert result.article_id == "abc123"
    assert collection.calls[0][0] == {"url": "https://example.com/artigo"}
    assert collection.calls[0][2] is True


def test_write_returns_updated_status_when_document_exists() -> None:
    class _CollectionStub:
        def __init__(self) -> None:
            self.calls: list[tuple[dict[str, object], dict[str, object], bool]] = []

        def update_one(self, filter: dict[str, object], update: dict[str, object], *, upsert: bool):
            self.calls.append((filter, update, upsert))
            return _UpdateResult(upserted_id=None, matched_count=1)

    collection = _CollectionStub()
    writer = MongoArticleWriter(collection)

    result = writer.write(_build_article(), "fingerprint-123")

    assert result.status == "updated"
    assert result.article_id is None
    assert len(collection.calls) == 1


def test_write_fallbacks_to_fingerprint_on_duplicate_key() -> None:
    class DuplicateKeyError(Exception):
        """Simula exceção de chave duplicada do Mongo."""

    class _CollectionStub:
        def __init__(self) -> None:
            self.calls: list[tuple[dict[str, object], dict[str, object], bool]] = []
            self._call_count = 0

        def update_one(self, filter: dict[str, object], update: dict[str, object], *, upsert: bool):
            self.calls.append((filter, update, upsert))
            self._call_count += 1
            if self._call_count == 1:
                raise DuplicateKeyError("duplicate key")
            return _UpdateResult(upserted_id=None, matched_count=1)

    collection = _CollectionStub()
    writer = MongoArticleWriter(collection)

    result = writer.write(_build_article(), "fingerprint-123")

    assert result.status == "updated"
    assert result.article_id is None
    assert collection.calls[1][0] == {"fingerprint": "fingerprint-123"}
    assert collection.calls[1][2] is False


def test_write_raises_error_when_fingerprint_not_found_after_duplicate() -> None:
    class DuplicateKeyError(Exception):
        """Simula exceção de chave duplicada do Mongo."""

    class _CollectionStub:
        def __init__(self) -> None:
            self._call_count = 0

        def update_one(self, filter: dict[str, object], update: dict[str, object], *, upsert: bool):
            self._call_count += 1
            if self._call_count == 1:
                raise DuplicateKeyError("duplicate key")
            return _UpdateResult(upserted_id=None, matched_count=0)

    writer = MongoArticleWriter(_CollectionStub())

    with pytest.raises(WriteError):
        writer.write(_build_article(), "fingerprint-123")
