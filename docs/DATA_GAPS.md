# 数据空缺清单 (DATA GAPS)

> **用途**：清晰记录所有「拿不到 / 无法解析 / 无法得到预期结构」的数据项,供人工复核。
> **持续更新**：每次重跑数据后,按下面的「如何刷新本文档」重新生成统计并更新条目。
> **最后更新**：2026-05-22(Phase O round 2 — JS 办卡页二次救回之后)

## 总则:三种空缺的区别

| 类型 | 含义 | 是否「真缺失」 | 处理方向 |
|---|---|---|---|
| **A. 拿不到 (unfetchable)** | 源站点挡爬虫 / 要登录 / JS 动态渲染且无可解析文本 | 数据存在,但本环境抓不到 | 换 IP、登录态、或人工录入 override |
| **B. 无法解析 (unparseable)** | 抓到了文本,但措辞自由,确定性 extractor 无法结构化 | 数据存在,结构化失败 | 扩 extractor 规则 或 人工 override |
| **C. 无预期结构 (genuinely absent)** | 该实体本身就没有这项数据(免费景点无门票价、步行游无固定营业时间) | **不是缺失,是真实状态** | 无需处理;`prices:[]` / `hours:unknown` 即正确答案 |

**铁律**:任何字段宁可留 `unknown` / `null` / `[]`,也绝不编造或推断。本文档列出的就是「诚实的没有」。

---

## 1. 图书馆 card_eligibility(办卡资格)— 12/59 仍 unknown

**当前**:47/59 已分类(全部有真实 rendered source phrase 佐证),12 仍 unknown(32.2% → **20.3%** unknown)。

本轮(Phase O round 2)做法:针对上一轮剩下、被认作「JS 办卡页拿不到」的 14 馆,逐馆用 Playwright 抓 `page.inner_text("body")` 全文(swallow nav timeout + 4× scroll),WebSearch 找首页型 seed 的真实 get-a-card URL,只采信「全文里有真实资格句 + 确定性分类器命中」的馆。新增/修正 7 馆 seed 的真实 card_page URL 并标 `requires_render_js:true`。同时把 `_has_eligibility_cue` 的 gate 改为「非 404/WAF 壳 AND 分类器对全文产出非 unknown」(关键词只是 fast-path),与分类器锁步,避免漏接新 idiom。

**本轮真正救回(7 个,均有真实 rendered source phrase verbatim)**:
| lib | 真实 card URL | 资格原句(verbatim) | 分类 |
|---|---|---|---|
| `lynnfield` | lynnfieldlibrary.org/about/get-a-library-card/ | "Library cards are free and available **regardless of where you live in Massachusetts**." | ma_resident |
| `acton` | actonmemoriallibrary.org/services/library-cards/ | "Library cards are available to anyone 4 years and older **who lives in Massachusetts** or works in Acton." | ma_resident |
| `reading` | readingpl.org/get-a-library-card/ | NOBLE eCard "Eligibility: **Massachusetts residency**" | ma_resident |
| `chelmsford` | chelmsfordlibrary.org/about/get-a-library-card | "If you **live anywhere in Massachusetts** (including Chelmsford) … you may apply for a library card online." | ma_resident |
| `everett` | everettpubliclibraries.org/get-a-library-card/ | "A library card is totally free, and **anyone can get one!**" | ma_resident |
| `weston` | westonma.gov/CivicSend/ViewMessage/message/165250(官方 WPL 通告) | "**If you have a Massachusetts address, you make the cut.**" | ma_resident |
| `boxford` | boxfordma.gov/210/Get-a-Library-Card | "**Any Boxford Resident is eligible** to obtain a Boxford Town Library … Card." | town_resident |

**附带修正(更准确,非回退)**:`newton/waltham/watertown/concord` 上一轮被判 `town_or_works`,但它们的办卡页明确写「任何在 MA 有地址 / 住在 MA 的人都能办卡」(newton: "Anyone with a current address in Massachusetts is eligible";watertown: "Anyone who lives in Massachusetts can get a library card";concord: "provide a valid ID with your current Massachusetts address";waltham: "…or are temporarily living in Massachusetts…you may be issued a Library card"),故升级为更准确的 `ma_resident`。分类器加了否定守卫,concord 的 source phrase 不再误命中 FAQ 反问句「I don't live in Massachusetts」,而是命中真正的「current Massachusetts address」要求。

**本轮新增/修改分类器 pattern(均有真实 snippet 进 `tests/test_eligibility_text.py`)**:
- ma_resident:`live(s)/reside (anywhere) in Massachusetts`(带否定守卫,排除 "don't/do not live in Massachusetts")、`have/with/provide (your/current) Massachusetts address`、`library card … anyone can get one`
- town_resident:`Any <Town> Resident is eligible … card`
- 诚实守卫全绿(stoneham/boxford-Hoopla/Sudbury-streaming 等 must-NOT-match 测试不变)。

### 1A. 拿不到 — WAF 阻挡
| lib | 现象 | 状态 |
|---|---|---|
| `arlington` (robbinslibrary.org) | seed `card_page` 已设 `/about/library-card/` 且标 `requires_render_js:true`;Playwright headless 渲染到页面但被指纹识别,正文无资格句 | **拿不到**。需非 headless 浏览器 / 住宅 IP / 人工录入 |

### 1B. 渲染到了真实办卡页,但页面本身没写居住范围 → 诚实 unknown(7)
这些馆本轮都已找到并 Playwright 渲染了**真实的 get-a-card 页全文**,但页面只列「带 ID + 当前地址证明即可办卡」,**没有任何「住 MA / 本镇居民」的范围句**——按铁律保持 unknown(绝不为凑数臆造范围):

