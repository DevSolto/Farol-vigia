from datetime import datetime

import pytest

from farol_core.domain.contracts import RawArticle
from farol_core.domain.errors import NormalizeError
from farol_core.infrastructure.parsing.normalizer import SimpleNormalizer


def test_normalizer_applies_defaults_and_metadata() -> None:
    article = RawArticle(
        url="https://example.com/article",
        title="Título",
        body="Conteúdo completo do artigo",
        metadata={
            "summary": "Resumo curto",
            "tags": ["politica", "nordeste"],
            "published_at": datetime(2024, 1, 1, 12, 0, 0),
        },
    )

    normalizer = SimpleNormalizer(default_tags=("default",), fallback_title="Fallback")

    normalized = normalizer.normalize(article)

    assert normalized.title == "Título"
    assert normalized.summary == "Resumo curto"
    assert normalized.tags == ("politica", "nordeste")
    assert normalized.metadata["summary"] == "Resumo curto"
    assert "normalized_at" in normalized.metadata


def test_normalizer_raises_without_body() -> None:
    article = RawArticle(
        url="https://example.com",
        title="Sem corpo",
        body="",
        metadata={},
    )
    normalizer = SimpleNormalizer()

    with pytest.raises(NormalizeError):
        normalizer.normalize(article)
