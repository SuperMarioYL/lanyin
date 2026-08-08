"""The column-level voice lock — LanYin's core primitive (m1).

``lock_voice`` clones a MiniMax-H3 voice from a sample and persists a
``ColumnVoiceLock`` to ``.lanyin/voice-lock.json``. From then on, every
episode of this column is synthesized against the same ``voice_id`` — that is
the taste/control moat: lock once, reference everywhere, re-record only a
changed segment without touching the rest.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import tts_minimax
from .config import lock_dir, lock_path, require_config
from .models import ChapterSchema, ColumnVoiceLock


class VoiceLockError(Exception):
    pass


def lock_voice(
    sample: Path | str,
    *,
    name: str,
    root: Path | str | None = None,
    api_key: str | None = None,
    client: tts_minimax.MiniMaxClient | None = None,
) -> ColumnVoiceLock:
    """Clone a MiniMax-H3 voice from ``sample`` and persist the column lock.

    Requires ``MINIMAX_API_KEY`` (or pass ``api_key``/a pre-built ``client`` —
    the latter is how tests inject a mock). With no key, raises
    ``VoiceLockError`` with a clear, actionable message — never silently falls
    back to a different voice (that would break the lock).
    """
    sample_path = Path(sample)
    if not sample_path.exists():
        raise VoiceLockError(f"sample file not found: {sample_path}")
    cfg = require_config(root)

    owns_client = client is None
    if client is None:
        key = api_key or os.environ.get(tts_minimax.ENV_API_KEY)
        if not key:
            raise VoiceLockError(
                f"{tts_minimax.ENV_API_KEY} is not set — export it to clone a "
                "MiniMax-H3 voice. See the README's Quickstart."
            )
        client = tts_minimax.MiniMaxClient(api_key=key)
    try:
        voice_id = client.clone_voice(sample_path, voice_name=name)
    finally:
        if owns_client:
            client.close()

    lock = ColumnVoiceLock(
        column_id=cfg.column_id,
        voice_id=voice_id,
        voice_prompt=name,
        chapter_schema=ChapterSchema(heading_level=cfg.chapter_heading_level),
        locked_at=datetime.now(timezone.utc),
    )
    save_lock(lock, root=root)
    return lock


def save_lock(lock: ColumnVoiceLock, *, root: Path | str | None = None) -> Path:
    """Persist the column voice lock to ``.lanyin/voice-lock.json``."""
    d = lock_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    path = lock_path(root)
    path.write_text(lock.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_lock(root: Path | str | None = None) -> ColumnVoiceLock | None:
    """Read the column voice lock, or ``None`` if none has been locked yet."""
    path = lock_path(root)
    if not path.exists():
        return None
    return ColumnVoiceLock.model_validate_json(path.read_text(encoding="utf-8"))


def show_lock(lock: ColumnVoiceLock) -> dict[str, Any]:
    """Return a flat dict suitable for a rich table / panel."""
    return {
        "column_id": lock.column_id,
        "voice_id": lock.voice_id,
        "voice_prompt": lock.voice_prompt,
        "heading_level": lock.chapter_schema.heading_level,
        "marker": lock.chapter_schema.marker,
        "locked_at": lock.locked_at.isoformat(),
    }
