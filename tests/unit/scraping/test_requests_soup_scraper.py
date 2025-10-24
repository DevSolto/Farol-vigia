from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pytest

from farol_core.domain.errors import FetchError
from farol_core.infrastructure.normalizers.url_normalizer import SimpleUrlNormalizer
from farol_core.infrastructure.scraping.requests_soup_scraper import (
    RequestsSoupScraper,
    SoupArticleParser,
    SoupListingParser,
)


@dataclass
class _FakeResponse:
    text: str
    url: str
    status_code: int = 200

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeClient:
    def __init__(self, responses: Mapping[tuple[str, tuple[tuple[str, object], ...] | None], _FakeResponse]) -> None:
        self._responses = dict(responses)
        self.calls: list[tuple[str, Mapping[str, object] | None]] = []

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, object] | None = None,
        timeout: float | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> _FakeResponse:
        key = (url, tuple(sorted((params or {}).items())) or None)
        self.calls.append((url, dict(params or {})))
        if key not in self._responses:
            raise RuntimeError(f"Requisição inesperada: {key}")
        return self._responses[key]


_LISTING_PAGE_1 = """
<html><body>
<ul>
<li class="item"><a href="/article-1">Primeiro</a><div class="summary">Resumo 1</div><span class="tag">a</span><span class="tag">b</span><time class="date">2024-01-10T10:00:00</time></li>
<li class="item"><a href="https://external.com/article-2">Segundo</a><div class="summary">Resumo 2</div></li>
</ul>
</body></html>
"""

_LISTING_PAGE_2 = """
<html><body>
<ul>
<li class="item"><a href="/article-3">Terceiro</a></li>
</ul>
</body></html>
"""

_ARTICLE_PAGE = """
<html><body>
<article>
<h1>Primeiro</h1>
<div class="content"><p>Conteúdo</p></div>
</article>
</body></html>
"""

_ARTICLE_NO_TITLE = """
<html><body>
<article>
<div class="content"><p>Sem título</p></div>
</article>
</body></html>
"""


@pytest.fixture
def scraper() -> RequestsSoupScraper:
    responses = {
        ("https://example.com/list", (("page", 1),)): _FakeResponse(
            text=_LISTING_PAGE_1,
            url="https://example.com/list?page=1",
        ),
        ("https://example.com/list", (("page", 2),)): _FakeResponse(
            text=_LISTING_PAGE_2,
            url="https://example.com/list?page=2",
        ),
        ("https://example.com/article-1", None): _FakeResponse(
            text=_ARTICLE_PAGE,
            url="https://example.com/article-1",
        ),
        ("https://external.com/article-2", None): _FakeResponse(
            text=_ARTICLE_NO_TITLE,
            url="https://external.com/article-2",
        ),
        ("https://example.com/article-3", None): _FakeResponse(
            text=_ARTICLE_PAGE,
            url="https://example.com/article-3",
        ),
    }
    client = _FakeClient(responses)
    listing_parser = SoupListingParser(
        item_selector="li.item",
        metadata_selectors={
            "tags": {"selector": ".tag", "all": True},
            "published_at": {"selector": ".date"},
        },
        summary_selector=".summary",
    )
    article_parser = SoupArticleParser(body_selector="article .content", title_selector="h1")
    normalizer = SimpleUrlNormalizer()
    return RequestsSoupScraper(
        client=client,
        listing_parser=listing_parser,
        article_parser=article_parser,
        url_normalizer=normalizer,
        pagination={"count": 2, "param": "page"},
    )


def test_iter_listing_returns_absolute_urls(scraper: RequestsSoupScraper) -> None:
    page_metadata = {"section": "news"}

    items = scraper.iter_listing(
        "https://example.com/list",
        page_metadata,
        {"count": 1, "param": "page"},
    )

    urls = [item.url for item in items]
    assert urls[0] == "https://example.com/article-1"
    assert urls[1] == "https://external.com/article-2"


def test_fetch_page_combines_metadata(scraper: RequestsSoupScraper) -> None:
    result = scraper.fetch_page({"url": "https://example.com/list", "metadata": {"section": "news"}})

    assert len(result) == 3
    first = result[0]
    assert first.url == "https://example.com/article-1"
    assert first.title == "Primeiro"
    assert first.summary_html == "<div class=\"summary\">Resumo 1</div>"
    assert first.tags == ("a", "b")
    assert first.published_at == "2024-01-10T10:00:00"
    assert first.metadata["section"] == "news"
    assert first.metadata["tags"] == ("a", "b")

    second = result[1]
    assert second.title == "Segundo"


def test_fetch_and_parse_article_uses_listing_title(scraper: RequestsSoupScraper) -> None:
    page_metadata = {"section": "news"}
    listing = scraper.iter_listing(
        "https://example.com/list",
        page_metadata,
        {"count": 1, "param": "page"},
    )[1]

    article = scraper.fetch_and_parse_article(listing, page_metadata)

    assert article.title == "Segundo"


def test_fetch_page_raises_on_http_error(scraper: RequestsSoupScraper) -> None:
    failing_client = scraper._client  # type: ignore[attr-defined]
    failing_client._responses[("https://example.com/article-1", None)].status_code = 500

    with pytest.raises(FetchError):
        scraper.fetch_page({"url": "https://example.com/list"})
