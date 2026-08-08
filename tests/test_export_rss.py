"""Tests for the RSS generation helper (pure; m3 export_series is gated on m2)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from lanyin.export_rss import ExportError, export_series, generate_rss


def _channel():
    return {
        "title": "硅谷早茶",
        "link": "https://example.com/column/sv-breakfast",
        "description": "一个把公众号连载变成有声系列的样例栏目",
        "author": "LanYin Demo",
        "language": "zh-cn",
        "category": "Technology",
        "image": "https://example.com/cover.jpg",
        "owner_email": "owner@example.com",
        "owner_name": "LanYin Demo",
    }


def _ep(n: int) -> dict:
    return {
        "title": f"第 {n} 章 样例标题",
        "description": f"第 {n} 章的简介。",
        "audio_url": f"https://cdn.example.com/ep{n:02d}.mp3",
        "size_bytes": 1234567,
        "duration": "642",
        "guid": f"lanyin-ep{n:02d}",
        "pub_date": f"Mon, {n:02d} Jul 2026 09:00:00 +0000",
    }


def test_generate_rss_well_formed_xml() -> None:
    xml = generate_rss([_ep(1), _ep(2)], channel=_channel())
    root = ET.fromstring(xml)  # raises on malformed XML
    assert root.tag == "rss"
    assert root.attrib["version"] == "2.0"
    channel = root.find("channel")
    assert channel is not None
    assert channel.findtext("title") == "硅谷早茶"
    assert channel.findtext("language") == "zh-cn"
    items = channel.findall("item")
    assert len(items) == 2
    assert items[0].findtext("title") == "第 1 章 样例标题"
    enc = items[0].find("enclosure")
    assert enc is not None
    assert enc.attrib["url"] == "https://cdn.example.com/ep01.mp3"
    assert enc.attrib["type"] == "audio/mpeg"
    assert items[0].findtext("itunes:duration", namespaces={"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}) == "642"


def test_generate_rss_empty_episodes_still_valid() -> None:
    xml = generate_rss([], channel=_channel())
    root = ET.fromstring(xml)
    channel = root.find("channel")
    assert channel is not None
    assert channel.findall("item") == []


def test_generate_rss_escapes_special_chars() -> None:
    ch = _channel()
    ch["title"] = "<硅谷>&早茶"
    xml = generate_rss([], channel=ch)
    root = ET.fromstring(xml)
    assert root.find("channel").findtext("title") == "<硅谷>&早茶"


def test_export_series_no_episodes_raises(tmp_path) -> None:
    # no dist/ and no built episodes in m1
    with __import__("pytest").raises(ExportError, match="no built episodes"):
        export_series("xiaoyuzhou", root=tmp_path)


def test_export_series_unknown_platform_raises(tmp_path) -> None:
    with __import__("pytest").raises(ExportError, match="unknown platform"):
        export_series("spotify", root=tmp_path)
