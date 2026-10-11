"""Markdown → Chapter[] parsing (markdown-it-py).

``##`` headings become chapter marks. This is the chapter half of episode
assembly — a pure, deterministic helper exercised by ``lanyin add`` (preview)
and ``lanyin build`` (``parse_sections`` slices the episode into per-chapter
text for synthesis).
"""

from __future__ import annotations

from pathlib import Path

from markdown_it import MarkdownIt

from .models import Chapter


class ChapterError(Exception):
    """Raised when an episode file cannot be read or parsed as markdown."""


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
    """Read a ``.md`` file and return its chapters.

    A file that is not valid UTF-8 (e.g. a GBK export) raises
    ``ChapterError`` — a clean one-line error, never a raw traceback.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ChapterError(
            f"cannot read {path} as valid UTF-8 markdown: {exc}"
        ) from exc
    return parse_chapters(text, heading_level=heading_level)


def parse_sections(
    markdown_text: str, *, heading_level: int = 2
) -> list[tuple[str, str]]:
    """Split markdown into ``(title, text)`` sections at the configured level.

    Each section runs from its heading line to just before the next heading at
    the same level (original markdown preserved verbatim), so the synthesized
    audio reads the chapter title then its body. Text before the first heading
    (a preamble) is prepended to the first section so no content is silently
    dropped; a document with no headings at the configured level is returned as
    a single ``("", text)`` section (the caller names it from the file stem).
    """
    md = MarkdownIt("commonmark")
    tokens = md.parse(markdown_text)
    tag = f"h{heading_level}"
    lines = markdown_text.splitlines()

    marks: list[tuple[str, int, int]] = []  # (title, start_line, end_line)
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.tag == tag and tok.map:
            title = ""
            if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                title = _inline_text(tokens[i + 1]).strip()
            if title:
                marks.append((title, tok.map[0], tok.map[1]))

    if not marks:
        text = markdown_text.strip()
        return [("", text)] if text else []

    sections: list[tuple[str, str]] = []
    preamble = "\n".join(lines[: marks[0][1]]).strip()
    for idx, (title, start, _end) in enumerate(marks):
        body_end = marks[idx + 1][1] if idx + 1 < len(marks) else len(lines)
        text = "\n".join(lines[start:body_end]).strip()
        if idx == 0 and preamble:
            text = preamble + "\n\n" + text
        sections.append((title, text))
    return sections


def _inline_text(tok) -> str:
    """Join the text children of an inline token, dropping raw syntax."""
    if tok.children:
        return "".join(
            c.content
            for c in tok.children
            if c.type in ("text", "code_inline", "text_special")
        )
    return tok.content or ""
