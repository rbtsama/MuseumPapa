# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## ⚙️ 会话开头必查:开发工具

**每次新会话开始时,先用下面两条命令确认本项目环境就绪。如果有任何一条失败,先帮用户补齐再开始干活。**

| 工具 | 用途 | 检查命令 | 修复指令 |
|---|---|---|---|
| **rtk**(Rust Token Killer) | 压缩工具输出,省 60-90% token | `rtk --version` 输出 `rtk <ver>` | 装:从 https://github.com/rtk-ai/rtk/releases 下 `rtk-x86_64-pc-windows-msvc.zip`,解压后把 `rtk.exe` 放到 `~/.local/bin/`(已在 PATH) |
| **superpowers**(Claude Code 插件) | 结构化软件开发方法论(design → plan → TDD → review) | `cat ~/.claude/plugins/installed_plugins.json` 里出现 `"projectPath": "F:\\pj\\NorthShore Kids Events"` 且对应 superpowers 条目 | **必须由用户在对话里运行**:`/plugin install superpowers@claude-plugins-official`(marketplace `claude-plugins-official` 已注册) |

**怎么用 rtk**:每个产生大输出的 shell 命令前缀 `rtk`,例如 `rtk git log`、`rtk pytest`、`rtk pnpm install`。详细命令清单见全局 `~/.claude/CLAUDE.md` 的 "RTK Commands by Workflow" 节。RTK 对没有专门 filter 的命令是直通,所以默认前缀总是安全的。

**怎么用 superpowers**:装好后会自动加载它的一套 skills(`debug`、`brainstorm` 等)。在 plan/implement 时 Claude 会主动用这些 skills 而不需要显式调用。

## Project Overview

**North Shore Library Benefits — Data Collection (v0.1)**

Massachusetts eastern MA 区域的图书馆 museum-pass 福利数据建设项目。抓取范围 59 家图书馆(对齐 backup/ 上一代已跑通的范围),产品交付焦点仍是 NorthShore(运营方住 Wakefield,持 5 张卡:Wakefield/Reading/BPL/Wilmington/Somerville)。本期 v0.1 的目标是把 BRD(`docs/BRD.md`)第 6/7 章列出的所有"应该能拿到"的数据,通过 scraper + Claude 会话内整理拿到本地,产出三份核心结构化 JSON:

- `data/structured/libraries.json` — 59 馆元数据
- `data/structured/attractions.json` — ~108 景元数据
- `data/structured/passes.json` — (馆 × 景) 矩阵的折扣/凭证/限制字段

中间产物 `data/structured/library_catalog.json` 是全平台规范快照,既给 diff_catalog 当锚点,也供 build 阶段拆出上面三份产物。

**本期不做**:HTML 渲染层、真实预订日志、Google Maps 距离 API、MA 全境扩展(中西部 CW MARS 网络)、自动下单、JSON Schema 校验框架、正式 README/PRD/chat.md。详细范围见 `docs/BRD.md` 和计划 `C:\Users\Administrator\.claude\plans\fluffy-whistling-lampson.md`。

## Repository Layout

