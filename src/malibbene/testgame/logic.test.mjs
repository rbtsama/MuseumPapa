import { test } from 'node:test';
import assert from 'node:assert/strict';
import { passState, usableCardsForPass, bestState } from './logic.mjs';

const open = { library_id: 'acton', attraction_slug: 'x', network: 'Minuteman', library_name: 'Acton', library_town: 'Acton', residency: 'no', summary: '50% off' };
const ro = { library_id: 'lexington', attraction_slug: 'blithewold', network: 'Minuteman', library_name: 'Cary Memorial Library', library_town: 'Lexington', residency: 'yes', summary: '50% off' };
const unk = { library_id: 'quincy', attraction_slug: 'y', network: 'OCLN', library_name: 'Quincy', library_town: 'Quincy', residency: 'unknown', summary: null };
const card = (id, network) => ({ id, network });

test('开放 pass：持同联盟任一卡 -> 完全符合', () => {
  assert.equal(passState(open, [card('belmont', 'Minuteman')], 'Salem'), 1);
});
test('开放 pass：只有跨联盟卡 -> 缺卡', () => {
  assert.equal(passState(open, [card('lynn', 'NOBLE')], 'Salem'), 2);
});
test('开放 pass：无卡 -> 缺卡（无居民限制，不出现 3/4）', () => {
  assert.equal(passState(open, [], 'Acton'), 2);
});
test('unknown 按开放处理：持同联盟卡 -> 完全符合', () => {
  assert.equal(passState(unk, [card('quincy', 'OCLN')], 'Salem'), 1);
});

// 用户的原始问题：Blithewold + 持 Acton(同 Minuteman)卡 + Lexington 居民
test('Blithewold：持 Acton 卡 + Lexington 居民 -> 缺卡（需本馆 Lexington 卡，同联盟无效）', () => {
  assert.equal(passState(ro, [card('acton', 'Minuteman')], 'Lexington'), 2);
  assert.equal(usableCardsForPass(ro, [card('acton', 'Minuteman')]).length, 0);
});
test('Blithewold：持 Lexington 本馆卡 + Lexington 居民 -> 完全符合', () => {
  assert.equal(passState(ro, [card('lexington', 'Minuteman')], 'Lexington'), 1);
});
test('Blithewold：持 Lexington 卡 + 非居民 -> 仅限居民', () => {
  assert.equal(passState(ro, [card('lexington', 'Minuteman')], 'Salem'), 3);
});
test('Blithewold：无卡 + 非居民 -> 都不符合', () => {
  assert.equal(passState(ro, [], 'Salem'), 4);
});
test('usableCardsForPass：开放 pass 取同联盟所有持卡', () => {
  const u = usableCardsForPass(open, [card('belmont', 'Minuteman'), card('lexington', 'Minuteman'), card('lynn', 'NOBLE')]);
  assert.equal(u.length, 2);
});
test('bestState 取最小，空为 5', () => {
  assert.equal(bestState([3, 1, 4]), 1);
  assert.equal(bestState([]), 5);
  assert.equal(bestState([2, 4]), 2);
});
