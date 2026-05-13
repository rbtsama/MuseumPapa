# North Shore Library Benefits — 项目业务说明

> 本文档是给业务和产品同事看的，**不讨论技术实现**。
> 内容会随讨论持续更新，新发现会追加进相应章节。

---

## 一、项目是什么

一句话：

> **帮 Massachusetts 有娃家庭把"用图书馆卡免费/打折逛博物馆"这件事变得简单可用的工具。**

在 Massachusetts，公共图书馆有一项标志性的家庭福利：持图书馆卡的居民，可以通过图书馆免费或大幅折扣预订博物馆、动物园、剧院、公园等景点的门票。一个有娃家庭一年能因此省下几千美金。

但这项福利对真正想用的人**非常难用**——后面"用户痛点"一节会展开。这个项目就是把这件事变得简单可用。

---

## 二、项目范围

### 2.1 地理范围

**仅限 Massachusetts (MA) 州**。
**当前抓取范围:eastern MA 共 59 家图书馆**（覆盖 NorthShore + Minuteman 西郊 + MVLC 北郊 + OCLN 南郊 + BPL）。这是 backup/ 上一代代码已经验证跑通的范围,本期照此对齐。
**产品交付焦点仍是 NorthShore**:运营方住在 Wakefield、主要用 Wakefield/Reading/BPL/Wilmington/Somerville 5 张卡。其他 ~50 家图书馆是顺手收下的"广覆盖底盘",用来跨馆比对凭证形态、跨网络验证可订性,以及问题 3"该办哪张卡"的全样本基线。
跑稳之后再考虑扩到 MA 全境（中西部 CW MARS 网络等),再之后才会考虑别的州。

### 2.2 用户画像

主力用户画像：

- 住在 NorthShore 区域的有娃家庭
- 经常带孩子出门玩，**频次足够高**到让"免费博物馆"有意义
- **不会频繁出 MA**（如果经常跨州，办个 NARM/ASTC 全美博物馆互惠会员卡更划算，不需要这个工具）
- 倾向用免费工具，对付费产品不敏感

### 2.3 商业模式

**免费 + 广告**。不收用户钱。

---

## 三、用户痛点（项目要解决的事）

为什么这个福利好但难用：

1. **每家图书馆有自己独立的预约网站**，想比较几家的票必须挨个打开。
2. **同一个博物馆，不同图书馆给的待遇完全不一样**：有的免费、有的半价、有的固定折扣金额；有的人数限制 4 人、有的 6 人；有的要去图书馆取票，有的发邮箱链接。
3. **不同图书馆对"谁能办卡、谁能预约"的政策差异很大**：有的对所有 MA 居民开放、有的只对本网络内的居民、有的只对本镇居民。
4. **热门景点档期紧张**，库存随时在变，靠人工每个网站轮询根本跟不上。
5. **预约本身流程繁琐**：打开表单 → 输入图书馆卡号 → 输入姓 → 提交。卡号是一串数字，每次手动复制易错。
6. **网站显示"可订"≠真的能订**。这点最坑：网站只检查"还有库存没"，不检查"你这张卡这次合规不"。常见的隐形拒绝理由包括：
   - 你过去爽约过被列入黑名单
   - 这个博物馆对图书馆卡之外还有居住身份要求
   - 同一家庭/网络这周已经用过限额
   - 这一天对这个景点是节日例外
   只有提交后才知道被拒，跑空一趟。

---

## 四、项目要回答的三个问题

按业务优先级排序：

| 优先级 | 问题 | 用户视角 |
|---|---|---|
| **核心** | 1. 我有 A、B、C 卡，我可以去哪些地方？ | 我已经办了几张卡，看看这些卡加起来能解锁哪些景点的福利。 |
| **核心** | 2. 我想去 X 地方，我现在可以订票么？ | 下周六想带娃去 Museum of Science，我手上的卡里哪一张、哪一天能订到？ |
| **补充** | 3. 我没有合适的卡订 Y 地方，我应该办哪个图书馆的卡？ | 想去某景点但现有的卡都不行，去办哪一家图书馆的卡能解锁？ |

