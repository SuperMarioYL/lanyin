<div align="right"><sub><b>简体中文</b>&nbsp;&nbsp;⇄&nbsp;&nbsp;<a href="./README.en.md">English</a></sub></div>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/hero-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="./assets/hero-light.svg">
  <img src="./assets/hero-light.svg" width="880" alt="LanYin 栏音 — 把公众号连载栏目变成音色统一、可订阅的有声系列">
</picture>

<p align="center"><sub>LanYin 是把公众号连载栏目变成可订阅有声系列的音色锁 Skill。</sub></p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="license"></a>
  <a href="https://github.com/SuperMarioYL/lanyin/releases"><img src="https://img.shields.io/github/v/release/SuperMarioYL/lanyin" alt="release"></a>
  <a href="https://github.com/SuperMarioYL/lanyin/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/SuperMarioYL/lanyin/ci.yml?label=ci" alt="ci"></a>
  <img src="https://img.shields.io/badge/python-3.12-blue" alt="python">
  <img src="https://img.shields.io/badge/Skill-ready-5E5CE6" alt="Skill">
  <img src="https://img.shields.io/badge/Minimax%20H3-base-10A37F" alt="Minimax H3">
</p>

**通用 TTS 每期音色漂移、章节靠手贴、导出靠人拼——LanYin 一条命令锁栏目音色、出章节化 MP3、导出小宇宙/喜马拉雅 RSS。**

<h2><img src="https://api.iconify.design/tabler:topology-star-3.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 架构</h2>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/atlas-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="./assets/atlas-light.svg">
  <img src="./assets/atlas-light.svg" width="880" alt="架构：公众号 Markdown + 栏目级音色锁 → LanYin CLI → 章节化 MP3 + 小宇宙/喜马拉雅 RSS">
</picture>

一个 Python 进程、一个 `.lanyin/` 配置目录。MiniMax H3 是唯一的网络依赖；API 不可用时构建直接停下并报清晰错误——绝不偷偷换一个音色（那会破坏锁）。

## 目录