| lib | 真实 card URL(已渲染) | 页面原句 | 为何 unknown |
|---|---|---|---|
| `stoneham` | stonehamlibrary.org/get-a-library-card/ | "you must bring a form of ID and/or another document with your current address" | 无范围 |
| `lynn` | lynnpubliclibrary.org/get-a-library-card/ | "bring in some form of identification that shows both your name and current address … and we will issue you a card" | 无范围 |
| `beverly` | beverlypubliclibrary.org/services/borrowing/ | "Present photo identification with name and proof of current address" | 无范围(seed URL 已更正) |
| `braintree` | thayerpubliclibrary.org/get-a-library-card/ | "photo identification … and proof of current address … is required in order to receive a card" | 无范围 |
| `milton` | miltonlibrary.org/about/faq/ | "Bring a picture ID and something with proof of your current address" | 无范围 |
| `natick` | morseinstitute.libguides.com/get-started | "To get a library card, visit any Minuteman library with ID and proof of current address"(morseinstitute.org 主站 ERR_CONNECTION_CLOSED,改用 libguides 子站全文) | 无范围 |
| `belmont` | belmontpubliclibrary.net/borrow/library-cards/ | "We follow the Minuteman Library Card Registration Policy, which outlines eligibility" | 只甩给 Minuteman 政策,自家页无范围句 |

**处理方向**:这 7 个要么从联盟(Minuteman/NOBLE/OCLN)政策站抓一次通用居住范围(Minuteman/NOBLE 实际都是「住 MA 即可」),要么人工 `data/overrides/libraries/<id>/card_eligibility.json`。**严禁**为凑数放宽分类器或 cue gate。

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

## 5. Pass 居住限制 residency_restriction(真正的预订筛选)— 987/1033 仍 unknown

这是 pass 能不能订的**真正筛选维度**(用户持哪张卡 + home ZIP)。绝大多数不写在 catalog 文本里,系统在预订时按办卡 ZIP 判定(见运营方截图)。`restricted` 三态:yes/no/unknown,默认 **unknown**(文本沉默 ≠ 开放)。

**已确定(46 个):** 4 个来自文本明写 + 42 个来自 booking probe(Phase P3)。
- **booking probe 实证规律**(用「同网络跨镇卡」试订到 card-validation 步,绝不完成预订):
  - **Wakefield 全部 17 个 pass = resident-only**:Reading(NOBLE 同网络非本镇)卡在每个 pass 都被挡(与运营方截图一致 —— 非本地居民订 Wakefield 的 Boston Children's Museum 被拒)。
  - **Reading 全部 25 个 pass = open**:Wakefield(NOBLE 非本镇)卡全部被接受,非本镇 NOBLE 居民可订。
  - 结论:**同属 NOBLE,但 Wakefield 限本镇、Reading 开放** —— 两馆策略相反,实证可复现。

### 5A. 拿不到 — 缺「同网络非本镇卡」无法 probe(剩余 ~40 馆 + wilmington/somerville/bpl)
booking probe 需要一张**目标馆同网络、但持卡人非本镇**的卡。运营方手上 5 张卡只有 Wakefield+Reading 同属 NOBLE 且互为异镇,所以只能 probe 这两馆。
- `wilmington`(MVLC)、`somerville`(Minuteman)、`bpl`(libcal):运营方在各自网络只有「本镇那一张卡」,没有同网络异镇卡 → **residency 测不了**,保持 unknown(诚实)。
- 其余 ~50 个 assabet 馆:没有它们网络的卡 → 同理 unknown。
**处理方向**:① 再办几张关键馆同网络异镇卡;② 或运营方提供已知的 resident-only 馆清单写 override;③ libcal/museumkey 的 probe 流程待实现(当前 probe 仅 Assabet)。

### 5C. 注意:unknown ≠ 开放
987 个 unknown **不代表**这些 pass 对非本地居民开放 —— 只代表我们还没实证。App 端筛选遇到 unknown 应**保守提示**「可能限本地居民,以预订页为准」,不能默认可订。

---

## 6. 平台级限制(结构性,非本期可解)

| 项 | 限制 | 类型 |
|---|---|---|
| **MuseumKey availability** | cohasset/hingham 的日历要登录才可见,27 个 pass 无 availability | A(要登录态) |
| **MuseumKey 3 个 coupon** | `cohasset-historical-society`、cohasset/hingham `trustees-go-pass` 是 free-form 句子,Phase J 已尽力,部分仍 discount 兜底 | B |
| **branches** | 仅 BPL(24)+ Cambridge(7)+ Brookline(3)有分馆建模;其余馆为单馆,无需分馆 | C(其余馆本就单馆) |

---

## 当前覆盖率快照(2026-05-22)

| 指标 | 数值 |
|---|---|
| libraries | 59(catalog 59/59, policy 57/59) |
| card_eligibility known | 47/59(unknown 20.3%;其余 12 见 §1) |
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

> 复核优先级建议:card_eligibility 已从上一轮 32.2% 再降到 **20.3%**(本轮又救回 7 馆)。剩 12 个里 §1B 的 7 馆是「真办卡页但页面本身没写居住范围」——只能从联盟政策站抓通用范围或人工 override,**不是 extractor 问题**;另 5 馆见 §1A/§1C(WAF / 张冠李戴 / OCLN 措辞)。收益已明显递减,建议优先转 **§3A/§4A(景点子页/ticketing 端点)**。
