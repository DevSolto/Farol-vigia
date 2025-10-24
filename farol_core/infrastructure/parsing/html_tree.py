"""Implementação simples de parsing HTML baseada em ``html.parser``."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser
from typing import Any, Iterable, Iterator


@dataclass
class HTMLNode:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    parent: HTMLNode | None = None
    children: list[HTMLNode | str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.tag

    def append_child(self, child: HTMLNode | str) -> None:
        if isinstance(child, HTMLNode):
            child.parent = self
        self.children.append(child)

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.attrs.get(key, default)

    def __getitem__(self, key: str) -> str:
        return self.attrs[key]

    def __setitem__(self, key: str, value: str) -> None:
        self.attrs[key] = value

    def __delitem__(self, key: str) -> None:
        if key in self.attrs:
            del self.attrs[key]

    def find_all(self, tags: Iterable[str] | bool = True) -> list[HTMLNode]:
        return list(self._find_all(tags))

    def _find_all(self, tags: Iterable[str] | bool) -> Iterator[HTMLNode]:
        tags_set: set[str] | None
        if tags is True:
            tags_set = None
        elif tags is False:
            return iter(())
        elif isinstance(tags, str):
            tags_set = {tags.lower()}
        else:
            tags_set = {str(tag).lower() for tag in tags}

        for node in self.iter_descendants(include_self=False):
            if tags_set is None or node.tag.lower() in tags_set:
                yield node

    def iter_descendants(self, *, include_self: bool = True) -> Iterator[HTMLNode]:
        if include_self and self.tag != "__root__":
            yield self
        for child in self.children:
            if isinstance(child, HTMLNode):
                yield from child.iter_descendants(include_self=True)

    def select(self, selector: str) -> list[HTMLNode]:
        parts = [_parse_selector(part) for part in selector.split() if part.strip()]
        if not parts:
            return []
        matches: list[HTMLNode] = []
        for node in self.iter_descendants(include_self=False):
            if _matches_selector(node, parts):
                matches.append(node)
        return matches

    def select_one(self, selector: str) -> HTMLNode | None:
        results = self.select(selector)
        return results[0] if results else None

    def get_text(self, separator: str = "", strip: bool = False) -> str:
        parts: list[str] = []
        _collect_text(self, parts)
        text = separator.join(parts)
        return text.strip() if strip else text

    def unwrap(self) -> None:
        if not self.parent:
            return
        index = self.parent.children.index(self)
        self.parent.children.pop(index)
        for child in reversed(self.children):
            self.parent.children.insert(index, child)

    def decompose(self) -> None:
        if not self.parent:
            return
        self.parent.children = [child for child in self.parent.children if child is not self]

    def __str__(self) -> str:
        return _node_to_html(self)


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HTMLNode("__root__")
        self.stack: list[HTMLNode] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = HTMLNode(tag, {k: v or "" for k, v in attrs})
        self.stack[-1].append_child(node)
        self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[: index]
                break

    def handle_data(self, data: str) -> None:
        if not data:
            return
        self.stack[-1].append_child(data)

    def handle_entityref(self, name: str) -> None:
        self.handle_data(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.handle_data(f"&#{name};")


@dataclass
class HTMLDocument:
    root: HTMLNode

    @classmethod
    def from_html(cls, html: str) -> HTMLDocument:
        parser = _TreeBuilder()
        parser.feed(html or "")
        parser.close()
        return cls(parser.root)

    def find_all(self, tags: Iterable[str] | bool = True) -> list[HTMLNode]:
        return self.root.find_all(tags)

    def select(self, selector: str) -> list[HTMLNode]:
        return self.root.select(selector)

    def select_one(self, selector: str) -> HTMLNode | None:
        return self.root.select_one(selector)

    def __call__(self, tags: Iterable[str] | bool = True) -> list[HTMLNode]:
        return self.find_all(tags)

    def __str__(self) -> str:
        return _node_children_to_html(self.root)


def _collect_text(node: HTMLNode, parts: list[str]) -> None:
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        else:
            _collect_text(child, parts)


def _node_to_html(node: HTMLNode) -> str:
    attrs = "".join(
        f' {key}="{escape(value, quote=True)}"'
        for key, value in node.attrs.items()
        if value is not None
    )
    inner = _node_children_to_html(node)
    return f"<{node.tag}{attrs}>{inner}</{node.tag}>"


def _node_children_to_html(node: HTMLNode) -> str:
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, HTMLNode):
            parts.append(_node_to_html(child))
        else:
            parts.append(child)
    return "".join(parts)


@dataclass
class _Selector:
    tag: str | None
    classes: tuple[str, ...]
    element_id: str | None


def _parse_selector(selector: str) -> _Selector:
    selector = selector.strip()
    tag: str | None = None
    classes: list[str] = []
    element_id: str | None = None
    i = 0
    length = len(selector)
    while i < length:
        prefix = selector[i]
        if prefix in {".", "#"}:
            i += 1
            start = i
            while i < length and selector[i] not in {".", "#"}:
                i += 1
            token = selector[start:i]
            if not token:
                continue
            if prefix == ".":
                classes.append(token)
            else:
                element_id = token
        else:
            start = i
            while i < length and selector[i] not in {".", "#"}:
                i += 1
            token = selector[start:i]
            if token:
                tag = token
    if tag == "":
        tag = None
    return _Selector(tag=tag, classes=tuple(classes), element_id=element_id)


def _matches_selector(node: HTMLNode, selectors: list[_Selector]) -> bool:
    current: HTMLNode | None = node
    for index, selector in enumerate(reversed(selectors)):
        if current is None or current.tag == "__root__":
            return False
        if index == 0:
            if not _matches_simple(current, selector):
                return False
            current = current.parent
            continue
        match_node = None
        while current is not None and current.tag != "__root__":
            if _matches_simple(current, selector):
                match_node = current
                current = current.parent
                break
            current = current.parent
        if match_node is None:
            return False
    return True


def _matches_simple(node: HTMLNode, selector: _Selector) -> bool:
    if selector.tag and node.tag.lower() != selector.tag.lower():
        return False
    if selector.element_id:
        node_id = node.attrs.get("id")
        if node_id != selector.element_id:
            return False
    if selector.classes:
        node_classes = set(node.attrs.get("class", "").split())
        if not all(cls in node_classes for cls in selector.classes):
            return False
    return True


__all__ = ["HTMLDocument", "HTMLNode"]