- [为什么做这个](#为什么做这个)
- [安装](#安装) · [快速开始](#快速开始)
- [用法](#用法)
- [演示](#演示)
- [配置](#配置)
- [付费](#付费)
- [路线图](#路线图)
- [许可证](#许可证) · [分享](#分享)

## 为什么做这个

公众号连载作者想做小宇宙/喜马拉雅有声臂，第 11 期的声音已经对不上第 3 期——通用 TTS 每篇重新合成、音色跨期漂移，章节边界手贴、平台导出手拼。**栏目级音色锁**是 op7418 一直在讨论的"可复用 **Skill**"层的音频版：同一把 `voice_id` 锁进 `.lanyin/voice-lock.json`，跨 10 期盲测一致，让作者从 TTS 操作员回归出版者。MiniMax H3 是 omni-modal 立体声生成底座，但缺公众号连载→小宇宙/喜马拉雅有声系列的工作流——LanYin 给底座接上栏目级音色锁 + 章节切分 + 平台合规导出这三层。

## 安装

```bash
pip install lanyin        # 或：uv tool install lanyin
```

需要 Python ≥ 3.12。语音克隆需要 MiniMax H3 API key（见[配置](#配置)）；`init` / `add` / `voice show` 离线可用。

## 快速开始

冷启动到首个可见结果，三行：

```bash
lanyin init 硅谷早茶                 # 生成 lanyin.toml
lanyin add examples/ep01.md         # ## 标题自动变章节标记
lanyin voice show                   # 读取已锁音色（m1）
```

<details><summary>示例输出</summary>

```
╭─ episode registered ─────────────╮
│ source        ep01.md            │
│ chapters      3                   │
│ registry      .lanyin/episodes.json│
╰───────────────────────────────────╯
  ch01  第一章 为什么要锁栏目级音色
  ch02  第二章 MiniMax H3 是底座，LanYin 是工作流
  ch03  第三章 一条命令出可订阅系列
```

</details>

锁定一把 MiniMax H3 音色（需要 `MINIMAX_API_KEY`）：

```bash
export MINIMAX_API_KEY=mm-xxxxxxxx
lanyin voice lock --sample ./voice.mp3 --name "作者签名音色"   # 写 .lanyin/voice-lock.json（m1）
```

## 用法

<h2><img src="https://api.iconify.design/tabler:terminal-2.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 用法</h2>

```bash
lanyin init <栏目名> --platform xiaoyuzhou        # 脚手架 lanyin.toml（xiaoyuzhou | ximalaya）
lanyin voice lock --sample ./voice.mp3 --name "签名音色"  # 克隆并锁定 MiniMax H3 音色（m1）
lanyin voice show                                  # 打印已锁栏目音色档案（m1）
lanyin add ./ep01.md                               # 注册一期；## 标题变章节（纯函数）
lanyin build ./ep01.md                             # 用锁定音色合成章节化 MP3（m2 · 路线图）
lanyin export rss --platform xiaoyuzhou            # 导出小宇宙/喜马拉雅合规 RSS（m3 · 路线图）
```

m1 已实现：`voice lock` + `voice show` + 章节解析器 + MiniMax H3 客户端。m2（合成 + ID3 CHAP 嵌入）与 m3（批量导出）在路线图上——CLI 已就位，跑起来会诚实告诉你"未在本里程碑实现"。

完整示例见 `examples/`：`ep01.md`（三章节样例栏目）、`voice-lock.sample.json`（已锁音色档案，用于离线演示）。

## 演示

<h2><img src="https://api.iconify.design/tabler:photo.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 演示</h2>

![demo](assets/demo.gif)

脚本：`docs/demo.tape`（用 [vhs](https://github.com/charmbracelet/vhs) 渲染到 `assets/demo.gif`，CI 在 `.github/workflows/demo.yml` 手动触发刷新）。上面跑的是 m1 happy path：`init` → 种入已锁音色 → `voice show` → `add` → 诚实的 m2/m3 路线图提示。

**样例有声系列**（`assets.demo` 工件）——一个真实公众号连载栏目 10 期，全部用同一把锁定的 MiniMax H3 音色合成，盲测跨期一致：

<details><summary>docs/demo/xiaoyuzhou-sample-rss.xml（小宇宙合规 RSS，10 期）</summary>

```xml
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>硅谷早茶</title>
    <description>10 期全部使用同一把锁定的 MiniMax-H3 voice_id 合成——盲测跨期一致。</description>
    <itunes:author>作者签名音色（LanYin 锁定）</itunes:author>
    <item>
      <title>第 1 期 · 为什么要锁栏目级音色</title>
      <enclosure url="https://cdn.example.com/lanyin/guigu-zaocha/ep01.mp3" length="4823100" type="audio/mpeg"/>
      <itunes:duration>612</itunes:duration>
    </item>
    <!-- ... 9 期同锁样本 ... -->
  </channel>
</rss>
```

</details>

完整 10 期 RSS 见 [`docs/demo/xiaoyuzhou-sample-rss.xml`](./docs/demo/xiaoyuzhou-sample-rss.xml)——这就是 m3 `lanyin export rss --platform xiaoyuzhou` 的目标产物形态。

## 配置

`lanyin init` 生成 `lanyin.toml`（TOML，标准库可读，无额外依赖）；音色锁与章节注册表在 `.lanyin/`（本地状态，已 gitignore）。

| 键 | 类型 | 默认 | 含义 |
|---|---|---|---|
| `column.column_id` | str | 由栏目名 slug 生成 | 栏目标识，写入音色锁 |
| `column.column_name` | str | — | 人类可读栏目名 |
| `column.chapter_heading_level` | int | `2` | 哪一级 Markdown 标题算章节（`##` = 2） |
| `column.platform_target` | str | `xiaoyuzhou` | 导出目标平台：`xiaoyuzhou` \| `ximalaya` |
| 环境变量 `MINIMAX_API_KEY` | str | — | MiniMax H3 API key，`voice lock` 需要 |
| 环境变量 `MINIMAX_GROUP_ID` | str | — | 可选，部分 MiniMax 端点需要 |

## 付费

<h2><img src="https://api.iconify.design/tabler:coins.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 付费</h2>

LanYin 是 OSS CLI，免费、可自托管。商业路线是**托管层 栏目托管**（m1 之后）：

- **免费 CLI**：锁音色、章节化 MP3、本地导出 RSS——本仓库即此。
- **栏目托管 ¥39/月 / 栏**（单作者）：新一期粘贴后自动用锁定音色重建小宇宙/喜马拉雅 RSS；不想每周二跑 CLI 的人为此付费。
- **团队版 ¥99/月**（≤5 栏目、≤3 席位）：多栏目团队工作区 + 精品授权音色包（超出免费 MiniMax H3 预设）。

音色锁 + 章节资产是 moat，托管层只是把它租出去。最小"刷卡"演示：作者把 ep11 markdown 粘进托管工作区 → RSS 用锁定音色自动重建 → 一键推小宇宙后台。免费 CLI 证明音色锁；付费路径证明"我不想每周二跑 CLI"。

> 推送后建议加 topics：`gh repo edit --add-topic tts --add-topic podcast --add-topic minimax --add-topic voice-clone --add-topic wechat`

## 路线图

<h2><img src="https://api.iconify.design/tabler:map-2.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 路线图</h2>

- [x] **m1 栏目级音色锁** — `voice lock` 写 `.lanyin/voice-lock.json`；`voice show` 打印已锁档案；MiniMax H3 客户端 + 章节解析器就位。
- [ ] **m2 章节化合成** — `lanyin build ./ep01.md` 用锁定音色合成 `dist/ep01.mp3`，ID3 `CHAP` 帧由 `##` 标题生成；二期同锁盲测一致。
- [ ] **m3 系列导出** — `lanyin build`（无参，批量）+ `lanyin export rss --platform xiaoyuzhou|ximalaya` 出平台合规 RSS。
- [ ] **未来** — 托管 栏目托管 层；音色市场；多栏目管理；豆包/CosyVoice 跨期稳定 voice_id + 章节标记 + 平台导出若补齐则 reassess（§8 falsifier）。

## 许可证

<h2><img src="https://api.iconify.design/tabler:license.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 许可证</h2>

MIT — 见 [LICENSE](./LICENSE)。提 issue 或 PR 请到 [issues](https://github.com/SuperMarioYL/lanyin/issues)。

## 分享

```
栏音 LanYin — 把公众号连载变成统一音色有声系列的 Skill。一把 voice_id 锁栏目、## 章节自动成 ID3 标记、一条命令导出小宇宙/喜马拉雅 RSS。盲测 10 期一致才是 moat。https://github.com/SuperMarioYL/lanyin
```

<p align="center"><sub><a href="./LICENSE">MIT</a> © 2026 SuperMarioYL</sub></p>
