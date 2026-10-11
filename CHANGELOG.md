# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-10-12

### Fixed

- `generate_rss` no longer double-escapes the `itunes:owner` name when
  `owner_name` is omitted: the fallback now uses the raw author value and each
  XML position is escaped exactly once, so an author like `A & B` decodes
  correctly instead of rendering as `A &amp; B`.
- `pubDate` rendering is locale-independent: weekday and month names come from
  fixed English tables instead of locale-dependent `strftime`, so a CLI run
  under e.g. zh_CN no longer emits invalid RFC 822 dates (`六, 12 9月 2026 ...`).
- `lanyin add` on a file that is not valid UTF-8 (e.g. a GBK export) now fails
  with a clean one-line `ChapterError` message instead of a raw
  `UnicodeDecodeError` traceback.
- README.md and README.en.md no longer document the pre-v0.2.0 string-based
  registry de-dup; both now describe the resolved-path normalization that
  ships since 0.2.0 (matching the website copy).

### Added

- The real episode build (`lanyin build`): each chapter section is synthesized
  in the locked column voice, the MP3 chunks are concatenated, cumulative ID3
  `CHAP`/`CTOC` offsets are embedded from the measured per-chapter durations,
  the file is written to `dist/<stem>.mp3`, and the registry entry is updated
  with `audio_path`, `size_bytes` and `duration_seconds`. Builds require a
  voice lock and `MINIMAX_API_KEY`; a failed API call halts with a clear error
  and never falls back to a different voice. `lanyin build` without arguments
  batch-builds every registered episode.

## [0.2.0] - 2026-09-10

### Fixed

- RSS export no longer emits malformed XML when an attribute value contains a
  double quote (`itunes:category text`, `itunes:image href`, `enclosure url`
  are now attribute-escaped), so 小宇宙/喜马拉雅 validators always receive a
  well-formed feed.
- `pubDate` rendering uses the datetime's own UTC offset instead of a
  hardcoded `+0000`, so tz-aware non-UTC publication dates are correct.
- `lanyin add` de-duplicates the episode registry by the resolved source path:
  registering the same file as `./ep01.md` and via an absolute path updates
  one entry instead of creating duplicates. Registry entries now store the
  resolved path.
- An invalid `lanyin.toml` (e.g. a non-integer `chapter_heading_level`) and a
  corrupt `.lanyin/voice-lock.json` now surface as clean one-line errors with
  exit code 1 instead of a raw pydantic `ValidationError` traceback.

### Added

- `lanyin.synth.embed_chapters` now really embeds ID3 chapters: one `CHAP`
  frame per chapter (ms offsets, title as `TIT2`) plus a top-level ordered
  `CTOC` frame, with end offsets defaulted to the next chapter start or the
  audio length. This is the offline half of the m2 episode build; synthesis
  itself (MiniMax-H3 calls) remains on the m2 roadmap.
- `CHANGELOG.md` and a version-lockstep test
  (`tests/test_v020_fixes.py::test_version_lockstep_across_surfaces`) keeping
  `VERSION`, `pyproject.toml` and `lanyin.__version__` in sync.

## [0.1.0] - 2026-08-08

### Added

- Column-level voice lock (m1): `lanyin voice lock --sample ./voice.mp3`
  clones a MiniMax-H3 voice and persists `.lanyin/voice-lock.json`;
  `lanyin voice show` prints the locked profile.
- `lanyin init` scaffolds `lanyin.toml` (column name, heading level, platform
  target).
- Markdown chapter parsing: `##` headings (configurable level) become chapter
  titles via markdown-it-py.
- Local episode registry: `lanyin add ./ep01.md` registers source + parsed
  chapters into `.lanyin/episodes.json`.
- MiniMax-H3 client (`clone_voice`, `synthesize`) over httpx with a mock
  transport for offline tests.
- RSS 2.0 + iTunes-namespace feed generation (`generate_rss`) for
  小宇宙/喜马拉雅 export; `lanyin build` and `lanyin export rss` are honest
  m2/m3 roadmap stubs.
