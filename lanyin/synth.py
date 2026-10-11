"""Per-episode synthesis + ID3 chapter embedding (the m2 build pipeline).

``embed_chapters`` writes one ``CHAP`` frame per chapter plus a ``CTOC`` table
of contents into an MP3, so chapter marks travel with the file into
小宇宙/喜马拉雅. ``synthesize_episode`` runs the full build for one episode:
parse sections → synthesize each section in the LOCKED voice → concat the MP3
chunks → embed cumulative chapter offsets → write ``dist/<stem>.mp3`` → upsert
the episode registry. The MiniMax call is the only external dependency; a
failure halts the build with a clear error (no silent fallback to a different
voice — that would break the lock).
"""

from __future__ import annotations

import io
from pathlib import Path

from . import chapter, tts_minimax, voice_lock
from .config import (
    dist_dir,
    episodes_path,
    load_episodes,
    require_config,
    save_episodes,
)
from .models import Chapter, Episode


class SynthError(Exception):
    pass


def embed_chapters(mp3_path: Path | str, chapters: list[Chapter]) -> int:
    """Embed ID3 ``CHAP`` frames + a ``CTOC`` toc into ``mp3_path``.

    One chapter = one ``CHAP`` frame (``element_id`` ``ch{idx:02d}``, offsets
    in ms, title in a ``TIT2`` sub-frame); a top-level ordered ``CTOC`` frame
    lists every chapter id so players can render the chapter menu. A chapter
    without ``end_offset`` runs until the next chapter starts; the last one
    runs to the end of the audio. Returns the number of chapters embedded.
    Re-embedding is idempotent: previous ``CHAP``/``CTOC`` frames are replaced.
    """
    try:
        from mutagen.id3 import CHAP, CTOC, ID3, TIT2  # type: ignore
        from mutagen.mp3 import MP3  # type: ignore
    except ImportError as exc:  # pragma: no cover - dep declared in pyproject
        raise SynthError("mutagen is required for ID3 chapter embed") from exc

    if not chapters:
        return 0

    path = Path(mp3_path)
    audio = MP3(path)
    tags = audio.tags if audio.tags is not None else ID3()
    tags.delall("CHAP")
    tags.delall("CTOC")

    starts = [float(ch.start_offset) for ch in chapters]
    ends = [float(ch.end_offset) if ch.end_offset else 0.0 for ch in chapters]
    for i in range(len(chapters)):
        if not ends[i]:
            ends[i] = starts[i + 1] if i + 1 < len(chapters) else float(audio.info.length)

    element_ids: list[str] = []
    for idx, ch in enumerate(chapters):
        element_id = f"ch{idx:02d}"
        element_ids.append(element_id)
        tags.add(
            CHAP(
                element_id=element_id,
                start_time=int(starts[idx] * 1000),
                end_time=int(ends[idx] * 1000),
                sub_frames=[TIT2(encoding=3, text=ch.title)],
            )
        )
    tags.add(
        CTOC(
            element_id="toc",
            flags=3,  # top-level + ordered
            child_element_ids=element_ids,
            sub_frames=[TIT2(encoding=3, text="Chapters")],
        )
    )
    tags.save(path)
    return len(chapters)


def _audio_seconds(mp3_bytes: bytes) -> float:
    """Length in seconds of an in-memory MP3 chunk."""
    from mutagen.mp3 import MP3  # type: ignore

    return float(MP3(io.BytesIO(mp3_bytes)).info.length)


def _upsert_registry(episode: Episode, *, root: Path | None) -> None:
    """Insert or replace the registry entry for this episode's resolved source."""
    registry = load_episodes(root)
    registry = [e for e in registry if e.get("source") != episode.source]
    registry.append(
        {
            "source": episode.source,
            "column_id": episode.column_id,
            "chapters": [c.model_dump() for c in episode.chapters],
            "audio_path": episode.audio_path,
            "size_bytes": episode.size_bytes,
            "duration_seconds": episode.duration_seconds,
        }
    )
    save_episodes(registry, root=root)


def synthesize_episode(
    episode_md: Path | str,
    *,
    root: Path | str | None = None,
    client: tts_minimax.MiniMaxClient | None = None,
) -> Episode:
    """Build one episode into ``dist/<stem>.mp3`` (m2).

    Flow: parse sections → synthesize each section in the locked voice →
    concat the MP3 chunks → embed cumulative ID3 chapter offsets → upsert the
    registry. Raises ``SynthError`` when no voice lock exists (the build never
    falls back to a different voice); ``MiniMaxError`` and ``ConfigError``
    propagate to the CLI's clean error paths. Tests inject a pre-built
    ``client``; by default one is constructed from the environment.
    """
    from mutagen.mp3 import MP3  # type: ignore

    src = Path(episode_md)
    if not src.exists():
        raise SynthError(f"episode file not found: {src}")

    cfg = require_config(root)
    lock = voice_lock.load_lock(root)
    if lock is None:
        raise SynthError(
            f"no voice lock at {voice_lock.lock_path(root)} — run "
            "`lanyin voice lock --sample ./voice.mp3 --name \"签名音色\"` first; "
            "build never falls back to a different voice"
        )

    try:
        text = src.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise chapter.ChapterError(
            f"cannot read {src} as valid UTF-8 markdown: {exc}"
        ) from exc
    sections = chapter.parse_sections(text, heading_level=cfg.chapter_heading_level)
    if not sections:
        raise SynthError(f"no chapter content in {src}")

    owns_client = client is None
    if client is None:
        client = tts_minimax.MiniMaxClient()
    try:
        chunks = [
            client.synthesize(section_text, voice_id=lock.voice_id)
            for _title, section_text in sections
        ]
    finally:
        if owns_client:
            client.close()

    # per-chapter durations give the cumulative CHAP offsets
    durations = [_audio_seconds(chunk) for chunk in chunks]
    starts: list[float] = []
    acc = 0.0
    for d in durations:
        starts.append(acc)
        acc += d

    chapters = [
        Chapter(
            title=title or src.stem,
            start_offset=start,
            end_offset=start + duration,
        )
        for (title, _text), start, duration in zip(sections, starts, durations)
    ]

    out = dist_dir(root) / f"{src.stem}.mp3"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"".join(chunks))
    embed_chapters(out, chapters)

    total = float(MP3(out).info.length)
    episode = Episode(
        column_id=cfg.column_id,
        source=str(src.resolve()),
        chapters=chapters,
        audio_path=f"{dist_dir(root).name}/{out.name}",
        size_bytes=out.stat().st_size,
        duration_seconds=round(total, 3),
    )
    _upsert_registry(episode, root=Path(root) if root else None)
    return episode


def synthesize_registered(
    *,
    root: Path | str | None = None,
    client: tts_minimax.MiniMaxClient | None = None,
) -> list[Episode]:
    """Batch-build every registered episode (``lanyin build`` with no args)."""
    registry = load_episodes(root)
    if not registry:
        raise SynthError(
            f"no registered episodes at {episodes_path(root)} — run "
            "`lanyin add ./ep01.md` first"
        )
    built: list[Episode] = []
    for entry in registry:
        source = entry.get("source")
        if not source:
            continue
        built.append(synthesize_episode(source, root=root, client=client))
    return built
