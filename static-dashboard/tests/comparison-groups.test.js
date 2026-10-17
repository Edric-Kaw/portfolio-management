import test from 'node:test';
import assert from 'node:assert/strict';
import {groupComparisons} from '../src/comparison-groups.js';
test('Type summaries aggregate account balances before calculating percent changes',()=>{
  const rows=[{Type:'Cash',current:120,previous:100},{Type:'Cash',current:80,previous:50},{Type:'Investment',current:50,previous:0}];
  const groups=groupComparisons(rows),cash=groups.find(g=>g.type==='Cash');
  assert.equal(cash.current,200);assert.equal(cash.previous,150);assert.equal(cash.change,50);assert.equal(cash.pct,50/150*100);assert.equal(cash.accounts.length,2);
  assert.equal(groups.find(g=>g.type==='Investment').pct,null);
  assert.equal(groups.reduce((s,g)=>s+g.change,0),100);
});
