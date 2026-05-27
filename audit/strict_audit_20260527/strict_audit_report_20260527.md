# Museum Papa 严格审计报告（第一轮）

## 范围与方法

- 审计日期：2026-05-27
- 审计范围：`admin/panel.html` 对应的后台数据与 panel 展示；忽略用户端。
- 本轮目标：先记录问题数据点，不展开修复方案。
- 忽略项：库存真假、具体日期可用性；日期仅被当作进入真实预约流程的通道。
- 真实验证方式：
  - `Assabet`：直接访问官网预约页，使用现有 5 张卡中的同网络跨镇卡，打到真实卡校验步骤。
  - `BPL / LibCal`：访问官网公开页，并尝试进入预订入口；因仓库只提供条码、未提供 PIN，无法完成需要 `card + PIN` 的最后登录步。

## 样本量

- `Assabet` 抽样 92 个数据点，其中 90 个拿到真实、明确的卡校验结论。
- 另外对 4 个阻塞点做了 Playwright 真人式复测，其中 3 个拿到了补充结论。
- `BPL / LibCal` 公开页核验 10 个数据点。
- 另外对 `BPL` 做了 4 个前台真实点击验证（使用用户临时提供的 `Malden` 卡号与 PIN；凭证未写入任何文件）。
- 总样本数：102。

## 本轮确认存在问题的数据点

### A. Assabet：结构化可预订权限与官网实测不一致

