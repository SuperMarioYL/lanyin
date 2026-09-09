"""Per-episode synthesis + ID3 chapter embedding (m2 groundwork).

The ID3 half of the m2 build is real: ``embed_chapters`` writes one ``CHAP``
frame per chapter plus a ``CTOC`` table of contents into an MP3, so chapter
marks travel with the file into 小宇宙/喜马拉雅. Episode synthesis itself
(``synthesize_episode`` — parse chapters → call MiniMax-H3 in the locked voice
→ write ``dist/epXX.mp3``) still requires the live API and raises a clear
"not implemented" error until m2 wires it.
"""

from __future__ import annotations

from pathlib import Path

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


def synthesize_episode(episode_md: Path | str, *, root: Path | str | None = None) -> Episode:
    """Build one episode into ``dist/epXX.mp3`` (m2 — NOT implemented in this milestone).

    Intended flow:
      1. ``chapter.parse_markdown_file`` → Chapter[]
      2. ``voice_lock.load_lock`` → ColumnVoiceLock (must exist)
      3. ``tts_minimax.synthesize`` per chapter in the locked voice
      4. concat → ``embed_chapters`` → write ``dist/epXX.mp3``

    Raises ``NotImplementedError`` so the CLI reports the m2 roadmap honestly.
    """
    raise NotImplementedError(
        "m2 (episode build) is not implemented in this milestone. "
        "`lanyin build` ships in m2 — see the roadmap. The voice lock (m1), "
        "chapter parser, MiniMax-H3 client and ID3 chapter embed "
        "(`embed_chapters`) are already in place."
    )