**初版重点交付问题 1 和问题 2**。问题 3 只做最基础的"办了 X 卡能多解锁哪些景点"，更深的功能（量化能省多少钱、量化提升多少订到率、个性化推荐）**不做**——属于真实使用一段时间后再根据用户反馈决定的方向。

---

## 五、战略定位（决定要把多少精力投到数据上）

理解后续所有取舍前，必须先想清楚：**这个项目的壁垒在哪。**

**壁垒不在数据，而在用户。**

- **数据是必须的**：没有数据，产品根本跑不起来。
- **数据不能用来挡竞争**：理论上谁都能重新爬一遍，但**没人会来抢这个市场**，原因如下：
  - **用户群太小，竞品做付费推广收不回成本**。NorthShore 这种粒度的目标家庭，加上"主要在 MA 内活动"的画像约束，总量小到任何竞品做线上投放都不划算。
  - **北美家庭用户在熟人网络里被推荐了一个能用的工具后几乎不会切换**。
  - **项目运营方本身就在这个家庭网络里**，推广不需要花钱，全靠口碑。
- **商业化压力低**：免费 + 广告模式，竞争不来自切换成本，而来自"被不被推荐"。

**这件事直接决定了要把多少精力投到数据上。**

> **数据只要"够用"就好。"完美"不会被熟人网络奖赏，反而会拖慢上线和稳定。**

具体推论：

- **优先做核心需求**：问题 1 和问题 2 必须扎实；问题 3 是补充。
- **不做甜点功能**：能省多少钱、订到率提升多少、个性化推荐、提醒订阅、历史趋势——这些**初版明确不做**。
- **从小做起**：第一版只做 NorthShore，已覆盖 13 家图书馆 + BPL，已经是家庭活跃度最高的区域。
- **测试投入也按这个尺度**：现有 4 张卡（Wakefield + Reading + BPL + Wilmington）已经覆盖 NorthShore 几乎所有图书馆类型（NOBLE 网络、MVLC 网络、BPL 自己一家、不同的居住身份政策、不同的凭证形态）。**真正要做的不是再去办很多卡，而是把每次预订的成功/失败完整记录下来**。

---

## 六、项目的核心是数据

整个项目本质上就是一件事：**把分散在几十个网站上的福利信息收集、整理、保持新鲜，让用户能用一句话拿到答案**。

呈现形态（搜索框 / 结构化筛选 / AI 问答）后续再定，对核心数据没有影响。

数据按更新频率分两类：

### 6.1 静态数据（变化慢，半年以上才更新一次）

低频抓取一次即可。这又分两个子类：

**A. 结构化静态数据**（网页上有现成字段，直接读就有）：
- 图书馆名称、城镇、所属网络（NOBLE / MVLC / Minuteman 等）
- 图书馆办卡政策（任何 MA 居民 / 仅本网络居民 / 仅本镇居民）
- 哪家图书馆和哪个景点有合作
- 凭证形态（数字券 / 纸质取票券 / 取了次日要还的循环借阅票）
- 预约页面的链接规律

**B. 非结构化静态数据**（藏在描述文字里，需要把文字逐条读懂）：
- 每张票的人数限制（比如"最多 4 个人"）
- 每张票的使用排除项（比如"不含 IMAX、boat programs、学校团"）
- **额外的居住身份要求**（比如 Reading 借的 Harvard Museums 票还要再证明同行人是 MA 居民）
- 季节性规则（比如"2025 年 6 月 1 日到 8 月 31 日只能周一到周五用"）
- **家庭/网络的使用配额**（比如 Winchester 每户每周最多用 2 次）
- 迟还罚款金额
- 节日的特殊不可用规则（比如"Salem Witch Museum 十月不可用"）
- 景点的营业时间、每周闭馆日、节假日闭馆