| 类型 | Network | Library | Attraction | 面板/结构化数据主张 | 官网实测 | 证据 |
|---|---|---|---|---|---|---|
| 面板偏严 | NOBLE | north-reading | ma-state-parks | 结构化数据判定为需要本馆卡/本镇资格 | 实测用 wakefield 卡可通过卡校验 | [源页](https://flintmemoriallibrary.assabetinteractive.com/museum-passes/by-museum/massachusetts-state-parks-department-of-conservation-and-recreation/) |
| 面板偏宽 | MVLC | billerica | trustees-of-reservations | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://billericalibrary.assabetinteractive.com/museum-passes/by-museum/trustees-of-the-reservations/) |
| 面板偏宽 | MVLC | boxford | peabody-essex-museum | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://boxfordlibrary.assabetinteractive.com/museum-passes/by-museum/peabody-essex-museum/) |
| 面板偏宽 | MVLC | middleton | real-pirates-salem | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://flintlibrary.assabetinteractive.com/museum-passes/by-museum/real-pirates-salem/) |
| 面板偏宽 | MVLC | andover | the-house-of-seven-gables | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://mhl.assabetinteractive.com/museum-passes/by-museum/the-house-of-seven-gables/) |
| 面板偏宽 | MVLC | middleton | sandmagination | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://flintlibrary.assabetinteractive.com/museum-passes/by-museum/sandmagination/) |
| 面板偏宽 | MVLC | middleton | north-shore-childrens-museum | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://flintlibrary.assabetinteractive.com/museum-passes/by-museum/north-shore-childrens-museum/) |
| 面板偏宽 | MVLC | boxford | museum-of-science | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://boxfordlibrary.assabetinteractive.com/museum-passes/by-museum/museum-of-science/) |
| 面板偏宽 | MVLC | haverhill | the-uss-constitution-museum | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://haverhillpl.assabetinteractive.com/museum-passes/by-museum/the-uss-constitution-museum/) |
| 面板偏宽 | MVLC | andover | new-england-quilt-museum | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://mhl.assabetinteractive.com/museum-passes/by-museum/new-england-quilt-museum/) |
| 面板偏严 | NOBLE | north-reading | butterfly-place | 结构化数据判定为需要本馆卡/本镇资格 | 实测用 wakefield 卡可通过卡校验 | [源页](https://flintmemoriallibrary.assabetinteractive.com/museum-passes/by-museum/the-butterfly-place/) |
| 面板偏宽 | MVLC | tewksbury | new-england-botanic-garden-at-tower-hill | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://tewksburypl.assabetinteractive.com/museum-passes/by-museum/new-england-botanic-garden-at-tower-hill/) |
| 面板偏宽 | MVLC | billerica | the-discovery-museums | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://billericalibrary.assabetinteractive.com/museum-passes/by-museum/the-discovery-museums/) |
| 面板偏宽 | MVLC | haverhill | harvard-museums-of-science-and-culture | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://haverhillpl.assabetinteractive.com/museum-passes/by-museum/harvard-museums-of-science-and-culture/) |
| 面板偏宽 | MVLC | haverhill | butterfly-place | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://haverhillpl.assabetinteractive.com/museum-passes/by-museum/the-butterfly-place/) |
| 面板偏宽 | MVLC | tewksbury | boston-childrens-museum | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://tewksburypl.assabetinteractive.com/museum-passes/by-museum/boston-childrens-museum/) |
| 面板偏严 | NOBLE | north-reading | boston-by-foot | 结构化数据判定为需要本馆卡/本镇资格 | 实测用 wakefield 卡可通过卡校验 | [源页](https://flintmemoriallibrary.assabetinteractive.com/museum-passes/by-museum/boston-by-foot/) |
| 面板偏宽 | MVLC | haverhill | museum-of-printing | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://haverhillpl.assabetinteractive.com/museum-passes/by-museum/museum-of-printing/) |
| 面板偏宽 | MVLC | middleton | ma-state-parks | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://flintlibrary.assabetinteractive.com/museum-passes/by-museum/massachusetts-state-parks-department-of-conservation-and-recreation/) |
| 面板偏宽 | MVLC | andover | seacoast-science-center | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://mhl.assabetinteractive.com/museum-passes/by-museum/seacoast-science-center/) |
| 面板偏宽 | MVLC | haverhill | museum-of-science | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://haverhillpl.assabetinteractive.com/museum-passes/by-museum/museum-of-science/) |
| 面板偏宽 | MVLC | tewksbury | peabody-essex-museum | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://tewksburypl.assabetinteractive.com/museum-passes/by-museum/peabody-essex-museum/) |
| 面板偏宽 | MVLC | burlington | harvard-museums-of-science-and-culture | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://burlington.assabetinteractive.com/museum-passes/by-museum/harvard-museums-of-science-and-culture/) |
| 面板偏宽 | MVLC | methuen | seacoast-science-center | 结构化数据判定为可被同网络非本镇卡预订 | 实测用 wilmington 卡在卡校验即被拒 | [源页](https://nevinslibrary.assabetinteractive.com/museum-passes/by-museum/seacoast-science-center/) |

Assabet 这一类一共确认了 24 个问题数据点。

### B. BPL / LibCal：公开页即可确认的问题

| Library | Attraction | 问题 | 证据 |
|---|---|---|---|
| bpl | american-repertory-theater | `pass_form` 与官网公开页冲突：官网明确写 `Digital (downloadable via email)`。 | [源页](https://bpl.libcal.com/passes/5bf37dc2bee6) |
| bpl | boch-center | `pass_form` 与官网公开页冲突：官网明确写 `Digital (downloadable via email)`。 | [源页](https://bpl.libcal.com/passes/572fd99e65a3) |
| bpl | hale-education | `source_url` 直接返回 404。 | [源页](https://bpl.libcal.com/passes/27fd343838f2) |
| bpl | harvard-museums-of-science-and-culture | `pass_form` 与官网公开页冲突：官网明确写“需 pickup，但 does not need to be returned”，不应归为 `pickup+return`。 | [源页](https://bpl.libcal.com/passes/92c222667367) |

BPL 这一类当前确认了 4 个公开页即可落锤的问题数据点。

### B2. BPL：前台真实点击登录补充验证

| Attraction | 验证方式 | 结果 | 备注 |
|---|---|---|---|
| american-repertory-theater | 从公开页进入，向后翻到 2026-07 仍无可点日期 | 未能验证到登录后页 | 公开页明确写 `Digital (downloadable via email)`，但 2026-05 到 2026-07 都没有可点日期；本轮不把它记成权限错误，只保留 `pass_form` 公开页冲突。 |
| boston-childrens-museum | 从公开页点可用日期 → BPL 登录 → 输入 `Malden` 卡 + PIN → 到 `Booking Details` | 可进入真实预订流 | 说明 `MBLN / Malden` 卡可以真实通过 BPL 登录，且该 pass 的权限通路是通的。 |
| harvard-museums-of-science-and-culture | 公开页切换 branch/location，且向后翻到 2026-07 | 未能验证到登录后页 | 页面语义明确是 physical / pickup 型；只是当前无可点日期，本轮不把它记成权限错误。 |
| mfa | 从公开页点可用日期 → BPL 登录 → 输入 `Malden` 卡 + PIN → 到 `Booking Details` | 可进入真实预订流 | 说明 `MBLN / Malden` 卡可以真实通过 BPL 登录，且该 pass 的权限通路是通的。 |

### B3. BPL / MBLN 联盟关系问题

| 关系点 | 当前结构化数据 | 实测 | 结论 |
|---|---|---|---|
| `malden` 与 `bpl` 的持卡覆盖关系 | `libraries.json` 中 `malden.network = MBLN`，`bpl.network = BPL`，按 panel 现有 `cardOk` 语义，两者不属于同一网络 | 用 `Malden` 卡可真实登录 BPL，并进入 `Boston Children's Museum` 与 `MFA` 的 `Booking Details` | 当前“联盟/网络”建模不正确，至少不足以表达 BPL 与 MBLN 图书馆之间的真实持卡覆盖关系。 |

### C. 阻塞复测后新增确认

| Library | Attraction | Playwright 复测结果 | 处理方式 |
|---|---|---|---|
| framingham | new-england-botanic-garden-at-tower-hill | `accepted` | 解除阻塞，但不记为问题数据点。 |
| belmont | isabella-stewart-gardner-museum | `rejected_resident` | 解除阻塞；与当前结构化结论一致，不新增问题点。 |
| newton | larz-anderson-auto-museum | `accepted` | 解除阻塞，但不记为问题数据点。 |

## 阻塞与未落锤项

### 1. 需要复测但暂不记为数据错误

- `everett / ma-state-parks`：Could not reach a conclusive card-validation result on a future available date.. Playwright 复测结果：`format_error`。

### 2. BPL / LibCal 的最终预订权限仍未完全落锤

- 本轮已经补充了少量真实登录验证：`Boston Children's Museum` 与 `MFA` 都能用用户临时提供的 `Malden` 卡真实进入 `Booking Details`。
- 但我们仍没有把全部 BPL pass 都做完，尤其是当前没有可点日期的项目（如 `American Repertory Theatre`、`Harvard Museums of Science and Culture`）还不能据此推导权限结论。
- 因此，BPL 的剩余未测项仍不记为数据错误，只记为覆盖不足。

## 联盟关系观察

- 本轮没有拿到足够证据证明 `library ↔ alliance/network` 映射本身有系统性错误。
- 相反，`Minuteman / NOBLE / MVLC` 中大量 pass 都能用同网络跨镇卡打到真实卡校验，说明网络识别总体是活的。
- 当前更像是“同一 network 内，不同 library 对具体 pass 的可预订权限差异很大，而结构化数据把它们放宽了”，尤其集中在 `MVLC`。
- 但 `BPL` 是一个明确例外：当前结构化数据把 `bpl` 单独标成 `BPL`，而真实测试表明 `Malden (MBLN)` 卡可以登录 BPL。因此 `BPL` 与 `MBLN` 的关系建模需要重做，不能继续只靠单一 `network` 字段。

## 重点结论

- 本轮总共确认 29 个问题数据点。
- 其中最显著的问题簇在 `MVLC`：多家 library 的多个 pass，结构化数据判定“同网络非本镇卡可订”，但官网真实卡校验直接拒绝。
- `North Reading` 出现反向问题：结构化数据把多个 pass 判成需要本馆卡，但实测同网络跨镇卡可以通过。
- `BPL` 至少有 3 个 pass 的 `pass_form` 与公开页矛盾，另有 1 个 `source_url` 已经 404。
- `BPL` 与 `MBLN` 的联盟/持卡覆盖关系建模错误：`Malden` 卡可真实登录 BPL，但现有结构化 `network` 语义表达不出来。
- `BPL` 的真实登录链路已被少量验证打通：`Malden` 卡可进入 `Boston Children's Museum` 与 `MFA` 的真实 `Booking Details` 页，因此后续 BPL 审计可以继续沿这条路径少量扩展。
