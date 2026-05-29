# Dead source_url 回填表(v2 — 已剔除审计误判)

> 2026-05-29 重新实测,带浏览器 UA + 跟 301 跳转,顺手核对了每个馆当前的 `by-museum/` 索引。
>
> **审计误判(已剔除,不在本表)**:
> - marblehead / lexington / everett / middleton / north-andover / wilmington 的 NEA 实际是活的 → 这 6 条要从 `passes.json` 里**加回来**(action 见底部 §3)
>
> **本表只列真死的 20 条**,分三组。

---

## 1. NEA 真死 · 10 馆(Assabet,索引里已无 NEA)

> 现状:这些馆 Assabet 目录里确认看不到 New England Aquarium,已从 `passes.json` 移除。
> 如果你拿到馆方公告说 NEA 又签回来了,填新 URL,我会还原。

| # | library_id | 旧 URL(404) | 新 URL(请填) |
|---|---|---|---|
| 1 | acton | https://actonmemoriallibrary.assabetinteractive.com/museum-passes/by-museum/new-england-aquarium/ | |
| 2 | belmont | https://belmontpubliclibrary.assabetinteractive.com/museum-passes/by-museum/new-england-aquarium/ | |
| 3 | framingham | https://framinghamlibrary.assabetinteractive.com/museum-passes/by-museum/new-england-aquarium/ | |
| 4 | sudbury | https://goodnowlibrary.assabetinteractive.com/museum-passes/by-museum/new-england-aquarium/ | |
| 5 | lynnfield | https://lynnfieldlibrary.assabetinteractive.com/museum-passes/by-museum/new-england-aquarium/ | |
| 6 | methuen | https://nevinslibrary.assabetinteractive.com/museum-passes/by-museum/new-england-aquarium/ | |
| 7 | peabody | https://peabodylibrary.assabetinteractive.com/museum-passes/by-museum/new-england-aquarium/ | |
| 8 | somerville | https://somervillepubliclibrary.assabetinteractive.com/museum-passes/by-museum/new-england-aquarium/ | |
| 9 | wellesley | https://wellesleyfreelibrary.assabetinteractive.com/museum-passes/by-museum/new-england-aquarium/ | |
| 10 | lawrence | https://lawrencepl.assabetinteractive.com/museum-passes/by-museum/new-england-aquarium/ | |

## 2. brookline 两条 LibCal · 真死

| # | attraction | 旧 URL(404) | 新 URL(请填) |
|---|---|---|---|
| 11 | new-england-aquarium | https://brooklinelibrary.libcal.com/passes/nea | |
| 12 | zoo-new-england | https://brooklinelibrary.libcal.com/passes/c284e6b3063b | |

## 3. lawrence 整馆迁 WhoFi · 8 条已重映射

> 现状:已通过 `audit_overrides.json` 改成 `https://lawrence-ma.whofi.com/passes/reserve/<id>`,前端能点。
> 留空 = 保持 WhoFi。要换别的入口才填。

| # | attraction | 旧 URL(404) | 当前生效(WhoFi) | 新 URL(请填) |
|---|---|---|---|---|
| 13 | boston-childrens-museum | https://lawrencepl.assabetinteractive.com/museum-passes/by-museum/boston-childrens-museum/ | https://lawrence-ma.whofi.com/passes/reserve/99 | |
| 14 | harvard-museums-of-science-and-culture | https://lawrencepl.assabetinteractive.com/museum-passes/by-museum/harvard-museums-of-science-and-culture/ | https://lawrence-ma.whofi.com/passes/reserve/98 | |
| 15 | ma-state-parks | https://lawrencepl.assabetinteractive.com/museum-passes/by-museum/massachusetts-state-parks-department-of-conservation-and-recreation/ | https://lawrence-ma.whofi.com/passes/reserve/103 | |
| 16 | mfa | https://lawrencepl.assabetinteractive.com/museum-passes/by-museum/museum-of-fine-arts/ | https://lawrence-ma.whofi.com/passes/reserve/100 | |
| 17 | museum-of-science | https://lawrencepl.assabetinteractive.com/museum-passes/by-museum/museum-of-science/ | https://lawrence-ma.whofi.com/passes/reserve/101 | |
| 18 | the-uss-constitution-museum | https://lawrencepl.assabetinteractive.com/museum-passes/by-museum/the-uss-constitution-museum/ | https://lawrence-ma.whofi.com/passes/reserve/104 | |
| 19 | wheelock-family-theatre | https://lawrencepl.assabetinteractive.com/museum-passes/by-museum/wheelock-family-theatre/ | https://lawrence-ma.whofi.com/passes/reserve/105 | |
| 20 | zoo-new-england | https://lawrencepl.assabetinteractive.com/museum-passes/by-museum/zoo-new-england/ | https://lawrence-ma.whofi.com/passes/reserve/106 | |

---

## 4. 不需要你回的:6 条审计误判,我会自动恢复

| library | attraction | 实测可用 URL |
|---|---|---|
| marblehead | new-england-aquarium | https://abbotlibrary.assabetinteractive.com/museum-passes/by-museum/new-england-aquarium/ |
| lexington | new-england-aquarium | https://carylibrary.assabetinteractive.com/museum-passes/by-museum/new-england-aquarium/ |
| everett | new-england-aquarium | https://everettpubliclibraries.assabetinteractive.com/museum-passes/by-museum/new-england-aquarium/ |
| middleton | new-england-aquarium | https://flintlibrary.assabetinteractive.com/museum-passes/by-museum/new-england-aquarium/ |
| north-andover | new-england-aquarium | https://stevensmemlib.assabetinteractive.com/museum-passes/by-museum/new-england-aquarium/ |
| wilmington | new-england-aquarium | https://wilmlibrary.assabetinteractive.com/museum-passes/by-museum/new-england-aquarium/ |
