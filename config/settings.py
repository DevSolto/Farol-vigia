"""Carregamento de configurações para o serviço Farol."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Mapping, Sequence


@dataclass(slots=True)
class HttpSettings:
    listing_url: str
    item_key: str = "items"


@dataclass(slots=True)
class ParserSettings:
    selectors: Mapping[str, str]


@dataclass(slots=True)
class DatabaseSettings:
    uri: str
    name: str
    collection: str


@dataclass(slots=True)
class ApplicationSettings:
    default_tags: Sequence[str] = field(default_factory=tuple)
    fallback_title: str = "Sem título"


@dataclass(slots=True)
class Settings:
    http: HttpSettings
    parser: ParserSettings
    database: DatabaseSettings
    application: ApplicationSettings


def _load_json(value: str | None, *, default: Mapping[str, str] | None = None) -> Mapping[str, str]:
    if not value:
        return default or {}
    try:
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError
        return {str(k): str(v) for k, v in parsed.items()}
    except ValueError as exc:  # noqa: PERF203 - trata entrada malformada
        raise RuntimeError("Variável de ambiente de seletores inválida") from exc


def _load_tags(value: str | None) -> Sequence[str]:
    if not value:
        return ()
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(tag) for tag in parsed]
    except json.JSONDecodeError:
        pass
    return tuple(tag.strip() for tag in value.split(",") if tag.strip())


def load_settings() -> Settings:
    """Carrega configurações a partir de variáveis de ambiente."""

    http = HttpSettings(
        listing_url=os.environ.get("FAROL_LISTING_URL", "https://example.com/listing"),
        item_key=os.environ.get("FAROL_LISTING_ITEM_KEY", "items"),
    )

    parser = ParserSettings(
        selectors=_load_json(
            os.environ.get("FAROL_PARSER_SELECTORS"),
            default={"title": "h1", "body": "article"},
        )
    )

    database = DatabaseSettings(
        uri=os.environ.get("FAROL_MONGODB_URI", "mongodb://localhost:27017"),
        name=os.environ.get("FAROL_MONGODB_DB", "farol"),
        collection=os.environ.get("FAROL_MONGODB_COLLECTION", "articles"),
    )

    application = ApplicationSettings(
        default_tags=_load_tags(os.environ.get("FAROL_DEFAULT_TAGS")),
        fallback_title=os.environ.get("FAROL_FALLBACK_TITLE", "Sem título"),
    )

    return Settings(http=http, parser=parser, database=database, application=application)
