"""v0.3.0 regression tests: RSS owner escaping, locale-independent pubDate,
non-UTF-8 add path, the real episode build, and version lockstep."""

from __future__ import annotations

import io
import json
import locale
import tomllib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from mutagen.mp3 import MP3
from typer.testing import CliRunner

from lanyin import __version__
from lanyin.chapter import parse_sections
from lanyin.cli import app
from lanyin.export_rss import _rfc822, generate_rss
from lanyin.models import ColumnVoiceLock
from lanyin.voice_lock import save_lock

_ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"


# --- m8: itunes:owner name escaping ------------------------------------------


def test_owner_name_not_double_escaped() -> None:
    channel = {"title": "t", "link": "", "description": "d", "author": "A & B"}

    root = ET.fromstring(generate_rss([], channel=channel))

    assert root.findtext(f"channel/{_ITUNES}author") == "A & B"
    assert root.findtext(f"channel/{_ITUNES}owner/{_ITUNES}name") == "A & B"

    explicit = {"title": "t", "link": "", "description": "d", "owner_name": 'O & "P"'}
    root2 = ET.fromstring(generate_rss([], channel=explicit))
    assert root2.findtext(f"channel/{_ITUNES}owner/{_ITUNES}name") == 'O & "P"'


# --- m9: RFC 822 pubDate under any locale -------------------------------------


def test_rfc822_locale_independent() -> None:
    saturday = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)
    assert _rfc822(saturday) == "Sat, 12 Sep 2026 10:00:00 +0000"

    minus_0530 = timezone(timedelta(hours=-5, minutes=-30))
    assert _rfc822(datetime(2026, 9, 12, 10, 0, tzinfo=minus_0530)).endswith("-0530")

    previous = ""
    try:
        previous = locale.setlocale(locale.LC_TIME, "zh_CN.UTF-8")
    except locale.Error:
        pytest.skip("zh_CN.UTF-8 locale not installed")
    try:
        out = _rfc822(saturday)
    finally:
        locale.setlocale(locale.LC_TIME, previous or "C")
    assert out.startswith("Sat, 12 Sep")


# --- m10: non-UTF-8 add path + README de-dup copy ------------------------------


def test_add_non_utf8_file_fails_cleanly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(app, ["init", "Demo Column"]).exit_code == 0

    (tmp_path / "ep.md").write_bytes(b"bad\xff\xfe md")
    res = runner.invoke(app, ["add", "ep.md"])

    assert res.exit_code == 1
    # rich wraps the message at 80 cols — compare whitespace-normalized
    assert "valid UTF-8" in " ".join(res.output.split())
    # the clean ChapterError path, not a leaked UnicodeDecodeError
    assert not isinstance(res.exception, UnicodeDecodeError)


def test_readmes_match_path_normalized_dedup() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    zh = (repo_root / "README.md").read_text(encoding="utf-8")
    en = (repo_root / "README.en.md").read_text(encoding="utf-8")
    # the pre-v0.2.0 string-based de-dup wording must be gone
    assert "来源路径字符串" not in zh
    assert "same source-path string" not in en
    # and the path-normalized wording must be present (matches web/site.json)
    assert "路径已归一化" in zh
    assert "paths are normalized" in en


# --- m11: the real episode build ------------------------------------------------


def _silent_mp3(frames: int) -> bytes:
    """Tiny valid MP3: silent MPEG1 Layer3 128kbps 44.1kHz frames (~26ms each)."""
    return (b"\xff\xfb\x90\x00" + b"\x00" * 413) * frames


class _FakeClient:
    """Records synthesize calls; returns silent MP3 chunks of set frame counts."""

    def __init__(self, frame_counts: list[int]) -> None:
        self.frame_counts = frame_counts
        self.calls: list[tuple[str, str]] = []
        self.closed = False

    def synthesize(self, text: str, *, voice_id: str) -> bytes:
        self.calls.append((text, voice_id))
        return _silent_mp3(self.frame_counts[len(self.calls) - 1])

    def close(self) -> None:
        self.closed = True


def _seed_lock(tmp_path: Path) -> None:
    save_lock(
        ColumnVoiceLock(
            column_id="demo-column",
            voice_id="v-lock-1",
            voice_prompt="签名音色",
            locked_at=datetime.now(timezone.utc),
        )
    )


