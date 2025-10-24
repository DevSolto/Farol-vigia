import json
from datetime import datetime

import pytest

from farol_core.interfaces import cli


class _LoggerStub:
    def __init__(self) -> None:
        self.info_calls: list[tuple[str, dict[str, object]]] = []

    def info(self, message: str, *, extra: dict[str, object]) -> None:
        self.info_calls.append((message, extra))

    def debug(
        self, message: str, *, extra: dict[str, object]
    ) -> None:  # pragma: no cover
        raise AssertionError("debug não deveria ser chamado em dry-run")

    def error(
        self, message: str, *, extra: dict[str, object]
    ) -> None:  # pragma: no cover
        raise AssertionError("error não deveria ser chamado em dry-run")

    def exception(
        self, message: str, *, extra: dict[str, object]
    ) -> None:  # pragma: no cover
        raise AssertionError("exception não deveria ser chamado em dry-run")


class _ClockStub:
    def __init__(self) -> None:
        self._now = datetime(2024, 1, 1, 10, 30, 0)

    def now(self) -> datetime:
        return self._now


def test_cli_main_dry_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    logger = _LoggerStub()
    monkeypatch.setattr(cli, "configure_logger", lambda: logger)
    monkeypatch.setattr(cli, "SystemClock", lambda: _ClockStub())

    exit_code = cli.main(["--dry-run"])

    assert exit_code == 0

    captured = capsys.readouterr()
    assert json.loads(captured.out) == []

    messages = [message for message, _ in logger.info_calls]
    assert "cli.start" in messages
    assert "cli.finish" in messages
