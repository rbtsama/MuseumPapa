# MuseumPass MA — Product Design Spec (v0.1)

> 本文件:产品交互/视觉设计 spec。UI 实现 = 全英文(见 [glossary.md](../../glossary.md)),内部沟通 = 中英混杂。
> 不讨论后端/数据抓取/具体技术栈细节(那些走 implementation plan)。
> 写作日期:2026-05-15。

---

## 0. 命名与定位

| 项 | 决议 |
|---|---|
| 产品名 | **MuseumPass MA** |
| 一句话定位 | 帮 MA 居民/学生/年轻人找到"用图书馆卡免费/打折逛博物馆"的折扣指南 |
| 用户范围 | C 全东麻持卡人(不限于 NorthShore,包含家庭/学生/想省钱的年轻人) |
| 商业模式 | 免费 + 广告(BRD §2.3) |
| 产品边界 | **查询工具,不替用户下单**。点 pass 选项 → 自动复制 barcode 到剪贴板 → 跳转图书馆官网完成预约 |
| 不替用户决策 | 推荐用结构(三类 pass 分组排序),不用文案/紧迫感/营销话术 |

---

## 1. 信息架构(降维漏斗)

```
首页 = 列表页(单日)
   ↓ 点景点卡片
详情页(多日 / 30 天日历 / 全部 pass)
   ↓ 点某个 pass
图书馆官网预约页(新 tab,barcode 已复制到剪贴板)
```

| 层 | 固定维度 | 剩余维度 | 用户负荷 |
|---|---|---|---|
| 列表页 | 单日(默认 today) | 108 景点 | 低,扫商品 |
| 详情页 | 景点 = 1 | 日期 × 馆 × pass 类型 | 中,做决策 |
| 跳转后 | + 馆 + 日期 + pass | 填表完成预约 | 高,但 barcode 已粘贴 |

---

## 2. 视觉系统

参考 `D:\desk\凯门汽车小红书私信机器人策略方案.html` 的编辑刊物风:Libre Baskerville (serif headings) + DM Sans (body) + 暖米白底。

### 2.1 CSS Tokens

```css
:root {
  /* Background */
  --bg: #F4F3EF;
  --paper: #ECEAE4;
  --white: #FAFAF7;

  /* Ink */
  --ink: #000000;
  --ink-2: #1A1917;
  --ink-3: #4A4845;

  /* Primary (Forest Green) — 用于主品牌色、digital pass tag、主要 CTA */
  --g: #1B5740;
  --g-2: #2A7055;
  --g-light: #C4DDCF;
  --g-pale: #EAF1EE;

  /* Amber/Gold — 用于 physical pickup tag、中等强调 */
  --au: #8C6018;
  --au-pale: #F4EFE8;

  /* Orange — 新增,用于 pickup & return tag、中等警示 */
  --or: #D97706;
  --or-pale: #FDF1E2;

  /* Red — 用于错误、强警示、库存满 */
  --rd: #8C2A1E;
  --rd-pale: #F4EAE9;

  /* Rules / borders */
  --rule: #D0CEC6;
  --rule-strong: #B5B2A8;
}
```

### 2.2 字体

| 用途 | 字体 |
|---|---|
| H1 / H2(品牌、景点名、详情页标题) | `'Libre Baskerville', Georgia, serif` |
| Body / UI | `'DM Sans', 'PingFang SC', 'Helvetica Neue', sans-serif` |
| Code / Barcode | `'DM Mono', 'Courier New', monospace` |

### 2.3 Pass 类型颜色映射

| Pass 类型 | tag 文字色 | tag 背景色 | icon 建议(Heroicons,UI 阶段最终选) |
|---|---|---|---|
| Digital pass | `--g`(深绿) | `--g-pale` | `bolt` / `device-phone-mobile` |
| Physical pickup | `--au`(金) | `--au-pale` | `ticket` |
| Pickup & return | `--or`(橙) | `--or-pale` | `arrow-path` |
| 无可用 | `--ink-3`(灰) | `--paper` | 无 icon,文字 "No passes available" |

