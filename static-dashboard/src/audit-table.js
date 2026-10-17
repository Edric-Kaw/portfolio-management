// Every control and value stays in memory; source strings are rendered as text.
export function auditValue(issue) {
  if (!Object.hasOwn(issue, 'value')) return '—';
  if (issue.value == null || issue.value === '') return '(blank)';
  if (issue.unit === 'MYR' && typeof issue.value === 'number' && Number.isFinite(issue.value)) {
    return `${new Intl.NumberFormat('en-MY', {minimumFractionDigits: 2, maximumFractionDigits: 2}).format(issue.value)} MYR`;
  }
  return `${String(issue.value)}${issue.unit ? ` ${issue.unit}` : ''}`;
}
const columns = [
  { key: 'sheet', title: 'Sheet' },
  { key: 'row', title: 'Row' },
  { key: 'level', title: 'Severity' },
  { key: 'code', title: 'Code' },
  { key: 'value', title: 'Value', display: auditValue },
  { key: 'message', title: 'Details' },
];
const dropdownKeys = new Set(['sheet', 'level', 'code']);
export function selectAuditRows(issues, filters, sort) {
  const entries = issues.filter(issue => columns.every(column => {
    const query = (filters[column.key] ?? '').trim().toLowerCase();
    const value = column.display ? column.display(issue) : String(issue[column.key] ?? '');
    if (dropdownKeys.has(column.key)) return !query || value.toLowerCase() === query;
    return value.toLowerCase().includes(query) || (column.key === 'value' && String(issue.value ?? '').toLowerCase().includes(query));
  }));
  if (!sort) return entries;
  return entries.sort((a, b) => {
    const av = a[sort.key], bv = b[sort.key];
    if (av == null) return bv == null ? 0 : 1;
    if (bv == null) return -1;
    const result = typeof av === 'number' && typeof bv === 'number'
      ? av - bv
      : String(av).localeCompare(String(bv), undefined, { numeric: true, sensitivity: 'base' });
    return sort.direction === 'ascending' ? result : -result;
  });
}
export function createAuditTable(container) {
  let issues = [], filters = {}, sort = null, page = 0;
  const pageSize = 50;
  const make = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  container.replaceChildren();
  const help = make('p', 'Click a column heading to sort. Filter any column below; filters combine across all audit entries.', 'chart-note');
  const table = make('table'), head = make('thead'), headings = make('tr'), filterRow = make('tr');
  const body = make('tbody'), headerControls = [], filterControls = [];
  for (const column of columns) {
    const th = make('th'); th.scope = 'col';
    const button = make('button', `${column.title} ↕`, 'audit-sort');
    button.type = 'button'; button.setAttribute('aria-label', `Sort by ${column.title}`);
    button.onclick = () => {
      sort = { key: column.key, direction: sort?.key === column.key && sort.direction === 'ascending' ? 'descending' : 'ascending' };
      page = 0; render();
    };
    th.append(button); headings.append(th); headerControls.push({ th, button, column });
    const filterCell = make('td'), input = make(dropdownKeys.has(column.key) ? 'select' : 'input');
    if (!dropdownKeys.has(column.key)) { input.type = 'search'; input.placeholder = `Filter ${column.title.toLowerCase()}`; }
    input.setAttribute('aria-label', `Filter ${column.title}`);
    const change = () => { filters[column.key] = input.value; page = 0; render(); };
    if (dropdownKeys.has(column.key)) input.onchange = change; else input.oninput = change;
    filterCell.append(input); filterRow.append(filterCell); filterControls.push(input);
    input.dataset.key = column.key;
  }
  head.append(headings, filterRow); table.append(head, body);
  filterRow.className = 'audit-filters'; table.className = 'audit-table';
  const scroll = make('div', null, 'table-scroll'); scroll.append(table);
  const footer = make('div', null, 'pagination'), count = make('span'); count.setAttribute('role', 'status');
  const controls = make('div'), clear = make('button', 'Clear filters & sort', 'secondary');
  const previous = make('button', 'Previous', 'secondary'), next = make('button', 'Next', 'secondary'), pageLabel = make('span');
  clear.onclick = () => { filters = {}; sort = null; page = 0; filterControls.forEach(input => { input.value = ''; }); render(); };
  previous.onclick = () => { page--; render(); }; next.onclick = () => { page++; render(); };
  controls.append(previous, pageLabel, next); footer.append(count, controls);
  container.append(help, clear, scroll, footer);
  function render() {
    const entries = selectAuditRows(issues, filters, sort), pages = Math.max(1, Math.ceil(entries.length / pageSize));
    page = Math.min(page, pages - 1); body.replaceChildren();
    for (const { th, button, column } of headerControls) {
      const direction = sort?.key === column.key ? sort.direction : 'none';
      th.setAttribute('aria-sort', direction);
      button.textContent = `${column.title} ${direction === 'ascending' ? '↑' : direction === 'descending' ? '↓' : '↕'}`;
    }
    for (const issue of entries.slice(page * pageSize, (page + 1) * pageSize)) {
      const tr = make('tr');
      for (const column of columns) tr.append(make('td', column.display ? column.display(issue) : issue[column.key], ['message', 'value'].includes(column.key) ? 'wrap' : ''));
      body.append(tr);
    }
    if (!entries.length) { const tr = make('tr'), td = make('td', 'No audit entries match these filters.'); td.colSpan = columns.length; tr.append(td); body.append(tr); }
    count.textContent = `${entries.length.toLocaleString()} of ${issues.length.toLocaleString()} audit entries · ${entries.length ? page * pageSize + 1 : 0}–${Math.min((page + 1) * pageSize, entries.length)} shown`;
    pageLabel.textContent = `${page + 1} / ${pages}`; previous.disabled = page === 0; next.disabled = page === pages - 1;
  }
  return { update(entries) {
    issues = entries;
    for (const control of filterControls.filter(c=>dropdownKeys.has(c.dataset.key))) {
      const key=control.dataset.key,selected=filters[key]??'';
      control.replaceChildren();
      const all=make('option',`All ${columns.find(c=>c.key===key).title.toLowerCase()}`);all.value='';control.append(all);
      const values=[...new Set(entries.map(i=>String(i[key]??'')))].filter(Boolean).sort();
      for(const value of values){const option=make('option',value);option.value=value;control.append(option);}
      if(values.includes(selected))control.value=selected;else{control.value='';filters[key]='';}
    }
    render();
  } };
}
