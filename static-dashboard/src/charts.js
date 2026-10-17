import Plotly from 'plotly.js-dist-min';
import {group,history,sum,percentageChange} from './asset-analysis.js';
export const colors=['#54dfbf','#62baff','#a695ef','#f4c66d','#ec93c3','#82d2e0','#ccd89b','#e99976'];
const types={Cash:colors[0],Investment:colors[1],Retirement:colors[2],Insurance:colors[4]};
export const color=(name,index)=>types[name]??colors[index%colors.length];
const layout={paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{family:'Segoe UI, Arial, sans-serif',color:'#a4b3c8',size:11},margin:{t:25,b:45,l:70,r:25},hoverlabel:{bgcolor:'#22364a',font:{color:'#edf3fa'}},xaxis:{gridcolor:'#263449',zerolinecolor:'#435368',automargin:true},yaxis:{gridcolor:'#263449',zerolinecolor:'#435368',automargin:true},legend:{orientation:'h',y:-.15},colorway:colors};
const config={responsive:true,displaylogo:false,scrollZoom:false,toImageButtonOptions:{filename:'portfolio-chart'},modeBarButtonsToRemove:['sendDataToCloud','lasso2d','select2d','toImage']};
export async function plot(id,traces,options={}) {
  const target=document.getElementById(id);
  return Plotly.react(target,traces,{...layout,...options},config);
}
export function empty(id,message='No data matches this selection.') {
  const target=document.getElementById(id);Plotly.purge(target);target.replaceChildren();const text=document.createElement('div');text.className='empty-chart';text.textContent=message;target.append(text);
}
export function purgeAll(){document.querySelectorAll('.chart').forEach(el=>{Plotly.purge(el);el.replaceChildren();});}
const safeLabel=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const names=groups=>groups.map(g=>safeLabel(g.name));
export function donut(id,rows,key) {
  const groups=group(rows,key);
  if(!groups.length)return empty(id);
  if(groups.some(g=>g.value<0))return bars(id,groups,'Signed balances shown as bars; donut segments cannot represent negatives.');
  if(groups.every(g=>g.value===0))return empty(id,'All selected balances are zero.');
  return plot(id,[{type:'pie',labels:names(groups),values:groups.map(g=>g.value),hole:.72,sort:false,marker:{colors:groups.map((g,i)=>color(g.name,i)),line:{color:'#141d2b',width:4}},textinfo:'none',hovertemplate:'%{label}<br>MYR %{value:,.2f}<br>%{percent}<extra></extra>'}],{margin:{t:15,b:50,l:15,r:15},annotations:[{text:'ALLOCATION',x:.5,y:.5,showarrow:false,font:{size:11,color:'#a4b3c8'}}],showlegend:true});
}
export function bars(id,groups,note){
  if(!groups.length)return empty(id);
  const sorted=[...groups].reverse();
  const showShare=id==='categories',total=groups.reduce((s,g)=>s+g.value,0);
  const shares=sorted.map(g=>total>0?`${(g.value/total*100).toFixed(1)}%`:'N/A');
  const max=Math.max(...sorted.map(g=>g.value));
  return plot(id,[{type:'bar',orientation:'h',y:names(sorted),x:sorted.map(g=>g.value),marker:{color:sorted.map((g,i)=>color(g.name,i)),cornerradius:5},...(showShare?{text:shares,textposition:'outside',textfont:{color:'#edf3fa',size:12},cliponaxis:false,customdata:shares}:{}),hovertemplate:showShare?'%{y}<br>MYR %{x:,.2f}<br>%{customdata} of filtered portfolio<extra></extra>':'%{y}<br>MYR %{x:,.2f}<extra></extra>'}],{margin:{t:note?40:20,b:45,l:100,r:showShare?50:25},xaxis:{...layout.xaxis,title:{text:'MYR'},tickformat:',.0f',...(showShare&&max>0&&sorted.every(g=>g.value>=0)?{range:[0,max*1.24]}:{})},yaxis:{...layout.yaxis,type:'category'},...(note?{annotations:[{text:note,x:0,y:1.14,xref:'paper',yref:'paper',showarrow:false,font:{size:9}}]}:{})});
}
export function hierarchy(rows,mode){
  if(!rows.length)return empty('hierarchy');
  if(rows.some(r=>r.BalanceInMYR<0))return empty('hierarchy','Hierarchy charts require non-negative balances. Signed balances remain visible in category bars and the ledger.');
  if(sum(rows)===0)return empty('hierarchy','All selected balances are zero.');
  const nodes=new Map([['root',{label:'Portfolio',parent:'',value:0,color:colors[0]}]]);
  const typeNames=[...new Set(rows.map(r=>r.Type))];
  for(const r of rows){nodes.get('root').value+=r.BalanceInMYR;let parent='root',path=[];
    for(const key of ['Type','Category','SubCategory','Account']){path.push(r[key]);const id=JSON.stringify(path);if(!nodes.has(id))nodes.set(id,{label:r[key],parent,value:0,color:color(r.Type,typeNames.indexOf(r.Type))});nodes.get(id).value+=r.BalanceInMYR;parent=id;}
  }
  const entries=[...nodes];
  return plot('hierarchy',[{type:mode,ids:entries.map(([id])=>id),labels:entries.map(([,n])=>safeLabel(n.label)),parents:entries.map(([,n])=>n.parent),values:entries.map(([,n])=>n.value),branchvalues:'total',maxdepth:mode==='sunburst'?3:4,marker:{colors:entries.map(([,n])=>n.color),line:{width:2,color:'#141d2b'}},textfont:{color:'#071b24'},hovertemplate:'%{label}<br>MYR %{value:,.2f}<extra></extra>',...(mode==='treemap'?{pathbar:{visible:true},textinfo:'label+value',texttemplate:'%{label}<br>MYR %{value:,.0f}'}:{textinfo:'label'})}],{margin:{t:20,l:5,r:5,b:5}});
}
export function overviewCharts(m){donut('allocation',m.selected,document.getElementById('allocation-dimension').value);bars('categories',group(m.selected,'Category'));hierarchy(m.selected,document.getElementById('hierarchy-mode').value);bars('currency',group(m.selected,'Currency'));}
export function growthCharts(calculated,filters,m){
  const points=history(calculated,filters),dimension=document.getElementById('trend-dimension').value;
  const series=dimension==='total'?['Total portfolio']:[...new Set(points.flatMap(p=>p.rows.map(r=>r[dimension])))];
  if(!points.length){empty('trend');empty('movement');empty('ytd');return;}
  plot('trend',series.map((name,i)=>{
    const values=points.map(p=>dimension==='total'?p.total:sum(p.rows.filter(r=>r[dimension]===name)));
    const customdata=values.map((value,index)=>{
      if(index===0)return ['First recorded snapshot','Not available'];
      const change=percentageChange(value,values[index-1]);
      return [change==null?'N/A (no positive baseline)':`${change>=0?'+':''}${change.toFixed(2)}%`,points[index-1].date];
    });
    return {type:'scatter',mode:'lines+markers',name:safeLabel(name),x:points.map(p=>p.date),y:values,customdata,line:{color:color(name,i),width:3},marker:{size:7},fill:dimension==='total'?'tozeroy':undefined,fillcolor:'#54dfbf12',hovertemplate:'%{x}<br>MYR %{y:,.2f}<br>Change vs previous: %{customdata[0]}<br>Previous snapshot: %{customdata[1]}<extra>%{fullData.name}</extra>'};
  }),{xaxis:{...layout.xaxis,type:'date'},yaxis:{...layout.yaxis,title:{text:'MYR'},tickformat:',.0f'},hovermode:'x unified'});
  const moves=points.slice(1).map((p,i)=>({date:p.date,value:p.total-points[i].total}));
  if(moves.length)plot('movement',[{type:'bar',x:moves.map(p=>p.date),y:moves.map(p=>p.value),marker:{color:moves.map(p=>p.value>=0?colors[0]:'#ff9b9b')},hovertemplate:'%{x}<br>MYR %{y:+,.2f}<extra></extra>'}],{xaxis:{...layout.xaxis,type:'category'},yaxis:{...layout.yaxis,title:{text:'MYR change'}}});else empty('movement','Add another snapshot to compare changes.');
  if(m.ytdDate){const keys=[...new Set([...m.selected,...m.ytdRows].map(r=>r.Type))];bars('ytd',keys.map(name=>({name,value:sum(m.selected.filter(r=>r.Type===name))-sum(m.ytdRows.filter(r=>r.Type===name))})));}else empty('ytd','No snapshot on or before the previous year-end.');
}
export function liquidityCharts(m){donut('liquidity-chart',m.selected,'CashLiquidity');if(!m.interest.length)return empty('yield-chart','No interest-bearing accounts in this selection.');const ordered=[...m.interest].sort((a,b)=>a.InterestRate-b.InterestRate);plot('yield-chart',[{type:'bar',orientation:'h',y:ordered.map(r=>safeLabel(r.Account)),x:ordered.map(r=>r.InterestRate*100),marker:{color:colors[0],cornerradius:4},hovertemplate:'%{y}<br>%{x:.2f}% interest rate<extra></extra>'}],{margin:{t:20,b:40,l:100,r:30},xaxis:{...layout.xaxis,title:{text:'Annual interest rate (%)'}},yaxis:{...layout.yaxis,type:'category'}});}