> B 这一层是当前数据完全没收的关键漏洞。是初版要补齐的核心。

### 6.2 动态数据（变化快，需要持续抓取）

**核心就一件事：每天的库存。**

某个景点 × 某家图书馆 × 某一天的票还有没有（有票 / 部分时段还有 / 已订满）。这是热门票真正的稀缺资源所在，也是问题 2"我现在能不能订"的唯一依据。

实际抓取频率不在本文讨论范围（属于后续技术设计），这里只确认它**确实是动态的**。

### 6.3 真实预订成功率（独有数据，需要靠自己跑出来）

这是市面上**任何来源都给不出**的数据。

来源：用项目运营方自己的几张图书馆卡，每次正常下单时把结果记下来——"这张卡、这一天、这个景点，我提交了，到底成没成？没成的话拒绝理由是什么？"

为什么必须自己记：

- 图书馆网站只检查"还有票没"，不检查"你这张卡这次合规不合规"——它根本不知道访问者是谁。
- 隐形规则（家庭配额用完了、之前爽过约被列黑名单、节日例外、网络外限制等等）只在你提交后才会冒出来拒绝。
- 一般用户根本产不出这种数据——没人会同时办 4 张卡跑实验。

**这反而是项目最有价值的资产**：它直接提升用户的"订到率"——预先过滤掉那些"看似能其实不能"的组合，让用户少跑空。

---

## 七、三个问题分别需要哪些数据

### 7.1 问题 1：我的卡能去哪些地方？

| 需要的数据 | 现状 | 怎么补齐 |
|---|---|---|
| 哪些景点 × 哪些图书馆有合作 | ✅ 已有 | 59 家图书馆 × ~108 个唯一景点的合作矩阵(backup 已抓全;v0.1 还在重抓中) |
| 每个组合的折扣力度（免费 / 半价 / 折扣金额）+ 备注 | ✅ 已有 | Assabet/LibCal 文本里抓 + `normalize_benefit` 词法归一(backup 已写,本期 port) |
| 凭证形态（数字 / 取票 / 取还） | ✅ 已有 | 52 家 Assabet 字段化抓取;5 家 LibCal 标题后缀 + availability blurb 识别;2 家 MuseumKey 文本关键词 |
| 每家图书馆的办卡政策 | ✅ 已有 | 人工整理 |
| 景点营业时间、每周闭馆日、二次预约模式 | ✅ 已有 | 人工整理 |
| 距离用户家的开车时间 | ⚠️ 粗略 | 当前是手填的非高峰估计，针对单一起点。后续可接地图 API 算精确值。 |
| **非结构化静态数据**（人数限制、排除项、额外居住要求、季节规则、家庭配额、节日例外） | ❌ 没收 | **初版要补齐的核心** |
| 节假日闭馆 | ❌ 没收 | 用通用美国节假日清单兜底 + 景点官网点对点核校 |
| 新景点 / 新合作自动发现 | ❌ 没收 | 定期重抓图书馆主索引页对比上次结果，发现新增就触发补录 |

### 7.2 问题 2：我现在能订么？

| 需要的数据 | 现状 | 怎么补齐 |
|---|---|---|
| 每个景点 × 每家图书馆 × 未来 30 天每天的可用性 | ✅ 已有 | Assabet 13 家 + BPL 都有自动抓取 |
| 在用户的卡里查"哪天哪张卡能订" | ✅ 已有 | 用现有数据查一下就有 |
| 哪张卡最划算（多数情况 BPL 优先） | ✅ 已有 | 按折扣力度排序 |
| 选定后能直接打开预约表单 | ✅ 已有 | 各家图书馆的 URL 有规律，直接拼出来 |
| 减少预约时的手输步骤 | ✅ 已有 | 自动复制卡号到剪贴板，用户粘贴即可 |
| 抓取失败时不要让用户误以为"那天没票" | ❌ 没做到 | 每次抓取记录成功还是失败；失败的标成"未知"而不是"订满" |
| **真实预订成功率**（"看似能其实不能"的修正） | ❌ 没做到 | 见 6.3：用现有 4 张卡每次提交后把结果记下来 |
| 节假日不让用户误判"那天能去" | ❌ 没做到 | 同 7.1 节假日补齐 |
| 故意不做：直接在产品内完成预约（连姓和 PIN 都不用再输） | ❌ | 自动帮用户提交订单可能违反图书馆网站的使用条款，风险太大。当前"打开表单 + 复制卡号"已经够好用 |

