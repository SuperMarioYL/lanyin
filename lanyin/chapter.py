"""Markdown → Chapter[] parsing (markdown-it-py).

``##`` headings become chapter marks. This is the chapter half of episode
assembly — a pure, deterministic helper exercised by ``lanyin add`` (preview)
and ``lanyin build`` (m2, where offsets are filled from the synthesized audio).
"""

from __future__ import annotations

from pathlib import Path

from markdown_it import MarkdownIt

from .models import Chapter


def parse_chapters(markdown_text: str, *, heading_level: int = 2) -> list[Chapter]:
    """Parse ``markdown_text``; return one ``Chapter`` per heading.

    Headings at the configured level (default ``##``) become chapter titles;
    offsets are left at 0.0 — they are filled by ``synth`` once the audio is
    generated (m2). Plain-text + inline-formatted headings are supported; the
    raw Markdown syntax is stripped so the title reads cleanly in a chapter
    list.
    """
    md = MarkdownIt("commonmark")
    tokens = md.parse(markdown_text)
    tag = f"h{heading_level}"
    chapters: list[Chapter] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open" and tok.tag == tag:
            if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                title = _inline_text(tokens[i + 1]).strip()
                if title:
                    chapters.append(Chapter(title=title))
        i += 1
    return chapters


def parse_markdown_file(path: Path | str, *, heading_level: int = 2) -> list[Chapter]:
    """Read a ``.md`` file and return its chapters."""
    text = Path(path).read_text(encoding="utf-8")
    return parse_chapters(text, heading_level=heading_level)


def _inline_text(tok) -> str:
    """Join the text children of an inline token, dropping raw syntax."""
    if tok.children:
        return "".join(
            c.content
            for c in tok.children
            if c.type in ("text", "code_inline", "text_special")
        )
    return tok.content or ""
