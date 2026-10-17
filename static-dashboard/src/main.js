import './styles.css';
import {renderComparisonGroups} from './comparison-groups.js';
let ledgerCleanup=()=>{};
import {setupComparisonScroll} from './comparison-scroll.js';
let comparisonCleanup=()=>{};
import {createAuditTable} from './audit-table.js';
import {normalize,calculate,metrics,FILTERS,group,history,comparison,percentageChange,csv,calendarDate} from './asset-analysis.js';
import {importWorkbook} from './importer.js';
import {demoSource} from './demo.js';
import {overviewCharts,growthCharts,liquidityCharts,purgeAll} from './charts.js';
const $=id=>document.getElementById(id);
const money=new Intl.NumberFormat('en-MY',{minimumFractionDigits:2,maximumFractionDigits:2});
const fmt=n=>n==null||!Number.isFinite(n)?'N/A':money.format(n);
const percent=n=>n==null||!Number.isFinite(n)?'N/A':`${n.toFixed(2)}%`;
const dateLabel=d=>new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(d+'T00:00:00Z'));
let model=null,calculated=null,filters={},view='overview',page=0,filename='',isDemo=false,pending=null,importGeneration=0,currentMetrics=null;
function el(tag,text,className){const node=document.createElement(tag);if(text!=null)node.textContent=text;if(className)node.className=className;return node;}
function visible(id,on){$(id).classList.toggle('hidden',!on);}
function notice(text,kind=''){const node=el('div',text,`notice ${kind}`);return node;}
function status(text,kind=''){ $('status').replaceChildren(...(text?[notice(text,kind)]:[])); }
function table(target,columns,rows){
  const container=$(target);container.replaceChildren();
  if(!rows.length){container.append(el('p','No records for this selection.'));return;}
  const t=el('table'),head=el('thead'),hr=el('tr');
  for(const c of columns){const th=el('th',c.title);th.scope='col';hr.append(th);}head.append(hr);t.append(head);
  const body=el('tbody');
  for(const row of rows){const tr=el('tr');for(const c of columns){const val=c.value(row);const td=el('td',val,c.number?'number':c.wrap?'wrap':'');tr.append(td);}body.append(tr);}t.append(body);container.append(t);
}
function showDialog(title,text){$('dialog-content').replaceChildren(el('h2',title),...text.map(p=>el('p',p)));$('dialog').showModal();}
$('close-dialog').onclick=()=>$('dialog').close();
$('privacy').onclick=()=>showDialog('Your data stays with you.',['Workbook contents, filenames, records and results stay in browser memory. The application does not upload them or store datasets in cookies or browser storage.','GitHub Pages serves the application files. Libraries, fonts and charts run locally; there are no analytics or remote financial services. Reloading or Reset Data clears the active dataset.','CSV downloads are generated locally only when you request them. Keep those downloaded files secure.']);
document.querySelectorAll('[data-module]').forEach(button=>button.onclick=()=>showDialog(`${button.dataset.module} analysis is coming next.`,['This is the Asset-first release agreed in the migration scope. Trade and Expense will become available after their calculation and privacy checks pass.','The current Python dashboard remains unchanged.']));
function preview(source,name,demo=false){
  const candidate=normalize(source);pending={model:candidate,name,demo};
  const panel=$('import-preview');panel.replaceChildren(el('div','REVIEW BEFORE ACTIVATING','eyebrow'),el('h2',demo?'Explore the synthetic portfolio':name));
  panel.append(el('p',`${source.sheets.Asset.length.toLocaleString()} Asset rows read · ${candidate.rows.length.toLocaleString()} usable before FX correction · ${source.sheets.Reference?.length??0} Reference rows · ${candidate.issues.length} validation notices.`));
  const detected=source.sheetNames??Object.keys(source.sheets);panel.append(el('p',`Detected sheets: ${detected.join(', ')}. Only Asset and Reference are processed in this release.`));
  panel.append(el('p','Activating replaces the current dataset. Formula caches may be stale; no formulas, macros or links are executed.'));
  const controls=el('div',null,'preview-actions'),activate=el('button','Activate dataset','primary'),cancel=el('button','Cancel','secondary');
  activate.onclick=()=>{const ready=pending;ledgerCleanup();ledgerCleanup=()=>{};comparisonCleanup();comparisonCleanup=()=>{};$('comparison-table')?.replaceChildren();$('comparison-legend')?.replaceChildren();auditTable=null;pending=null;visible('import-preview',false);model=ready.model;filename=ready.name;isDemo=ready.demo;$('correction').checked=true;calculated=calculate(model,true);$('snapshot').replaceChildren(...calculated.dates.toReversed().map(d=>{const o=el('option',`${dateLabel(d)}${d===calculated.dates.at(-1)?' · Latest':''}`);o.value=d;return o;}));buildFilters();$('search').value='';page=0;view='overview';status('');visible('welcome',false);for(const id of ['dashboard','filters','source','reset','snapshot-control'])visible(id,true);visible('demo-banner',isDemo);$('source').replaceChildren(el('strong',filename),el('span',`${model.rows.length.toLocaleString()} usable source rows · memory only`));render();};
  cancel.onclick=()=>{pending=null;visible('import-preview',false);};controls.append(activate,cancel);panel.append(controls);visible('import-preview',true);
}
function demo(){++importGeneration;status('');preview(demoSource(),'Synthetic portfolio · demo',true);}
$('demo').onclick=demo;$('demo-main').onclick=demo;
$('file').addEventListener('change',async event=>{const file=event.target.files[0];if(!file)return;const generation=++importGeneration;status('Reading workbook locally…');$('file').disabled=true;pending=null;visible('import-preview',false);try{await new Promise(resolve=>setTimeout(resolve,30));const source=await importWorkbook(file);if(generation!==importGeneration)return;preview(source,file.name);status('Workbook read. Review the preview before activating it.');}catch(error){if(generation===importGeneration)status(`${error.message} ${model?'Your previous dataset is still active.':''}`,'error');}finally{$('file').disabled=false;event.target.value='';}});
function buildFilters(){
  const rows=calculated.rows.filter(r=>r.date===$('snapshot').value);filters={};const target=$('filter-fields');target.replaceChildren();
  for(const key of FILTERS){const options=[...new Set(rows.map(r=>r[key]))].sort();filters[key]=[...options];const details=el('details',null,'filter-group');details.open=key==='Type';const summary=el('summary',`${key==='CashLiquidity'?'Liquidity rating':key} · ${options.length}`);const actions=el('div',null,'filter-actions');for(const [label,checked] of [['All',true],['None',false]]){const button=el('button',label);button.type='button';button.onclick=()=>{details.querySelectorAll('input').forEach(c=>c.checked=checked);filters[key]=checked?[...options]:[];page=0;render();};actions.append(button);}const list=el('div',null,'filter-options');for(const value of options){const label=el('label');const input=el('input');input.type='checkbox';input.checked=true;input.value=value;input.onchange=()=>{filters[key]=[...list.querySelectorAll('input:checked')].map(c=>c.value);page=0;render();};label.append(input,el('span',value));list.append(label);}details.append(summary,actions,list);target.append(details);}
}
$('snapshot').onchange=()=>{buildFilters();page=0;render();};$('clear-filters').onclick=()=>{buildFilters();page=0;render();};$('correction').onchange=()=>{if(!model)return;calculated=calculate(model,$('correction').checked);buildFilters();page=0;render();};
document.querySelectorAll('[data-view]').forEach(button=>button.onclick=()=>{view=button.dataset.view;render();});
function metric(title,value,unit,description,positive=false){const card=el('article',null,'metric');card.append(el('div',title,'metric-title'));const val=el('div',value,'metric-value');if(unit)val.append(el('small',unit));card.append(val,el('div',description,`metric-description ${positive?'positive':''}`));return card;}
function render(){
  if(!calculated)return;
  const m=metrics(calculated,$('snapshot').value,filters);currentMetrics=m;
  const delta=m.previous?`${m.change>=0?'+':''}${fmt(m.change)} MYR · ${m.changePercent==null?'No positive baseline':percent(m.changePercent)} vs ${dateLabel(m.previous)}`:'First recorded snapshot';
  const usd=m.selected.filter(r=>r.Currency==='USD').reduce((s,r)=>s+r.Balance,0);
  $('metrics').replaceChildren(metric('Total portfolio assets',fmt(m.total),'MYR',delta,m.change>=0),metric('USD exposure',fmt(usd),'USD','Original-currency balance'),metric('Weighted yield',percent(m.yield==null?null:m.yield*100),'','On interest-bearing capital'),metric('Liquid capital',percent(m.liquidity),'',`${fmt(m.liquid)} MYR · Very High + High`));
  $('issue-count').textContent=calculated.issues.length;
  $('quality-banner').replaceChildren();
  const excluded=calculated.issues.filter(i=>i.level==='excluded').length,corrected=calculated.issues.filter(i=>i.code==='FX_CORRECTION').length;
  if(excluded||corrected||calculated.issues.length){const banner=notice(`${corrected} FX corrections · ${excluded} exclusion notices · ${calculated.issues.length} total audit entries. Review Data quality for source rows and rates.`,excluded?'warning':'');$('quality-banner').append(banner);}
  if(!m.selected.length)$('quality-banner').append(notice('No usable assets match this snapshot and filter selection. Adjust your filters or inspect the audit.','warning'));
  document.querySelectorAll('[data-view]').forEach(b=>{const selected=b.dataset.view===view;b.classList.toggle('selected',selected);b.setAttribute('aria-pressed',String(selected));});document.querySelectorAll('.view').forEach(v=>v.classList.toggle('hidden',v.id!==`view-${view}`));
  if(view==='overview'){overviewCharts(m);renderInsights(m);}
  if(view==='growth'){renderGrowth(m);growthCharts(calculated,filters,m);}
  if(view==='liquidity'){liquidityCharts(m);renderYield(m);}
  if(view==='ledger')renderLedger(m);
  if(view==='quality')renderQuality();
}
function renderInsights(m){const target=$('insights');target.replaceChildren();const cats=group(m.selected,'Category'),cur=group(m.selected,'Currency');const data=[['Largest allocation',cats.length?`${cats[0].name} holds MYR ${fmt(cats[0].value)}${m.total>0?` (${percent(cats[0].value/m.total*100)} of the selected total)`:''}.`:'No selected assets.'],['Accessible capital',`MYR ${fmt(m.liquid)} is rated Very High or High liquidity. Review maturity dates before planning withdrawals.`],['Currency perspective',`${cur.length} currencies represented. Exposure is reported in MYR using source conversions and optional audited corrections.`]];data.forEach(([title,body],i)=>{const item=el('div',null,'insight');const content=el('div');content.append(el('strong',title),el('p',body));item.append(el('span',`0${i+1}`,'insight-index'),content);target.append(item);});}
function renderGrowth(m){
  $('ytd-summary').replaceChildren();if(m.ytdDate){const delta=m.total-m.ytdTotal,pct=percentageChange(m.total,m.ytdTotal);$('ytd-summary').append(el('div',`${delta>=0?'+':''}${fmt(delta)} MYR`,`summary-value ${delta>=0?'positive':'negative'}`),el('p',`${percent(pct)} · Baseline ${dateLabel(m.ytdDate)}${m.ytdDate.endsWith('-12-31')?'':' (latest available before year-end)'}. Same filters apply to both snapshots.`));}else $('ytd-summary').append(el('p','Add a prior-year snapshot to enable this comparison.'));
  const points=history(calculated,filters).map((p,i,all)=>({...p,change:i?p.total-all[i-1].total:null,pct:i?percentageChange(p.total,all[i-1].total):null}));
  table('history-table',[{title:'Reporting date',value:r=>dateLabel(r.date)},{title:'Accounts',value:r=>r.rows.length,number:true},{title:'Portfolio (MYR)',value:r=>fmt(r.total),number:true},{title:'Change (MYR)',value:r=>fmt(r.change),number:true},{title:'Change (%)',value:r=>percent(r.pct),number:true}],points);
  if(!$('comparison-table')){const panel=el('article',null,'panel');panel.append(el('h2','Historical snapshot change ledger'),el('p','Selected snapshot versus the previous snapshot. Both periods use the same filters; repeated identities are aggregated.'));const legend=el('div',null,'comparison-legend');legend.id='comparison-legend';panel.append(legend);const container=el('div',null,'table-scroll');container.id='comparison-table';container.tabIndex=0;container.setAttribute('role','region');container.setAttribute('aria-label','Historical snapshot comparison ledger');panel.append(container);$('view-growth').append(panel);}
  $('comparison-legend').replaceChildren(el('span',`SELECTED · ${dateLabel($('snapshot').value)}`,'selected-snapshot'),el('span',`PREVIOUS · ${m.previous?dateLabel(m.previous):'No earlier snapshot'}`,'previous-snapshot'));
  comparisonCleanup();
  renderComparisonGroups($('comparison-table'),comparison(calculated,$('snapshot').value,filters),fmt,percent);
  comparisonCleanup=setupComparisonScroll($('comparison-table'));
}
function renderYield(m){$('yield-summary').textContent=`Estimated annual earnings: MYR ${fmt(m.earnings)} · Interest-bearing capital: MYR ${fmt(m.capital)} · Weighted yield: ${percent(m.yield==null?null:m.yield*100)}`;table('yield-table',[{title:'Account',value:r=>r.Account},{title:'Balance (MYR)',value:r=>fmt(r.BalanceInMYR),number:true},{title:'Interest rate',value:r=>percent(r.InterestRate*100),number:true},{title:'Annual estimate (MYR)',value:r=>fmt(r.BalanceInMYR*r.InterestRate),number:true}],m.interest);}
function ledgerRows(m){const query=$('search').value.toLowerCase().trim();const rows=m.selected.filter(r=>['Account','Type','Category','SubCategory','Currency','CashLiquidity'].some(k=>r[k].toLowerCase().includes(query)));const sort=$('sort').value;return rows.sort((a,b)=>sort==='account'?a.Account.localeCompare(b.Account):sort==='yield'?b.InterestRate-a.InterestRate:sort==='value-asc'?a.BalanceInMYR-b.BalanceInMYR:b.BalanceInMYR-a.BalanceInMYR);}
function renderLedger(m){ledgerCleanup();const rows=ledgerRows(m),pages=Math.max(1,Math.ceil(rows.length/20));page=Math.min(page,pages-1);table('ledger',[{title:'Account',value:r=>r.Account},{title:'Type',value:r=>r.Type},{title:'Category',value:r=>`${r.Category} / ${r.SubCategory}`},{title:'Currency',value:r=>r.Currency},{title:'Balance',value:r=>fmt(r.Balance),number:true},{title:'MYR value',value:r=>fmt(r.BalanceInMYR),number:true},{title:'Interest rate',value:r=>percent(r.InterestRate*100),number:true},{title:'Liquidity',value:r=>r.CashLiquidity},{title:'Maturity',value:r=>r.original.MaturityDate?dateLabelSafe(r.original.MaturityDate):'—'},{title:'FX audit',value:r=>r.fx?`${r.fx.rate} · ${r.fx.date}`:'Source / MYR balance'}],rows.slice(page*20,page*20+20));ledgerCleanup=setupComparisonScroll($('ledger'),'Scroll account ledger columns horizontally');$('ledger-count').textContent=`${rows.length.toLocaleString()} matching rows · MYR ${fmt(rows.reduce((s,r)=>s+r.BalanceInMYR,0))}`;$('page-label').textContent=`${page+1} / ${pages}`;$('prev-page').disabled=page===0;$('next-page').disabled=page===pages-1;}
function dateLabelSafe(value){const date=calendarDate(value,model.source.date1904);return date?dateLabel(date):String(value);}
$('search').oninput=()=>{page=0;if(currentMetrics)renderLedger(currentMetrics);};$('sort').onchange=()=>{page=0;if(currentMetrics)renderLedger(currentMetrics);};$('prev-page').onclick=()=>{page--;renderLedger(currentMetrics);};$('next-page').onclick=()=>{page++;renderLedger(currentMetrics);};
function renderQuality(){
  $('quality-summary').textContent=`${model.rows.length} normalized Asset rows · ${calculated.rows.length} included across all snapshots · ${model.references.length} valid FX references. ${$('correction').checked?'Correction enabled.':'Correction disabled: MYR source values used without conversion.'}`;
  if(!auditTable || !$('quality-table').querySelector('table')) auditTable=createAuditTable($('quality-table'));
  auditTable.update(calculated.issues);
  $('source-row').replaceChildren(...model.source.sheets.Asset.map((r,i)=>{const option=el('option',`Row ${r.__row??i+2} · ${r.Account??'Unnamed account'}`);option.value=i;return option;}));renderSource();
}
let auditTable=null;
function renderSource(){const row=model.source.sheets.Asset[+$('source-row').value];table('source-values',[{title:'Source column',value:r=>r.key},{title:'Original value',value:r=>r.value,wrap:true}],Object.entries(row??{}).filter(([key])=>key!=='__row').map(([key,value])=>({key,value:value==null?'(blank)':String(value)})));}
$('source-row').onchange=renderSource;
for(const id of ['allocation-dimension','hierarchy-mode','trend-dimension'])$(id).onchange=render;
for(const dimension of ['SubCategory','Account']){const option=el('option',dimension==='SubCategory'?'Subcategory':dimension);option.value=dimension;$('trend-dimension').append(option);}
$('export').onclick=()=>{const rows=ledgerRows(currentMetrics).map(r=>({ReportingDate:r.date,Type:r.Type,Category:r.Category,SubCategory:r.SubCategory,Account:r.Account,Currency:r.Currency,Balance:r.Balance,BalanceInMYR:r.BalanceInMYR,InterestRate:r.InterestRate,CashLiquidity:r.CashLiquidity,MaturityDate:r.original.MaturityDate??'',SourceRow:r.row,OriginalBalanceInMYR:r.sourceMYR,FXRate:r.fx?.rate??'',FXReferenceDate:r.fx?.date??'',FXMethod:r.fx?.method??''}));const columns=['ReportingDate','Type','Category','SubCategory','Account','Currency','Balance','BalanceInMYR','InterestRate','CashLiquidity','MaturityDate','SourceRow','OriginalBalanceInMYR','FXRate','FXReferenceDate','FXMethod'];const url=URL.createObjectURL(new Blob([csv(rows,columns)],{type:'text/csv;charset=utf-8'}));const link=el('a');link.href=url;link.download=`asset-ledger-${$('snapshot').value}.csv`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
$('reset').onclick=()=>{++importGeneration;ledgerCleanup();ledgerCleanup=()=>{};comparisonCleanup();comparisonCleanup=()=>{};$('comparison-legend')?.replaceChildren();auditTable=null;model=calculated=pending=currentMetrics=null;filters={};filename='';isDemo=false;page=0;purgeAll();$('file').value='';$('source').replaceChildren();$('snapshot').replaceChildren();$('filter-fields').replaceChildren();$('metrics').replaceChildren();for(const id of ['ledger','quality-table','source-values','yield-table','history-table','comparison-table','insights','ytd-summary','quality-summary','yield-summary','import-preview','quality-banner'])$(id)?.replaceChildren();$('source-row').replaceChildren();$('search').value='';$('ledger-count').textContent='';$('page-label').textContent='';for(const id of ['dashboard','filters','source','reset','snapshot-control','import-preview'])visible(id,false);visible('welcome',true);status('Active dataset cleared. Import a workbook to begin again.');};
$('asset-nav').onclick=()=>{view='overview';if(model)render();};
