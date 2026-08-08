"""Tests for the markdown → Chapter[] parser (pure, no network)."""

from __future__ import annotations

from pathlib import Path

from lanyin.chapter import parse_chapters, parse_markdown_file


SAMPLE = """# 栏目标题

## 第一章 开篇
正文段落一。

### 小节（不是章节，level 3）
正文。

## 第二章 为什么是音色锁
另一段正文。

## 第三章 平台导出
导出说明。
"""


def test_parses_h2_headings_only() -> None:
    chapters = parse_chapters(SAMPLE)
    assert [c.title for c in chapters] == [
        "第一章 开篇",
        "第二章 为什么是音色锁",
        "第三章 平台导出",
    ]


def test_offsets_default_zero_until_synth() -> None:
    chapters = parse_chapters(SAMPLE)
    assert all(c.start_offset == 0.0 for c in chapters)
    assert all(c.end_offset == 0.0 for c in chapters)


def test_respects_heading_level() -> None:
    chapters = parse_chapters(SAMPLE, heading_level=3)
    assert [c.title for c in chapters] == ["小节（不是章节，level 3）"]


def test_inline_formatting_stripped() -> None:
    md = "## 一段 **加粗** 与 _斜体_ 标题\n正文\n## 第二"
    chapters = parse_chapters(md)
    assert chapters[0].title == "一段 加粗 与 斜体 标题"
    assert chapters[1].title == "第二"


def test_no_headings_returns_empty() -> None:
    assert parse_chapters("只有正文，没有标题。") == []


def test_parse_markdown_file(tmp_path: Path) -> None:
    p = tmp_path / "ep01.md"
    p.write_text(SAMPLE, encoding="utf-8")
    chapters = parse_markdown_file(p)
    assert len(chapters) == 3
    assert chapters[0].title == "第一章 开篇"
