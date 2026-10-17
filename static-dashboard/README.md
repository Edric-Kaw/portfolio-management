# Portfolio — static Asset dashboard

A separate, local-first Asset Analytics application. The existing Python dashboard and services are unchanged. This release covers Asset Analysis; Trade and Expense are future releases, explicitly identified in the interface.

## Run and build

Use Node.js 22.12+ (development only):

```powershell
cd static-dashboard
npm ci
npm run build
npm run preview
```

Open `http://127.0.0.1:4173/asset_analysis/`. The production HTML entry is `dist/index.html`; keep its `assets/` directory and notices alongside it. Serve the built directory over HTTP/HTTPS. This is a modular static website, not a self-contained file intended for double-click opening.

For development, use `npm run dev`. The production Content Security Policy deliberately disables connections, including Vite's development hot-reload connection; manually refresh after edits or use the production preview.

Try **Explore synthetic demo**, then **Activate dataset** to inspect the interface without using private information.

## Features

- Local `.xlsx` import with detected sheets, validation preview, explicit activation, and safe failed-import recovery.
- Snapshot selection and multi-select Type, Category, Currency and liquidity filters.
- Total assets, original-currency USD exposure, interest-bearing weighted yield, and liquid-capital metrics.
- Interactive allocation donut, category/currency bars, treemap or sunburst hierarchy, historical trends with Type/Category/Subcategory/Account/Currency breakdowns, period changes, and prior-year-end comparisons.
- Historical comparison ledger with expandable Type totals and account changes, liquidity profile, annual interest estimates, and yield ledger. Trend hover cards include percentage change against the previous snapshot. Account and comparison ledgers keep headers pinned and provide a synchronized horizontal scrollbar below the header.
- Searchable, sorted, paginated account ledger and local CSV downloads with formula-prefix protection.
- FX correction toggle; audit entries show rate, source date, lookup method and source row. Original source values remain inspectable.
- Responsive interface, accessible labels and keyboard controls, reduced-motion support, and explanatory empty states.

## Workbook contract

The Asset sheet must have these exact headers:

`ReportingDate`, `Type`, `Category`, `SubCategory`, `Account`, `Currency`, `Balance`, `BalanceInMYR`, `InterestRate`, `CashLiquidity`.

`MaturityDate` is optional. `Reference` is optional for already-valued records; when present and populated it must have `ReportingDate`, `Currency`, `Rate`. Other sheets are detected but not processed in this release.

Dates support Excel serials with 1900/1904 workbook epochs and explicit `YYYY-MM-DD` strings (optionally midnight). Ambiguous date strings are rejected. Interest rates use fractions (`0.04` means 4%); explicit `4%` text is also supported. Invalid numeric rows are excluded, rather than silently turned into real zero balances. Blank numeric values normalize to zero with audit warnings.

No formulas, macros, embedded links, or imported markup execute. Required formulas with cached values trigger stale-cache warnings; those without usable caches exclude their source rows with instructions to recalculate in Excel. Merged source tables and duplicate headers are rejected.

Initial guards: 10 MB compressed file size, 25,000 combined usable source rows, at most 25,000 Excel data-row indices per sheet, and 101 columns per processed sheet. These bounds are conservative input guards, not universal memory or responsiveness guarantees. Dense hierarchy charts and very many distinct accounts may remain slower than the synthetic benchmark; Web Workers and further chart aggregation are future improvements.

The quality view provides sorting and per-column filters for Sheet, Row, Severity, Code, Value, and Details. Sheet, Severity and Code use dropdowns of imported values; the other columns retain text search. Filters combine across the full audit; pagination shows 50 entries per page. Value displays the source/cached cell value (including zero or blank), or the corrected MYR result for FX corrections. Corrected MYR amounts display two decimal places; calculations and numeric sorting keep the original precision.

## Privacy

Application assets load from the host. Imported records and results remain in browser memory. There is no analytics, telemetry, API, dataset persistence, or runtime CDN. A restrictive Content Security Policy blocks network connections and frames. Rendered source strings use text nodes; chart labels are escaped. Reset and reload clear the active dataset. CSV downloads are generated locally on explicit request.

Do not commit private workbooks, reports, fixtures, or credentials. The `.gitignore` excludes frontend workbooks, CSVs, build output, test output, and dependencies. Do not put private files in the built `dist/` folder.

## Verification

```powershell
npm test
npm run test:parity
npx playwright install chromium
npm run build
npm run test:browser
```

`test:parity` requires the existing project virtual environment with pandas, or `node scripts/check-parity.js <python-path>`. It extracts only the existing Asset cleaning functions without running Streamlit, using synthetic input and explicit float fixture columns. It never reads the private runtime workbook. It compares every synthetic MYR ledger value, correction count, total assets, weighted yield, and liquid capital. This is a representative parity check, not proof of every possible workbook behavior.

Browser checks run the production build under `/asset_analysis/`, test import/failed replacement, chart/navigation controls, search, CSV download, reset/reload, hostile labels, mobile overflow, filter changes, and network/storage privacy. Screenshots are generated in ignored `tests/output/`. Browser scenarios were validated in Chromium and installed Microsoft Edge. To repeat the native Edge run in PowerShell, set `$env:STATIC_TEST_EDGE='1'` before `npm run test:browser`. Keyboard/screen-reader review and physical-device checks remain release tasks.

## GitHub Pages

Vite emits relative asset paths (`base: './'`) suitable for a project path or a root/custom-domain site. Build with `npm ci` and `npm run build`, and publish only `static-dashboard/dist/` after validation. Never copy private workbooks or exports into that directory.

This workspace currently has no Git remote or Pages deployment workflow. Repository settings, deployment automation, and the live site must be configured separately. Verify the deployed site with synthetic data before using personal data locally.

## Dependencies and licenses

- SheetJS Community Edition 0.20.3, Apache-2.0, installed from its [official distribution](https://docs.sheetjs.com/docs/getting-started/installation/nodejs/).
- Plotly.js distribution 4.1.2, MIT; all required chart trace types bundled locally.
- Vite 8.3.3 and Playwright 1.63.0 are development/verification dependencies only.

The lockfile pins resolved dependencies. The build writes runtime license notices to `dist/THIRD_PARTY_NOTICES.txt`. See [Vite's static deployment guidance](https://vite.dev/guide/static-deploy.html) for the hosting model.
