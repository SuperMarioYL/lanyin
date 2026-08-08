"""MiniMax-H3 API client (httpx).

The omni-modal stereo generation base. LanYin uses two surfaces:

* ``clone_voice`` — clone/lock a voice reference from a sample (m1).
* ``synthesize``  — text→stereo MP3 in a locked voice (m2; called by synth.py).

NOTE: ``schema_unverified: true`` per mvp_plan.md. The exact endpoints/field
names below are the documented MiniMax OpenPlatform shape as understood at plan
time; on the first real integration, adjust the request/response parsing here
and only here — the rest of LanYin talks to this client, not to the network.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

# Illustrative — the official MiniMax OpenPlatform base. Adjust on first
# integration if the hostname differs (e.g. international vs CN endpoint).
DEFAULT_BASE_URL = "https://api.minimaxi.chat/v1"

ENV_API_KEY = "MINIMAX_API_KEY"
ENV_GROUP_ID = "MINIMAX_GROUP_ID"  # some MiniMax endpoints want group_id


class MiniMaxError(Exception):
    """Raised when the MiniMax-H3 API rejects a request."""


class MiniMaxClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        group_id: str | None = None,
        timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        key = api_key or os.environ.get(ENV_API_KEY)
        if not key:
            raise MiniMaxError(
                f"{ENV_API_KEY} is not set — export it to call the MiniMax-H3 API. "
                "See the README's Quickstart."
            )
        self._api_key = key
        self._group_id = group_id or os.environ.get(ENV_GROUP_ID)
        self._base_url = base_url.rstrip("/")
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        # transport hook lets tests inject a mock without touching the network.
        self._client = httpx.Client(
            base_url=self._base_url,
            headers=headers,
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MiniMaxClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # --- m1: voice clone --------------------------------------------------

    def clone_voice(self, sample: Path | str, *, voice_name: str) -> str:
        """Clone a voice from an audio sample; return the locked ``voice_id``.

        The returned id is what ``voice_lock.lock_voice`` persists into
        ``.lanyin/voice-lock.json`` — every future episode references it.
        """
        sample_path = Path(sample)
        if not sample_path.exists():
            raise MiniMaxError(f"sample file not found: {sample_path}")
        # multipart upload — the platform expects the raw audio bytes.
        with sample_path.open("rb") as fh:
            files = {"file": (sample_path.name, fh, "audio/mpeg")}
            data: dict[str, str] = {"voice_name": voice_name}
            if self._group_id:
                data["group_id"] = self._group_id
            resp = self._client.post("/voice_clone", files=files, data=data)
        payload = _parse(resp)
        # schema_unverified: tolerate a few common field names.
        voice_id = (
            payload.get("voice_id")
            or payload.get("data", {}).get("voice_id")
            or payload.get("voice", {}).get("id")
        )
        if not voice_id:
            raise MiniMaxError(f"voice clone succeeded but no voice_id in response: {payload}")
        return str(voice_id)

    # --- m2: text→audio (called by synth.py once m2 is wired) --------------

    def synthesize(self, text: str, *, voice_id: str) -> bytes:
        """Synthesize ``text`` in the locked voice; return MP3 bytes.

        Called by synth.synthesize_episode (m2). Kept here so the only network
        surface in LanYin is this file.
        """
        body: dict[str, Any] = {
            "text": text,
            "voice_id": voice_id,
            "model": "speech-02-hd",  # MiniMax-H3 audio model handle (adjust on integration)
            "audio": {"format": "mp3", "channel": 2},  # stereo, per the H3 thesis
        }
        if self._group_id:
            body["group_id"] = self._group_id
        resp = self._client.post("/t2a_v2", json=body)
        # the platform returns the audio either inline (base64) or as a URL.
        payload = _parse(resp, expect_audio=True)
        if isinstance(payload, (bytes, bytearray)):
            return bytes(payload)
        if "data" in payload and isinstance(payload["data"], (bytes, bytearray)):
            return bytes(payload["data"])
        audio = payload.get("audio") or payload.get("data", {}).get("audio")
        if isinstance(audio, str) and audio.startswith("http"):
            # fetch the generated MP3 from the returned URL
            return httpx.get(audio, timeout=120.0).content
        raise MiniMaxError(f"synthesize response had no audio payload: {payload}")


def _parse(resp: httpx.Response, *, expect_audio: bool = False) -> Any:
    if resp.status_code >= 400:
        raise MiniMaxError(f"MiniMax API {resp.status_code}: {resp.text[:400]}")
    if expect_audio and resp.headers.get("content-type", "").startswith("audio"):
        return resp.content
    try:
        return resp.json()
    except ValueError:
        return resp.content
