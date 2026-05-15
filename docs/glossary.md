# Glossary · 中英术语对照词典

> 本项目对话/spec/注释用**中英混杂**;最终产品 UI 用**全英文**(北美用户语言习惯)。
>
> 这份词典记录所有出现过的术语,**英文一列就是 UI 里实际会出现的措辞**。后续审查 UI 文案时以本表为准。
> 新术语随脑暴持续追加。每条:中文 / English / 中文解释。

---

## 1. 产品 & 品牌

| 中文 | English | 中文解释 |
|---|---|---|
| 产品名 | **MuseumPapa** | 服务范围是 Massachusetts 全境;Logo / 浏览器标题 / 顶部 brand 用此名。原名 MuseumPass MA 已弃用(2026-05-16) |
| 项目代号(内部) | North Shore Library Benefits | 仓库名 / 内部文档名仍沿用;不出现在 UI |
| 折扣指南 | Discount guide / Pass finder | 产品定位描述,不是 UI 文案 |

---

## 2. 核心实体

| 中文 | English | 中文解释 |
|---|---|---|
| 景点 | **Attraction** | 博物馆/水族馆/动物园/历史古宅/州立公园等;数据中称为 attraction(108 个) |
| 图书馆 | **Library** | 公共图书馆,作为 pass 发放方;数据中 59 家 |
| 网络 | **Network** | 图书馆联盟(NOBLE / MVLC / Minuteman / OCLN / CW MARS / BPL 等);跨网借阅 |
| 平台 | **Platform** | 图书馆 pass 系统的后台(Assabet / LibCal / MuseumKey) |
| 镇 | **Town** | 图书馆/景点所在的 MA 行政镇;UI 默认用 town 命名图书馆,如 "Wakefield" |
| 正式馆名 | **Library full name** | 如 "Lucius Beebe Memorial Library";详情页等大空间处展示 |

---

## 3. Pass 类型(三档,权威定义)

| 中文 | English | 中文解释 |
|---|---|---|
| 电子券 | **E-pass** (UI 显示) / Digital pass (内部) | 在线领取的 coupon,链接发邮箱或浏览器内出示;**距离成本 = 0**。UI 弃用 "Online" (2026-05-16:不够地道) |
| 纸质 | **Pickup** | 用户必须去对应图书馆 pickup 拿到实体凭证;**单程距离成本** |
| 取还 | **Pickup & Return** | 去图书馆 pickup,使用后还要 return;**双程距离成本** |

> Internal pass_type enum:`digital` / `physical-coupon` / `loan-card`(数据字段名保留 backup 命名)

---

## 4. 折扣 & 价格

| 中文 | English | 中文解释 |
|---|---|---|
| 原价 / 划线价 | **Original price** / Regular admission | 景点官网公开的成人门票标价;UI 划线展示 |
| 折后价 | **Your price** / Final price | 用 pass 后实际付的价格 |
| 折扣力度 | **Discount tier** | 三档由强到弱:Free / Half-price / $N off |
| 免费 | **Free** | UI tag 直接显示 "Free" |
| 半价 | **Half-price** | 50% off;UI 显示 "50% off" 或 "Half-price" |
| $N 减免 | **$N off** | 固定金额减免,如 "$5 off" |
| 库存 | **Availability** | 某 (景点 × 馆 × 日期) 有没有票 |
| 库存日历 | **Availability calendar** | 30 天可订状态网格,详情页用 |
| 当日满 | **Sold out today** | tag 状态 |
| 无折扣可用 | **No passes available** | 卡片下方空 slot 文案 |

---

## 5. 用户 & 账户

| 中文 | English | 中文解释 |
|---|---|---|
| 用户 | **User** | 已登录账户的人 |
| 游客 | **Guest** | 未登录访问者;ZIP/卡包只存浏览器 localStorage,关浏览器丢 |
| 账户 | **Account** | v1 是 mock auth,3 个硬编码账号(alex/rbt/admin) |
| 登录 | **Sign in** | UI 用 "Sign in"(北美主流,优于 "Login") |
| 注册 | **Sign up** | v1 暂不开放;按钮 disabled |
| 退出登录 | **Sign out** | |
| 卡包 | **My passes** / **Library cards** | 用户持有的图书馆卡集合;UI 用 "My passes" |
| 卡号 | **Barcode** | 图书馆卡背面条码数字;预约时填入 |
| 姓 | **Last name** | 部分图书馆预约要求姓氏校验 |
| PIN | **PIN** | 部分图书馆要求的 4 位数字 |
| 邮编 | **ZIP code** | 5 位数,用来算距离;访客可临时填,登录后存账户 |
| 收藏 | **Favorite** | ❤️ 标记的景点,列表内置顶 |
| 收藏夹 | **Favorites** | 收藏景点集合 |