### 7.3 问题 3：我应该办哪个图书馆的卡？

仅做最基础的一档：

| 需要的数据 | 现状 | 怎么补齐 |
|---|---|---|
| 假设办了 X 卡，能多解锁哪些景点 | ✅ 已有 | 对比一下当前没解锁的、X 卡能解锁的就是答案 |
| 每家图书馆的办卡门槛（任何 MA / 仅本网络 / 仅本镇） | ✅ 已有 | 已经记录在数据里 |
| 办卡的操作信息（在线可办 / 必须现场 / 需要什么证件 / 临时电子卡能不能预约 museum pass） | ⚠️ 信息散落在描述里 | 拆成几个独立字段（在线可办：是/否、所需证件清单、电子卡限制），初版要做 |

**明确不做**（编号保留供未来反查）：

- 3.4 量化能多省多少钱
- 3.5 量化能多提升多少订到率
- 3.6 个性化推荐
- 3.7 沉淀"已考虑过但放弃"的图书馆

这些是真实使用一段时间后用户反馈驱动才决定要不要做的方向。

---

## 八、当前状态总览

按"已经做到 / 还差什么"摊开：

### 8.1 已经做到的事

- 59 家图书馆 + ~108 个景点的合作矩阵已抓通(backup 跑过,v0.1 正在按新结构对齐)
- 折扣值、备注、凭证形态在 backup 已结构化(`normalize_benefit.py` 词法表)
- 30 天可用性自动抓取覆盖:Assabet 52 家 + LibCal 5 家(含 BPL)。MuseumKey 2 家仅 catalog(日历需登录,故意不抓)
- 用户持卡组合下"哪天哪张卡能订"能算(5 张卡:Wakefield/Reading/BPL/Wilmington/Somerville)
- 一键打开预约页 + 自动复制卡号能用

### 8.2 初版要补齐的事

| 缺口 | 影响哪个问题 | 价值 |
|---|---|---|
| 非结构化静态数据（人数限制、排除项、额外居住要求、季节规则、家庭配额） | 1 + 2 | 高——直接决定用户能不能用某张票 |
| 节假日闭馆识别 | 1 + 2 | 高——避免用户跑空 |
| 真实预订成功率记录（"看似能其实不能"） | 2 | **最高**——市面独有的数据，直接提升用户订到率 |
| 抓取失败状态记录 | 2 | 中——避免误把"没抓到"当"订满" |
| 办卡操作信息结构化 | 3 | 中——支撑问题 3 的最小可用版本 |

### 8.3 故意不做的事

- **全自动帮用户下单**：可能违反图书馆网站使用条款，风险太大；现在"打开表单 + 复制卡号"已经够省事。
- **实时刷新**：用户自己点"刷新"按钮已经够用，搞实时反而成本高。
- **BPL 之外其他用 LibCal 平台的图书馆**：用户没那些卡，抓了也没用。
- **能省多少钱、订到率提升多少、个性化推荐等甜点功能**：不是必需。
- **跨设备同步、多用户共用**：先证明对一个家庭真的有用，再考虑扩展。

---

## 九、给业务方的一句话

