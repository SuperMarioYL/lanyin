"""Regression tests for the v0.2 fix batch: RSS feed validity, local-state
contract, and the ID3 chapter embed."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lanyin.cli import app
from lanyin.config import ConfigError, load_config
from lanyin.export_rss import _iso, generate_rss
from lanyin.models import Chapter
from lanyin.synth import embed_chapters

_ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"


# --- m4: RSS feed validity --------------------------------------------------


def test_generate_rss_quote_in_attribute_values_stays_well_formed() -> None:
    channel = {
        "title": "硅谷早茶",
        "link": "https://example.com/column",
        "description": "d",
        "author": "a",
        "category": 'Technology "AI"',
        "image": 'https://example.com/cover"a.jpg',
    }
    ep = {"title": "ep1", "audio_url": 'https://cdn.example.com/a"b.mp3', "size_bytes": 1}

    xml = generate_rss([ep], channel=channel)

    root = ET.fromstring(xml)  # must parse: attribute values stay quoted
    channel_el = root.find("channel")
    assert channel_el.find(f"{_ITUNES}category").attrib["text"] == 'Technology "AI"'
    assert channel_el.find(f"{_ITUNES}image").attrib["href"] == 'https://example.com/cover"a.jpg'
    item = channel_el.find("item")
    enclosure = item.find("enclosure")
    assert enclosure.attrib["url"] == 'https://cdn.example.com/a"b.mp3'
    # the guid falls back to the raw audio_url — escaped once, not twice
    assert item.findtext("guid") == 'https://cdn.example.com/a"b.mp3'


def test_iso_renders_non_utc_offset() -> None:
    plus8 = timezone(timedelta(hours=8))
    assert _iso(datetime(2026, 8, 8, 12, 0, tzinfo=plus8)).endswith("+0800")
    assert _iso(datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)).endswith("+0000")
    # naive datetimes are treated as UTC, not silently mislabeled
    assert _iso(datetime(2026, 8, 8, 12, 0)).endswith("+0000")


# --- m5: local-state contract -----------------------------------------------


def test_add_dedup_normalizes_source_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(app, ["init", "Demo Column"]).exit_code == 0

    ep = tmp_path / "ep01.md"
    ep.write_text("# 标题\n\n## 第一章\n正文\n", encoding="utf-8")
    assert runner.invoke(app, ["add", "ep01.md"]).exit_code == 0
    assert runner.invoke(app, ["add", "./ep01.md"]).exit_code == 0
    assert runner.invoke(app, ["add", str(ep)]).exit_code == 0

    registry = json.loads((tmp_path / ".lanyin" / "episodes.json").read_text(encoding="utf-8"))
    assert len(registry) == 1
    assert registry[0]["source"] == str(ep.resolve())
    assert [c["title"] for c in registry[0]["chapters"]] == ["第一章"]


def test_load_config_invalid_field_raises_config_error(tmp_path: Path) -> None:
    (tmp_path / "lanyin.toml").write_text(
        '[column]\ncolumn_id = "c1"\ncolumn_name = "Col"\n'
        'chapter_heading_level = "two"\nplatform_target = "xiaoyuzhou"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="invalid lanyin.toml"):
        load_config(tmp_path)


def test_voice_show_corrupt_lock_exits_cleanly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    lock = tmp_path / ".lanyin" / "voice-lock.json"
    lock.parent.mkdir()
    lock.write_text("not valid json{{{", encoding="utf-8")

    res = CliRunner().invoke(app, ["voice", "show"])

    assert res.exit_code == 1
    assert "corrupt voice lock" in res.output
    assert "Traceback" not in res.output


# --- m6: ID3 chapter embed ----------------------------------------------------


def _minimal_mp3(path: Path, frames: int = 40) -> Path:
    """A tiny valid MP3: silent MPEG1 Layer3 128kbps 44.1kHz frames (~417B each)."""
    path.write_bytes((b"\xff\xfb\x90\x00" + b"\x00" * 413) * frames)
    return path


def test_embed_chapters_writes_chap_and_ctoc(tmp_path: Path) -> None:
    from mutagen.mp3 import MP3

    mp3 = _minimal_mp3(tmp_path / "ep.mp3")
    chapters = [
        Chapter(title="认识缓存", start_offset=0.0, end_offset=0.5),
        Chapter(title="失效策略", start_offset=0.5, end_offset=1.0),
    ]
    assert embed_chapters(mp3, chapters) == 2

    tags = MP3(mp3).tags
    chaps = sorted(tags.getall("CHAP"), key=lambda f: f.element_id)
    assert [c.element_id for c in chaps] == ["ch00", "ch01"]
    assert [(c.start_time, c.end_time) for c in chaps] == [(0, 500), (500, 1000)]
    assert [str(c.sub_frames["TIT2"]) for c in chaps] == ["认识缓存", "失效策略"]
    (ctoc,) = tags.getall("CTOC")
    assert ctoc.element_id == "toc"
    assert ctoc.child_element_ids == ["ch00", "ch01"]

    # re-embedding replaces the old marks instead of stacking duplicates
    embed_chapters(mp3, chapters)
    tags = MP3(mp3).tags
    assert len(tags.getall("CHAP")) == 2
    assert len(tags.getall("CTOC")) == 1


def test_embed_chapters_defaults_end_offsets(tmp_path: Path) -> None:
    from mutagen.mp3 import MP3

    mp3 = _minimal_mp3(tmp_path / "ep.mp3")
    chapters = [Chapter(title="一"), Chapter(title="二", start_offset=0.5)]
    embed_chapters(mp3, chapters)

    chaps = sorted(MP3(mp3).tags.getall("CHAP"), key=lambda f: f.element_id)
    assert (chaps[0].start_time, chaps[0].end_time) == (0, 500)
    assert chaps[1].end_time == int(MP3(mp3).info.length * 1000)