---

## 6. 导航 & 页面

| 中文 | English | 中文解释 |
|---|---|---|
| 列表页 | **Attractions list** / Home | 首页,展示全部 108 景点;时间维度=单日 |
| 详情页 | **Attraction detail** | 钉死一个景点,展示 30 天日历 + 全部 pass 选项;时间维度=多日 |
| 卡包设置页 | **My passes settings** | 配置持卡 + barcode/姓氏/PIN + ZIP |
| 顶部栏 | **Top bar** / Header | 含 logo、搜索框、用户菜单 |
| 通知栏 | **Banner** | 顶部条幅,游客/admin 引导添加 pass |
| 筛选栏 | **Filter bar** | 顶部下方;含日期/排序/搜索 |
| 用户菜单 | **User menu** | 右上角头像下拉(My passes / Sign out) |

---

## 7. 列表 & 卡片

| 中文 | English | 中文解释 |
|---|---|---|
| 景点卡片 | **Attraction card** | 列表页一行 |
| 卡片 header | **Card header** | 缩略图 + 名称 + 城镇 + 介绍 + 原价 |
| 标签 | **Tag** | 卡片底部的 pass 选项,3 种颜色对应 3 类 |
| 查询日期 | **Search date** | 列表页顶部单日选择,默认 today |
| 查询窗口 | **Date range** | 详情页用,默认 30 天 |
| 排序 | **Sort by** | UI 选项:Favorites first (default) / A–Z / Distance / Discount |
| 距离 | **Distance** | 单位 miles (UI 显示 `5 mi`);算法:用户 ZIP centroid → 景点/馆地址直线距离(haversine) |

---

## 8. 状态文案 / 关键 UI 文案

| 中文 | English | 中文解释 |
|---|---|---|
| 今天 | **Today** | 日期 picker 默认 |
| 即将开放 | **Opens soon** | 库存日历状态 |
| 已售罄 | **Booked / Sold out** | 库存状态 |
| 未知 | **Unknown** | scraper 失败时,避免误判为"满" |
| 登录后可见 | **Sign in to view X discount options** | 游客/admin 卡片底部小字 |
| 添加你的 library pass | **Add your library pass to unlock discounts →** | 顶部 banner 文案(游客/admin) |
| 当日没 coupon | **No coupons available today** | 卡片底部弱化提示 |
| 当日不营业 | **Closed today** | 卡片角标 + 整卡置灰 |
| 价格行 | **$30 adult · $25 kids** | 景点 header 原价(2026-05-16 弃用 "Adult $30 Child $25" 误读形式) |
| 详情页 section 标题 | **Available coupons** | 替代 "Discount options"(2026-05-16) |
| 详情页 per-date 计数 | **N coupons available** | 替代 "N options"(2026-05-16) |
| 预约弹窗 header | **GET PASS FROM** + Library Name | 替代 "Reserve at"(2026-05-16:NA museum pass 程序的标准动词) |
| 预约弹窗主 CTA | **Go to library website →** | 跳转 source_url 新标签页 |
| 预约弹窗 credential 框 | **Card number** / **PIN** | 库卡卡号 / 4 位数 PIN(选填) |
| Copy 按钮 | **COPY** / **COPIED ✓** | UI 全大写惯例 |
| favorite 按钮 aria | **Add to favorites** / **Remove from favorites** | 心形 toggle |
| Book 按钮 | **Book** | option 行右侧 CTA |

---

## 9. 数据/系统术语(internal,UI 不暴露)

| 中文 | English | 中文解释 |
|---|---|---|
| 抓取 | Scrape / Crawl | 数据采集 |
| 规范化 | Normalize | benefit_text → 结构化档位 |
| 快照 | Snapshot | 主索引页历史副本,供 diff |
| 差异 | Diff | 索引页变更检测 |
| 办卡资格 | Eligibility / Card policy | open_ma_resident / residents_only / network_only |
| 持卡 | Cardholder | UI 不直说,通过"my passes"含蓄表达 |
