"""Column config + path store.

The column config is a small TOML file (``lanyin.toml``) at the project root;
the voice lock + episode registry live under ``.lanyin/``. Both are local-only
state — nothing leaves the user's machine except the MiniMax-H3 API call in
``voice_lock.lock_voice``.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from pydantic import BaseModel

CONFIG_FILENAME = "lanyin.toml"
LOCK_DIRNAME = ".lanyin"
LOCK_FILENAME = "voice-lock.json"
EPISODES_FILENAME = "episodes.json"
DIST_DIRNAME = "dist"


class LanyinConfig(BaseModel):
    """The column config written by ``lanyin init``."""

    column_id: str
    column_name: str
    chapter_heading_level: int = 2
    platform_target: str = "xiaoyuzhou"  # xiaoyuzhou | ximalaya


class ConfigError(Exception):
    pass


def project_root(start: Path | str | None = None) -> Path:
    return (Path(start) if start else Path.cwd()).resolve()


def config_path(root: Path | str | None = None) -> Path:
    return project_root(root) / CONFIG_FILENAME


def lock_dir(root: Path | str | None = None) -> Path:
    return project_root(root) / LOCK_DIRNAME


def lock_path(root: Path | str | None = None) -> Path:
    return lock_dir(root) / LOCK_FILENAME


def episodes_path(root: Path | str | None = None) -> Path:
    return lock_dir(root) / EPISODES_FILENAME


def dist_dir(root: Path | str | None = None) -> Path:
    return project_root(root) / DIST_DIRNAME


def slugify(text: str) -> str:
    """ASCII-safe slug for column_id (CN columns fall back to pinyin-free slug)."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    text = re.sub(r"(?u)[\u4e00-\u9fff]+", "", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "column"


def load_config(root: Path | str | None = None) -> LanyinConfig | None:
    path = config_path(root)
    if not path.exists():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"invalid {CONFIG_FILENAME}: {exc}") from exc
    table = data.get("column", data)
    return LanyinConfig(**table)


def require_config(root: Path | str | None = None) -> LanyinConfig:
    cfg = load_config(root)
    if cfg is None:
        raise ConfigError(
            f"no {CONFIG_FILENAME} found in {project_root(root)} — "
            "run `lanyin init <column-name>` first"
        )
    return cfg


def _toml_dump(cfg: LanyinConfig) -> str:
    """Hand-roll a tiny TOML (the config has only scalar fields)."""
    return (
        "# LanYin column config — see https://github.com/SuperMarioYL/lanyin\n"
        "[column]\n"
        f'column_id = "{_escape(cfg.column_id)}"\n'
        f'column_name = "{_escape(cfg.column_name)}"\n'
        f"chapter_heading_level = {int(cfg.chapter_heading_level)}\n"
        f'platform_target = "{_escape(cfg.platform_target)}"\n'
    )


def _escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def write_config(cfg: LanyinConfig, root: Path | str | None = None) -> Path:
    path = config_path(root)
    path.write_text(_toml_dump(cfg), encoding="utf-8")
    return path


def init_config(
    column_name: str,
    *,
    column_id: str | None = None,
    chapter_heading_level: int = 2,
    platform_target: str = "xiaoyuzhou",
    root: Path | str | None = None,
) -> LanyinConfig:
    cfg = LanyinConfig(
        column_id=column_id or slugify(column_name) or "column",
        column_name=column_name,
        chapter_heading_level=chapter_heading_level,
        platform_target=platform_target,
    )
    write_config(cfg, root=root)
    # ensure the local state dir exists
    lock_dir(root).mkdir(parents=True, exist_ok=True)
    return cfg


# --- episode registry (a thin JSON store under .lanyin/) -------------------


def load_episodes(root: Path | str | None = None) -> list[dict]:
    path = episodes_path(root)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:  # pragma: no cover - defensive
        return []


def save_episodes(episodes: list[dict], root: Path | str | None = None) -> Path:
    d = lock_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    path = episodes_path(root)
    path.write_text(json.dumps(episodes, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
