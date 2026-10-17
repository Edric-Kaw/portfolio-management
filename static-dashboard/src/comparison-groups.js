import {percentageChange} from './asset-analysis.js';
export function groupComparisons(entries) {
  const groups=new Map();
  for(const row of entries){
    if(!groups.has(row.Type))groups.set(row.Type,{type:row.Type,current:0,previous:0,accounts:[]});
    const group=groups.get(row.Type);group.current+=row.current;group.previous+=row.previous;group.accounts.push(row);
  }
  return [...groups.values()].map(g=>({...g,change:g.current-g.previous,pct:percentageChange(g.current,g.previous)})).sort((a,b)=>Math.abs(b.change)-Math.abs(a.change));
}
export function renderComparisonGroups(container,entries,fmt,percent){
  container.replaceChildren();
  if(!entries.length){const p=document.createElement('p');p.textContent='No records for this selection.';container.append(p);return;}
  const make=(tag,text)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;return n;};
  const table=make('table'),head=make('thead'),header=make('tr'),body=make('tbody');
  for(const title of ['Type / Account','Category / Subcategory','Currency','Selected (MYR)','Previous (MYR)','Change (MYR)','Change (%)']){const th=make('th',title);th.scope='col';header.append(th);}head.append(header);table.append(head,body);
  const changeText=r=>r.pct==null?(r.current>0?'New / no positive baseline':'N/A'):percent(r.pct);
  const values=(tr,r)=>{for(const value of [fmt(r.current),fmt(r.previous),fmt(r.change),changeText(r)]){const td=make('td',value);td.className='number';tr.append(td);}};
  groupComparisons(entries).forEach((group,index)=>{
    const summary=make('tr');summary.className='comparison-type-summary';
    const label=make('td'),button=make('button',`▸ ${group.type}`);button.className='comparison-expand';button.type='button';button.setAttribute('aria-expanded','false');button.setAttribute('aria-label',`Expand ${group.type} account changes`);
    label.append(button);summary.append(label,make('td',`${group.accounts.length} account entries · Type total`),make('td','MYR reporting'));values(summary,group);body.append(summary);
    const children=group.accounts.map((account,childIndex)=>{const tr=make('tr');tr.className='comparison-account';tr.id=`comparison-account-${index}-${childIndex}`;tr.hidden=true;tr.append(make('td',account.Account),make('td',`${account.Category} / ${account.SubCategory}`),make('td',account.Currency));values(tr,account);body.append(tr);return tr;});
    button.setAttribute('aria-controls',children.map(tr=>tr.id).join(' '));
    button.onclick=()=>{const expanded=button.getAttribute('aria-expanded')!=='true';button.setAttribute('aria-expanded',String(expanded));button.setAttribute('aria-label',`${expanded?'Collapse':'Expand'} ${group.type} account changes`);button.textContent=`${expanded?'▾':'▸'} ${group.type}`;children.forEach(tr=>tr.hidden=!expanded);};
  });
  container.append(table);
}
