"""LanYin (栏音) — turn a serialized WeChat column into a voice-locked, chapter-structured, subscribable audio series.

The core primitive is the column-level voice lock (栏目级音色锁): a persisted
voice profile that survives across episodes, so every episode of one column
sounds like the same narrator.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
