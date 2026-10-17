import test from 'node:test';
import assert from 'node:assert/strict';
import {auditValue,selectAuditRows} from '../src/audit-table.js';
test('audit values distinguish zero, blank, missing context and calculated MYR amounts',()=>{
  assert.equal(auditValue({value:0}),'0');
  assert.equal(auditValue({value:null}),'(blank)');
  assert.equal(auditValue({}),'—');
  assert.equal(auditValue({value:123.45,unit:'MYR'}),'123.45 MYR');
  assert.equal(auditValue({value:64726.479999999996,unit:'MYR'}),'64,726.48 MYR');
  assert.equal(auditValue({value:'<script>test</script>'}),'<script>test</script>');
});
test('audit filters combine over all entries and numeric sorts preserve numeric order',()=>{
  const rows=Array.from({length:600},(_,i)=>({sheet:'Asset',row:i+2,level:'warning',code:'FORMULA_CACHE',value:i,message:'Balance uses a cached result'}));
  assert.equal(selectAuditRows(rows,{row:'601',value:'599'},null).length,1);
  assert.equal(selectAuditRows(rows,{sheet:'reference'},null).length,0);
  const selected=selectAuditRows([rows[10],rows[2],rows[0]],{}, {key:'value',direction:'ascending'});
  assert.deepEqual(selected.map(r=>r.value),[0,2,10]);
  assert.deepEqual(selectAuditRows(selected,{}, {key:'row',direction:'descending'}).map(r=>r.row),[12,4,2]);
  assert.equal(rows[0].value,0);
});
