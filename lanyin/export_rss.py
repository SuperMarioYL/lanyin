"""RSS 2.0 + iTunes-namespace feed generation (m3 — partial).

``generate_rss`` is a pure, fully-tested helper that turns a list of episodes
into a 小宇宙/喜马拉雅-compatible podcast RSS feed (the artifact the plan's
``assets.demo`` points at).

``export_series`` is the m3 CLI surface: it loads *built* episodes from
``dist/`` and writes ``dist/rss.xml``. Because episode building is m2 (not
wired in this milestone), in m1 there are no built episodes to export, so the
CLI reports the m3 roadmap honestly instead of emitting an empty feed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from .config import dist_dir, episodes_path
from .models import Episode


class ExportError(Exception):
    pass


# 小宇宙 (Xiaoyuzhou) and 喜马拉雅 (Ximalaya) both accept RSS 2.0 with the
# iTunes podcast namespace; the per-platform variance is small (category tax
# required by 喜马拉雅, itunes:explicit handling). The default namespace set
# below satisfies both validators.
_ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


def _iso(dt: str | datetime | None) -> str:
    if dt is None:
        return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    if isinstance(dt, datetime):
        return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
    return str(dt)


def generate_rss(
    episodes,
    *,
    channel,
) -> str:
    """Render an RSS 2.0 + iTunes feed string from ``episodes``.

    ``channel`` is a dict with at minimum: ``title``, ``link``, ``description``,
    ``author``; optional: ``category``, ``language``, ``image``, ``owner_email``,
    ``owner_name``.
    """
    if not isinstance(episodes, list):
        raise ExportError("episodes must be a list")
    title = escape(str(channel.get("title", "Untitled column")))
    link = escape(str(channel.get("link", "")))
    description = escape(str(channel.get("description", "")))
    author = escape(str(channel.get("author", "")))
    language = escape(str(channel.get("language", "zh-cn")))
    category = escape(str(channel.get("category", "Technology")))
    image = channel.get("image")
    owner_email = escape(str(channel.get("owner_email", "")))
    owner_name = escape(str(channel.get("owner_name", author)))

    items: list[str] = []
    for ep in episodes:
        if isinstance(ep, Episode):
            ep = ep.model_dump()
        items.append(_render_item(ep))

    image_block = ""
    if image:
        image_block = f'<itunes:image href="{escape(str(image))}"/>'

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" '
        f'xmlns:itunes="{_ITUNES_NS}" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/">\n'
        "  <channel>\n"
        f"    <title>{title}</title>\n"
        f"    <link>{link}</link>\n"
        f"    <description>{description}</description>\n"
        f"    <language>{language}</language>\n"
        f"    <itunes:author>{author}</itunes:author>\n"
        f"    <itunes:summary>{description}</itunes:summary>\n"
        f"    <itunes:category text=\"{category}\"/>\n"
        f"    {image_block}\n".rstrip()
        + "\n"
        + "    <itunes:explicit>false</itunes:explicit>\n"
        + f"    <itunes:owner><itunes:name>{owner_name}</itunes:name>"
        f"<itunes:email>{owner_email}</itunes:email></itunes:owner>\n"
        + "".join(items)
        + "  </channel>\n</rss>\n"
    )


def _render_item(ep: dict) -> str:
    title = escape(str(ep.get("title", "Untitled episode")))
    audio_url = escape(str(ep.get("audio_url", ep.get("audio_path", ""))))
    duration = str(ep.get("duration", ep.get("duration_seconds", "")))
    guid = escape(str(ep.get("guid", audio_url or title)))
    pub = escape(_iso(ep.get("pub_date", ep.get("published_at"))))
    desc = escape(str(ep.get("description", "")))
    size = str(ep.get("size_bytes", "0"))
    return (
        "    <item>\n"
        f"      <title>{title}</title>\n"
        f"      <description>{desc}</description>\n"
        f"      <enclosure url=\"{audio_url}\" length=\"{size}\" type=\"audio/mpeg\"/>\n"
        f"      <guid isPermaLink=\"false\">{guid}</guid>\n"
        f"      <pubDate>{pub}</pubDate>\n"
        f"      <itunes:duration>{duration}</itunes:duration>\n"
        "    </item>\n"
    )


def export_series(
    platform: str = "xiaoyuzhou",
    *,
    root: Path | str | None = None,
) -> Path:
    """Load built episodes from ``dist/`` and write ``dist/rss.xml`` (m3).

    Requires episodes built by ``lanyin build`` (m2) — i.e. registry entries
    that carry a synthesized ``audio_path``. In m1 no episodes are built yet
    (``add`` only registers the source + chapter titles), so this raises
    ``ExportError`` pointing at the roadmap. The pure ``generate_rss`` helper
    above is available and tested regardless.
    """
    if platform not in ("xiaoyuzhou", "ximalaya"):
        raise ExportError(
            f"unknown platform {platform!r} — choose xiaoyuzhou or ximalaya"
        )
    registry = _load_built_episodes(root)
    if not registry:
        raise ExportError(
            "no built episodes found — `lanyin build` (m2) is not implemented "
            "in this milestone, so there is nothing to export yet. See the roadmap."
        )
    from .config import load_config  # local import to avoid a cycle
    cfg = load_config(root)
    channel = {
        "title": (cfg.column_name if cfg else f"{platform} column"),
        "link": "",
        "description": f"LanYin-generated column ({platform})",
        "author": "LanYin",
        "language": "zh-cn",
        "category": "Technology",
    }
    xml = generate_rss(registry, channel=channel)
    out = dist_dir(root) / "rss.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(xml, encoding="utf-8")
    return out


def _load_built_episodes(root: Path | str | None = None) -> list[dict]:
    """Read the episode registry and return only entries that have been built.

    ``add`` registers source + chapter titles but no audio; ``build`` (m2)
    fills ``audio_path``/``duration``/``size_bytes``. Only built entries are
    exportable, so in m1 this always returns ``[]``.
    """
    path = episodes_path(root)
    if not path.exists():
        return []
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:  # pragma: no cover - defensive
        return []
    return [e for e in registry if e.get("audio_path") or e.get("audio_url")]