> 这个项目的壁垒**不在数据层，而在用户层**——MA NorthShore 这种粒度的家庭用户群对任何竞品都不值得做付费投放，运营方本身又在熟人网络里推广成本为零。所以**数据只要"够用"就好**，不必追求完美。
>
> 初版要扎实的只有两件事：
> 1. **问题 1**（我的卡能去哪些地方）—— 已经基本能回答，需要补齐非结构化静态数据（人数限制、排除项、额外居住要求等）。
> 2. **问题 2**（我现在能订么）—— 库存抓取已经能跑，需要把"看似能其实不能"的真实情况记下来（用现有 4 张卡每次提交后把结果记录下来）。
>
> 问题 3 只做最基础的"办了 X 卡能多解锁哪些景点 + 办卡门槛 + 操作信息"，**能省多少钱、订到率提升、个性化推荐这些甜点功能不在初版**——等真实使用反馈出现再决定。
>
> 范围**先收到 NorthShore**，跑稳后再考虑扩到 MA 全境。

---

# 附录

> 附录是给后续技术同事和数据维护者的参考材料。业务同事可以跳过。

---

## 附录 A：所有相关网站清单

### A.1 全 59 馆按平台分组(完整列表见 `config/library_seeds.json`)

四个抓取平台 + 一个跳过平台:

| 平台 | 馆数 | 索引页规律 | 抓取状态 |
|---|---|---|---|
| **Assabet Interactive** | 52 | `<sub>.assabetinteractive.com/museum-passes/by-museum/` | catalog + availability(自动) |
| **LibCal**(BPL + 4 馆) | 5 | `<sub>.libcal.com/passes` | catalog + availability(自动) |
| **MuseumKey** | 2 | `www2.museumkey.com/ui/byMuseum/?code=<x>&branchID=<n>` | **仅 catalog**;availability 需登录,故意不抓 |
| **Winpublib(自研)** | 0 (跳过) | `winpublib.org/museumpasses/` | Winchester 自研系统已迁到 Assabet(`winpublib.assabetinteractive.com`),原 winpublib.org 不再抓 |

#### A.1.1 LibCal 5 家

| 图书馆 | 城镇 | 入口 |
|---|---|---|
| Boston Public Library (BPL) | Boston | https://bpl.libcal.com/passes |
| Cambridge Public Library | Cambridge | https://cambridgepl.libcal.com/passes |
| Brookline Public Library | Brookline | https://brooklinelibrary.libcal.com/passes |
| Thayer Public Library | Braintree | https://thayerpubliclibrary.libcal.com/passes |
| Milton Public Library | Milton | https://miltonlibrary.libcal.com/passes |

BPL 票使用条款总页:https://www.bpl.org/faq/museum-pass-details/

#### A.1.2 MuseumKey 2 家(catalog-only)

| 图书馆 | 城镇 | 入口 |
|---|---|---|
| Paul Pratt Memorial Library | Cohasset | https://www2.museumkey.com/ui/byMuseum/?code=paulma02025&branchID=231 |
| Hingham Public Library | Hingham | https://www2.museumkey.com/ui/byMuseum/?code=hingma02043&branchID=505 |

#### A.1.3 Assabet 52 家

详见 `config/library_seeds.json` 中 `platform=="assabet"` 的条目。地理上覆盖:NOBLE 北郊(Wakefield/Reading/Stoneham/Lynnfield/Peabody/Saugus/Malden/Melrose/Woburn/N.Reading + Beverly/Danvers/Lynn/Marblehead/Everett/Chelsea)、MVLC 北郊与梅里马克河谷(Burlington/Wilmington/Billerica/Topsfield/Boxford/Tewksbury/Chelmsford/Haverhill/Lawrence/Methuen/Andover/N.Andover/Middleton)、Minuteman 西郊(Medford/Winchester/Arlington/Newton/Lincoln/Acton/Framingham/Maynard/Carlisle/Wayland/Weston/Sudbury/Belmont/Lexington/Wellesley/Waltham/Watertown/Concord/Bedford/Needham/Natick/Somerville)、OCLN 南郊(Quincy)。

### A.2 平台 pass_id 映射

每平台的 pass_id 命名空间不同,需要手工对照表把 source-side id 映射回项目的 canonical `benefit_id`。这三份手工表放在 `config/platform_pass_ids/{bpl,libcal,museumkey}.json`,Assabet 不需要(slug 即 benefit_id)。

