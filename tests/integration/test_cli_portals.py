from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable

import pytest

from farol_core.interfaces import cli
from tests.integration.doubles import CREATED_COMPONENTS, reset_components


class _LoggerStub:
    def __init__(self, name: str) -> None:
        self.name = name
        self.info_calls: list[tuple[str, dict[str, object]]] = []
        self.error_calls: list[tuple[str, dict[str, object]]] = []
        self.exception_calls: list[tuple[str, dict[str, object]]] = []

    def info(self, message: str, *, extra: dict[str, object]) -> None:
        self.info_calls.append((message, extra))

    def error(self, message: str, *, extra: dict[str, object]) -> None:
        self.error_calls.append((message, extra))

    def exception(self, message: str, *, extra: dict[str, object]) -> None:
        self.exception_calls.append((message, extra))


class _ClockStub:
    def __init__(self) -> None:
        self._now = datetime(2024, 1, 1, 12, 0, 0)

    def now(self) -> datetime:
        return self._now


def _configure_logger_stub() -> tuple[dict[str, _LoggerStub], Callable[[str], _LoggerStub]]:
    loggers: dict[str, _LoggerStub] = {}

    def factory(name: str = "farol") -> _LoggerStub:
        if name not in loggers:
            loggers[name] = _LoggerStub(name)
        return loggers[name]

    return loggers, factory


def _write_portal_config(
    base_dir: Path,
    *,
    name: str,
    pages: list[dict[str, object]],
    items: dict[str, list[dict[str, object]]],
    deduper_options: dict[str, object] | None = None,
) -> Path:
    config = {
        "name": name,
        "logger": f"test.{name.lower()}",
        "pages": pages,
        "metadata": {"segment": "test"},
        "components": {
            "scraper": {
                "factory": "tests.integration.doubles:build_scraper",
                "options": {"items": items},
            },
            "url_normalizer": {
                "factory": "tests.integration.doubles:build_url_normalizer"
            },
            "date_normalizer": {
                "factory": "tests.integration.doubles:build_date_normalizer"
            },
            "text_cleaner": {
                "factory": "tests.integration.doubles:build_text_cleaner"
            },
            "deduper": {
                "factory": "tests.integration.doubles:build_deduper",
                "options": deduper_options or {},
            },
            "writer": {
                "factory": "tests.integration.doubles:build_writer"
            },
        },
    }
    path = base_dir / f"{name}.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_cli_processa_multiplos_portais(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reset_components()
    logger_registry, logger_factory = _configure_logger_stub()
    monkeypatch.setattr(cli, "configure_logger", logger_factory)
    monkeypatch.setattr(cli, "SystemClock", lambda: _ClockStub())

    portal_a = _write_portal_config(
        tmp_path,
        name="PortalA",
        pages=[{"url": "https://example.com/a"}],
        items={
            "https://example.com/a": [
                {
                    "url": "/item-a",
                    "title": "Item A",
                    "content_html": "<p>conteudo A</p>",
                    "published_at": "2024-01-01T09:00:00",
                }
            ]
        },
    )
    portal_b = _write_portal_config(
        tmp_path,
        name="PortalB",
        pages=[{"url": "https://example.com/b"}],
        items={
            "https://example.com/b": [
                {
                    "url": "/item-b",
                    "title": "Item B",
                    "content_html": "<p>conteudo B</p>",
                }
            ]
        },
    )

    exit_code = cli.main([str(portal_a), str(portal_b)])

    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert [entry["portal"] for entry in payload] == ["PortalA", "PortalB"]
    assert payload[0]["result"]["metrics"]["processed"] == 1
    assert payload[1]["result"]["metrics"]["processed"] == 1

    assert "PortalA" in CREATED_COMPONENTS and "PortalB" in CREATED_COMPONENTS
    assert "scraper" in CREATED_COMPONENTS["PortalA"]
    assert "writer" in CREATED_COMPONENTS["PortalB"]

    assert any(
        message == "cli.portal.finish"
        for message, _ in logger_registry["test.portala"].info_calls
    )


def test_cli_override_de_paginas(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    reset_components()
    _, logger_factory = _configure_logger_stub()
    monkeypatch.setattr(cli, "configure_logger", logger_factory)
    monkeypatch.setattr(cli, "SystemClock", lambda: _ClockStub())

    portal = _write_portal_config(
        tmp_path,
        name="PortalPages",
        pages=[{"url": "https://example.com/default", "metadata": {"section": "default"}}],
        items={},
    )

    override_pages = [
        {"url": "https://override.com/page", "metadata": {"section": "override"}}
    ]

    exit_code = cli.main([str(portal), "--pages", json.dumps(override_pages)])

    assert exit_code == 0

    scraper = CREATED_COMPONENTS["PortalPages"]["scraper"]
    assert [page["url"] for page in scraper.pages] == ["https://override.com/page"]
    assert scraper.pages[0]["metadata"]["portal_name"] == "PortalPages"
    assert scraper.pages[0]["metadata"]["section"] == "override"


def test_cli_skip_dedup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reset_components()
    _, logger_factory = _configure_logger_stub()
    monkeypatch.setattr(cli, "configure_logger", logger_factory)
    monkeypatch.setattr(cli, "SystemClock", lambda: _ClockStub())

    portal = _write_portal_config(
        tmp_path,
        name="PortalDedup",
        pages=[{"url": "https://example.com/dedup"}],
        items={
            "https://example.com/dedup": [
                {
                    "url": "/item-1",
                    "title": "Mesmo título",
                    "content_html": "<p>conteudo 1</p>",
                },
                {
                    "url": "/item-2",
                    "title": "Mesmo título",
                    "content_html": "<p>conteudo 2</p>",
                },
            ]
        },
        deduper_options={"fingerprint_field": "title"},
    )

    exit_code = cli.main([str(portal), "--skip-dedup"])

    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload[0]["result"]["metrics"]["processed"] == 2
    assert "deduper" not in CREATED_COMPONENTS["PortalDedup"]

