# Museum Papa 整改 Plan（基于 2026-05-27 审计）

关联报告：
- [strict_audit_report_20260527.md](/F:/pj/MuseumPapa/audit/strict_audit_20260527/strict_audit_report_20260527.md)

## 目标

本轮不是“再抓一遍数据”，而是重做一部分数据语义和验证链路，避免同类错误继续生成。

核心目标只有 4 个：

1. 把“是否可预订”从模糊推断改成证据驱动。
2. 把“联盟/网络”从单字段粗暴建模改成可表达真实覆盖关系的模型。
3. 把 `pass_form`、`source_url`、`requires_own_card` 这类高影响字段改成可验证、可回归的构建结果。
4. 让 panel 不再把“未知”展示成“确定可订”。

## 本次扫描后的根因判断

### 1. `network` 字段被赋予了过多含义

当前代码把一个 `network` 同时拿来表达：

- 图书馆联盟名称
- 持卡互认范围
- 预订认证覆盖范围
- panel 的 `cardOk` 判断依据

但真实结果已经证明这不成立：

- `libraries.json` 里 `malden.network = MBLN`
- `libraries.json` 里 `bpl.network = BPL`
- panel 的 `cardOk()` 只按 `network` 是否相等做 fallback
- 实测 `Malden` 卡可以真实登录 BPL，并进入 `Booking Details`

所以当前模型无法表达“BPL 与 MBLN 某些卡在认证上互通，但展示上又不是简单同联盟”的事实。

### 2. `booking probe` 的结论语义过于粗糙

当前 `build_passes()` 对 probe 结果的消费逻辑在 [passes.py](/F:/pj/MuseumPapa/src/malibbene/build/passes.py)：

- `accepted` -> `residency_restriction = no`
- `rejected_resident` -> `requires_own_card = true`，并把 `residency_restriction` 也改成 `no`

这里的问题有 3 个：

- probe 输出只有少量分类，不能区分“本馆卡要求”“居民限制”“卡格式前置拦截”“站点异常”“日期 stale”
- 一次 probe 直接写成结构化真相，缺少 freshness / confidence / rerun 机制
- `format_error`、连接被断、页面 stale 等都没有进入可审计状态机，只是散落在脚本输出里

### 3. `panel` 对“可订”过度乐观

[panel.logic.mjs](/F:/pj/MuseumPapa/admin/assets/panel.logic.mjs) 与 [panel.js](/F:/pj/MuseumPapa/admin/assets/panel.js) 当前的核心问题：

- `cardOk()`：只要持有同 `network` 的卡，就默认卡覆盖成立
- `residencyOk()`：很多 `unknown` 会以 `ok + warn` 形式继续通过
- `cellTier()` 会把这些“证据不足但未被拦截”的格子排到较高层级

结果就是：

- 数据未知
- probe 过期
- network 建模错误

这三类问题会被 panel 合成成“看起来可订”。

### 4. `pass_form` 目前没有统一的权威来源

当前 `pass_form` 主要来自：

- Assabet index 的 `pass_type`
- 老的 `coupons` 提取
- `pass_coupons`
- build fallback

但 BPL 已经证明确实会出现：

- 官网写 `Digital (downloadable via email)`，结构化数据却不是 `digital_email`
- 官网写 `pickup but does not need to be returned`，结构化数据却被建成 `physical_circ`

说明 LibCal/BPL 的 `pass_form` 还没有稳定的、确定性的规则。

### 5. 现在的验证器只查“结构没坏”，不查“语义错了”

[validate.py](/F:/pj/MuseumPapa/src/malibbene/build/validate.py) 现在主要检查：

- 引用完整性
- unknown 百分比
- coupon 是否缺失

但它不检查：

- `source_url` 是否 404
- `pass_form` 是否与公开页文本冲突
- `network` 关系是否与真实认证冲突
- probe 是否过期或样本不足
- panel 会不会把 `unknown` 错排成 `a/b` 档