```
.
├── CLAUDE.md                  # 本文件
├── pyproject.toml             # Python 3.11+,依赖 playwright(可选)
├── .gitignore                 # 排除 data/.cache/、config/owned_*.json、_tmp_*
├── backup/                    # 上一代代码,只读参考
├── docs/BRD.md                # 业务需求文档(权威)
├── src/malibbene/             # 主包(MA Library Benefits)
│   ├── common/                # http / browser / snapshot / status / normalize
│   └── sources/               # 一个平台一个模块
│       ├── assabet/           # 52 馆,catalog + availability
│       ├── libcal/            # 5 馆(BPL+Cambridge+Brookline+Braintree+Milton),catalog + availability
│       ├── museumkey/         # 2 馆(Cohasset+Hingham),仅 catalog(availability 需登录)
│       ├── attractions/       # 景点官网爬虫(prices / images 等)
│       ├── libraries/         # 图书馆主站爬虫(addresses)
│       ├── holidays/          # 美国节假日生成
│       └── policies.py        # 各馆办卡资格抓取
├── scripts/                   # CLI 入口(scrape_static / scrape_dynamic / snapshot_diff / diff_catalog / geocode_all / fetch_*_pages)
├── data/raw/<platform>/       # scraper 直接产出
├── data/structured/           # Claude 整理后的最终数据(含 library_catalog.json 中间快照、geo.json)
├── data/dynamic/              # availability(可频繁覆盖)
├── data/static/
│   ├── images/<slug>.<ext>          # hero 图本地缓存(gitignored)
│   └── placeholders/<category>.svg  # category fallback SVG(入 git)
├── data/snapshots/<日期>/     # 历史快照,供 diff
└── config/                    # 配置种子
    ├── library_seeds.json     # 59 馆元数据
    ├── platform_pass_ids/     # 三平台手工 pass-id 映射(bpl/libcal/museumkey)
    └── owned_*.json           # 私(gitignored,卡 barcode 等)
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
- **平台抽象**:每个 `sources/<platform>/` 模块对外暴露 `index_page.main()`(catalog,必有)和 `availability.main()`(动态,museumkey 不实现)。平台 pass_id 命名空间不通用,各自有手工映射表(`config/platform_pass_ids/*.json`),Assabet 例外(slug 直接是 benefit_id)
- **Catalog vs availability 分层**:`raw/<platform>/<dataset>/<lib_id>.json` → 合并 + `normalize_benefit` → `structured/library_catalog.json`(规范快照 + diff 锚点)→ 拆分成 BRD §6.1 三大产物 `libraries.json`/`attractions.json`/`passes.json`。`manual_overrides.json` 在最后拆分阶段 merge
- **Geocoding**:OSM Nominatim(免费、1 req/sec)via `malibbene.common.geocode.geocode(query)`,结果缓存到 `data/.cache/geocode.json`。直线距离用 `haversine_miles`。失败区分:`no_results`(语义命中,缓存)vs 网络异常(瞬时,不缓存,下次重试)
- **LLM 提取**(铁律:不调 Anthropic API):需要 LLM 时,Python fetcher 只把 HTML 落盘到 `_pages/`,extraction 通过 subagent dispatch 完成(controller 派 Sonnet),subagent 用 Read/Grep 读 HTML、Write 落 JSON
- **Hero images**:从景点官网 `<meta property="og:image">` 抓,缓存到 `data/static/images/<slug>.<ext>`(gitignored,体积大);抓不到时前端 fallback `data/static/placeholders/<category>.svg`

## Reusable code from `backup/`

| backup 文件 | 复用到 | 程度 |
|---|---|---|
| `scrape_availability.py` | `sources/assabet/availability.py` | 90% |
| `scrape_pass_format.py` | `sources/assabet/index_page.py` 切块 | 60% |
| `scrape_catalog_assabet.py` | `sources/assabet/index_page.py` 切块 | 70% |
| `scrape_bpl_availability.py` | `sources/libcal/availability.py`(BPL 是 lib_id) | 95% |
| `scrape_libcal_availability.py` | `sources/libcal/availability.py`(参数化) | 90% |
| `scrape_catalog_libcal.py` | `sources/libcal/index_page.py` | 95% |
| `scrape_catalog_museumkey.py` | `sources/museumkey/index_page.py`(仅 catalog) | 90% |
| `normalize_benefit.py` | `common/normalize.py`(整文件 port,词法表已带 self-test) | 100% |
| `diff_catalog.py` | `scripts/diff_catalog.py` | 90% |
| `bpl_id_map.py` / `libcal_id_map.py` / `museumkey_id_map.py` | `config/platform_pass_ids/{bpl,libcal,museumkey}.json` | 100%(已 port) |
| `slug_map.py` 的 LIB_DOMAIN | `config/library_seeds.json` `domain` 字段 | 100%(已 port) |
| `library-cards.json` | `.env`(`<LIB>_BARCODE` 形式) | 100%(已 port) |
| `library_catalog.json` | 59 馆 + `platform`+`url` 派生 `library_seeds.json` 新增 44 条 | 100%(已 port) |

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
