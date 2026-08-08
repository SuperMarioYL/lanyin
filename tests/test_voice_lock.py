"""Tests for the column voice lock (m1) — pure persistence + show, no network.

The real MiniMax-H3 clone call lives in ``tts_minimax.MiniMaxClient.clone_voice``
and is only exercised when ``MINIMAX_API_KEY`` is set; here we inject a fake
client so the lock primitive is testable offline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from lanyin import tts_minimax, voice_lock
from lanyin.config import init_config, lock_path
from lanyin.models import ChapterSchema, ColumnVoiceLock


class _FakeClient:
    """Stand-in for MiniMaxClient — records the call, returns a fixed voice_id."""

    def __init__(self, voice_id: str = "voice-demo-abc123") -> None:
        self.voice_id = voice_id
        self.closed = False
        self.calls: list[tuple[str, str]] = []

    def clone_voice(self, sample, *, voice_name):  # noqa: ANN001 - matches client signature
        self.calls.append((str(sample), voice_name))
        return self.voice_id

    def close(self) -> None:
        self.closed = True


def _seed_sample(tmp_path: Path) -> Path:
    p = tmp_path / "voice.mp3"
    p.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00\x00fake-audio-bytes")
    return p


def test_save_load_round_trip(tmp_path: Path) -> None:
    init_config("test column", root=tmp_path)
    lock = ColumnVoiceLock(
        column_id="test-column",
        voice_id="voice-xyz",
        voice_prompt="作者签名音色",
        chapter_schema=ChapterSchema(heading_level=2),
        locked_at=datetime(2026, 8, 8, 8, 14, 48, tzinfo=timezone.utc),
    )
    written = voice_lock.save_lock(lock, root=tmp_path)
    assert written == lock_path(tmp_path)
    assert written.exists()

    loaded = voice_lock.load_lock(tmp_path)
    assert loaded is not None
    assert loaded.voice_id == "voice-xyz"
    assert loaded.column_id == "test-column"
    assert loaded.voice_prompt == "作者签名音色"
    assert loaded.chapter_schema.heading_level == 2


def test_load_returns_none_when_no_lock(tmp_path: Path) -> None:
    init_config("empty column", root=tmp_path)
    assert voice_lock.load_lock(tmp_path) is None


def test_lock_voice_persists_via_injected_client(tmp_path: Path) -> None:
    init_config("demo column", root=tmp_path)
    sample = _seed_sample(tmp_path)
    fake = _FakeClient(voice_id="voice-cloned-789")

    lock = voice_lock.lock_voice(
        sample, name="签名音色", root=tmp_path, client=fake
    )

    assert fake.calls == [(str(sample), "签名音色")]
    assert fake.closed is False  # injected client is caller-owned, not closed
    assert lock.voice_id == "voice-cloned-789"
    assert lock.voice_prompt == "签名音色"
    # persisted to the canonical path
    on_disk = voice_lock.load_lock(tmp_path)
    assert on_disk is not None
    assert on_disk.voice_id == "voice-cloned-789"


def test_lock_voice_missing_sample_raises(tmp_path: Path) -> None:
    init_config("demo column", root=tmp_path)
    with pytest.raises(voice_lock.VoiceLockError, match="sample file not found"):
        voice_lock.lock_voice(
            tmp_path / "nope.mp3", name="x", root=tmp_path, client=_FakeClient()
        )


def test_lock_voice_without_config_raises(tmp_path: Path) -> None:
    sample = _seed_sample(tmp_path)
    with pytest.raises(Exception):  # ConfigError subclass
        voice_lock.lock_voice(
            sample, name="x", root=tmp_path, client=_FakeClient()
        )


def test_lock_voice_without_key_or_client_raises(tmp_path: Path, monkeypatch) -> None:
    init_config("demo column", root=tmp_path)
    sample = _seed_sample(tmp_path)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    with pytest.raises(voice_lock.VoiceLockError, match="MINIMAX_API_KEY is not set"):
        voice_lock.lock_voice(sample, name="x", root=tmp_path)


def test_lock_voice_owns_and_closes_real_client(tmp_path: Path) -> None:
    """The real path: lock_voice builds its own MiniMaxClient (owns_client=True)
    over a mock transport, calls clone, and closes it. No network."""
    import httpx

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/voice_clone"
        return httpx.Response(200, json={"voice_id": "voice-owned-42"})

    transport = httpx.MockTransport(_handler)
    # Monkey-patch the client factory so the real constructor (which needs a
    # live httpx) is replaced by one that injects our mock transport.
    orig_client = tts_minimax.MiniMaxClient

    class _OwnedClient(orig_client):
        def __init__(self, **kwargs):
            kwargs.setdefault("api_key", "fake-key-for-test")
            super().__init__(transport=transport, **kwargs)

    tts_minimax.MiniMaxClient = _OwnedClient
    init_config("demo column", root=tmp_path)
    sample = _seed_sample(tmp_path)
    try:
        lock = voice_lock.lock_voice(sample, name="签名音色", root=tmp_path, api_key="fake-key-for-test")
    finally:
        tts_minimax.MiniMaxClient = orig_client
    assert lock.voice_id == "voice-owned-42"
    on_disk = voice_lock.load_lock(tmp_path)
    assert on_disk is not None and on_disk.voice_id == "voice-owned-42"


def test_show_lock_flattens_for_display(tmp_path: Path) -> None:
    lock = ColumnVoiceLock(
        column_id="c", voice_id="v", voice_prompt="p",
        chapter_schema=ChapterSchema(), locked_at=datetime.now(timezone.utc),
    )
    row = voice_lock.show_lock(lock)
    assert row["column_id"] == "c"
    assert row["voice_id"] == "v"
    assert row["voice_prompt"] == "p"
    assert row["heading_level"] == 2
    assert row["marker"] == "CHAP"
    assert "T" in row["locked_at"]  # ISO datetime
