import {test} from 'node:test';
import assert from 'node:assert/strict';
import {applicationState} from '../web/support-state.mjs';
const now=new Date('2026-11-08T20:00:00+09:00');
const base={last_checked_at:'2026-11-08T19:00:00+09:00',verification_status:'collected',application_start:'2026-11-01T09:00+09:00',application_end:'2026-11-30T18:00+09:00'};
test('explicit early close overrides a future deadline',()=>assert.equal(applicationState({...base,source_state:'마감'},now).key,'closed'));
test('old collection cannot claim an open application',()=>assert.equal(applicationState({...base,last_checked_at:'2026-11-01T19:00+09:00'},now).key,'unknown'));
test('future, current and expired complete periods are distinct',()=>{
 assert.equal(applicationState(base,now).key,'open');
 assert.equal(applicationState({...base,application_start:'2026-11-10T09:00+09:00'},now).key,'upcoming');
 assert.equal(applicationState({...base,application_end:'2026-11-07T18:00+09:00'},now).key,'closed');
});
test('a posted date or benefit amount never establishes an application window',()=>assert.equal(applicationState({last_checked_at:base.last_checked_at,published_on:'2026-11-01',support_text:'최대 100만원'},now).key,'unknown'));
test('explicit stale item is not advertised as currently open',()=>assert.equal(applicationState({...base,verification_status:'stale'},now).key,'unknown'));
test('source open label is attributed rather than eligibility being promised',()=>{
 const result=applicationState({last_checked_at:base.last_checked_at,source_state:'모집중'},now);
 assert.equal(result.key,'open');assert.match(result.label,/원문/);
});
