"""RSS 2.0 + iTunes-namespace feed generation.

``generate_rss`` is a pure, fully-tested helper that turns a list of episodes
into a 小宇宙/喜马拉雅-compatible podcast RSS feed (the artifact the plan's
``assets.demo`` points at).

``export_series`` is the CLI surface: it loads *built* episodes (registry
entries whose audio exists in ``dist/``) and writes ``dist/rss.xml`` in the
platform given by ``--platform`` or, by default, the column's
``platform_target``. It does not host the audio — enclosures keep their local
``dist/<stem>.mp3`` path and the user uploads the files to the platform.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from .config import dist_dir, load_config, load_episodes
from .models import Episode


class ExportError(Exception):
    pass


def _attr(value) -> str:
    """Escape a value for use inside a double-quoted XML attribute.

    ``escape`` alone leaves ``"`` untouched, so a value containing a double
    quote would terminate the attribute early and produce malformed XML.
    """
    return escape(str(value), {'"': "&quot;"})


_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _rfc822(dt: datetime) -> str:
    """Render ``dt`` as an RFC 822 date with its own UTC offset.

    Weekday and month names come from fixed English tables, not ``strftime``:
    ``%a``/``%b`` follow the process locale, so a user running under e.g.
    zh_CN would otherwise emit ``六, 12 9月 2026 ...`` which is not a valid
    RFC 822 date and can be rejected by feed validators.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    seconds = int((dt.utcoffset() or timedelta(0)).total_seconds())
    sign = "+" if seconds >= 0 else "-"
    hh, mm = divmod(abs(seconds) // 60, 60)
    return (
        f"{_WEEKDAYS[dt.weekday()]}, {dt.day:02d} {_MONTHS[dt.month - 1]} {dt.year:04d} "
        f"{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d} {sign}{hh:02d}{mm:02d}"
    )


def _iso(dt: str | datetime | None) -> str:
    if dt is None:
        return _rfc822(datetime.now(timezone.utc))
    if isinstance(dt, datetime):
        return _rfc822(dt)
    return str(dt)


# 小宇宙 (Xiaoyuzhou) and 喜马拉雅 (Ximalaya) both accept RSS 2.0 with the
# iTunes podcast namespace; the per-platform variance is small (category tax
# required by 喜马拉雅, itunes:explicit handling). The default namespace set
# below satisfies both validators.
_ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


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
    # raw author feeds the owner_name fallback; each position escapes exactly once
    author_raw = str(channel.get("author", ""))
    title = escape(str(channel.get("title", "Untitled column")))
    link = escape(str(channel.get("link", "")))
    description = escape(str(channel.get("description", "")))
    author = escape(author_raw)
    language = escape(str(channel.get("language", "zh-cn")))
    # raw category feeds the attribute below, which escapes it exactly once
    category = str(channel.get("category", "Technology"))
    image = channel.get("image")
    owner_email = escape(str(channel.get("owner_email", "")))
    owner_name = escape(str(channel.get("owner_name", author_raw)))

    items: list[str] = []
    for ep in episodes:
        if isinstance(ep, Episode):
            ep = ep.model_dump()
        items.append(_render_item(ep))

    image_block = ""
    if image:
        image_block = f'<itunes:image href="{_attr(image)}"/>'

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
        f"    <itunes:category text=\"{_attr(category)}\"/>\n"
        f"    {image_block}\n".rstrip()
        + "\n"
        + "    <itunes:explicit>false</itunes:explicit>\n"
        + f"    <itunes:owner><itunes:name>{owner_name}</itunes:name>"
        f"<itunes:email>{owner_email}</itunes:email></itunes:owner>\n"
        + "".join(items)
        + "  </channel>\n</rss>\n"
    )


def _duration(value) -> str:
    """Render an ``itunes:duration`` value.

    The podcast spec accepts whole seconds or ``HH:MM:SS``, but a built
    registry entry carries the measured length as a float, so numeric values
    are rounded to whole seconds; caller-supplied strings ("642", "10:42")
    pass through untouched.
    """
    if value is None or value == "":
        return ""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    return str(int(round(value)))


def _render_item(ep: dict) -> str:
    # raw values feed the guid fallback; each position escapes exactly once
    source = str(ep.get("source", ""))
    # the registry records a source path but no episode title, so the file
    # stem is the stable documented name for a registry-built episode
    stem = Path(source).stem if source else ""
    title_raw = str(ep.get("title") or stem or "Untitled episode")
    audio_raw = str(ep.get("audio_url", ep.get("audio_path", "")))
    title = escape(title_raw)
    audio_url = _attr(audio_raw)
    duration = _duration(ep.get("duration", ep.get("duration_seconds", "")))
    guid = escape(str(ep.get("guid", audio_raw or title_raw)))
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
    platform: str | None = None,
    *,
    root: Path | str | None = None,
) -> Path:
    """Load built episodes from ``dist/`` and write ``dist/rss.xml``.

    ``platform`` defaults to the column's configured ``platform_target``
    (``xiaoyuzhou`` when there is no config). Requires episodes built by
    ``lanyin build`` — registry entries that carry a synthesized
    ``audio_path``; ``add`` alone registers no audio, so an unbuilt column
    raises ``ExportError`` telling the user to run the build first.
    """
    cfg = load_config(root)
    platform = platform or (cfg.platform_target if cfg else "xiaoyuzhou")
    if platform not in ("xiaoyuzhou", "ximalaya"):
        raise ExportError(
            f"unknown platform {platform!r} — choose xiaoyuzhou or ximalaya"
        )
    registry = _load_built_episodes(root)
    if not registry:
        raise ExportError(
            "no built episodes found — run `lanyin build` (or `lanyin build "
            "<file>`) first; only episodes with audio in dist/ can be exported"
        )
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
    """Return the registry entries that have been built.

    ``add`` registers source + chapter titles but no audio; ``build`` fills in
    ``audio_path``/``size_bytes``/``duration_seconds``. Only built entries are
    exportable; ``load_episodes`` owns reading (and rejecting) the file.
    """
    return [
        entry
        for entry in load_episodes(root)
        if entry.get("audio_path") or entry.get("audio_url")
    ]
