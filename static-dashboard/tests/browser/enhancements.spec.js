import {test,expect} from '@playwright/test';
import * as XLSX from 'xlsx';
import {demoSource} from '../../src/demo.js';
test('trend changes, expandable Type totals, and pinned account ledger controls',async({page})=>{
  await page.setViewportSize({width:1242,height:668});
  const source=demoSource();source.sheets.Asset=source.sheets.Asset.flatMap(r=>[r,{...r,Account:`Additional synthetic account with a long display name / ${r.Account}`}]);
  const wb=XLSX.utils.book_new();for(const [name,rows]of Object.entries(source.sheets))XLSX.utils.book_append_sheet(wb,XLSX.utils.json_to_sheet(rows),name);
  await page.goto('./');await page.locator('#file').setInputFiles({name:'synthetic-enhancements.xlsx',mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer:XLSX.write(wb,{type:'buffer',bookType:'xlsx'})});await page.getByRole('button',{name:'Activate dataset'}).click();
  await page.locator('[data-view="growth"]').click();await page.locator('#trend-dimension').selectOption('Type');
  const traces=await page.locator('#trend').evaluate(e=>e.data.map(t=>({y:t.y,customdata:t.customdata,template:t.hovertemplate})));
  for(const trace of traces){expect(trace.customdata[0][0]).toBe('First recorded snapshot');expect(trace.customdata[1][1]).toBe('2025-12-31');const change=(trace.y[1]-trace.y[0])/trace.y[0]*100;expect(trace.customdata[1][0]).toBe(`${change>=0?'+':''}${change.toFixed(2)}%`);expect(trace.template).toContain('Change vs previous');}
  const comparison=page.locator('#comparison-table');await expect(comparison.locator('.comparison-type-summary')).toHaveCount(3);await expect(comparison.locator('.comparison-account:visible')).toHaveCount(0);
  const expand=comparison.getByRole('button',{name:'Expand Cash account changes'});await expand.click();await expect(comparison.locator('.comparison-account:visible')).toHaveCount(6);await expect(comparison.getByRole('button',{name:'Collapse Cash account changes'})).toHaveAttribute('aria-expanded','true');await comparison.getByRole('button',{name:'Collapse Cash account changes'}).click();await expect(comparison.locator('.comparison-account:visible')).toHaveCount(0);
  await page.locator('[data-view="ledger"]').click();const ledger=page.locator('#ledger');await ledger.scrollIntoViewIfNeeded();const before=await ledger.locator('thead').boundingBox();await ledger.evaluate(e=>{e.scrollTop=150;e.querySelector('.comparison-horizontal-scroll').scrollLeft=120;});await page.waitForTimeout(100);
  const scroll=await ledger.evaluate(e=>({top:e.scrollTop,left:e.scrollLeft,bar:e.querySelector('.comparison-horizontal-scroll').scrollLeft,header:e.querySelector('thead').getBoundingClientRect().top}));expect(scroll.top).toBeGreaterThan(0);expect(scroll.left).toBe(120);expect(scroll.bar).toBe(120);expect(Math.abs(scroll.header-before.y)).toBeLessThan(2);
  await page.locator('#reset').click();await expect(ledger).toBeEmpty();
});
