# platform_pass_ids/ — 手工 pass-id 映射

每个 LibCal / MuseumKey 馆都有自己的 pass id 命名空间(BPL 用 12-hex、Cambridge 用 slug、Brookline 多用短代码),无法机械派生 → benefit_id 的对应,只能手工对照。Assabet 不需要(slug 即 benefit_id)。

## 文件

| 文件 | 内容 | 何时改 |
|---|---|---|
| `bpl.json` | `benefit_id → 12-hex pass_id`(BPL 单独成文件,因其命名空间与其他 LibCal 馆不共享) | BPL 新增 / 重命名 / 下架 pass 时 |
| `libcal.json` | 4 个非 BPL LibCal 馆(Cambridge / Brookline / Braintree / Milton),每馆 `{domain, passes: {libcal_id → benefit_id}}` | 这些馆新增 pass、改 libcal_id、换 subdomain 时 |
| `museumkey.json` | 2 个 MuseumKey 馆(Cohasset / Hingham)的 `{code, branchID}` + 全平台共享的 `name → benefit_id` 表 | MuseumKey 馆新增、改 branchID、加新景点显示名时 |

## benefit_id 是什么

跨平台的"景点规范 id",在 `data/structured/attractions.json` 里唯一。同一景点在 Assabet 用 `boston-childrens-museum`,在 Brookline LibCal 用代码 `BCM`,在 Cohasset MuseumKey 用 `"boston children's museum"`(名字)。这三个 source-side id 都要映射回同一个 benefit_id。

## 怎么补一条新映射

1. 跑一次最新 catalog scrape,从 raw json 里找到那条 pass 的 source-side id(libcal_id / musID / 馆显示名)
2. 决定它属于哪个 benefit_id:
   - 如果 `data/structured/attractions.json` 里已经有这个景点 → 用现有的 benefit_id
   - 如果是全新景点 → 选个 kebab-case slug 作为新 benefit_id,并在 attractions.json 里新建条目
3. 写一条 `{source_id: benefit_id}` 到对应文件的 `passes` 块里
4. 提交,并在 commit message 里说明新增映射的来源

## 已知限制

- **BPL 的 hale-education**:BPL 提供 Hale Education physical pass,但本项目数据集里还没建 `hale-education` benefit。保留这条映射是为了将来一旦景点入库就能匹配上,不会孤儿。
- **Brookline 的 c284e6b3063b**:这个 hex id 是 zoo-new-england — 同一馆里多数 pass 用短代码,只有这条用 hex,原因不明,猜是新建时没设短代码。
- **MuseumKey 的 musID**:musID 是 library-specific 的数字,所以这里用"馆显示名(lowercased)"作 key 而非 musID。如果上游改了显示名(如增减"the"),需要同步补对应大小写变体。
