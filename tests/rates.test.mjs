import {test} from 'node:test';
import assert from 'node:assert/strict';
import {displayRate, estimate, freshness} from '../web/rates.mjs';

test('selected term controls sorting and interest, not representative rate', () => {
  const item = {type: 'deposit', base: 3, max: 4, save_trm: 12, options: [
    {save_trm: 6, intr_rate: 1, intr_rate2: 2, intr_type: '단리'},
    {save_trm: 12, intr_rate: 3, intr_rate2: 4, intr_type: '단리'}]};
  assert.equal(displayRate(item, '6', false), 2);
  assert.equal(estimate(item, {amount: 1000000, term: '6'}).interest, 10000);
});
test('unverified parking tiers must not apply advertised maximum to all money', () => {
  assert.equal(estimate({type: 'parking', max: 7, rate_model: 'unverified_tiers'}, {amount: 10000000}), null);
});
test('verified marginal tiers apply each rate only to its balance segment', () => {
  const item = {type: 'parking', rate_model: 'verified_tiers', rate_tiers: [
    {from: 0, to: 1000000, base: 5, max: 5}, {from: 1000000, to: null, base: 1, max: 1}]};
  assert.equal(estimate(item, {amount: 10000000, days: 365}).interest, 140000);
  item.rate_tiers[1].from = 2000000;
  assert.equal(estimate(item, {amount: 10000000}), null);
});
test('CMA uses chosen days instead of defaulting to 12-month deposit', () => {
  const item = {type: 'cma', rate_model: 'flat', rate_tiers: [{from: 0, to: null, base: 2, max: 2}]};
  assert.equal(estimate(item, {amount: 3650000, days: 30}).interest, 6000);
});
test('bank parking accounts cannot accrue estimates above their verified deposit limit', () => {
  const item = {type: 'parking', rate_model: 'flat', rate_tiers: [{from: 0, to: 100000000, base: 1.2, max: 1.2}]};
  assert.equal(estimate(item, {amount: 100000000, days: 365}).interest, 1200000);
  assert.equal(estimate(item, {amount: 100000001, days: 365}), null);
});
test('savings considers staggered monthly contributions', () => {
  const item = {type: 'savings', save_trm: 12, base: 3, max: 3, intr_type: '단리'};
  assert.equal(estimate(item, {amount: 100000}).interest, 19500);
});
test('unknown compound and free-installment cash flows are not estimated', () => {
  assert.equal(estimate({type: 'deposit', save_trm: 12, max: 3, intr_type: '복리'}, {amount: 100000}), null);
  const item = {type: 'savings', options: [{save_trm: 12, intr_rate: 3, intr_rate2: 3, intr_type: '단리', rsrv_type: '자유적립식'}]};
  assert.equal(estimate(item, {amount: 100000, index: 0}), null);
});
test('old values and failed checks cannot be labeled fresh', () => {
  assert.equal(freshness({}), '미확인');
  assert.equal(freshness({last_checked_at: '2026-11-01', verification_status: 'verified'}, new Date('2026-11-08')), '확인 지연');
  assert.equal(freshness({last_checked_at: '2026-11-08', verification_status: 'stale'}, new Date('2026-11-08')), '확인 지연');
});
