"""Composition root CLI para executar o caso de uso de coleta."""

from __future__ import annotations

import json
from contextlib import ExitStack
from typing import TYPE_CHECKING, Tuple

from farol_core.application.collect_usecase import CollectUseCase
from farol_core.domain.errors import FarolError
from farol_core.infrastructure.db.mongo_writer import MongoArticleWriter
from farol_core.infrastructure.http.httpx_fetcher import HttpxFetcher
from farol_core.infrastructure.logging.logger import configure_logger
from farol_core.infrastructure.parsing.normalizer import SimpleNormalizer
from farol_core.infrastructure.parsing.selectolax_parser import SelectolaxParser
from farol_core.infrastructure.time.system_clock import SystemClock
from config.settings import load_settings

if TYPE_CHECKING:  # pragma: no cover - dicas de tipo
    import httpx
    from pymongo.collection import Collection
    from pymongo.mongo_client import MongoClient


def main() -> int:
    settings = load_settings()
    logger = configure_logger()
    clock = SystemClock()

    logger.info("cli.start", extra={"extra": {"at": clock.now().isoformat()}})

    with ExitStack() as stack:
        http_client = _build_http_client()
        stack.enter_context(http_client)

        mongo_client, collection = _build_mongo_collection(settings)
        stack.enter_context(mongo_client)

        fetcher = HttpxFetcher(
            http_client,
            settings.http.listing_url,
            item_key=settings.http.item_key,
        )
        parser = SelectolaxParser(settings.parser.selectors)
        normalizer = SimpleNormalizer(
            default_tags=settings.application.default_tags,
            fallback_title=settings.application.fallback_title,
        )
        writer = MongoArticleWriter(collection)

        use_case = CollectUseCase(
            fetcher=fetcher,
            parser=parser,
            normalizer=normalizer,
            writer=writer,
            clock=clock,
            logger=logger,
        )

        try:
            result = use_case.execute()
        except FarolError as exc:
            logger.exception(
                "cli.error", extra={"extra": {"error": exc.__class__.__name__}}
            )
            return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    logger.info(
        "cli.finish",
        extra={"extra": {"at": clock.now().isoformat(), "count": len(result)}},
    )
    return 0


def _build_http_client() -> "httpx.Client":
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - dependência externa
        raise RuntimeError("Biblioteca httpx não está instalada") from exc
    client = httpx.Client()
    return client


def _build_mongo_collection(settings) -> Tuple["MongoClient", "Collection"]:
    try:
        from pymongo import MongoClient
    except ImportError as exc:  # pragma: no cover - dependência externa
        raise RuntimeError("Biblioteca pymongo não está instalada") from exc

    client = MongoClient(settings.database.uri)
    collection = client[settings.database.name][settings.database.collection]
    return client, collection


if __name__ == "__main__":  # pragma: no cover - entrypoint manual
    raise SystemExit(main())
