[English](./README.en.md) · [Website](https://lanyin.lei6393.com) · [GitHub](https://github.com/SuperMarioYL/lanyin)

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/hero-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/hero-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/hero-dark.svg">
  <img src="./assets/presentation/hero-light.svg" width="960" alt="Hero diagram">
</picture>

# 栏音 LanYin

**先整理栏目，再准备配音**

栏音保存栏目配置，从 Markdown 提取章节标题并登记每期内容，还提供 MiniMax 客户端记录可复用音色档案；lanyin build 以锁定的音色按章节合成单集音频并嵌入 ID3 章节标记。

## 为什么需要它

连载音频项目需要一致的单集结构，也需要明确记录准备使用的音色配置。栏音把这些准备工作放在一起，使每篇文章在合成前都可以检查。

- **Markdown 章节** — 按配置的标题级别提取有序章节列表。
- **本地单集登记** — 来源路径和解析后的章节元数据保存到 .lanyin/episodes.json。
- **可复用音色档案** — 音色锁文件记录选定的服务商 Voice ID 及其配置。

## 架构

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/architecture-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/architecture-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/architecture-dark.svg">
  <img src="./assets/presentation/architecture-light.svg" width="960" alt="Architecture diagram">
</picture>

config.py 读取 lanyin.toml 并管理本地登记文件；chapter.py 使用 MarkdownIt 提取标题、去掉强调等语法。add 按归一化的来源路径保存章节数据。voice_lock.py 通过 MiniMax 上传选定参考音频并保存返回档案；synthesize_episode 以锁定的音色逐章合成、拼接音频并嵌入章节帧。

| 组件 | 职责 |
| --- | --- |
| `Column TOML` | name and heading level |
| `Markdown parser` | ordered chapter titles |
| `Episode registry` | source and chapter metadata |
| `Voice profile` | provider voice ID |

## 安装与快速上手

需要 Python 3.12+ 和 uv。章节示例不需要音频服务或密钥。

```bash
git clone https://github.com/SuperMarioYL/lanyin.git
cd lanyin
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .
```

示例内含完整 Markdown 单集内容，在临时目录创建栏目、保存解析后的章节并重新读取登记文件，只生成元数据。

```bash
.venv/bin/python examples/presentation_demo.py
```

## 实际运行示例

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/process-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/process-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/process-dark.svg">
  <img src="./assets/presentation/process-light.svg" width="960" alt="Process diagram">
</picture>

One locally registered episode with three chapter titles; all timing offsets remain zero.

```text
{
  "column_id": "cache-notes",
  "episodes": 1,
  "chapters": [
    {
      "title": "认识缓存",
      "start_offset": 0.0,
      "end_offset": 0.0
    },
    {
      "title": "失效策略",
      "start_offset": 0.0,
      "end_offset": 0.0
    },
    {
      "title": "下一步",
      "start_offset": 0.0,
      "end_offset": 0.0
    }
  ]
}
Scope: chapter parsing and local episode registry; offsets are placeholders, no audio synthesized.
```

完整命令与输出保存在 [docs/demo-results.json](./docs/demo-results.json). 输入和复现代码均随仓提供。

![已有终端录制](./assets/demo.gif)

保留已有录制供参考；上方文字示例给出当前可复现的操作。

## 用法

在准备保存 lanyin.toml 的目录运行 init。add 会替换同一来源文件的登记条目：路径已归一化，./ep01.md 与绝对路径指向同一条记录。voice show 显示现有音色锁，未创建时返回 1。创建音色锁需配置服务商变量，再以有权使用的参考音频运行 voice lock --sample ./voice.mp3 --name "Narrator"。

```bash
lanyin init my-column --heading-level 2
lanyin add ./examples/ep01.md
lanyin voice show
```

## 配置

[column] 定义 column_id、column_name、chapter_heading_level（默认 2）和 platform_target（xiaoyuzhou 或 ximalaya）。.lanyin/voice-lock.json 保存音色档案，.lanyin/episodes.json 保存来源及标题。服务商操作需要 MINIMAX_API_KEY，MINIMAX_GROUP_ID 是可选端点配置。build 之后，章节偏移来自每个章节音频的实际时长。

## 集成与职责分工

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/integrations-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/integrations-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/integrations-dark.svg">
  <img src="./assets/presentation/integrations-light.svg" width="960" alt="Integrations diagram">
</picture>

本地解析器和登记功能无需 API。音色锁路径需要服务商账户并上传参考样本。generate_rss 可将给定单集元数据生成 XML，但不会合成音频、托管文件或证明播客平台接收成功。

| 路径 | 已实现职责 |
| --- | --- |
| Markdown | heading-based chapter extraction |
| TOML | column configuration |
| JSON | episode and voice metadata |
| MiniMax API | voice-profile request client |
| RSS helper | XML generation from supplied metadata |

## 限制与后续方向

- lanyin build 需要已创建的音色锁和 MINIMAX_API_KEY：它逐章调用服务商接口，离线示例无法运行完整合成。
- RSS 导出需要已生成音频的单集。示例 RSS URL 是说明性内容，不代表已发布音频。
- 记录示例未测量音色质量、跨集一致性或平台导入。

已实现栏目初始化、Markdown 章节、单集登记、服务商客户端、音色档案保存和按章节合成（含带时间信息的 ID3 章节帧与音频拼接）。托管、订阅和音色市场尚未实现。

## 许可与贡献

许可见 [LICENSE](./LICENSE). 反馈问题时请提供最小输入、执行命令和实际输出。