### 2.4 UI 框架

**HeroUI**(<https://heroui.com/docs/react/getting-started>),Tailwind-based React。
默认主题 token override 成上面这套配色。

---

## 3. 鉴权(Mock Auth — v1)

### 3.1 三个硬编码账号

| Username | Password | 角色 | 卡数 | 演示状态 |
|---|---|---|---|---|
| `alex` | `alex` | 重度用户 | **5 张**(Wakefield / Reading / BPL / Wilmington / Somerville) | 折扣力度排序激活,几乎每个景点都有 coupon |
| `rbt` | `rbt` | 轻度用户 | **1 张**(Wakefield) | 多数景点无 coupon,banner 引导加卡 |
| `admin` | `admin` | 空卡包 | **0 张** | 已登录但卡包空;banner 引导去 My passes settings |

> alex 是为运营方真实持卡组合 5 张的演示;rbt 是轻量入门状态;admin 是空账户。  
> 注册按钮 v1 disabled(tooltip: "Sign-up coming soon")。

### 3.2 数据存储分层

| 数据 | 存储位置 | 入 git? |
|---|---|---|
| 用户名 / 显示名 / 密码 hash | 前端硬编码 JSON(`src/mock/users.json`) | ✅ 入 git |
| 卡包 (barcode / 姓 / PIN) | localStorage | ❌ 不入 git(`.gitignore`) |
| ZIP code | localStorage(账户绑) | ❌ |
| Favorites | localStorage(账户绑) | ❌ |
| Session | localStorage(刷新不掉,关浏览器也不掉,**长期持久化**) | — |

> 严格遵守 CLAUDE.md "barcode 严禁推到远端" 铁律。

### 3.3 登录弹窗(简版)

```
┌──────────────────────────────────────────┐
│  Sign in to MuseumPass MA          [×]   │
│                                          │
│  Username  [_________________]           │
│  Password  [_________________]           │
│                                          │
│  [ Sign in ]                             │
│                                          │
│  Don't have an account?                  │
│  [ Sign up ] (disabled, tooltip)         │
│                                          │
│  Error: "Invalid username or password"   │
└──────────────────────────────────────────┘
```

- Modal 居中,backdrop 半透明
- 登录失败:错误文案显示在 button 上方
- 登录成功:modal 关,顶部 banner 消失(若有),user menu 出现

### 3.4 已登录态:顶部 user menu

```
[👤 alex ▼]
   ├─ My passes
   ├─ ─────────
   └─ Sign out
```

---

## 4. 列表页(首页)

### 4.1 整体结构

```
┌────────────────────────────────────────────────────────────────────┐
│  [Logo] MuseumPass MA          [🔍 Search]          [👤 alex ▼]    │ ← Top bar (固定)
├────────────────────────────────────────────────────────────────────┤
│  ⓘ Add your library pass to unlock discounts →                     │ ← Banner (仅游客/admin)
├────────────────────────────────────────────────────────────────────┤
│  Date: [📅 Today  ▼ ]              Sort: [Favorites first  ▼]      │ ← Filter bar
├────────────────────────────────────────────────────────────────────┤
│  ❤️ ┌─ Attraction card ──┐                                          │ ← Favorites 在列表内置顶,无独立分组
│     ┌─ Attraction card ──┐                                          │
│     ┌─ Attraction card ──┐                                          │
│     ...                                                             │
│  ── No passes available ─────────────────────────────────────────  │ ← 分隔线
│     ┌─ Attraction card ──┐(沉底)                                   │
│     ...                                                             │
└────────────────────────────────────────────────────────────────────┘
```

### 4.2 Top bar

| 元素 | 行为 |
|---|---|
| Logo + 品牌 | 点击 → 回首页(reset 筛选) |
| 搜索框 | 全局搜索景点名(模糊匹配);v1 不搜索图书馆/category |
| 用户菜单 / Sign in 按钮 | 未登录显示 [Sign in];登录后显示 [👤 username ▼] |

### 4.3 Banner

显示条件:用户未登录 **或** 已登录但卡包空(admin)。

| 状态 | 文案 |
|---|---|
| 游客 | `Add your library pass to unlock discounts →` (点击→拉起登录 modal) |
| admin(已登录 0 卡) | `Set up your library passes to see your discounts →` (点击→跳 My passes) |

### 4.4 Filter bar(v1 极简)

只有两个 control:

| Control | 行为 |
|---|---|
| **Date** | 单日 picker,默认 Today;弹日历选具体某天 |
| **Sort** | dropdown,选项:`Favorites first` (default) / `A–Z` / `Distance` (需 ZIP)/ `Discount` |

> 分类 / pass 类型 / 图书馆筛选 / ZIP 输入暂不在顶部(分类数据 21 个 tag 已就绪,V1 后开放)。

### 4.5 排序规则

**主分组(永远生效):**

```
1. Favorites 永远置顶(用户标了 ❤️ 的景点,内部按用户选定的 sort 字段二级排)
2. 有可用 pass 的景点 — 按 sort dropdown 选定字段排
3. "No passes available" 景点 — 沉底,内部按 A–Z 排
```

**默认 sort = Favorites first 实际语义:**
- Favorites > 非 Favorites
- 同层内按 A–Z

**Sort 可选项展开:**

| 选项 | 行为 | 备注 |
|---|---|---|
| `Favorites first`(default) | 上述主分组 | 总是先 Favorites |
| `A–Z` | 字母序 | 主分组仍生效(no-passes 沉底) |
| `Distance` | 用户 ZIP → 景点直线距离 asc | 需 ZIP;无 ZIP 时该选项 disabled |
| `Discount` | 按"该用户能拿到的最优折扣力度" desc | 游客没卡包 → 按"全馆最优"排 |

### 4.6 景点卡片(列表页核心)

```
┌──────────────────────────────────────────────────────────────────┐
│ ❤️ [80×80 img]  Museum of Science                  Original $30 │
│                 Boston · Hands-on science museum                 │
├──────────────────────────────────────────────────────────────────┤
│ 5/16  ⚡ Free   📄 Half-price · Wakefield 5 mi   📄 $5 off · Reading 8 mi   🔄 Free · Wilmington 12 mi │
└──────────────────────────────────────────────────────────────────┘
```

> 列表页**只显示当日一行 tag**(单日聚焦)。多日浏览进详情页。

#### 4.6.1 Card header(单行水平排版,~60px 高)

| 元素 | 内容 | 字体 |
|---|---|---|
| Favorite 标记 | 左上 ❤️ icon(已收藏)/ ♡ icon(未) | — |
| 缩略图 | 80×80 px 圆角 | — |
| 景点名 | `Museum of Science` | Libre Baskerville 16px bold |
| 城镇 + 介绍 | `Boston · Hands-on science museum`(≤25 字英文介绍) | DM Sans 13px `--ink-3` |
| 原价 | `Original $30`(右对齐);抓不到原价时此字段空着 | DM Sans 12px,有划线时另一处显示折后 |

#### 4.6.2 Tag 行(当日)

- 日期标识:`5/16` 格式(月/日)
- 最多 **4 个 tag**
- Tag 算法(详见 §5)填充

#### 4.6.3 Favorite 入口(双入口)

- a) 卡片左上 ❤️ / ♡ icon,点击切换(列表页内)
- b) 详情页内独立按钮(详见 §6)