## 新的数据语义设计

### A. 拆分 `network`

不要再让一个字段承载所有语义。

建议新增：

- `consortium_label`
  - 展示用联盟名
  - 例如 `NOBLE`、`MVLC`、`Minuteman`
- `card_auth_groups`
  - 该 library 在“卡认证”层接受哪些持卡来源
  - 例如 `["MBLN", "BPL"]`
- `card_issuance_group`
  - 该馆卡的发卡归属组
  - 例如 `MBLN`
- `panel_card_fallback_groups`
  - panel 在没有逐 pass 实证时，最多允许采用哪些 fallback group
  - 默认应非常保守

具体落地：

- 修改 [config/library_seeds.json](/F:/pj/MuseumPapa/config/library_seeds.json)
- 修改 [libraries.py](/F:/pj/MuseumPapa/src/malibbene/build/libraries.py)
- 修改 [panel.logic.mjs](/F:/pj/MuseumPapa/admin/assets/panel.logic.mjs)
- 修改 [panel.js](/F:/pj/MuseumPapa/admin/assets/panel.js)

### B. 重做 per-pass 的访问判定模型

当前字段：

- `residency_restriction`
- `requires_own_card`

不足以表达真实世界。

建议新增一个更明确的对象，例如：

```json
"booking_access": {
  "same_group_card": "accepted|rejected|format_error|not_tested|stale|site_blocked",
  "own_card_required": "yes|no|unknown",
  "resident_scope": "town|ma|none|unknown",
  "pin_required": true,
  "evidence_type": "browser_probe|http_probe|public_text|manual_override",
  "evidence_at": "2026-05-27T...",
  "evidence_note": "..."
}
```

然后：

- `residency_restriction` 可以保留作兼容层
- 但 panel 和后续 build 逻辑要优先读取 `booking_access`

涉及文件：

- [passes.py](/F:/pj/MuseumPapa/src/malibbene/build/passes.py)
- [panel.logic.mjs](/F:/pj/MuseumPapa/admin/assets/panel.logic.mjs)
- [panel.js](/F:/pj/MuseumPapa/admin/assets/panel.js)

### C. 给 `pass_form` 建立明确优先级

建议按平台分别定义权威来源：

#### Assabet

优先级：

1. index 页 `pass_type`
2. 真实预订页文案中的 pickup / return 语义
3. override

#### LibCal / BPL

优先级：

1. 公开页明确文案
   - `Digital (downloadable via email)` -> `digital_email`
   - `must be picked up` + `does not need to be returned` -> `physical_coupon`
   - `must be picked up` + `returned` -> `physical_circ`
2. booking 页的 `Type` / `Terms & Conditions`
3. override

不要再让旧 `coupons` 或默认值把 `pass_form` 回填错。

涉及文件：

- [src/malibbene/sources_v2/libcal/catalog.py](/F:/pj/MuseumPapa/src/malibbene/sources_v2/libcal/catalog.py)
- [src/malibbene/build/passes.py](/F:/pj/MuseumPapa/src/malibbene/build/passes.py)

## 具体整改方案

## Phase 0：先补测试与证据，不改行为

目标：先把会回归的测试框起来。

### 0.1 新增 BPL/MBLN 关系测试

新增测试表达：

- `Malden` 卡可以覆盖 BPL 登录
- 因此 `cardOk()` 不能只看 `network === network`

建议新增：

- `admin/assets/panel.logic.test.mjs`
- `tests/test_build_passes_v2.py`
- 额外增加 `tests/test_library_access_model.py`

### 0.2 新增 `pass_form` 回归测试

至少覆盖：

- `american-repertory-theater` -> digital
- `boch-center` -> digital
- `harvard-museums-of-science-and-culture` -> physical_coupon
- `hale-education` -> source_url 404 fail-fast

### 0.3 新增 `source_url` liveness 测试