### A.3 已知跳过

| 来源 | 原因 |
|---|---|
| 原 Winchester `winpublib.org/museumpasses/` | 已经迁到 Assabet 平台(`winpublib.assabetinteractive.com`),原自研系统下线 |
| MuseumKey 可用性日历 | 需登录(图书馆卡 barcode),不能匿名抓取;Cohasset/Hingham 仅有 catalog 数据 |

### A.4 图书馆网络主站（用于查办卡资格、网络政策）

| 网络 | 入口 | 作用 |
|---|---|---|
| MBLC（MA 图书馆委员会，福利出资方、官方目录） | https://mblc.state.ma.us/directories/libraries/ | 全州图书馆通讯录，没有 pass 搜索能力 |
| NOBLE | https://www.noblenet.org/ | 北郊主要网络，多数 Assabet 馆在内 |
| MVLC | https://www.mvlc.org/ | Burlington / Wilmington 在内 |
| Minuteman | https://www.minlib.net/ | Medford / Acton / Cambridge 在内；网络内通用卡 |
| CW MARS | https://www.cwmars.org/ | 中部/西部 MA 网络 |

### A.5 景点官方网站（用于校对营业时间 / 节假日 / 使用规则）

> 已收录 52 个景点，下面只列代表条目。完整清单见项目数据文件。

| 景点 | URL |
|---|---|
| Museum of Science | https://www.mos.org/visit |
| New England Aquarium | https://www.neaq.org/ |
| Boston Children's Museum | https://www.bostonkids.org/ |
| Museum of Fine Arts (MFA) | https://www.mfa.org/ |
| Isabella Stewart Gardner Museum | https://www.gardnermuseum.org/ |
| Peabody Essex Museum | https://www.pem.org/ |
| Zoo New England | https://www.zoonewengland.org/ |
| Discovery Museum (Acton) | https://www.discoveryacton.org/ |
| Mass Audubon | https://www.massaudubon.org/ |
| Trustees of Reservations | https://thetrustees.org/ |
| MA State Parks (DCR) | https://www.mass.gov/dcr |
| Harvard Museums of Science & Culture | https://hmsc.harvard.edu/ |
| Plimoth Patuxet Museums | https://plimoth.org/ |
| ICA Boston | https://www.icaboston.org/ |
| JFK Library | https://www.jfklibrary.org/ |
| MASS MoCA | https://massmoca.org/ |

### A.6 博物馆反向清单（仅 3 家公开发布"哪些图书馆参与我们的 pass"）

实测：抽查 14 家 MA 主流博物馆，**只有 3 家**公开发布了结构化的"参与图书馆"清单。其余 11 家全部只有一句"问你家图书馆"。

| 博物馆 | URL | 对项目的价值 |
|---|---|---|
| **Discovery Museum (Acton)** | https://www.discoveryacton.org/member-libraries | **NorthShore 项目超高价值**——Discovery 是亲子向重头戏，这份清单可作为该景点合作关系的最权威校对源 |
| JFK Library | https://www.jfklibrary.org/visit-museum/visit/plan-your-trip/public-library-museum-pass-program | 该景点的最权威校对源 |
| MASS MoCA | https://massmoca.org/library-pass-program/ | 该景点的最权威校对源 |

**用法**：不能作为系统性校对源（覆盖率太低，只有 3/14），但可以对这 3 个景点做**机会主义校对**——定期对一下我们抓到的"哪些馆有此 pass" vs 它们公布的，发现差异说明上游有变化。

---

## 附录 B：每类数据从哪里来、怎么拿

### B.1 静态数据