未登录 guest 也能 favorite(存 localStorage,无账户绑)。登录后融入账户。

#### 4.6.4 无可用 pass 的卡片

```
┌──────────────────────────────────────────────────────────────────┐
│ ❤️ [80×80 img]  Some Niche Museum                  Original $20 │
│                 Smalltown · Local history collection             │
├──────────────────────────────────────────────────────────────────┤
│ 5/16  No passes available                                        │
└──────────────────────────────────────────────────────────────────┘
```

整个景点沉底("无折扣可用"段),除非 Favorited 则置顶。

#### 4.6.5 游客 / admin(卡包空)看到的卡片

```
┌──────────────────────────────────────────────────────────────────┐
│ ❤️ [80×80 img]  Museum of Science                  Original $30 │
│                 Boston · Hands-on science museum                 │
├──────────────────────────────────────────────────────────────────┤
│ Sign in to view 25 discount options                              │ ← 替代 tag 行
└──────────────────────────────────────────────────────────────────┘
```

- 不显示具体 tag(避免画饼)
- "X discount options" = 该景点合作馆数
- 该卡片点击仍可进详情页(详情页对游客也显示理论选项,详见 §6)

---

## 5. Tag 推荐算法(单景点 / 单日)

### 5.1 输入

- 景点 `attraction_id`
- 日期 `D`
- 用户卡包 `user_cards`(可为空)
- 全量 pass × library 矩阵
- 库存日历 calendar[attraction_id][library_id][D] ∈ {available, booked, unknown}
- 用户 ZIP(若有,用于距离)

