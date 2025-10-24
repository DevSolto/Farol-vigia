"""Definições de exceções para o domínio do Farol."""

from __future__ import annotations


class FarolError(Exception):
    """Exceção base para erros conhecidos da aplicação."""

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class FetchError(FarolError):
    """Erro ocorrido durante a busca de dados."""


class ParseError(FarolError):
    """Erro ocorrido durante o parsing dos dados."""


class NormalizeError(FarolError):
    """Erro ocorrido durante a normalização dos dados."""


class WriteError(FarolError):
    """Erro ocorrido durante a escrita dos dados no armazenamento."""
