import * as XLSX from 'xlsx';
import { REQUIRED } from './asset-analysis.js';
export const MAX_BYTES=10*1024*1024, MAX_ROWS=25000;
export async function importWorkbook(file) {
  if(!file.name.toLowerCase().endsWith('.xlsx')) throw new Error('Choose an .xlsx workbook. HTML, legacy .xls and encrypted workbooks are not supported in this release.');
  if(file.size>MAX_BYTES) throw new Error('Workbook exceeds the initial 10 MB file limit. Use a smaller workbook.');
  const bytes=await file.arrayBuffer();
  const signature=new Uint8Array(bytes,0,Math.min(bytes.byteLength,4));
  if(signature[0]!==0x50||signature[1]!==0x4b) throw new Error('This is not an unencrypted .xlsx archive. Save an unencrypted .xlsx workbook in Excel and try again.');
  let workbook;
  try{workbook=XLSX.read(bytes,{type:'array',cellDates:false,cellFormula:true,cellHTML:false,bookVBA:false,sheetRows:MAX_ROWS+2});}
  catch{throw new Error('Unable to read this workbook. Save an unencrypted .xlsx file in Excel and try again.');}
  const source={sheets:{},headers:{},issues:[],date1904:!!workbook.Workbook?.WBProps?.date1904,sheetNames:workbook.SheetNames};
  let count=0;
  for(const name of ['Asset','Reference']) {
    const sheet=workbook.Sheets[name];if(!sheet) continue;
    if(!sheet['!ref']) {source.sheets[name]=[];source.headers[name]=[];continue;}
    const range=XLSX.utils.decode_range(sheet['!fullref']??sheet['!ref']);
    if(range.e.r>MAX_ROWS||range.e.c>100) throw new Error(`${name} exceeds the initial ${MAX_ROWS.toLocaleString()} source-row or 101-column limit. Remove excessive formatting/unused rows and save again.`);
    if(sheet['!merges']?.length) throw new Error(`${name} contains merged cells. Use an unmerged source table with one header row.`);
    const header=[];
    for(let c=range.s.c;c<=range.e.c;c++)header.push(String(sheet[XLSX.utils.encode_cell({r:range.s.r,c})]?.v??'').trim());
    const used=header.filter(Boolean);
    if(new Set(used).size!==used.length) throw new Error(`${name} has duplicate column headers.`);
    source.headers[name]=used;source.sheets[name]=[];
    for(let r=range.s.r+1;r<=range.e.r;r++) {
      const record={__row:r+1};let present=false,blocking=false;
      for(let c=range.s.c;c<=range.e.c;c++) {
        const key=header[c-range.s.c];if(!key) continue;
        const cell=sheet[XLSX.utils.encode_cell({r,c})];record[key]=cell?.v??null;
        if(cell?.v!=null||cell?.f)present=true;
        if(cell?.t==='e') {record[key]=null;source.issues.push({sheet:name,row:r+1,code:'CELL_ERROR',field:key,value:XLSX.utils.format_cell(cell),level:'excluded',message:`${key} contains an Excel error; row excluded.`});blocking=true;}
        if(cell?.f) {
          const required=name==='Asset'?REQUIRED.includes(key):['ReportingDate','Currency','Rate'].includes(key);
          if(required&&(cell.v==null||cell.v==='')) {blocking=true;source.issues.push({sheet:name,row:r+1,code:'FORMULA_NO_CACHE',field:key,value:cell?.v??null,level:'excluded',message:`${key} has no usable cached formula value. Recalculate and save in Excel; row excluded.`});}
          else source.issues.push({sheet:name,row:r+1,code:'FORMULA_CACHE',field:key,value:cell?.v??null,level:'warning',message:`${key} uses a cached formula result that may be stale. No formula was executed.`});
        }
      }
      if(present&&!blocking){source.sheets[name].push(record);count++;}
    }
  }
  if(count>MAX_ROWS) throw new Error(`Combined Asset and Reference input exceeds ${MAX_ROWS.toLocaleString()} rows.`);
  return source;
}
