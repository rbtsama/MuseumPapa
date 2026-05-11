# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

**North Shore Library Benefits — Data Collection (v0.1)**

Massachusetts NorthShore 区域(Wakefield 周边 ~20 分钟车程)的图书馆 museum-pass 福利数据建设项目。本期 v0.1 的目标是把 BRD(`docs/BRD.md`)第 6/7 章列出的所有"应该能拿到"的数据,通过 scraper + Claude 会话内整理拿到本地,产出三份核心结构化 JSON:

- `data/structured/libraries.json` — 15 馆元数据
- `data/structured/attractions.json` — 52 景元数据
- `data/structured/passes.json` — (馆 × 景) 矩阵的折扣/凭证/限制字段

**本期不做**:HTML 渲染层、真实预订日志、Google Maps 距离 API、MA 全境扩展、自动下单、JSON Schema 校验框架、正式 README/PRD/chat.md。详细范围见 `docs/BRD.md` 和计划 `C:\Users\Administrator\.claude\plans\fluffy-whistling-lampson.md`。

## Repository Layout

```
.
├── CLAUDE.md                  # 本文件
├── pyproject.toml             # Python 3.11+,依赖 playwright(可选)
├── .gitignore                 # 排除 data/.cache/、config/owned_*.json、_tmp_*
├── backup/                    # 上一代代码,只读参考
├── docs/BRD.md                # 业务需求文档(权威)
├── src/malibbene/             # 主包(MA Library Benefits)
│   ├── common/                # http / browser / snapshot / status
│   └── sources/               # 一个数据源一个模块(assabet/bpl/winchester/...)
├── scripts/                   # CLI 入口
├── data/raw/                  # scraper 直接产出
├── data/structured/           # Claude 整理后的最终数据
├── data/dynamic/              # availability(可频繁覆盖)
├── data/snapshots/<日期>/     # 历史快照,供 diff
└── config/                    # 配置种子(library_seeds.json + benefit_seeds.json + owned_cards.json[私])
```

## File Naming Convention (CRITICAL)

- **scraper 模块**:`src/malibbene/sources/<source>/<dataset>.py`(snake_case)
- **CLI 入口**:`scripts/<动词>_<对象>.py`(`scripts/scrape_static.py`)
- **raw 数据**:`data/raw/<source>/<dataset>[/<entity>].<ext>`
- **结构化数据**:`data/structured/<entity>.json`
- **动态库存**:`data/dynamic/<source>_availability.json`
- **历史快照**:`data/snapshots/<YYYY-MM-DD>/<同 raw 路径>`
- **配置种子**:`config/<entity>_seeds.json`
- **私有数据**(gitignored):`config/owned_*.json`
- **临时文件**:**必须以 `_tmp_` 开头**,放在最相关目录里,版本里程碑前清空

`_tmp_` 前缀适用于任何一次性、调试、scratch、探索性文件。`git ls-files | grep _tmp_` 应该列出可删清单。

## How to Run

```bash
# Phase 1 — 一次性静态数据(完成后产出 data/raw/*)
python scripts/scrape_static.py

# Phase 2 — 在 Claude Code 会话里说"整理 libraries / attractions / passes"
#           我会读 data/raw/* 并写 data/structured/*

# Phase 3 — 动态库存(可重复跑)
python scripts/scrape_dynamic.py

# 维护:索引页变更检测
python scripts/snapshot_diff.py
```

需要 Playwright 时(JS-rendered 景点官网):

```bash
pip install playwright
playwright install chromium
```

## Key Technical Decisions

- **HTTP 层**:`malibbene.common.http.fetch(url, *, render_js=False, force=False)`,默认 urllib + 3 次指数退避 + 30s 超时,同 URL 24h 缓存到 `data/.cache/`
- **Playwright**:可选依赖,首次 `render_js=True` 检测缺失才提示安装
- **状态兜底**:每个 raw JSON 顶层 `meta.status_summary = {ok, empty, failed}`,parser 失败的 cell 标 `status: "failed:<reason>"`,不静默丢失
- **快照 + diff**:每次主索引页 scraper 跑完先把上一份 raw 移到 `data/snapshots/<日期>/`

## Reusable code from `backup/`

| backup 文件 | 复用到 | 程度 |
|---|---|---|
| `scrape_availability.py` | `sources/assabet/availability.py` | 90% |
| `scrape_pass_format.py` | `sources/assabet/index_page.py` 切块 | 60% |
| `scrape_bpl_availability.py` | `sources/bpl/availability.py` | 95% |
| `slug_map.py` 的 LIB_DOMAIN | `config/library_seeds.json` 初值 | 100% |
| `library-cards.json` | `config/owned_cards.json` | 100% |

## General Rules (来自用户全局配置)

- 回复语言:默认中文,技术术语保留英文
- 回复结构:
  - 📊 记忆使用:X%
  - 🎯 理解总结:[用户需求简要概括]
  - 📝 任务清单:
    □ 任务1
    □ 任务2
  - 🚀 执行结果:[详细内容]
- 编码规范:所有文件使用 UTF-8,中文注释优先
- 确认机制:重要操作前先确认理解
- 时区:所有时间显示使用美国加州时间(PST/PDT, UTC-8/UTC-7)
- **⚠️ Git 提交铁律(强制执行)**:
  - 每次修改代码后必须立即 `git add` 相关文件 + `git commit`
  - 提交信息清晰描述修改内容
  - 不暂存 `_tmp_*` 文件、不提交 `config/owned_*.json`(已 gitignored)
- 用户卡 barcode 严禁出现在 commit message / 日志输出 / 任何会推到远端的位置
