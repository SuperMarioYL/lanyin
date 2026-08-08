"""Pydantic data models for LanYin.

The new primitive is the column-level voice lock (栏目级音色锁) — a persisted
voice profile that survives across episodes — plus a chapter schema that makes
each episode a subscribable, editable asset.

See mvp_plan.md §2 for the authoritative shape.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChapterSchema(BaseModel):
    """How Markdown headings map to chapter marks.

    ``heading_level`` is the heading level (e.g. ``2`` for ``##``) that becomes
    a chapter boundary; ``marker`` is the ID3 frame id used when embedding.
    """

    heading_level: int = 2
    marker: str = "CHAP"


class Chapter(BaseModel):
    """One chapter inside an episode."""

    title: str
    start_offset: float = 0.0  # seconds from episode start
    end_offset: float = 0.0  # seconds from episode start (0 = unknown)


class ColumnVoiceLock(BaseModel):
    """The column-level voice lock — the persisted primitive.

    Lock once (``lanyin voice lock``), reference everywhere: every episode of
    this column is synthesized against ``voice_id`` so the narrator is stable
    across episodes. This is the taste/control moat.
    """

    column_id: str
    voice_id: str
    voice_prompt: str  # locked tone/style label for the column
    chapter_schema: ChapterSchema = Field(default_factory=ChapterSchema)
    locked_at: datetime


class Episode(BaseModel):
    """One episode of a column, post-synthesis."""

    column_id: str
    source: str  # 公众号 URL or local .md path
    chapters: list[Chapter] = Field(default_factory=list)
    audio_path: str = ""  # MP3 with embedded ID3 chapters
