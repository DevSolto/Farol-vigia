"""Contratos e estruturas de dados compartilhadas no domínio do Farol."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Mapping, MutableMapping, Protocol, Sequence


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
    content: str
    summary: str | None
    tags: Sequence[str]
    published_at: datetime | None
    metadata: Mapping[str, object] = field(default_factory=dict)


class Fetcher(Protocol):
    """Interface para componentes responsáveis por buscar dados."""

    def fetch(self) -> Iterable[RawListingItem]:
        """Recupera itens brutos a partir de uma fonte externa."""


class Parser(Protocol):
    """Interface para componentes que transformam itens da listagem em artigos brutos."""

    def parse(self, item: RawListingItem) -> RawArticle:
        """Realiza o parsing do conteúdo bruto."""


class Normalizer(Protocol):
    """Interface para normalização de artigos brutos em estrutura canônica."""

    def normalize(self, article: RawArticle) -> ArticleInput:
        """Normaliza o artigo para o formato esperado pelo sistema."""


class ArticleWriter(Protocol):
    """Interface para persistência de artigos normalizados."""

    def write(self, article: ArticleInput) -> str | None:
        """Persiste o artigo e retorna um identificador opcional."""


class Clock(Protocol):
    """Interface para abstrair o acesso ao relógio do sistema."""

    def now(self) -> datetime:
        """Retorna o instante atual."""