| 数据 | 主要来源 | 怎么拿 | 备份/校对来源 |
|---|---|---|---|
| 图书馆名称、城镇、网络归属 | MBLC 目录 + 各馆主站 | 一次性人工整理 | 各网络主站 |
| 图书馆办卡政策 | 各馆主站 "Get a Card" 页 | 半人工：抓借阅政策页 + 人工归类成 3 档 | 网络主站政策页 |
| 图书馆 × 景点合作关系 | Assabet 各馆主索引页 / LibCal 福利列表(BPL + 4 馆)/ MuseumKey byMuseum 页(Cohasset/Hingham) | 抓主索引页里的景点条目 | 景点官网反向页（仅 3 个景点有） |
| 折扣力度 | Assabet 主索引页里每张票的描述段；LibCal/MuseumKey 单票详情页 | `normalize_benefit.py` 词法表归一(免费/$N per person/half/N% off/...)+ 人工核校 | 景点官网 |
| 凭证形态 | Assabet 主索引页字段化；LibCal 标题后缀 + availability blurb;MuseumKey 文本关键词 | 三平台各自识别 | — |
| **非结构化静态数据**（人数、排除项、季节规则、额外居住要求、家庭配额、罚款金额） | Assabet 各馆主索引页的 "Benefits" 自由文字；BPL 单票详情页 | 用 AI 模型从自由文字里逐条读出来（写法不统一，机械文本匹配不可靠） | 景点官网 |
| 景点营业时间、每周闭馆日 | 景点官网 "Visit"/"Hours" 页 | 用 AI 提取 / 接 Google Places API | 图书馆主索引页（往往过期，仅供交叉验证） |
| 节假日闭馆 | 景点官网 + 通用美国节假日清单 | 通用清单兜底 + 景点官网年初公告核校 | 用户反馈 |
| 二次预约模式 | 景点官网 + 图书馆 pass 备注 | 半人工归类成 6 档（walk-in / 推荐预约 / 必须预约 / promo code / 定时导览 / 季节性） | — |
| 预约直达链接规则 | 平台 URL 结构（Assabet 与 LibCal 各自有规律） | 总结一次后写入模板 | — |

### B.2 动态数据

| 数据 | 来源 | 怎么拿 | 注意事项 |
|---|---|---|---|
| Assabet 13 家某 (馆 × 景点) 的 30 天可用性 | 各馆景点页的日历区 | 解析每日 HTML 元素的状态：有票 / 部分时段可用 / 订满 | 翻页拼出未来 ~3 个月 |
| BPL 某张票的可用性 | BPL LibCal 内部异步接口（按月） | HTTP 请求拿 HTML 片段，识别状态：可订 / 已订 / 尚未开放 | LibCal 用异步加载，不能直接抓页面，必须走该接口 |
| 同一景点在多家图书馆的库存横向对比 | 上面两个数据源合并 | 合并查询 | BPL 与 Assabet 是独立的库存池 |
| **真实预订成功率**（"网站说能但提交被拒"的修正） | 自有真实卡每次提交后把结果记下来 | 现有 4 张卡（Wakefield + Reading + BPL + Wilmington）已覆盖 NorthShore 几乎所有图书馆类型。重点是每次提交都记录"成功还是被拒、被拒理由是什么"，不是再去办更多卡 | 用脚本批量自动提交可能违反图书馆网站使用条款，要靠人工正常下单的过程顺手记录 |

### B.3 边界与已知盲点

- **节假日**：景点官网公告时机不固定，靠人工拉取容易漏。建议通用节假日清单 + 官网年初公告 + 用户反馈三层兜底。
- **个人账户层面的状态**：爽约黑名单、取消提前期要求、家庭配额——这些**对外完全不可见**，只能靠用户自己记录或提交日志反推。
- **新景点 / 新合作的发现**：靠定期（每月/每季）重抓主索引页对比上次结果，发现新增就触发人工补录或 AI 提取。
- **季节性规则的过期**：藏在描述文字里的"From June 1–August 31, 2025 ..."这种规则，定期重抓就会刷新；但识别"哪些规则现在生效"需要解析时附带日期判断。

---

> **本文件随讨论持续更新**。新的发现、决策、放弃理由、数据源变化都会追加进相应章节。
