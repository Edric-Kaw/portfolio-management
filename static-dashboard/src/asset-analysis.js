export const REQUIRED = ['ReportingDate','Type','Category','SubCategory','Account','Currency','Balance','BalanceInMYR','InterestRate','CashLiquidity'];
export const FILTERS = ['Type','Category','Currency','CashLiquidity'];
const DAY = 86400000;
export function calendarDate(value, date1904=false) {
  if(value instanceof Date && Number.isFinite(value.getTime())) return `${value.getUTCFullYear()}-${String(value.getUTCMonth()+1).padStart(2,'0')}-${String(value.getUTCDate()).padStart(2,'0')}`;
  if(typeof value==='number' && Number.isFinite(value)) {
    const serial=Math.floor(value);
    if(serial<0 || (!date1904 && serial===60)) return null;
    const base=date1904?Date.UTC(1904,0,1):Date.UTC(1899,11,31);
    const date=new Date(base+(serial-(!date1904&&serial>60?1:0))*DAY);
    return Number.isFinite(date.getTime())?date.toISOString().slice(0,10):null;
  }
  const text=String(value??'').trim();
  const m=/^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T]00:00(?::00(?:\.0+)?)?)?$/.exec(text);
  if(!m) return null;
  const y=+m[1], month=+m[2], day=+m[3];
  const date=new Date(Date.UTC(y,month-1,day));
  if(y<1900||y>9999||date.getUTCFullYear()!==y||date.getUTCMonth()+1!==month||date.getUTCDate()!==day) return null;
  return date.toISOString().slice(0,10);
}
export function numeric(value, percentage=false) {
  if(value==null||String(value).trim()==='') return 0;
  if(typeof value==='boolean') return null;
  if(typeof value==='number') return Number.isFinite(value)?value:null;
  const s=String(value).trim();
  if(percentage && /^[-+]?\d+(?:\.\d+)?%$/.test(s)) return Number(s.slice(0,-1))/100;
  if(!/^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?$/i.test(s)) return null;
  return Number.isFinite(Number(s))?Number(s):null;
}
export function validateSource(source) {
  const headers=source.headers?.Asset??Object.keys(source.sheets.Asset?.[0]??{});
  const missing=REQUIRED.filter(h=>!headers.includes(h));
  if(!source.sheets.Asset) throw new Error('Missing Asset worksheet. This release requires a usable Asset sheet.');
  if(missing.length) throw new Error(`Asset worksheet is missing columns: ${missing.join(', ')}.`);
  if(!source.sheets.Asset.length) throw new Error(`The Asset worksheet has no usable data rows.${source.issues?.some(i=>i.code==='FORMULA_NO_CACHE')?' Required formulas have no cached results; recalculate and save in Excel first.':''}`);
  if(source.sheets.Reference?.length) {
    const rh=source.headers?.Reference??Object.keys(source.sheets.Reference[0]);
    const rm=['ReportingDate','Currency','Rate'].filter(h=>!rh.includes(h));
    if(rm.length) throw new Error(`Reference worksheet is missing columns: ${rm.join(', ')}.`);
  }
}
export function normalize(source) {
  validateSource(source);
  const issues=[...(source.issues??[])], rows=[], references=[];
  const issue=(sheet,row,code,message,level='warning',context={})=>issues.push({sheet,row,code,message,level,...context});
  for(const [i,r] of (source.sheets.Reference??[]).entries()) {
    const row=r.__row??i+2, date=calendarDate(r.ReportingDate,source.date1904), rate=numeric(r.Rate), currency=String(r.Currency??'').trim();
    if(!date||!currency||rate==null||rate<=0) {issue('Reference',row,'INVALID_REFERENCE','Invalid date, currency or non-positive FX rate; reference excluded.','excluded',{value:!date?r.ReportingDate:!currency?r.Currency:r.Rate});continue;}
    references.push({date,currency,rate,row});
  }
  if(!references.length) issue('Reference','—','NO_FX','No usable FX references. Missing foreign MYR conversions will be excluded when correction is enabled.');
  for(const [i,r] of source.sheets.Asset.entries()) {
    const row=r.__row??i+2,date=calendarDate(r.ReportingDate,source.date1904);
    if(!date){issue('Asset',row,'INVALID_DATE','ReportingDate must be an Excel date or YYYY-MM-DD; row excluded.','excluded',{field:'ReportingDate',value:r.ReportingDate});continue;}
    const n={date,row,original:r};let invalid=false;
    for(const key of ['Balance','BalanceInMYR','InterestRate']) {
      n[key]=numeric(r[key],key==='InterestRate');
      if(n[key]==null){issue('Asset',row,'INVALID_NUMBER',`${key} is not a valid number; row excluded.`,'excluded',{field:key,value:r[key]});invalid=true;}
      else if(r[key]==null||String(r[key]).trim()==='') issue('Asset',row,'BLANK_NUMBER',`${key} is blank; normalized to zero, matching the dashboard.`,'warning',{field:key,value:r[key]??null});
    }
    if(invalid) continue;
    for(const key of ['Type','Category','SubCategory','Account','Currency','CashLiquidity']) {
      n[key]=String(r[key]??'').trim()||'N/A';
      if(n[key]==='N/A') issue('Asset',row,'MISSING_LABEL',`${key} is missing; displayed as N/A.`,'warning',{field:key,value:r[key]??null});
    }
    if(n.Currency==='N/A'){issue('Asset',row,'MISSING_CURRENCY','Missing currency; row excluded.','excluded',{field:'Currency',value:r.Currency??null});continue;}
    n.sourceMYR=n.BalanceInMYR; rows.push(n);
  }
  if(!rows.length) throw new Error('No usable Asset rows remain after validation. Check dates and numeric source fields.');
  return {rows,references,issues,source};
}
export function calculate(model, correction=true) {
  const rows=[],issues=[...model.issues];
  for(const r of model.rows) {
    const row={...r,fx:null};
    if(correction&&row.Currency==='MYR') row.BalanceInMYR=row.Balance;
    else if(correction&&Math.abs(row.sourceMYR)<1e-4&&Math.abs(row.Balance)>1e-4) {
      const refs=model.references.filter(x=>x.currency===row.Currency);
      let ref=refs.find(x=>x.date===row.date),method='Exact date';
      if(!ref){ref=refs.find(x=>x.date.slice(5)===row.date.slice(5));method='Matching month/day';}
      if(!ref&&refs.length){ref=refs.reduce((best,x)=>Math.abs(Date.parse(x.date)-Date.parse(row.date))<Math.abs(Date.parse(best.date)-Date.parse(row.date))?x:best);method='Closest date';}
      if(!ref) {issues.push({sheet:'Asset',row:row.row,code:'MISSING_FX',value:row.sourceMYR,unit:'MYR',level:'excluded',message:`No FX for ${row.Currency}; zero/missing MYR conversion excluded from results.`});continue;}
      row.BalanceInMYR=row.Balance*ref.rate;row.fx={...ref,method};
      issues.push({sheet:'Asset',row:row.row,code:'FX_CORRECTION',value:row.BalanceInMYR,unit:'MYR',level:'correction',message:`${row.Currency} ${row.Balance} × ${ref.rate} = MYR ${row.BalanceInMYR}. ${method}: ${ref.date}; Reference row ${ref.row}.`});
    }
    if(!Number.isFinite(row.BalanceInMYR)){issues.push({sheet:'Asset',row:row.row,code:'NUMERIC_OVERFLOW',value:row.BalanceInMYR,unit:'MYR',level:'excluded',message:'Converted value exceeds numeric limits; row excluded.'});continue;}
    rows.push(row);
  }
  return {rows,issues,dates:[...new Set(model.rows.map(r=>r.date))].sort()};
}
export const sum=(rows,key='BalanceInMYR')=>rows.reduce((s,r)=>s+r[key],0);
export function matches(row,filters) {return FILTERS.every(key=>!filters[key]||filters[key].includes(row[key]));}
export function group(rows,key) {const values=new Map();for(const r of rows) values.set(r[key],(values.get(r[key])??0)+r.BalanceInMYR);return [...values].map(([name,value])=>({name,value})).sort((a,b)=>b.value-a.value||a.name.localeCompare(b.name));}
export function percentageChange(current,previous) {return previous>0?(current-previous)/previous*100:null;}
export function metrics(calculated,date,filters={}) {
  const selected=calculated.rows.filter(r=>r.date===date&&matches(r,filters)),total=sum(selected),interest=selected.filter(r=>r.InterestRate>0),capital=sum(interest),earnings=interest.reduce((s,r)=>s+r.BalanceInMYR*r.InterestRate,0),liquid=sum(selected.filter(r=>['Very High','High'].includes(r.CashLiquidity)));
  const previous=calculated.dates.filter(d=>d<date).at(-1)??null;
  const baseline=previous?sum(calculated.rows.filter(r=>r.date===previous&&matches(r,filters))):null;
  const ytdDate=calculated.dates.filter(d=>d<=`${Number(date.slice(0,4))-1}-12-31`).at(-1)??null;
  const ytdRows=ytdDate?calculated.rows.filter(r=>r.date===ytdDate&&matches(r,filters)):[];
  return {selected,total,interest,capital,earnings,yield:capital!==0?earnings/capital:null,liquid,liquidity:total>0?liquid/total*100:0,previous,baseline,change:baseline==null?null:total-baseline,changePercent:baseline==null?null:percentageChange(total,baseline),ytdDate,ytdRows,ytdTotal:ytdDate?sum(ytdRows):null};
}
export function history(calculated,filters={}) {return calculated.dates.map(date=>{const rows=calculated.rows.filter(r=>r.date===date&&matches(r,filters));return {date,total:sum(rows),rows};});}
export function comparison(calculated,date,filters={}) {
  const previous=calculated.dates.filter(d=>d<date).at(-1);if(!previous)return [];
  const keys=['Type','Category','SubCategory','Account','Currency'],groups=new Map();
  for(const r of calculated.rows.filter(r=>(r.date===date||r.date===previous)&&matches(r,filters))){const id=JSON.stringify(keys.map(k=>r[k]));if(!groups.has(id))groups.set(id,{...Object.fromEntries(keys.map(k=>[k,r[k]])),current:0,previous:0});groups.get(id)[r.date===date?'current':'previous']+=r.BalanceInMYR;}
  return [...groups.values()].map(r=>({...r,change:r.current-r.previous,pct:percentageChange(r.current,r.previous)})).sort((a,b)=>Math.abs(b.change)-Math.abs(a.change));
}
export function csv(rows,columns) {
  const cell=(value)=>{let str=String(value??'');if(typeof value!=='number'&&/^[\s\u0000-\u001f]*[=+@-]/.test(str)) str="'"+str;return '"'+str.replaceAll('"','""')+'"';};
  return '\uFEFF'+[columns.map(cell).join(','),...rows.map(row=>columns.map(c=>cell(row[c])).join(','))].join('\r\n');
}
