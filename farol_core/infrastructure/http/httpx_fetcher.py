"""Adapter de busca baseado em httpx."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from farol_core.domain.contracts import Fetcher, RawListingItem
from farol_core.domain.errors import FetchError


class HttpxFetcher(Fetcher):
    """Implementação de ``Fetcher`` usando um cliente httpx síncrono."""

    def __init__(self, client: Any, url: str, *, item_key: str = "items") -> None:
        self._client = client
        self._url = url
        self._item_key = item_key

    def fetch(self) -> Iterable[RawListingItem]:
        try:
            response = self._client.get(self._url)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise FetchError("Falha ao buscar listagem remota", cause=exc) from exc

        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise FetchError(
                "Resposta inválida ao decodificar JSON", cause=exc
            ) from exc

        items_data = self._extract_items(payload)
        return [self._build_item(entry) for entry in items_data]

    def _extract_items(self, payload: object) -> list[Mapping[str, object]]:
        if isinstance(payload, Mapping):
            items = payload.get(self._item_key)
        else:
            items = payload

        if not isinstance(items, list):
            raise FetchError("Formato inesperado da listagem remota")

        valid_items: list[Mapping[str, object]] = []
        for entry in items:
            if isinstance(entry, Mapping):
                valid_items.append(entry)
        return valid_items

    def _build_item(self, entry: Mapping[str, object]) -> RawListingItem:
        try:
            url = str(entry["url"])
            content = str(entry.get("content", ""))
        except KeyError as exc:
            raise FetchError(
                "Item da listagem sem campo obrigatório", cause=exc
            ) from exc

        metadata = {k: v for k, v in entry.items() if k not in {"url", "content"}}
        return RawListingItem(url=url, content=content, metadata=metadata)
