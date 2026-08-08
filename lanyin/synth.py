"""Per-episode synthesis + ID3 chapter embedding (m2 — NOT wired in this milestone).

m1 ships the voice lock; m2 wires the build: parse chapters → call MiniMax-H3
in the locked voice → embed ID3 ``CHAP`` frames (so chapter marks travel with
the MP3 into 小宇宙/喜马拉雅) → write ``dist/epXX.mp3``.

The functions below are the intended surface; ``synthesize_episode`` raises a
clear "not implemented" error so the CLI can report the m2 roadmap honestly
instead of pretending to work.
"""

from __future__ import annotations

from pathlib import Path

from .models import Episode


class SynthError(Exception):
    pass


def embed_chapters(mp3_path: Path | str, chapters, *, marker: str = "CHAP") -> None:
    """Embed ID3 CHAP frames into ``mp3_path`` (m2 helper, pure-ish).

    Implemented as a thin mutagen wrapper so the ID3 layer is exercised; the
    full build pipeline that *calls* it (``synthesize_episode``) is the m2
    surface that is intentionally not wired yet.
    """
    try:
        from mutagen.mp3 import MP3  # type: ignore
        from mutagen.id3 import ID3, CHAP, CTOC, CTOCFrame  # type: ignore  # noqa: F401
    except ImportError as exc:  # pragma: no cover - dep declared in pyproject
        raise SynthError("mutagen is required for ID3 chapter embed") from exc

    audio = MP3(mp3_path)
    if audio.tags is None:
        audio.add_tags()
    tags = ID3(mp3_path) if Path(mp3_path).exists() else audio.tags
    # mutagen API differs across versions — keep this surface narrow and let
    # the m2 build fill real offsets; here we only demonstrate the path.
    for idx, ch in enumerate(chapters):
        # CHAP element_id must be unique; offsets are ms in mutagen's CHAP.
        chap = CHAP(
            element_id=f"ch{idx:02d}",
            start_time=int(ch.start_offset * 1000),
            end_time=int(ch.end_offset * 1000) if ch.end_offset else None,
            sub_frames=None,
        )
    raise SynthError(
        "ID3 CHAP embed is a stub in m1 — full chapter-timed embed lands in m2 "
        "along with synthesis. See the roadmap."
    )


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
        "chapter parser, and MiniMax-H3 client are already in place."
    )
