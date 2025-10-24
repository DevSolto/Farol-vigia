"""Implementações utilitárias para scrapers baseados em ``requests``."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from farol_core.application.collect_usecase import RequestsSoupScraper as ScraperProtocol
from farol_core.application.collect_usecase import ScrapedItem
from farol_core.domain.contracts import Parser, RawArticle, RawListingItem, UrlNormalizer
from farol_core.domain.errors import FetchError, ParseError
from farol_core.infrastructure.parsing.html_tree import HTMLDocument, HTMLNode


@dataclass(slots=True)
class _FetchedPage:
    html: str
    url: str
    metadata: Mapping[str, object]


class PaginatedHttpFetcher:
    """Busca páginas de listagem com suporte a paginação simples."""

    def __init__(
        self,
        client: Any,
        *,
        timeout: float | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self._client = client
        self._timeout = timeout
        self._headers = dict(headers or {})

    def fetch(self, url: str, pagination: Mapping[str, object] | None = None) -> Iterable[_FetchedPage]:
        requests = list(self._build_requests(url, pagination))
        results: list[_FetchedPage] = []
        for request_url, params, meta in requests:
            try:
                response = self._client.get(
                    request_url,
                    params=params,
                    timeout=self._timeout,
                    headers=self._headers or None,
                )
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                raise FetchError("Falha ao buscar página de listagem", cause=exc) from exc

            html = getattr(response, "text", "")
            final_url = str(getattr(response, "url", request_url))
            results.append(_FetchedPage(html=html, url=final_url, metadata=meta))
        return results

    def _build_requests(
        self, url: str, pagination: Mapping[str, object] | None
    ) -> Iterable[tuple[str, Mapping[str, object] | None, Mapping[str, object]]]:
        if not pagination:
            yield url, None, {}
            return

        param = str(pagination.get("param", "page"))
        start = int(pagination.get("start", 1))
        stop = pagination.get("stop")
        step = int(pagination.get("step", 1)) or 1
        extra_params = dict(pagination.get("params", {}))
        explicit_pages = pagination.get("pages")
        limit = pagination.get("limit")

        if explicit_pages is not None:
            pages = [int(page) for page in explicit_pages]
        else:
            if stop is not None:
                stop_int = int(stop)
                pages = list(range(start, stop_int + (1 if step > 0 else -1), step))
            else:
                count = int(pagination.get("count", 1))
                pages = [start + step * index for index in range(max(count, 1))]
        if limit is not None:
            pages = pages[: int(limit)]

        for page in pages:
            params = dict(extra_params)
            params[param] = page
            yield url, params, {"page": page}


class SoupListingParser:
    """Extrai itens da listagem a partir de HTML."""

    def __init__(
        self,
        *,
        item_selector: str,
        link_selector: str = "a",
        url_attribute: str = "href",
        title_selector: str | None = None,
        summary_selector: str | None = None,
        metadata_selectors: Mapping[str, Mapping[str, object] | str] | None = None,
    ) -> None:
        self._item_selector = item_selector
        self._link_selector = link_selector
        self._url_attribute = url_attribute
        self._title_selector = title_selector
        self._summary_selector = summary_selector
        self._metadata_selectors = {
            key: (value if isinstance(value, Mapping) else {"selector": value})
            for key, value in (metadata_selectors or {}).items()
        }

    def extract(
        self,
        html: str,
        *,
        base_url: str,
        page_metadata: Mapping[str, object] | None = None,
    ) -> Iterable[RawListingItem]:
        soup = HTMLDocument.from_html(html)
        items = soup.select(self._item_selector)
        results: list[RawListingItem] = []
        for element in items:
            link_element = element.select_one(self._link_selector) if self._link_selector else element
            href = (link_element.get(self._url_attribute, "") if link_element else "").strip()
            if not href:
                continue
            metadata = dict(page_metadata or {})
            if link_element:
                link_text = link_element.get_text(" ", strip=True)
                if link_text and "title" not in metadata:
                    metadata["title"] = link_text
            if self._title_selector:
                title_node = element.select_one(self._title_selector)
                if title_node and (title_text := title_node.get_text(" ", strip=True)):
                    metadata.setdefault("title", title_text)
            if self._summary_selector:
                summary_node = element.select_one(self._summary_selector)
                if summary_node:
                    metadata.setdefault("summary_html", str(summary_node))
                    metadata.setdefault("summary_text", summary_node.get_text(" ", strip=True))
            for key, options in self._metadata_selectors.items():
                value = self._extract_metadata(element, options)
                if value is not None:
                    metadata[key] = value
            results.append(
                RawListingItem(
                    url=href,
                    content=str(element),
                    metadata=metadata,
                )
            )
        return results

    def _extract_metadata(self, element: HTMLNode, options: Mapping[str, object]) -> object | None:
        selector = str(options.get("selector", "")).strip()
        if not selector:
            return None
        attr = options.get("attr")
        collect_all = bool(options.get("all"))
        if collect_all:
            nodes = element.select(selector)
        else:
            node = element.select_one(selector)
            nodes = [node] if node else []
        if not nodes:
            return None
        values: list[object] = []
        for node in nodes:
            if attr == "html":
                values.append(str(node))
            elif isinstance(attr, str) and attr:
                values.append(node.get(attr))
            else:
                values.append(node.get_text(" ", strip=True))
        if collect_all:
            return tuple(value for value in values if value is not None)
        return next((value for value in values if value is not None), None)


class SoupArticleParser(Parser):
    """Parser de artigos baseado no parser HTML interno."""

    def __init__(
        self,
        *,
        body_selector: str,
        title_selector: str | None = None,
        metadata_selectors: Mapping[str, Mapping[str, object] | str] | None = None,
    ) -> None:
        self._body_selector = body_selector
        self._title_selector = title_selector
        self._metadata_selectors = {
            key: (value if isinstance(value, Mapping) else {"selector": value})
            for key, value in (metadata_selectors or {}).items()
        }

    def parse(self, item: RawListingItem) -> RawArticle:
        soup = HTMLDocument.from_html(item.content)
        body_node = soup.select_one(self._body_selector)
        if not body_node:
            raise ParseError("Não foi possível localizar o corpo do artigo")

        metadata = dict(item.metadata)
        if self._title_selector:
            title_node = soup.select_one(self._title_selector)
            if title_node and (title_text := title_node.get_text(" ", strip=True)):
                metadata.setdefault("title", title_text)
        for key, options in self._metadata_selectors.items():
            value = self._extract_metadata(soup, options)
            if value is not None:
                metadata[key] = value

        title_value = metadata.get("title")
        if title_value is not None:
            title_value = str(title_value)

        return RawArticle(
            url=item.url,
            title=title_value,
            body=str(body_node),
            metadata=metadata,
        )

    def _extract_metadata(self, soup: HTMLDocument, options: Mapping[str, object]) -> object | None:
        selector = str(options.get("selector", "")).strip()
        if not selector:
            return None
        attr = options.get("attr")
        collect_all = bool(options.get("all"))
        if collect_all:
            nodes = soup.select(selector)
        else:
            node = soup.select_one(selector)
            nodes = [node] if node else []
        if not nodes:
            return None
        values: list[object] = []
        for node in nodes:
            if attr == "html":
                values.append(str(node))
            elif isinstance(attr, str) and attr:
                values.append(node.get(attr))
            else:
                values.append(node.get_text(" ", strip=True))
        if collect_all:
            return tuple(value for value in values if value is not None)
        return next((value for value in values if value is not None), None)


class RequestsSoupScraper(ScraperProtocol):
    """Implementação padrão do protocolo de scraper para portais HTML."""

    def __init__(
        self,
        *,
        client: Any,
        listing_parser: SoupListingParser,
        article_parser: Parser,
        url_normalizer: UrlNormalizer,
        pagination: Mapping[str, object] | None = None,
        request_timeout: float | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self._url_normalizer = url_normalizer
        self._listing_parser = listing_parser
        self._article_parser = article_parser
        self._fetcher = PaginatedHttpFetcher(
            client,
            timeout=request_timeout,
            headers=headers,
        )
        self._client = client
        self._pagination = pagination or {}
        self._request_timeout = request_timeout
        self._headers = dict(headers or {})

    def fetch_page(self, page: Mapping[str, object]) -> Iterable[ScrapedItem]:
        page_metadata = self._to_metadata(page.get("metadata"))
        page_url = str(page.get("url", ""))
        pagination = page.get("pagination") or self._pagination
        items: list[ScrapedItem] = []
        for listing_item in self.iter_listing(page_url, page_metadata, pagination):
            try:
                raw_article = self.fetch_and_parse_article(listing_item, page_metadata)
            except ParseError:
                raise
            except FetchError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise ParseError("Erro inesperado ao processar artigo", cause=exc) from exc

            metadata = dict(page_metadata)
            metadata.update(listing_item.metadata)
            metadata.update(raw_article.metadata)

            title = raw_article.title or metadata.get("title")
            summary_html = metadata.get("summary_html")
            tags = self._normalize_tags(metadata.get("tags"))
            published_at = metadata.get("published_at")
            published_str = str(published_at) if published_at is not None else None

            items.append(
                ScrapedItem(
                    url=raw_article.url,
                    title=str(title) if title is not None else None,
                    content_html=raw_article.body,
                    summary_html=str(summary_html) if summary_html is not None else None,
                    tags=tags,
                    published_at=published_str,
                    metadata=metadata,
                )
            )
        return items

    def iter_listing(
        self,
        page_url: str,
        page_metadata: Mapping[str, object],
        pagination: Mapping[str, object] | None,
    ) -> Iterable[RawListingItem]:
        fetched_pages = self._fetcher.fetch(page_url, pagination)
        normalized_items: list[RawListingItem] = []
        for fetched in fetched_pages:
            base_meta = dict(page_metadata)
            base_meta.update(fetched.metadata)
            for item in self._listing_parser.extract(
                fetched.html,
                base_url=fetched.url,
                page_metadata=base_meta,
            ):
                absolute_url = self._url_normalizer.to_absolute(item.url, fetched.url)
                metadata = dict(item.metadata)
                metadata.setdefault("page_url", fetched.url)
                normalized_items.append(
                    RawListingItem(
                        url=absolute_url,
                        content=item.content,
                        metadata=metadata,
                    )
                )
        return normalized_items

    def fetch_and_parse_article(
        self,
        listing_item: RawListingItem,
        page_metadata: Mapping[str, object],
    ) -> RawArticle:
        try:
            response = self._client.get(
                listing_item.url,
                timeout=self._request_timeout,
                headers=self._headers or None,
            )
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise FetchError("Falha ao buscar artigo", cause=exc) from exc

        html = getattr(response, "text", "")
        content_item = RawListingItem(
            url=listing_item.url,
            content=html,
            metadata={**page_metadata, **listing_item.metadata},
        )
        article = self._article_parser.parse(content_item)
        if not article.title and listing_item.metadata.get("title"):
            article.metadata.setdefault("title", listing_item.metadata["title"])
            article = RawArticle(
                url=article.url,
                title=str(listing_item.metadata["title"]),
                body=article.body,
                metadata=article.metadata,
            )
        return article

    def _normalize_tags(self, tags: object) -> tuple[str, ...]:
        if tags is None:
            return ()
        if isinstance(tags, str):
            return tuple(
                part.strip()
                for part in tags.split(",")
                if part and part.strip()
            )
        if isinstance(tags, Iterable) and not isinstance(tags, (bytes, str)):
            normalized = []
            for tag in tags:
                if tag is None:
                    continue
                cleaned = str(tag).strip()
                if cleaned:
                    normalized.append(cleaned)
            return tuple(normalized)
        return (str(tags),)

    def _to_metadata(self, metadata: object) -> Mapping[str, object]:
        if isinstance(metadata, Mapping):
            return dict(metadata)
        return {}


__all__ = [
    "PaginatedHttpFetcher",
    "RequestsSoupScraper",
    "SoupArticleParser",
    "SoupListingParser",
]
