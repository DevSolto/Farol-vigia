from datetime import datetime

from farol_core.domain.contracts import (
    ArticleInput,
    DateNormalizer,
    Deduper,
    RawListingItem,
    TextCleaner,
    UrlNormalizer,
)


def test_raw_listing_item_metadata_isolated() -> None:
    item = RawListingItem(url="https://example.com", content="html")
    item.metadata["key"] = "value"

    another = RawListingItem(url="https://example.org", content="html")

    assert "key" not in another.metadata
    assert another.metadata == {}


class StubUrlNormalizer:
    def to_absolute(self, url: str, base_url: str | None = None) -> str:
        if base_url and not url.startswith("http"):
            return base_url.rstrip("/") + "/" + url.lstrip("/")
        return url


def test_url_normalizer_protocol_stub() -> None:
    normalizer: UrlNormalizer = StubUrlNormalizer()

    assert (
        normalizer.to_absolute("/noticias/politica", "https://example.com")
        == "https://example.com/noticias/politica"
    )
    assert normalizer.to_absolute("https://example.com/about") == "https://example.com/about"


class StubTextCleaner:
    def clean_html_to_text(self, html: str) -> str:
        return html.replace("<p>", "").replace("</p>", "").strip()

    def sanitize_html(self, html: str) -> str:
        return html.replace("<script>", "").replace("</script>", "")


def test_text_cleaner_protocol_stub() -> None:
    cleaner: TextCleaner = StubTextCleaner()

    assert cleaner.clean_html_to_text("<p>Olá Mundo</p>") == "Olá Mundo"
    assert cleaner.sanitize_html("<div><script>evil()</script></div>") == "<div>evil()</div>"


class StubDateNormalizer:
    def parse(self, value: str, reference: datetime | None = None) -> datetime | None:
        if reference is not None:
            return reference
        return datetime.fromisoformat(value)


def test_date_normalizer_protocol_stub() -> None:
    normalizer: DateNormalizer = StubDateNormalizer()

    reference = datetime(2024, 1, 1, 12, 0, 0)
    assert normalizer.parse("2024-02-01T08:30:00") == datetime(2024, 2, 1, 8, 30, 0)
    assert normalizer.parse("ignored", reference=reference) == reference


class StubDeduper:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def fingerprint(self, article: ArticleInput) -> str:
        return article.url

    def is_new(self, fingerprint: str) -> bool:
        if fingerprint in self._seen:
            return False
        self._seen.add(fingerprint)
        return True


def test_deduper_protocol_stub() -> None:
    deduper: Deduper = StubDeduper()

    article = ArticleInput(
        url="https://example.com/noticia", 
        title="Título",
        content="Conteúdo",
        summary=None,
        tags=(),
        published_at=None,
    )

    fingerprint = deduper.fingerprint(article)

    assert deduper.is_new(fingerprint) is True
    assert deduper.is_new(fingerprint) is False
