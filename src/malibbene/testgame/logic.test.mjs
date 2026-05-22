import { test } from 'node:test';
import assert from 'node:assert/strict';
import { classifyAttraction } from './logic.mjs';

// 真实抽样的最小子集
const DATA = {
  passes: [
    { library_id:'lexington', attraction_slug:'blithewold', network:'Minuteman', library_name:'Cary Memorial Library', library_town:'Lexington', residency:'yes', scope:'town', summary:'50% off' },
    { library_id:'lynn', attraction_slug:'isabella-stewart-gardner-museum', network:'NOBLE', library_name:'Lynn Public Library', library_town:'Lynn', residency:'yes', scope:'town', summary:'$10/person' },
    { library_id:'lynnfield', attraction_slug:'isabella-stewart-gardner-museum', network:'NOBLE', library_name:'Lynnfield Public Library', library_town:'Lynnfield', residency:'no', scope:null, summary:'FREE' },
  ],
};

test('state 1: 持卡且居民 -> 完全符合', () => {
  const r = classifyAttraction('blithewold', DATA, ['lexington'], 'Lexington');
  assert.equal(r.state, 1);
  assert.deepEqual(r.tags, []);
  assert.equal(r.usableCards.length, 1);
  assert.equal(r.usableCards[0].library_id, 'lexington');
});

test('state 3: 持卡但非居民 -> Resident Only', () => {
  const r = classifyAttraction('blithewold', DATA, ['lexington'], 'Salem');
  assert.equal(r.state, 3);
  assert.deepEqual(r.tags, ['resident_only']);
  assert.deepEqual(r.residentOnlyTowns, ['Lexington']);
  assert.equal(r.usableCards.length, 1);
});

test('state 2: 居民但无卡 -> Library Pass Needed', () => {
  const r = classifyAttraction('blithewold', DATA, [], 'Lexington');
  assert.equal(r.state, 2);
  assert.deepEqual(r.tags, ['library_pass_needed']);
  assert.equal(r.recommendCards.some(c => c.library_id === 'lexington'), true);
});

test('state 4: 无卡且非居民（全 resident-only 景点）-> 双警告', () => {
  const r = classifyAttraction('blithewold', DATA, [], 'Salem');
  assert.equal(r.state, 4);
  assert.deepEqual(r.tags, ['resident_only', 'library_pass_needed']);
});

test('state 2: 无卡但有 open pass 兜底 -> 仅缺卡', () => {
  const r = classifyAttraction('isabella-stewart-gardner-museum', DATA, [], 'Salem');
  assert.equal(r.state, 2);
  assert.equal(r.recommendCards.some(c => c.library_id === 'lynnfield'), true);
});

test('state 1: open 馆持卡直接可用', () => {
  const r = classifyAttraction('isabella-stewart-gardner-museum', DATA, ['lynnfield'], 'Salem');
  assert.equal(r.state, 1);
});

test('state 3: 持 resident-only 卡且非居民，open 馆未持有', () => {
  const r = classifyAttraction('isabella-stewart-gardner-museum', DATA, ['lynn'], 'Salem');
  assert.equal(r.state, 3);
  assert.deepEqual(r.residentOnlyTowns, ['Lynn']);
});

test('edge: empty passes -> state 4 with empty card lists', () => {
  const r = classifyAttraction('blithewold', { passes: [] }, [], 'Lexington');
  assert.equal(r.state, 4);
  assert.equal(r.offeringCards.length, 0);
  assert.equal(r.residentOnlyTowns.length, 0);
});

test('edge: duplicate library_id rows dedupe in card lists', () => {
  const dup = { passes: [
    { library_id:'lynnfield', attraction_slug:'museum-of-science', network:'NOBLE', library_name:'Lynnfield Public Library', library_town:'Lynnfield', residency:'no', scope:null, summary:'50% off' },
    { library_id:'lynnfield', attraction_slug:'museum-of-science', network:'NOBLE', library_name:'Lynnfield Public Library', library_town:'Lynnfield', residency:'no', scope:null, summary:'FREE' },
  ]};
  const r = classifyAttraction('museum-of-science', dup, ['lynnfield'], 'Salem');
  assert.equal(r.state, 1);
  assert.equal(r.usableCards.length, 1);
  assert.equal(r.offeringCards.length, 1);
});
