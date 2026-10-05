"""
Packs strings into one HTML document and splits the translated document apart.

Every string travels as ``<div data-st-id="N">…</div>``. Supertext translates each such
element as a unit and keeps markup and attributes, so a wagtail-localize string (a whole
paragraph with its ``<b>``, ``<i>`` and ``<a id="a1">`` tags) is translated as one sentence.
"""

from __future__ import annotations

from bs4 import BeautifulSoup


def build(strings: list[str]) -> str:
    """``strings`` are HTML fragments (wagtail-localize StringValue.data)."""
    body = "".join(f'<div data-st-id="{i}">{html}</div>\n' for i, html in enumerate(strings))
    return f'<!DOCTYPE html>\n<html><head><meta charset="utf-8"></head><body>\n{body}</body></html>'


def parse(html: str) -> dict[int, str]:
    """Returns segment id -> translated inner HTML (whitespace at the ends trimmed)."""
    soup = BeautifulSoup(html, "html.parser")
    out: dict[int, str] = {}
    for element in soup.find_all(attrs={"data-st-id": True}):
        try:
            index = int(element["data-st-id"])
        except (TypeError, ValueError):
            continue
        out[index] = element.decode_contents().strip()
    return out


def chunks(strings: list[str], limit: int) -> list[list[int]]:
    """Indexes of ``strings`` grouped so each group's text stays below ``limit`` characters."""
    groups: list[list[int]] = [[]]
    size = 0
    for index, text in enumerate(strings):
        if groups[-1] and size + len(text) > limit:
            groups.append([])
            size = 0
        groups[-1].append(index)
        size += len(text)
    return groups
