"""Register a complete Markdown episode without calling a TTS provider."""
import json
from tempfile import TemporaryDirectory
from lanyin.chapter import parse_chapters
from lanyin.config import init_config, save_episodes, load_episodes
markdown = "# 示例栏目\n\n## 认识缓存\n缓存保存可复用的结果。\n\n## **失效策略**\n数据变化后需要重新计算。\n\n## 下一步\n为每类数据选择有效期。\n"
with TemporaryDirectory(prefix="lanyin-demo-") as root:
    config = init_config("Cache notes", root=root)
    chapters = parse_chapters(markdown, heading_level=config.chapter_heading_level)
    save_episodes([{"source":"episode.md","column_id":config.column_id,"chapters":[c.model_dump() for c in chapters]}], root=root)
    episodes = load_episodes(root)
    print(json.dumps({"column_id":config.column_id,"episodes":len(episodes),"chapters":episodes[0]["chapters"]}, ensure_ascii=False, indent=2))
print("Scope: chapter parsing and local episode registry; offsets are placeholders, no audio synthesized.")
