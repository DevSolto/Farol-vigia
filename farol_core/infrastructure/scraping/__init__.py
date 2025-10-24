"""Componentes para scrapers baseados em requests e parsing HTML leve."""

from .requests_soup_scraper import (
    PaginatedHttpFetcher,
    RequestsSoupScraper,
    SoupArticleParser,
    SoupListingParser,
)

__all__ = [
    "PaginatedHttpFetcher",
    "RequestsSoupScraper",
    "SoupArticleParser",
    "SoupListingParser",
]
