"""Configuração de logging canônico para o Farol."""

from __future__ import annotations

import json
import logging
from logging import Logger, LogRecord


class StructuredFormatter(logging.Formatter):
    """Formatter que serializa o atributo ``extra`` caso exista."""

    def format(self, record: LogRecord) -> str:  # noqa: D401
        if not hasattr(record, "extra"):
            record.extra = {}  # type: ignore[attr-defined]
        elif not isinstance(record.extra, dict):  # type: ignore[attr-defined]
            record.extra = {"value": record.extra}  # type: ignore[attr-defined]
        record.extra = json.dumps(record.extra, ensure_ascii=False)  # type: ignore[attr-defined]
        return super().format(record)


def configure_logger(name: str = "farol") -> Logger:
    """Cria um logger com formatação estruturada simples."""

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    formatter = StructuredFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s | extra=%(extra)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger
