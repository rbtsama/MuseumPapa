# 数据空缺清单 (DATA GAPS)

> **用途**：清晰记录所有「拿不到 / 无法解析 / 无法得到预期结构」的数据项,供人工复核。
> **持续更新**：每次重跑数据后,按下面的「如何刷新本文档」重新生成统计并更新条目。
> **最后更新**：2026-05-21(全量重建 + Recovery + Phase H/I/J/K/M 之后)

## 总则:三种空缺的区别

| 类型 | 含义 | 是否「真缺失」 | 处理方向 |
|---|---|---|---|
| **A. 拿不到 (unfetchable)** | 源站点挡爬虫 / 要登录 / JS 动态渲染且无可解析文本 | 数据存在,但本环境抓不到 | 换 IP、登录态、或人工录入 override |
| **B. 无法解析 (unparseable)** | 抓到了文本,但措辞自由,确定性 extractor 无法结构化 | 数据存在,结构化失败 | 扩 extractor 规则 或 人工 override |
| **C. 无预期结构 (genuinely absent)** | 该实体本身就没有这项数据(免费景点无门票价、步行游无固定营业时间) | **不是缺失,是真实状态** | 无需处理;`prices:[]` / `hours:unknown` 即正确答案 |

**铁律**:任何字段宁可留 `unknown` / `null` / `[]`,也绝不编造或推断。本文档列出的就是「诚实的没有」。

---

## 1. 图书馆 card_eligibility(办卡资格)— 19/59 仍 unknown

**当前**:40/59 已分类(全部有真实 rendered source phrase 佐证),19 仍 unknown(72.9% → 32.2% unknown)。

本轮(seed-driven recovery)做法:`scrape_rendered.py policies` 现在按 seed 的 `requires_render_js:true` 标志逐馆用 Playwright 渲染 `card_page`,只有 `_has_eligibility_cue()` 通过 + 分类器产出非 unknown 时才采信,并持久化完整 rendered `policy_text`(reclassify 不会回退)。新增 26 个 seed 的真实 get-a-card URL(WebSearch 找到 + 渲染验证)。其中 24 个分类成功(见下),lynnfield/sudbury 渲染到了页面但正文无可分类资格句,arlington 仍被 WAF 拦。

**本轮真正救回(24 个,均有真实 rendered source phrase)**:
`woburn, medford, burlington, bpl, danvers, marblehead, chelsea, billerica, topsfield, lawrence, methuen, andover, middleton, newton, framingham, maynard, wayland, wellesley, waltham, watertown, concord, somerville, quincy, cambridge`(tewksbury 上一轮已救回)。

### 1A. 拿不到 — WAF 阻挡
| lib | 现象 | 状态 |
|---|---|---|
| `arlington` (robbinslibrary.org) | seed `card_page` 已设 `/about/library-card/` 且标 `requires_render_js:true`;Playwright headless 渲染到页面但被指纹识别,正文无资格句通过 cue | **拿不到**。需非 headless 浏览器 / 住宅 IP / 人工录入 |

### 1B. 拿不到 — get-a-card 页是 JS 渲染(渲染后正文仍只有导航壳/未水合资格块)
这些馆已找到候选 URL,但 Playwright 渲染后正文里没有可分类的资格句(JS 客户端渲染只吐了导航壳,或资格块未及时水合):
`stoneham, reading, lynnfield(已标 requires_render_js,渲染到页但正文无资格句), beverly, lynn, everett, boxford, chelmsford, acton(只渲染出证件清单,无"住 MA/在本镇工作"那句), weston(首页只 ~1k 字壳), belmont, natick(morseinstitute.org 直接 ERR_CONNECTION_CLOSED), braintree, milton`。
**处理方向**:这些需要更强的渲染(non-headless / 等待具体资格 selector 出现 / 抓具体子页 JSON 端点),或人工 override。**严禁**为凑数放宽 `_has_eligibility_cue` 或分类器。

### 1C. 无预期结构 / 联盟入口 — 自家页无资格正文
| lib | 现象 | 状态 |
|---|---|---|
| `sudbury` (goodnowlibrary.org) | 首页 cue 命中的是 "Sudbury residents only" 但那是 Kanopy 流媒体限制句(分类器正确判为 unknown,见 `test_card_streaming_residents_only_does_not_match`) | unknown(诚实) |
| `lincoln` | `lincolnpubliclibrary.org` 实为 **别州的 "Lincoln Public Library District"**,非 Lincoln, MA — 故意不采信,避免张冠李戴 | unknown(诚实);MA Lincoln 的真实办卡页待人工确认 |
| `cohasset`/`hingham` (OCLN/museumkey) | hingham 渲染正文有 "issued free of charge to residents of towns participating in OCLN" —— 是真实 network 资格句,但 cue gate + `_NETWORK` 分类器措辞不匹配;不为单馆放宽两处规则 | unknown(诚实);可后续扩 `_NETWORK` 措辞或人工 override |

**处理方向**:从联盟站抓一次通用资格文本,或人工写 `data/overrides/libraries/<id>/card_eligibility.json`。

> **注**:`pass_pickup_default` 96.6% unknown 是**诚实的**数字 —— 旧分类器把「work」「博物馆周日免费」等误判,新分类器(Phase H)清掉了假阳性。真实的 pass-pickup 政策极少写在公开页面上。

---

## 2. Pass coupon(优惠详情)— 18/1033 仍 failed

**当前**:836/1033 有 coupon,179 是「pass 存在但 catalog 无 benefit 文本」(多为 circulating/permit 类),18 是确定性 extractor 判定 failed。

### 2B. 无法解析 / 2C. 无预期结构 — 18 个 failed(已逐条核验为「真的没有可结构化的优惠文本」)
```
andover__harvard-museums-of-science-and-culture     boxford__isabella-stewart-gardner-museum
bpl__american-repertory-theatre                     bpl__boch-center-tours
bpl__sandwich-glass-museum-digital-coupon-pass       bpl__tacc-x-paddle-boston-coupon-code
braintree__boston-by-foot                            burlington__ecotarium
burlington__garden-in-the-woods-native-plant-trust   everett__isabella-stewart-gardner-museum
malden__new-england-aquarium                         medford__new-england-aquarium
needham__new-england-botanic-garden-at-tower-hill    needham__the-discovery-museums
reading__north-shore-childrens-museum                sudbury__new-england-botanic-garden-at-tower-hill
wakefield__salem-witch-museum                        weston__boston-harbor-island-ferry
```
**为什么 failed**(Phase J 逐条核验):
- BPL libcal 那批:页面只有博物馆简介 + 地址,无优惠/价格文本
- 其余:`benefit_text` 只有「general admission」无折扣、或纯 checkout/物流说明、或「prices vary」
- `boxford__isabella-stewart-gardner-museum`:文本只说「显示在车上的停车费」,免费与否属领域推断 —— 故意不抽,保持 failed(诚实)

**处理方向**:这些大多是 C 类(源头确实没写优惠);若要补,只能人工核对各馆原始 benefit 文本后写 override。

---

## 3. 景点 prices(门票价)— 15/48 仍空

> Phase K 已对每个空 prices 景点做了诚实判定,详见 `data/raw/attractions/_coverage_audit.json`。

### 3A. 拿不到 — JS 渲染(8)
价格在客户端购物车/widget 里,静态 + Playwright 都抓不到结构化价:
`concord-museum, griffin-museum-of-photography, museum-of-science, north-shore-childrens-museum, plimoth-patuxet, the-childrens-piazza, the-spellman-museum-of-stamps-and-postal-history, zoo-new-england`
**处理方向**:逐站找 ticketing API/JSON 端点(类似 libcal museum_id 的做法),或人工录入。

### 3A. 拿不到 — 价格在未抓取的子页(3)
`boston-harbor-island-ferry`(运营商票务页)、`garden-in-the-woods`(admission 页)、`gore-place`(Mansion Tours 页)
**处理方向**:把这些具体子页 URL 加进 `scrape_attractions.py` 的子页探测名单。

### 3C. 无预期结构 — 本就无固定门票(4)
`boston-by-foot`(步行游,按场次)、`boston-harbor-islands`(免费户外公园)、`greater-boston-stage-company`(剧院,按演出)、`paddle-boston`(租船,无门票)
→ **不是缺失**,`prices:[]` 即正确。

---

## 4. 景点 hours(营业时间)— 12/48 仍 unknown

### 4A. 拿不到 — JS 渲染 / 未抓子页(6)
`mass-audubon, mass-audubon-drumlin-farm`(各保护区独立页,org 页无)、`boston-harbor-island-ferry`(运营商时刻表)、`gore-place`、`plimoth-patuxet`、`zoo-new-england`(JS widget)
**处理方向**:抓对应子页或 render_js。

### 4A. 拿不到 — JS-only widget(2)
`the-childrens-piazza`(Square SPA)、`the-spellman-museum-of-stamps-and-postal-history`
**处理方向**:逐站找数据端点或人工录入。

### 4C. 无预期结构 — 本就无固定营业时间(4)
`boston-by-foot, boston-harbor-islands, greater-boston-stage-company, paddle-boston`
→ **不是缺失**,`hours:unknown` 即正确。

> Phase M 已把 12→36 个景点的 hours 从「extractor 漏抓」修成正确抽取(en-dash 日期、「Open Daily」、a.m./p.m. 等),USS Constitution 价格也已修复。剩下的 12 个不是 extractor 问题,是上面的 4A/4C。

---

## 5. 平台级限制(结构性,非本期可解)

| 项 | 限制 | 类型 |
|---|---|---|
| **MuseumKey availability** | cohasset/hingham 的日历要登录才可见,27 个 pass 无 availability | A(要登录态) |
| **MuseumKey 3 个 coupon** | `cohasset-historical-society`、cohasset/hingham `trustees-go-pass` 是 free-form 句子,Phase J 已尽力,部分仍 discount 兜底 | B |
| **branches** | 仅 BPL(24)+ Cambridge(7)+ Brookline(3)有分馆建模;其余馆为单馆,无需分馆 | C(其余馆本就单馆) |

---

## 当前覆盖率快照(2026-05-21)

| 指标 | 数值 |
|---|---|
| libraries | 59(catalog 59/59, policy 57/59) |
| card_eligibility known | 40/59(unknown 32.2%;其余 19 见 §1) |
| attractions | 48 |
| attractions w/ prices | 33/48(其余见 §3) |
| attractions w/ hours | 36/48(其余见 §4) |
| attractions w/ visitor_eligibility | 48/48 |
| attractions w/ reservation | 48/48 |
| passes | 1033 |
| passes w/ coupon | 836/1033(18 failed 见 §2) |
| passes w/ availability | 1002/1033(31 museumkey 要登录) |
| branches | 34(BPL 24 + Cambridge 7 + Brookline 3) |
| calendar 天数 | 31,062 |

---

## 如何刷新本文档

```bash
# 1) 重跑你想补的数据(各步独立幂等)
python scripts/scrape_libraries.py
python scripts/scrape_rendered.py policies      # WAF / JS 渲染的 policy
python scripts/scrape_availability.py
python scripts/scrape_attractions.py
python scripts/extract_attractions.py --force
python scripts/enqueue_coupons.py && python scripts/extract_coupons.py --force
python scripts/reclassify_policies.py
python scripts/build_all.py

# 2) 重新统计空缺(命令见各节;关键来源)
#    - data/raw/attractions/_coverage_audit.json  (景点 prices/hours 逐条判定)
#    - data/raw/*/coupons/*.json  里 status=="failed" 的
#    - data/structured/libraries.json 里 card_eligibility=="unknown" 的

# 3) 把变化更新进本文件,并改「最后更新」日期
```

> 复核优先级建议:**§1B(给 JS 办卡页加 requires_render_js)** 本轮已把 24 个馆从 unknown 救回(72.9%→32.2%);剩 19 个多数是渲染后正文仍是壳或措辞不匹配,收益递减。其次 **§3A/§4A(景点子页/ticketing 端点)**。§C 类无需处理。
