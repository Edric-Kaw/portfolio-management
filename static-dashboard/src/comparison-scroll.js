// Native horizontal scroll control immediately below the column labels.
export function setupComparisonScroll(container, label='Scroll historical comparison columns horizontally') {
  const table = container.querySelector('table');
  if (!table) return () => {};
  const row = document.createElement('tr');
  row.className = 'comparison-scroll-row';
  const cell = document.createElement('td');
  cell.colSpan = table.tHead.rows[0].cells.length;
  const bar = document.createElement('div');
  bar.className = 'comparison-horizontal-scroll';
  bar.tabIndex = 0;
  bar.setAttribute('role', 'region');
  bar.setAttribute('aria-label', label);
  const spacer = document.createElement('div');
  spacer.setAttribute('aria-hidden', 'true');
  bar.append(spacer); cell.append(bar); row.append(cell); table.tHead.append(row);
  let lastTableLeft = container.scrollLeft;
  const fromBar = () => {
    if (container.scrollLeft !== bar.scrollLeft) container.scrollLeft = bar.scrollLeft;
    lastTableLeft = container.scrollLeft;
  };
  const fromTable = () => {
    // Vertical scroll events must not overwrite a pending horizontal drag.
    if (lastTableLeft === container.scrollLeft) return;
    lastTableLeft = container.scrollLeft;
    if (bar.scrollLeft !== container.scrollLeft) bar.scrollLeft = container.scrollLeft;
  };
  bar.addEventListener('scroll', fromBar);
  container.addEventListener('scroll', fromTable);
  const resize = () => {
    bar.style.width = `${container.clientWidth}px`;
    spacer.style.width = `${table.scrollWidth}px`;
    fromTable();
  };
  const observer = new ResizeObserver(resize);
  observer.observe(container); observer.observe(table); resize();
  return () => { observer.disconnect(); bar.removeEventListener('scroll', fromBar); container.removeEventListener('scroll', fromTable); };
}
