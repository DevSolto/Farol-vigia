from datetime import datetime

from farol_core.domain.contracts import ArticleInput
from datetime import datetime

from farol_core.domain.contracts import ArticleInput
from farol_core.infrastructure.hashing.sha256_deduper import Sha256Deduper


def _article(url: str, title: str, *, tags: tuple[str, ...] = ("tag",)) -> ArticleInput:
    return ArticleInput(
        url=url,
        title=title,
        portal_name="Portal",
        summary=None,
        content_html="<p>conteudo</p>",
        content_text="conteudo",
        tags=tags,
        published_at_raw=None,
        published_at=None,
        collected_at=datetime(2024, 1, 1, 0, 0, 0),
    )


def test_fingerprint_changes_when_relevant_fields_change() -> None:
    deduper = Sha256Deduper(fields=("url", "title"))

    article_a = _article("https://example.com/a", "Titulo")
    article_b = _article("https://example.com/a", "Outro")

    assert deduper.fingerprint(article_a) != deduper.fingerprint(article_b)


def test_is_new_tracks_seen_fingerprints() -> None:
    deduper = Sha256Deduper()

    article = _article("https://example.com/a", "Titulo")
    fingerprint = deduper.fingerprint(article)

    assert deduper.is_new(fingerprint) is True
    assert deduper.is_new(fingerprint) is False


def test_factory_accepts_fields_as_string() -> None:
    deduper = Sha256Deduper(fields=("title",))

    article_a = _article("https://example.com/a", "Titulo", tags=("a", "b"))
    article_b = _article("https://example.com/b", "Titulo", tags=("a", "b"))

    assert deduper.fingerprint(article_a) == deduper.fingerprint(article_b)
