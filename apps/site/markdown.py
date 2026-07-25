"""Markdown → safe HTML.

Everything rendered here is authored by Siphira in admin, so this is a
formatting layer, not a sanitiser for hostile input. Raw HTML is nonetheless
disabled (`escape=True`) so a pasted snippet can't inject script tags by
accident.
"""
import functools

import mistune

_renderer = mistune.create_markdown(
    escape=True,
    plugins=['strikethrough', 'table', 'url', 'footnotes'],
)


@functools.lru_cache(maxsize=256)
def _render_cached(text):
    return _renderer(text)


def render(text):
    if not text:
        return ''
    return _render_cached(text)