### 5.2 算法

```
输入 = 该景点所有 pass × library 行,其中:
  - library 在 user_cards 中(若 user_cards 非空)
  - calendar[D] = "available"(可用)
  - 用户满足办卡资格(BRD §7.1 已在数据里标)

分三组:digital / physical / loan-card

A. Digital 组(零距离):
   按折扣力度 desc 排
   只取第一名(免费 > 半价 > $N off),不显示地点
   → 0 或 1 个 tag

B. Physical 组:
   按 (折扣力度 desc, 距离 asc) 排
   全部保留(地点是有效差异化信号)
   → 0~N 个 tag

C. Loan-card 组:
   同 Physical
   → 0~N 个 tag

输出顺序:[A] + [B] + [C],总数限制 ≤4

如果用户卡包为空 → 跳过用户过滤,但 UI 用 §4.6.5 替代(不显示具体 tag)
```

### 5.3 Tag 文案模板

| 类型 | 模板 | 例子 |
|---|---|---|
| Digital | `⚡ {Discount}` | `⚡ Free` / `⚡ Half-price` / `⚡ $5 off` |
| Physical | `📄 {Discount} · {Town} {N} mi` | `📄 Half-price · Wakefield 5 mi` |
| Loan-card | `🔄 {Discount} · {Town} {N} mi` | `🔄 Free · Wilmington 12 mi` |

> 馆名用 **town**(short, 北美口语习惯),不缩写;空间不够 UI 阶段再处理(换行/缩字号)。

### 5.4 折扣力度文案(全英文)

| 内部 enum | UI 显示 |
|---|---|
| `free` | `Free` |
| `half-price` | `50% off` 或 `Half-price`(UI 阶段最终选一) |
| `dollars-off:5` | `$5 off` |
| `dollars-off:10` | `$10 off` |
| `unknown` | 不显示 tag |

### 5.5 折后价显示(原价 + 折后)

卡片 header 右侧"原价"附近,如果能算出折后:

```
Original $30 → Your price: Free
Original $30 → Your price: $15 (50% off)
Original $30 → Your price: $25
```

抓不到原价时:卡片只显示 tag 里的折扣描述,不显示原价/折后行。
**fallback 表:**

| 抓到原价 | 拿到折扣 | header 那行显示 |
|---|---|---|
| ✅ $30 | Free | `Original $30 → Free` |
| ✅ $30 | 50% off | `Original $30 → $15` |
| ✅ $30 | $5 off | `Original $30 → $25` |
| ❌ 无 | Free | `Free`(tag 里) |
| ❌ 无 | $5 off | `$5 off`(tag 里) |

---

## 6. 景点详情页

### 6.1 进入方式

点列表页景点卡片任意位置(除 Favorite icon)。URL 形如 `/attractions/museum-of-science`。

### 6.2 整体结构