不是所有 URL 都要实时联网验证进 CI，但 build 后至少应支持离线检查脚本：

- 200 / 30x 通过
- 404 直接列为 blocking error

建议新增脚本：

- `scripts/validate_source_urls.py`

## Phase 1：重做访问模型

### 1.1 引入 `booking_access`

在 [passes.py](/F:/pj/MuseumPapa/src/malibbene/build/passes.py)：

- 保留旧字段，新增 `booking_access`
- 所有 probe 结果先写 `booking_access`
- 只有当证据足够明确时，再同步旧字段

### 1.2 不再把 `format_error` 当作“居民限制”或“own card”

当前 Everett 的例子说明：

- `format_error`
- `rejected_resident`

不是一回事。

build 里必须做到：

- `format_error` -> `own_card_required = unknown`
- `resident_scope = unknown`
- panel 不得展示为“确定不可订”

### 1.3 probe 要带 freshness

增加：

- `evidence_at`
- `probe_method`
- `probe_card_label`
- `probe_date`

panel 上如果证据超过阈值未更新，直接显示 `stale`，不要继续按 A/B 档排序。

## Phase 2：升级抓取与 probe

### 2.1 Assabet probe 分层

保留现有 HTTP probe，但新增 browser probe fallback：

- 第一层：HTTP 快速 probe
- 第二层：若结果为 `format_error / unknown / stale-date / connection-reset`
  - 自动切到 Playwright 真人式点击
  - 从 `by-museum` 前台页出发
  - 真实点日期
  - 真实填卡
  - 只到卡校验或下一个 booking step

建议新增或修改：

- [scripts/run_booking_probe.py](/F:/pj/MuseumPapa/scripts/run_booking_probe.py)
- 新增 `scripts/run_booking_probe_browser.py`
- 新增 `src/malibbene/sources_v2/assabet/booking_probe_browser.py`

### 2.2 probe 不要只看一个日期

当前不少阻塞点本质上是：

- 数据说 available
- 实际点进去 stale

改法：

- 从 availability 里取未来 5 到 8 个日期
- 遇到 stale 自动换下一个
- 只有连续多次都失败才记 `no_conclusive_date`

### 2.3 BPL/LibCal 的“权限验证”与“库存/日期”分离

对 BPL：

- 只要有一个可点日期，并能登录到 `Booking Details`
- 就说明“该卡对该 pass 类型具备预订权限”

不需要把日期是否稀缺和权限混在一起。

建议新增轻量脚本：

- `scripts/probe_bpl_login.py`

功能：

- 前台点第一个 available date
- 登录
- 记录是否到 `Booking Details`
- 不点击最终 `Continue`

## Phase 3：修 build

### 3.1 `libraries.json` 改模型

在 [libraries.py](/F:/pj/MuseumPapa/src/malibbene/build/libraries.py)：

- 增加 `consortium_label`
- 增加 `card_auth_groups`
- 增加 `card_issuance_group`
- 增加 `access_notes`

### 3.2 `passes.json` 改模型

在 [passes.py](/F:/pj/MuseumPapa/src/malibbene/build/passes.py)：

- 增加 `booking_access`
- `requires_own_card` 只作为兼容镜像字段
- `residency_restriction` 只在证据明确时写死
- `format_error`、`stale`、`site_blocked` 不再硬翻译成 `no` / `yes`

### 3.3 `pass_form` 的平台化判定

在 [libcal/catalog.py](/F:/pj/MuseumPapa/src/malibbene/sources_v2/libcal/catalog.py)：

- 从详情页文案直接抽取：
  - digital/downloadable
  - pick up
  - returned / does not need to be returned

必要时把这一步单独抽成：

- `sources_v2/libcal/pass_form.py`

### 3.4 增加 `source_url` 失活拦截

build 期间如果：

- `source_url` 404

则：

- 直接进入 validate 报告的 blocking 项
- panel 上展示为 `broken source`

## Phase 4：修 panel

