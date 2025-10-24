"""Contratos e estruturas de dados compartilhadas no domínio do Farol."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from typing import Protocol


@dataclass(slots=True)
class RawListingItem:
    """Item bruto retornado pelo coletor da listagem principal."""

    url: str
    content: str
    metadata: MutableMapping[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class RawArticle:
    """Artigo bruto após o parsing do conteúdo HTML."""

    url: str
    title: str | None
    body: str
    metadata: MutableMapping[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ArticleInput:
    """Entrada canônica para persistir um artigo normalizado."""

    url: str
    title: str
    portal_name: str
    summary: str | None
    content_html: str
    content_text: str
    tags: Sequence[str]
    published_at_raw: str | None
    published_at: datetime | None
    collected_at: datetime
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ArticleWriteResult:
    """Representa o resultado da tentativa de gravação de um artigo."""

    status: Literal["inserted", "updated"]
    article_id: str | None = None


class Fetcher(Protocol):
    """Interface para componentes responsáveis por buscar dados."""

    def fetch(self) -> Iterable[RawListingItem]:
        """Recupera itens brutos a partir de uma fonte externa."""


class Parser(Protocol):
    """Interface para transformar itens da listagem em artigos brutos."""

    def parse(self, item: RawListingItem) -> RawArticle:
        """Realiza o parsing do conteúdo bruto."""


class Normalizer(Protocol):
    """Interface para normalização de artigos brutos em estrutura canônica."""

    def normalize(self, article: RawArticle) -> ArticleInput:
        """Normaliza o artigo para o formato esperado pelo sistema."""


class ArticleWriter(Protocol):
    """Interface para persistência de artigos normalizados."""

    def write(self, article: ArticleInput, fingerprint: str) -> ArticleWriteResult:
        """Persiste o artigo retornando o status da operação."""


class Clock(Protocol):
    """Interface para abstrair o acesso ao relógio do sistema."""

    def now(self) -> datetime:
        """Retorna o instante atual."""


class UrlNormalizer(Protocol):
    """Interface responsável por normalizar URLs relativas."""

    def to_absolute(self, url: str, base_url: str | None = None) -> str:
        """Converte uma URL possivelmente relativa em absoluta."""


class TextCleaner(Protocol):
    """Interface para sanitização e conversão de HTML em texto limpo."""

    def clean_html_to_text(self, html: str) -> str:
        """Remove marcações HTML retornando apenas o texto."""

    def sanitize_html(self, html: str) -> str:
        """Produz HTML seguro para exibição."""


class DateNormalizer(Protocol):
    """Interface para normalização de datas representadas como texto."""

    def parse(self, value: str, reference: datetime | None = None) -> datetime | None:
        """Interpreta uma data textual retornando um ``datetime`` normalizado."""


class Deduper(Protocol):
    """Interface responsável por detectar duplicatas de artigos."""

    def fingerprint(self, article: ArticleInput) -> str:
        """Gera um identificador de unicidade para um artigo."""

    def is_new(self, fingerprint: str) -> bool:
        """Indica se o identificador fornecido já foi visto anteriormente."""


__all__ = (
    "ArticleInput",
    "ArticleWriteResult",
    "ArticleWriter",
    "Clock",
    "DateNormalizer",
    "Deduper",
    "Fetcher",
    "Normalizer",
    "Parser",
    "RawArticle",
    "RawListingItem",
    "TextCleaner",
    "UrlNormalizer",
)