```
┌──────────────────────────────────────────────────────────────────┐
│  ← Back to attractions                              [❤ Favorite] │ ← 详情页内 Favorite 入口(§4.6.3 b)
├──────────────────────────────────────────────────────────────────┤
│  [Hero image, wide]                                              │
│                                                                  │
│  Museum of Science                                               │
│  Boston, MA · Hands-on science museum, family-friendly           │
│                                                                  │
│  [Visit official site →]    Original price: $30 adult / $25 kid │
│  Hours: Daily 9–17 · Closed Wed                                  │
├──────────────────────────────────────────────────────────────────┤
│  Pick your dates                                                 │
│  [📅 5/16 — 5/18 (3 days)]   ※ 详情页最多 30 天                  │
├──────────────────────────────────────────────────────────────────┤
│  5/16                                                            │
│    ⚡ Free                                                       │
│    📄 Half-price · Wakefield 5 mi                                │
│    📄 $5 off · Reading 8 mi                                      │
│    🔄 Free · Wilmington 12 mi                                    │
│    [Show all 8 options ▾](展开剩余,详情页不限 4 个)            │
│                                                                  │
│  5/17                                                            │
│    (同上结构)                                                   │
│                                                                  │
│  5/18                                                            │
│    No passes available                                           │
├──────────────────────────────────────────────────────────────────┤
│  About this attraction                                           │
│  Long description (full text)                                    │
│  Address: 1 Science Park, Boston, MA 02114                       │
│  Phone: (617) 723-2500                                           │
├──────────────────────────────────────────────────────────────────┤
│  Participating libraries (25)                                    │
│  Lucius Beebe Memorial Library (Wakefield) — Half-price physical │
│  Reading Public Library (Reading) — $5 off physical              │
│  ...(full library full names in this section)                   │
└──────────────────────────────────────────────────────────────────┘
```

### 6.3 关键差异 vs 列表页

| 维度 | 列表页 | 详情页 |
|---|---|---|
| 日期范围 | 单日 | **最多 30 天**(默认未来 3 天) |
| Tag 数量 | ≤4 | 不限,可"Show all" 展开 |
| 馆名 | town 短名 | **正式名(full name)**,空间充足 |
| 信息 | 卡片 header 极简 | 全 description / 地址 / 电话 / 营业时间 / 所有合作馆清单 |

### 6.4 游客/admin 看详情页

显示所有理论选项(不按卡包过滤),但 tag 旁有锁 icon 🔒。点 tag → 弹窗 "You need a [Library] card. [Sign in / Add card]"。

天然回答 BRD Q3 "我该办哪张卡"。

---

## 7. 点击 Pass → 跳转预约

### 7.1 流程

```
用户点 tag/pass 选项
  ↓
弹窗:"Your barcode for [Library] has been copied to clipboard.
       Click [Open booking page] to proceed."
       [Open booking page →]   [Cancel]
  ↓
点 [Open booking page] → 新 tab 打开图书馆预约页 URL
  ↓
用户在图书馆官网粘贴 barcode + 填姓/PIN(如需) + 完成预约
```

### 7.2 卡号复制规则

| 条件 | 行为 |
|---|---|
| 用户有该馆卡 | 复制 barcode 到剪贴板,弹窗提示 |
| 用户无该馆卡(详情页对游客显示理论选项) | 弹窗替换为 "You need a [Library] card. [Sign in / Add card]" |
| 已登录但该馆卡 barcode 未填 | 弹窗提示 "Add your barcode for [Library] in My passes →" |

### 7.3 姓 / PIN

v1 不替用户填表,用户进图书馆官网时**自己**用之前填的姓/PIN(他们已经记得自己的 last name)。**未来增强**:浏览器扩展自动填表(out of scope v1)。

---

## 8. My passes settings(卡包设置页)

### 8.1 进入方式

- User menu → "My passes"
- 顶部 banner 点击(admin / 游客登录后)

URL: `/settings/passes`

### 8.2 页面结构