### 4.1 `cardOk()` 不能再只看 `network`

在 [panel.logic.mjs](/F:/pj/MuseumPapa/admin/assets/panel.logic.mjs)：

- `cardOk(lib, heldLibIds, libsById, requiresOwnCard)` 改成读取：
  - `card_auth_groups`
  - `card_issuance_group`
  - per-pass `booking_access`

逻辑优先级：

1. 如果 `booking_access.same_group_card = accepted`，直接可用
2. 如果 `own_card_required = yes`，只有本馆卡可用
3. 如果只有 group overlap，但没有逐 pass 证据，状态为 `tentative`，不要进 A 档
4. 如果 `format_error / unknown / stale`，状态为 `unknown`，不要展示为确定可订

### 4.2 panel 的 tier 重新定义

当前 `a/b/c/d` 太粗。

建议改成：

- `verified_access`
- `tentative_access`
- `own_card_only`
- `resident_blocked`
- `unknown`
- `broken_source`

排序时：

- `verified_access` 才能排最前
- `tentative_access` 明显低于已验证

### 4.3 panel 要把证据来源直接露出来

每个 cell popup 至少显示：

- 结论
- 来源类型：`browser_probe / http_probe / public_text / override`
- 证据时间
- 用哪张卡测的
- 是否因日期 stale 自动换过日期

这会极大降低“黑盒感”。

### 4.4 panel 区分“无日期可点”与“无权限”

BPL 的例子已经证明：

- 当前没有 available date
- 不代表这张卡没权限

所以 popup / 审计视图里要拆成：

- `booking permission`
- `date availability`

不能再混成一个 yes/no。

## Phase 5：增强 validate 与审计闭环

### 5.1 `validate.py` 增加语义型错误

新增至少以下检查：

- `source_url_404_count`
- `pass_form_public_text_conflict_count`
- `stale_probe_count`
- `unknown_access_count`
- `network_model_conflict_count`

### 5.2 建一个“高风险馆”白名单

从这轮审计看，优先级最高的是：

- `MVLC`
- `North Reading`
- `BPL`

建议加一个专项校验列表：

- 这些馆 build 后必须跑 live probe sampling
- 没有 probe freshness 就不允许上线

### 5.3 审计结果回灌方式要变

现在 audit 更像人工 override。

更好的做法是：

- audit 结果先进入 `data/overrides/audit_overrides.json`
- 同时形成 machine-readable 的 `data/audit/live_findings.json`
- build 可以读取它，标记 `verified_bad` / `needs_rerun`

这样就不会只有 panel 看得到，build 却忘了修。

## 建议的执行顺序

### Step 1

先做不改行为的测试补强：

- BPL/MBLN 关系测试
- `pass_form` 回归测试
- `source_url` 404 校验脚本

### Step 2

重做 `network` / `booking_access` 数据模型，但先兼容旧字段。

### Step 3

升级 Assabet probe：

- 多日期
- browser fallback
- freshness

### Step 4

修 BPL / LibCal 的 `pass_form` 和 `source_url` 语义。

### Step 5

重写 panel 的 `cardOk`、tier、evidence 展示。

### Step 6

把 `MVLC + BPL + North Reading` 做成固定 live regression 套餐。

## 预期收益

如果按这个 Plan 落地，最直接的收益是：

- panel 不会再把“未知”展示成“可订”
- `MVLC` 这类整簇过宽判定会大幅减少
- `BPL` 的真实认证关系终于能被模型表达
- `pass_form` 不会再频繁把 digital / pickup / return 混掉
- 审计将从“发现错误”升级成“能阻止同类错误再次生成”

## 最后判断

现在最该做的不是继续堆 override，而是：

- 先拆掉错误的数据语义
- 再补 browser probe
- 最后收紧 panel 的乐观展示逻辑

否则你即使改掉这 29 个点，下一轮 rebuild 还是会生成一批新的“看起来像真、其实没证据”的错误结果。
