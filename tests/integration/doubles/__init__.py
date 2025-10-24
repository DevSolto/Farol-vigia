"""Dobles utilizados pelos testes de integração da CLI."""

from __future__ import annotations

from collections.abc import Mapping

from .portal_components import (  # noqa: F401
    CREATED_COMPONENTS,
    build_date_normalizer,
    build_deduper,
    build_scraper,
    build_text_cleaner,
    build_url_normalizer,
    build_writer,
    reset_components,
)

__all__ = [
    "CREATED_COMPONENTS",
    "build_date_normalizer",
    "build_deduper",
    "build_scraper",
    "build_text_cleaner",
    "build_url_normalizer",
    "build_writer",
    "reset_components",
]
