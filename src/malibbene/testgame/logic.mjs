// 纯决策逻辑：无 DOM 依赖。构建时会被剥掉 `export` 内联进 HTML。
//
// 卡覆盖规则（来自真实 booking-probe 数据）：
//   开放 pass（residency 非 'yes'，即 no / unknown）：探测证明"同联盟非本镇的卡被接受"
//     → 持有【同联盟任一馆】的卡即可覆盖；且无居民限制。
//   仅限居民 pass（residency === 'yes'，scope=town）：探测证明"连同联盟的卡都被拦"
//     → 只认【发证馆本馆】的卡，且需本镇居民。

// 能用于这条 pass 的、用户持有的卡。heldCards: [{id, network, ...}]
export function usableCardsForPass(pass, heldCards) {
  if (pass.residency !== 'yes') return heldCards.filter((c) => c.network === pass.network);
  return heldCards.filter((c) => c.id === pass.library_id);
}

// 单条 pass 的状态：
//   1 = 完全符合   2 = 缺卡   3 = 仅限居民（有卡但非居民）   4 = 都不符合
export function passState(pass, heldCards, homeTown) {
  const usable = usableCardsForPass(pass, heldCards).length > 0;
  if (pass.residency !== 'yes') return usable ? 1 : 2; // 开放：无居民限制，只看卡
  const resident = homeTown === pass.library_town;
  if (usable && resident) return 1;
  if (!usable && resident) return 2;
  if (usable && !resident) return 3;
  return 4;
}

// 景点整体状态 = 名下所有 pass 里"最好"（最小）的那个；无 pass 返回 5。
// 排序语义：1(完全符合) < 2(缺卡) < 3(仅限居民) < 4(都不符合) < 5(无 pass)。
export function bestState(states) {
  return states.reduce((min, s) => Math.min(min, s), 5);
}