```
┌──────────────────────────────────────────────────────────────────┐
│  My passes                                                       │
│  Manage the library cards you hold. Stored only in your browser. │
├──────────────────────────────────────────────────────────────────┤
│  ZIP code  [01880_____]   (used to calculate distance)           │
├──────────────────────────────────────────────────────────────────┤
│  Your libraries                                                  │
│                                                                  │
│  ☑ Lucius Beebe Memorial Library (Wakefield)                     │
│      Barcode  [21000123456789]                                   │
│      Last name [He]                                              │
│      PIN [____] (optional)                                       │
│                                                                  │
│  ☑ Reading Public Library (Reading)                              │
│      ...                                                         │
│                                                                  │
│  ☐ Boston Public Library (Boston)                                │
│  ☐ Wilmington Memorial Library (Wilmington)                      │
│  ... (collapsed list of all 59 libraries, search/filter)         │
├──────────────────────────────────────────────────────────────────┤
│  [Save]                                                          │
└──────────────────────────────────────────────────────────────────┘
```

### 8.3 字段

每张卡 4 个字段:

| 字段 | English label | 必填 | 说明 |
|---|---|---|---|
| 持有 | (checkbox) | — | 勾选才展开下 3 个字段 |
| Barcode | `Barcode` | ✅ | 数字串,通常 13-14 位 |
| Last name | `Last name` | ✅ | 部分馆预约要求姓氏校验 |
| PIN | `PIN` (optional) | ❌ | 部分馆要求,部分不要 |

### 8.4 数据持久化

| 用户类型 | 行为 |
|---|---|
| 游客 | localStorage 临时存;关浏览器丢 |
| 登录用户 | localStorage 按 username 命名空间存(如 `museumpass.alex.passes`);下次登录自动代入 |

不上远端,符合 CLAUDE.md barcode 铁律。

---

## 9. 数据依赖

v1 实现需要这些字段已具备(部分需在数据层补齐):

| 字段 | 现状 | 备注 |
|---|---|---|
| 景点列表(108) | ✅ | `data/structured/attractions.json`(build 阶段) |
| 景点 lat/lon | ❌ | **本 spec 新增需求**:OSM Nominatim 一次性 geocode(免费) |
| 景点 categories | ✅ | 21 个 tag(Family 889 / Children 467 / History 415...);v1 不暴露,后续筛选用 |
| 景点 original price | ⚠️ | 部分有,部分需补:成人/儿童两档,从景点官网 admission 页抓 |
| 景点 hero image | ❌ | **本 spec 新增需求**:每景点 1 张代表图(可手工 curate ~30 张,长尾用占位) |
| 景点营业时间 | ⚠️ | 部分有(详情页用) |
| 图书馆列表(59)+ town + full name + 网络 + 平台 | ✅ | `config/library_seeds.json` |
| 图书馆 lat/lon | ❌ | **本 spec 新增需求**:同景点 geocode 一次 |
| Pass 矩阵(库 × 景 × 折扣 × 类型) | ✅ | `data/raw/<platform>/index/*.json` |
| 库存日历(30 天) | ✅ | `data/raw/<platform>/availability/*.json` |
| 办卡资格 | ✅ | `non_resident_policy_initial` |

> **本 spec 引入的新数据任务**:景点+图书馆 geocode、景点 original price、景点 hero image。在 implementation plan 阶段拆分。

---

## 10. 明确不做(v1 out of scope)

- 顶部分类筛选(categories chip 横条)— 数据 ready,留 v1.1
- Pass 类型筛选 / 图书馆筛选 / 高级筛选抽屉
- 关键词搜索图书馆/category(只搜景点名)
- 真后端账户 / 注册 / 找密码 / 邮箱验证
- 浏览器扩展自动填表
- 距离用真实开车时间(Google Distance Matrix API)
- 移动端独立设计(v1 单列照搬桌面)
- 实时刷新库存
- 全自动下单
- 价格历史 / 提醒订阅 / 个性化推荐 / 量化省钱

---

## 11. Open questions(留给下一轮)

- 详情页 30 天日历的视觉形态(网格 vs 列表)
- Banner / 弹窗的精确文案微调(英文母语顺一遍)
- Heroicons 最终选哪 3 个 pass 类型 icon
- 移动端断点 / 手势细节
- 法律 / 隐私 / 关于页文案
- Logo 设计(目前只有文字 brand)
