"""v0.4.0 regression tests: local-state validation, RSS export output, export
platform selection and messages, provider error contract, and version lockstep."""

from __future__ import annotations

import json
import tomllib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from lanyin import __version__
from lanyin.cli import app
from lanyin.config import (
    ConfigError,
    init_config,
    load_config,
    load_episodes,
    save_episodes,
)
from lanyin.export_rss import ExportError, export_series, generate_rss
from lanyin.models import ColumnVoiceLock, Episode
from lanyin.tts_minimax import MiniMaxClient, MiniMaxError
from lanyin.voice_lock import save_lock

_ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"

_CHANNEL = {
    "title": "硅谷早茶",
    "link": "https://example.com/column",
    "description": "d",
    "author": "a",
}


def _silent_mp3(frames: int) -> bytes:
    """Tiny valid MP3: silent MPEG1 Layer3 128kbps 44.1kHz frames."""
    return (b"\xff\xfb\x90\x00" + b"\x00" * 413) * frames


class _FakeClient:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.calls = 0

    def synthesize(self, text: str, *, voice_id: str) -> bytes:
        chunk = self.chunks[self.calls]
        self.calls += 1
        return chunk

    def close(self) -> None:
        pass


def _seed_lock() -> None:
    save_lock(
        ColumnVoiceLock(
            column_id="demo-column",
            voice_id="v-lock-1",
            voice_prompt="签名音色",
            locked_at=datetime.now(timezone.utc),
        )
    )


# --- m13: local-state validation ----------------------------------------------