def test_build_synthesizes_sections_in_locked_voice(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(app, ["init", "Demo Column"]).exit_code == 0
    _seed_lock(tmp_path)

    ep = tmp_path / "ep01.md"
    ep.write_text(
        "# 栏目\n\n引言文字。\n\n## 第一章\n\n第一章正文。\n\n## 第二章\n\n第二章正文。\n",
        encoding="utf-8",
    )
    fake = _FakeClient([40, 80])
    monkeypatch.setattr("lanyin.tts_minimax.MiniMaxClient", lambda: fake)

    res = runner.invoke(app, ["build", "ep01.md"])

    assert res.exit_code == 0, res.output
    # one call per section, in the LOCKED voice, preamble merged into section 1
    assert [(t, v) for t, v in fake.calls] == [
        (fake.calls[0][0], "v-lock-1"),
        (fake.calls[1][0], "v-lock-1"),
    ]
    assert "引言文字。" in fake.calls[0][0]
    assert "第一章正文。" in fake.calls[0][0]
    assert "第一章正文。" not in fake.calls[1][0]
    assert "第二章正文。" in fake.calls[1][0]
    assert fake.closed

    mp3 = tmp_path / "dist" / "ep01.mp3"
    assert mp3.exists()
    tags = MP3(mp3).tags
    chaps = sorted(tags.getall("CHAP"), key=lambda f: f.element_id)
    assert [c.element_id for c in chaps] == ["ch00", "ch01"]
    # ms offsets equal the cumulative per-chunk durations
    d0 = MP3(io.BytesIO(_silent_mp3(40))).info.length
    d1 = MP3(io.BytesIO(_silent_mp3(80))).info.length
    assert abs(chaps[0].end_time - d0 * 1000) <= 1
    assert abs(chaps[1].start_time - d0 * 1000) <= 1
    assert abs(chaps[1].end_time - (d0 + d1) * 1000) <= 1
    assert [str(c.sub_frames["TIT2"]) for c in chaps] == ["第一章", "第二章"]
    (ctoc,) = tags.getall("CTOC")
    assert ctoc.child_element_ids == ["ch00", "ch01"]

    registry = json.loads(
        (tmp_path / ".lanyin" / "episodes.json").read_text(encoding="utf-8")
    )
    assert len(registry) == 1
    entry = registry[0]
    assert entry["source"] == str(ep.resolve())
    assert entry["audio_path"] == "dist/ep01.mp3"
    assert entry["size_bytes"] == mp3.stat().st_size
    assert entry["duration_seconds"] > 0
    assert [c["title"] for c in entry["chapters"]] == ["第一章", "第二章"]


def test_build_batch_builds_registered(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(app, ["init", "Demo Column"]).exit_code == 0
    _seed_lock(tmp_path)

    for name in ("ep01.md", "ep02.md"):
        (tmp_path / name).write_text("## 章\n\n正文。\n", encoding="utf-8")
        assert runner.invoke(app, ["add", name]).exit_code == 0

    monkeypatch.setattr(
        "lanyin.tts_minimax.MiniMaxClient", lambda: _FakeClient([40, 40])
    )
    res = runner.invoke(app, ["build"])

    assert res.exit_code == 0, res.output
    assert (tmp_path / "dist" / "ep01.mp3").exists()
    assert (tmp_path / "dist" / "ep02.mp3").exists()
    registry = json.loads(
        (tmp_path / ".lanyin" / "episodes.json").read_text(encoding="utf-8")
    )
    assert all(e.get("audio_path") for e in registry)


def test_build_without_lock_fails_cleanly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(app, ["init", "Demo Column"]).exit_code == 0
    (tmp_path / "ep01.md").write_text("## 章\n\n正文。\n", encoding="utf-8")

    res = runner.invoke(app, ["build", "ep01.md"])

    assert res.exit_code == 1
    assert "no voice lock" in res.output
    assert "Traceback" not in res.output
    assert isinstance(res.exception, SystemExit)


def test_build_without_api_key_fails_cleanly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    runner = CliRunner()
    assert runner.invoke(app, ["init", "Demo Column"]).exit_code == 0
    _seed_lock(tmp_path)
    (tmp_path / "ep01.md").write_text("## 章\n\n正文。\n", encoding="utf-8")

    res = runner.invoke(app, ["build", "ep01.md"])

    assert res.exit_code == 1
    assert "MINIMAX_API_KEY" in res.output
    assert "Traceback" not in res.output


def test_parse_sections_preamble_and_headings() -> None:
    md = "前言。\n\n## 一\n\n甲\n\n## 二\n\n乙\n\n### 子标题\n\n子内容\n"

    secs = parse_sections(md, heading_level=2)

    assert [title for title, _text in secs] == ["一", "二"]
    assert secs[0][1].startswith("前言。")
    assert "## 一" in secs[0][1] and "甲" in secs[0][1]
    # a deeper heading stays inside the enclosing section
    assert "### 子标题" in secs[1][1] and "子内容" in secs[1][1]

    assert parse_sections("只有正文", heading_level=2) == [("", "只有正文")]
    assert parse_sections("", heading_level=2) == []


# --- m12: version lockstep ------------------------------------------------------


def test_version_lockstep_across_surfaces() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    version_file = (repo_root / "VERSION").read_text(encoding="utf-8").strip()
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))

    assert version_file == "0.3.0"
    assert pyproject["project"]["version"] == "0.3.0"
    assert __version__ == "0.3.0"

    changelog = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [0.1.0] - 2026-08-08" in changelog
    assert "## [0.2.0] - 2026-09-10" in changelog
    assert "## [0.3.0] - 2026-10-12" in changelog

    site = json.loads((repo_root / "web" / "site.json").read_text(encoding="utf-8"))
    # content_version is a monotonic site-refresh counter (bumped per docs
    # commit), so pin only the seeded floor, not the current value
    assert site["meta"]["content_version"] >= 1
