"""Composition root CLI para executar o caso de uso de coleta."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from config.settings import Settings, load_settings
from farol_core.application.collect_usecase import CollectUseCase
from farol_core.domain.errors import FarolError
from farol_core.infrastructure.logging.logger import configure_logger
from farol_core.infrastructure.time.system_clock import SystemClock


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Executor do coletor Farol")
    parser.add_argument(
        "configs",
        nargs="*",
        help="Arquivos de configuração JSON de portais.",
    )
    parser.add_argument(
        "--portals-dir",
        help="Diretório contendo configurações de portais (busca recursiva).",
    )
    parser.add_argument(
        "--pages",
        help="JSON com lista de páginas que sobrescreve as configurações.",
    )
    parser.add_argument(
        "--since",
        help="Valor repassado para os scrapers como referência temporal.",
    )
    parser.add_argument(
        "--skip-dedup",
        action="store_true",
        help="Desabilita a etapa de deduplicação de itens.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inicializa componentes sem executar o fluxo de coleta.",
    )
    return parser


@dataclass(slots=True)
class PortalComponentConfig:
    name: str
    factory: str
    options: Mapping[str, object]

    @classmethod
    def from_mapping(cls, name: str, data: Mapping[str, object]) -> "PortalComponentConfig":
        factory = data.get("factory")
        if not isinstance(factory, str) or not factory.strip():
            raise RuntimeError(
                f"Configuração do componente '{name}' inválida: campo 'factory' obrigatório"
            )
        options_raw = data.get("options", {})
        if not isinstance(options_raw, Mapping):
            raise RuntimeError(
                f"Configuração do componente '{name}' inválida: 'options' deve ser um objeto"
            )
        return cls(name=name, factory=factory, options=dict(options_raw))


@dataclass(slots=True)
class PortalConfig:
    name: str
    logger_name: str
    pages: Sequence[Mapping[str, object]]
    components: Mapping[str, PortalComponentConfig]
    metadata: Mapping[str, object]
    source: Path

    REQUIRED_COMPONENTS = (
        "scraper",
        "url_normalizer",
        "date_normalizer",
        "text_cleaner",
        "deduper",
        "writer",
    )

    @classmethod
    def load(cls, path: Path) -> "PortalConfig":
        data = json.loads(path.read_text("utf-8"))
        if not isinstance(data, Mapping):
            raise RuntimeError(
                f"Conteúdo inválido no arquivo de portal '{path}': esperado objeto JSON"
            )
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise RuntimeError(
                f"Configuração inválida no arquivo '{path}': campo 'name' obrigatório"
            )
        logger_name = data.get("logger")
        if not isinstance(logger_name, str) or not logger_name.strip():
            logger_name = f"farol.portal.{name.strip().lower()}"

        pages_raw = data.get("pages", [])
        if not isinstance(pages_raw, Sequence):
            raise RuntimeError(
                f"Configuração inválida no arquivo '{path}': campo 'pages' deve ser uma lista"
            )
        pages: list[Mapping[str, object]] = []
        for index, page in enumerate(pages_raw, start=1):
            if not isinstance(page, Mapping):
                raise RuntimeError(
                    f"Configuração inválida no arquivo '{path}': página #{index} deve ser um objeto"
                )
            pages.append(dict(page))

        components_raw = data.get("components")
        if not isinstance(components_raw, Mapping):
            raise RuntimeError(
                f"Configuração inválida no arquivo '{path}': campo 'components' obrigatório"
            )
        components: dict[str, PortalComponentConfig] = {}
        for required in cls.REQUIRED_COMPONENTS:
            raw_component = components_raw.get(required)
            if not isinstance(raw_component, Mapping):
                raise RuntimeError(
                    f"Configuração inválida no arquivo '{path}': componente '{required}' ausente"
                )
            components[required] = PortalComponentConfig.from_mapping(required, raw_component)

        metadata_raw = data.get("metadata", {})
        if not isinstance(metadata_raw, Mapping):
            raise RuntimeError(
                f"Configuração inválida no arquivo '{path}': campo 'metadata' deve ser um objeto"
            )

        return cls(
            name=name.strip(),
            logger_name=logger_name,
            pages=tuple(pages),
            components=components,
            metadata=dict(metadata_raw),
            source=path,
        )

    def build_use_case(
        self,
        *,
        settings: Settings,
        clock: SystemClock,
        logger,
        pages_override: Sequence[Mapping[str, object]] | None,
        since: str | None,
        skip_dedup: bool,
    ) -> CollectUseCase:
        pages = self._build_pages(pages_override)
        scraper = self._build_component(
            "scraper",
            settings=settings,
            pages=pages,
            since=since,
        )
        url_normalizer = self._build_component("url_normalizer", settings=settings)
        date_normalizer = self._build_component("date_normalizer", settings=settings)
        text_cleaner = self._build_component("text_cleaner", settings=settings)
        deduper = self._build_deduper(settings=settings, skip_dedup=skip_dedup)
        writer = self._build_component("writer", settings=settings)

        return CollectUseCase(
            scraper,
            pages=pages,
            url_normalizer=url_normalizer,
            date_normalizer=date_normalizer,
            text_cleaner=text_cleaner,
            deduper=deduper,
            writer=writer,
            clock=clock,
            logger=logger,
        )

    def _build_pages(
        self, override: Sequence[Mapping[str, object]] | None
    ) -> Sequence[Mapping[str, object]]:
        chosen = override if override is not None else self.pages
        result: list[Mapping[str, object]] = []
        for index, page in enumerate(chosen, start=1):
            if not isinstance(page, Mapping):
                raise RuntimeError(
                    f"Página #{index} inválida para o portal '{self.name}': deve ser um objeto"
                )
            page_dict = dict(page)
            metadata = page_dict.get("metadata", {})
            if metadata is None:
                metadata = {}
            if not isinstance(metadata, Mapping):
                raise RuntimeError(
                    f"Metadados da página #{index} inválidos para o portal '{self.name}'"
                )
            metadata_dict = {**self.metadata, **dict(metadata)}
            metadata_dict.setdefault("portal_name", self.name)
            page_dict["metadata"] = metadata_dict
            result.append(page_dict)
        return tuple(result)

    def _build_component(
        self,
        component_name: str,
        *,
        settings: Settings,
        pages: Sequence[Mapping[str, object]] | None = None,
        since: str | None = None,
    ) -> Any:
        component_cfg = self.components[component_name]
        factory = _import_from_string(component_cfg.factory)
        options = dict(component_cfg.options)
        options.setdefault("portal", self)
        options.setdefault("settings", settings)
        if pages is not None:
            options.setdefault("pages", pages)
        if since is not None:
            options.setdefault("since", since)
        try:
            return factory(**options)
        except TypeError as exc:  # pragma: no cover - validação adicional
            raise RuntimeError(
                f"Falha ao instanciar componente '{component_name}' do portal '{self.name}'"
            ) from exc

    def _build_deduper(self, *, settings: Settings, skip_dedup: bool) -> Any:
        if skip_dedup:
            return _NullDeduper()
        return self._build_component("deduper", settings=settings)


class _NullDeduper:
    def fingerprint(self, article: Any) -> str:  # pragma: no cover - simples
        return f"noop:{getattr(article, 'url', '')}"

    def is_new(self, fingerprint: str) -> bool:  # pragma: no cover - simples
        return True


def main(argv: Sequence[str] | None = None) -> int:
    arg_parser = _build_parser()
    args = arg_parser.parse_args(argv)

    settings = load_settings()
    logger = configure_logger()
    clock = SystemClock()

    logger.info("cli.start", extra={"extra": {"at": clock.now().isoformat()}})

    if args.dry_run:
        logger.info("cli.dry_run", extra={"extra": {"at": clock.now().isoformat()}})
        print(json.dumps([], ensure_ascii=False, indent=2))
        logger.info(
            "cli.finish",
            extra={
                "extra": {
                    "at": clock.now().isoformat(),
                    "count": 0,
                    "dry_run": True,
                }
            },
        )
        return 0

    try:
        portal_configs = _load_portal_configs(args.configs, args.portals_dir)
    except RuntimeError as exc:
        logger.exception("cli.config_error", extra={"extra": {"error": str(exc)}})
        return 1

    pages_override = None
    if args.pages is not None:
        try:
            loaded = json.loads(args.pages)
        except json.JSONDecodeError as exc:  # noqa: PERF203 - entrada externa
            logger.exception(
                "cli.pages_invalid", extra={"extra": {"error": exc.msg}}
            )
            return 1
        if not isinstance(loaded, list):
            logger.error(
                "cli.pages_invalid", extra={"extra": {"error": "esperado lista"}}
            )
            return 1
        pages_override = loaded

    results: list[Mapping[str, object]] = []
    exit_code = 0

    for portal_config in portal_configs:
        portal_logger = configure_logger(portal_config.logger_name)
        portal_logger.info(
            "cli.portal.start",
            extra={
                "extra": {
                    "at": clock.now().isoformat(),
                    "portal": portal_config.name,
                    "source": str(portal_config.source),
                }
            },
        )
        try:
            use_case = portal_config.build_use_case(
                settings=settings,
                clock=clock,
                logger=portal_logger,
                pages_override=pages_override,
                since=args.since,
                skip_dedup=args.skip_dedup,
            )
            result = use_case.execute()
        except FarolError as exc:
            portal_logger.exception(
                "cli.portal.error",
                extra={"extra": {"error": exc.__class__.__name__}},
            )
            exit_code = 1
            continue
        except RuntimeError as exc:
            portal_logger.exception(
                "cli.portal.error",
                extra={"extra": {"error": str(exc)}},
            )
            exit_code = 1
            continue

        results.append({"portal": portal_config.name, "result": result})
        portal_logger.info(
            "cli.portal.finish",
            extra={
                "extra": {
                    "at": clock.now().isoformat(),
                    "portal": portal_config.name,
                    "processed": result.get("metrics", {}).get("processed"),
                }
            },
        )

    print(json.dumps(results, ensure_ascii=False, indent=2))
    logger.info(
        "cli.finish",
        extra={
            "extra": {
                "at": clock.now().isoformat(),
                "count": len(results),
                "dry_run": False,
            }
        },
    )
    return exit_code


def _load_portal_configs(
    config_paths: Sequence[str], portals_dir: str | None
) -> Sequence[PortalConfig]:
    paths: list[Path] = []
    for entry in config_paths:
        path = Path(entry)
        if not path.is_file():
            raise RuntimeError(f"Arquivo de configuração inexistente: {entry}")
        paths.append(path)

    if portals_dir:
        dir_path = Path(portals_dir)
        if not dir_path.exists():
            raise RuntimeError(f"Diretório de portais inexistente: {portals_dir}")
        for file_path in dir_path.rglob("*.json"):
            if file_path.is_file():
                paths.append(file_path)

    if not paths:
        raise RuntimeError("Nenhum portal informado")

    unique_paths = []
    seen: set[Path] = set()
    for path in paths:
        if path not in seen:
            unique_paths.append(path)
            seen.add(path)

    return [PortalConfig.load(path) for path in unique_paths]


def _import_from_string(path: str) -> Any:
    module_name, sep, attr = path.partition(":")
    if not sep:
        module_name, _, attr = path.rpartition(".")
    if not module_name or not attr:
        raise RuntimeError(f"Caminho de importação inválido: '{path}'")
    module = import_module(module_name)
    try:
        return getattr(module, attr)
    except AttributeError as exc:  # pragma: no cover - proteção adicional
        raise RuntimeError(f"Atributo '{attr}' não encontrado em '{module_name}'") from exc


if __name__ == "__main__":  # pragma: no cover - entrypoint manual
    raise SystemExit(main())