@pytest.mark.parametrize(
    "flag",
    [["--heading-level", "0"], ["--heading-level", "7"], ["--platform", "spotify"]],
)
def test_init_rejects_invalid_column_values(
    tmp_path: Path, monkeypatch, flag: list[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    res = CliRunner().invoke(app, ["init", "Demo", *flag])

    out = " ".join(res.output.split())
    assert res.exit_code == 1
    assert "invalid column config" in out
    assert "Traceback" not in res.output
    # a rejected config must not be written
    assert not (tmp_path / "lanyin.toml").exists()


def test_load_config_rejects_out_of_range_heading_level(tmp_path: Path) -> None:
    (tmp_path / "lanyin.toml").write_text(
        '[column]\ncolumn_id = "c1"\ncolumn_name = "Col"\n'
        "chapter_heading_level = 0\nplatform_target = \"xiaoyuzhou\"\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="invalid lanyin.toml"):
        load_config(tmp_path)


def test_add_corrupt_registry_fails_cleanly_and_preserves_the_file(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(app, ["init", "Demo"]).exit_code == 0
    (tmp_path / "ep01.md").write_text("## 一\n\n甲\n", encoding="utf-8")
    assert runner.invoke(app, ["add", "ep01.md"]).exit_code == 0

    registry_file = tmp_path / ".lanyin" / "episodes.json"
    registry_file.write_text("{ not json", encoding="utf-8")

    res = runner.invoke(app, ["add", "ep01.md"])

    assert res.exit_code == 1
    assert "corrupt episode registry" in " ".join(res.output.split())
    assert "Traceback" not in res.output
    # the corrupt file is reported, never silently replaced by a one-entry list
    assert registry_file.read_text(encoding="utf-8") == "{ not json"


@pytest.mark.parametrize(
    "payload, message",
    [('{"source": "ep01.md"}', "expected a JSON list"),
     ('["ep01.md"]', "must be a JSON object")],
)
def test_load_episodes_rejects_malformed_payloads(
    tmp_path: Path, payload: str, message: str
) -> None:
    state = tmp_path / ".lanyin"
    state.mkdir()
    (state / "episodes.json").write_text(payload, encoding="utf-8")

    with pytest.raises(ConfigError, match=message):
        load_episodes(tmp_path)


# --- m14: RSS export output ----------------------------------------------------


def test_rss_item_title_falls_back_to_source_and_duration_is_whole_seconds() -> None:
    episode = Episode(
        column_id="c",
        source="/abs/ep01.md",
        audio_path="dist/ep01.mp3",
        size_bytes=123,
        duration_seconds=642.4,
    )

    root = ET.fromstring(generate_rss([episode], channel=_CHANNEL))
    item = root.find("channel/item")

    assert item.findtext("title") == "ep01"
    assert item.findtext(f"{_ITUNES}duration") == "642"


def test_rss_item_keeps_explicit_title_and_string_duration() -> None:
    root = ET.fromstring(
        generate_rss(
            [{"title": "第 1 期", "audio_url": "u", "duration": "10:42"}],
            channel=_CHANNEL,
        )
    )
    item = root.find("channel/item")

    assert item.findtext("title") == "第 1 期"
    assert item.findtext(f"{_ITUNES}duration") == "10:42"


def test_rss_item_without_title_or_source_keeps_placeholder() -> None:
    root = ET.fromstring(generate_rss([{"audio_url": "u"}], channel=_CHANNEL))
    assert root.find("channel/item").findtext("title") == "Untitled episode"


def test_itunes_category_is_escaped_exactly_once() -> None:
    channel = {**_CHANNEL, "category": "Science & Tech"}

    root = ET.fromstring(generate_rss([], channel=channel))

    category = root.find("channel").find(f"{_ITUNES}category")
    assert category.attrib["text"] == "Science & Tech"


# --- m15: export platform + messages ------------------------------------------


def test_export_series_uses_configured_platform_target(tmp_path: Path) -> None:
    init_config("硅谷早茶", platform_target="ximalaya", root=tmp_path)
    save_episodes(
        [{"source": str(tmp_path / "ep01.md"), "audio_path": "dist/ep01.mp3"}],
        root=tmp_path,
    )

    out = export_series(root=tmp_path)

    assert "(ximalaya)" in out.read_text(encoding="utf-8")
    # an explicit argument still wins over the column config
    out = export_series("xiaoyuzhou", root=tmp_path)
    assert "(xiaoyuzhou)" in out.read_text(encoding="utf-8")


def test_export_series_unbuilt_message_points_at_build(tmp_path: Path) -> None:
    init_config("Demo", root=tmp_path)

    with pytest.raises(ExportError, match="run `lanyin build`"):
        export_series(root=tmp_path)


def test_export_cli_reports_failure_without_the_roadmap_label(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(app, ["init", "Demo"]).exit_code == 0
    (tmp_path / "ep01.md").write_text("## 一\n\n甲\n", encoding="utf-8")
    assert runner.invoke(app, ["add", "ep01.md"]).exit_code == 0

    res = runner.invoke(app, ["export", "rss"])

    out = " ".join(res.output.split())
    assert res.exit_code == 1
    assert "export failed" in out
    assert "roadmap" not in out
    assert "not implemented" not in out


# --- m16: provider error contract ---------------------------------------------


def test_client_translates_transport_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = MiniMaxClient(api_key="sk-test", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(MiniMaxError, match="request failed"):
            client.synthesize("你好", voice_id="v1")
    finally:
        client.close()


def test_voice_lock_provider_error_exits_cleanly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")
    runner = CliRunner()
    assert runner.invoke(app, ["init", "Demo"]).exit_code == 0
    (tmp_path / "voice.mp3").write_bytes(b"fake sample")

    class _RejectingClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def clone_voice(self, sample, *, voice_name):
            raise MiniMaxError("MiniMax API 401: invalid api key")

        def close(self) -> None:
            pass

    monkeypatch.setattr("lanyin.tts_minimax.MiniMaxClient", _RejectingClient)

    res = runner.invoke(app, ["voice", "lock", "--sample", "voice.mp3", "--name", "N"])

    assert res.exit_code == 1
    assert "voice lock failed" in " ".join(res.output.split())
    assert "Traceback" not in res.output


def test_build_non_mp3_payload_fails_cleanly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(app, ["init", "Demo"]).exit_code == 0
    _seed_lock()
    (tmp_path / "ep01.md").write_text("## 一\n\n甲\n", encoding="utf-8")
    monkeypatch.setattr(
        "lanyin.tts_minimax.MiniMaxClient",
        lambda: _FakeClient([b"<html>502 bad gateway</html>"]),
    )

    res = runner.invoke(app, ["build", "ep01.md"])

    assert res.exit_code == 1
    assert "not a readable MP3" in " ".join(res.output.split())
    assert "Traceback" not in res.output


# --- m17: version lockstep ----------------------------------------------------


def test_version_lockstep_across_surfaces() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    version = (repo_root / "VERSION").read_text(encoding="utf-8").strip()
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))

    assert version == "0.4.0"
    assert pyproject["project"]["version"] == version
    assert __version__ == version

    changelog = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = [line for line in changelog.splitlines() if line.startswith("## [")]
    # the NEWEST heading must be this version, not merely present somewhere
    assert headings
    assert headings[0].startswith(f"## [{version}] ")
    for previous in ("## [0.1.0] - 2026-08-08", "## [0.2.0] - 2026-09-10",
                     "## [0.3.0] - 2026-10-12"):
        assert previous in changelog

    site = json.loads((repo_root / "web" / "site.json").read_text(encoding="utf-8"))
    # content_version is a monotonic integer site-refresh counter, not a version
    assert isinstance(site["meta"]["content_version"], int)
    assert site["meta"]["content_version"] >= 3
