# Asset Portfolio Analytics

Asset Portfolio Analytics is a local Streamlit dashboard for reviewing personal or small-team financial data from a structured Excel workbook. It combines asset allocation, historical portfolio snapshots, liquidity and yield analysis, investment trade performance, and expense analysis in one interface.

The application is designed around Malaysian Ringgit (MYR) as the reporting currency and uses Plotly for interactive charts.

> [!IMPORTANT]
> This project processes financial information. The runtime workbook is intentionally excluded from Git. Do not commit personal balances, transactions, account identifiers, or authentication credentials.

## Contents

- [Features](#features)
- [Dashboard modules](#dashboard-modules)
- [Project architecture](#project-architecture)
- [Prerequisites](#prerequisites)
- [Quick start on Windows](#quick-start-on-windows)
- [Manual setup](#manual-setup)
- [Workbook requirements](#workbook-requirements)
- [Business terminology](#business-terminology)
- [Using the dashboard](#using-the-dashboard)
- [Data processing behavior](#data-processing-behavior)
- [Testing and validation](#testing-and-validation)
- [Troubleshooting](#troubleshooting)
- [Deployment](#deployment)
- [Security and privacy](#security-and-privacy)
- [Contributing](#contributing)

## Features

- Reporting-snapshot selection for historical asset views
- Portfolio allocation by type, category, subcategory, account, and currency
- Historical balance and year-to-date movement analysis
- Liquidity classification and emergency-cash readiness
- Interest-rate and estimated annual-yield analysis
- Optional correction of missing foreign-currency MYR values
- Trade cash-flow, realised profit/loss, unrealised profit/loss, and open-position analysis
- Trade-ledger filtering by date, platform, market, currency, ticker, sector, industry, and trade type
- Monthly, quarterly, weekday, and wealth-sustainability expense analysis
- Data-quality reporting for invalid, incomplete, or fallback-calculated records
- Interactive Plotly charts and downloadable tabular results where available

## Dashboard modules

### Asset Analysis

The default dashboard provides:

- total portfolio assets
- currency exposure
- weighted portfolio yield
- liquid-capital ratio
- asset allocation and hierarchy views
- historical growth trends
- liquidity and currency analysis
- an interactive asset ledger

The sidebar controls the reporting snapshot and filters the active view by asset type, category, currency, and liquidity rating.

### Trade Analysis

Trade Analysis calculates transaction cash flow and position performance from the `Trade`, `Prices`, and `Reference` worksheets. It includes:

- total buy cost and transaction fees
- realised, unrealised, and total profit/loss
- latest market value
- remaining open cost basis
- open-position details
- trade-ledger summaries
- data-quality errors and warnings

### Expense Analysis

Expense Analysis reads the `Expenses` worksheet and provides spending patterns across periods and categories, including:

- net expense totals
- monthly and quarterly movement
- weekday patterns
- category and merchant analysis
- period-over-period percentage changes
- wealth-sustainability context derived from available financial data

## Project architecture

```text
AssetAndInvestmentAnalysis/
├── app.py                         # Streamlit entry point and Asset Analysis
├── trade_dashboard.py             # Trade Analysis presentation layer
├── expense_dashboard.py           # Expense Analysis presentation layer
├── services/
│   ├── trade_analysis.py          # Trade loading, validation, and calculations
│   └── expense_analysis.py        # Expense loading, validation, and calculations
├── tests/
│   ├── test_trade_analysis.py
│   └── test_expense_analysis.py
├── documentation/                 # Design, worksheet, and deployment guides
├── Template_InvestmentDetails.xlsx # Local only; excluded from public source
├── InvestmentDetails.xlsx         # Local runtime data; ignored by Git
├── requirements.txt
└── run_dashboard.bat
```

Presentation code is kept in the dashboard modules, while reusable trade and expense calculations live under `services/`. Tests primarily target these service-layer calculations.

## Prerequisites

- Windows, macOS, or Linux
- Python 3.10 or newer recommended
- `pip`
- A populated `InvestmentDetails.xlsx` workbook in the repository root
- A modern browser

The application dependencies are:

- Streamlit
- pandas
- openpyxl
- Plotly

## Quick start on Windows

The included launcher creates a virtual environment, installs or updates dependencies, and starts Streamlit:

```powershell
.\run_dashboard.bat
```

After startup, open [http://localhost:8501](http://localhost:8501) if the browser does not open automatically.

The launcher performs these operations:

1. Checks that Python is available.
2. Creates `.venv` when it does not exist.
3. Upgrades `pip`.
4. Installs packages from `requirements.txt`.
5. Runs `streamlit run app.py`.

## Manual setup

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

If PowerShell blocks activation, the environment can be used without activating it:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

Stop the development server with `Ctrl+C`.

## Workbook requirements

Create a local `InvestmentDetails.xlsx` workbook using the worksheet descriptions below. The application expects the workbook at the repository root with that exact filename. Workbooks, including the existing local template, are excluded from public source because they can contain private metadata and external-link caches. For a data-free public demonstration, use the synthetic demo in [the static dashboard](static-dashboard/README.md).

### `Asset` worksheet

Core columns include:

| Column | Purpose |
|---|---|
| `ReportingDate` | Snapshot date for the asset record |
| `ReportingDate_YYYYMM` | Reporting month identifier |
| `ReportingDate_YYYYQQ` | Reporting quarter identifier |
| `Type` | Primary asset classification |
| `Category` | Broad financial category |
| `SubCategory` | Detailed category |
| `Account` | Account or product identifier |
| `Currency` | Original balance currency |
| `Balance` | Balance in the original currency |
| `BalanceInMYR` | Balance converted to MYR |
| `MaturityDate` | Product maturity date, where applicable |
| `InterestRate` | Decimal interest or return rate |
| `CashLiquidity` | `Very High`, `High`, `Medium`, `Low`, or `N/A` |

### `Reference` worksheet

Contains dated currency conversion rates used by Asset, Trade, and Expense calculations. At minimum, records should identify the reporting date, currency, and conversion rate to MYR.

### `Trade` worksheet

Contains buy and sell transactions. The analysis service validates available columns, normalizes records, calculates fees and MYR values, and matches transactions into positions.

### `Prices` worksheet

Contains security prices used to value open positions and calculate unrealised profit/loss. Without usable prices, realised calculations can still be available, but market value and unrealised results may show as unavailable.

### `Expenses` worksheet

Contains expense transactions and their descriptive dimensions. Expense Analysis uses this worksheet together with reference rates and asset context.

`Expenses.csv` is not the primary runtime source for the current dashboard; the application reads the `Expenses` worksheet from `InvestmentDetails.xlsx`.

## Business terminology

### Liquidity levels

The dashboard presents liquidity as expected time to usable cash under normal conditions:

| Level | Display rule | Meaning |
|---|---:|---|
| Very High | Within 1 business day | Ready cash with no material withdrawal penalty |
| High | 2–7 days | Easy to access with minimal cost or restriction |
| Medium | 8–30 days | Requires notice, settlement, or a moderate exit cost |
| Low | More than 30 days | Long-term or restricted; early exit may cause a loss or penalty |
| N/A | Not assessed | The source record does not have a liquidity classification |

The workbook supplies the `CashLiquidity` category. Users responsible for the workbook should apply the definitions consistently when assigning each asset.

### Open Cost Basis

The remaining purchase cost, in MYR, of currently open positions that can be valued. It excludes the cost already assigned to units that were sold.

### Net Capital Deployed

Total buy amount minus total sell amount for the selected trades:

```text
Net Capital Deployed = Total Buy Amount - Total Sell Amount
```

A positive result means net capital remains invested. A negative result means the selected sales recovered more capital than the selected purchases deployed.

### Realised and unrealised profit/loss

- **Realised P/L** is the gain or loss associated with completed sales.
- **Unrealised P/L** is the difference between the latest available market value and the remaining cost basis of valued open positions.
- **Total P/L** combines realised and unrealised profit/loss when open-position prices are available.

## Using the dashboard

1. Start Streamlit and open the local URL.
2. Select `Asset Analysis`, `Trade Analysis`, or `Expense Analysis` from the sidebar.
3. Choose the reporting snapshot or date range.
4. Apply the relevant sidebar filters.
5. Hover over chart marks and help icons for definitions and calculation context.
6. Review data-quality warnings before relying on calculated results.
7. Use the reload button after changing the workbook while the application is running.

Streamlit caches loaded data for performance. Reloading clears the cache and reads the current workbook contents.

## Data processing behavior

### Foreign-currency correction

When **Enable Excel Correction** is active, Asset Analysis can recalculate a foreign-currency `BalanceInMYR` value when the workbook value is effectively zero but the original-currency balance is non-zero.

The exchange-rate lookup order is:

1. Exact currency and reporting-date match.
2. Same currency with a matching month and day.
3. Closest available date for that currency.

The dashboard reports corrected rows so users can review the applied rate and reference date.

### Data-quality handling

Trade and expense services distinguish usable records from invalid or incomplete records. Errors and warnings can include missing required values, invalid prices, fallback exchange rates, and currency mismatches. Review these messages before using the dashboard for decisions.

### Financial interpretation

This application is an analytical aid, not accounting, tax, legal, or investment advice. Results depend on the completeness and accuracy of the workbook.

## Testing and validation

Run the service-layer test suite from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

If `pytest` is not installed:

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
```

Perform a syntax check for the dashboard modules:

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py trade_dashboard.py expense_dashboard.py
```

Recommended browser smoke-test coverage:

- application loads at `http://localhost:8501`
- all three dashboard modules are selectable
- charts render with the expected workbook data
- filters update metrics and charts
- liquidity hover content remains readable at common viewport sizes
- Open Cost Basis and Net Capital Deployed help tooltips display
- data-quality expanders render without errors

## Troubleshooting

### `InvestmentDetails.xlsx` cannot be found

Confirm that the file is named exactly `InvestmentDetails.xlsx` and is located beside `app.py`.

### Python is not recognized

Install Python and enable **Add Python to PATH**, then open a new terminal.

### PowerShell blocks virtual-environment activation

Use the virtual environment's Python executable directly instead of activating it:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

### Updated workbook data does not appear

Use the relevant **Reload Data** button or restart Streamlit to clear cached data.

### Market value or unrealised P/L is unavailable

Check that the `Prices` worksheet contains valid prices for open positions and that currency information matches the corresponding trade records.

### External font or icon does not load

The dashboard references external font and icon resources. Restricted or offline networks may block them; core calculations and local charts should continue to work.

### Tooltip content is clipped

Plotly tooltips may be constrained by narrow dashboard columns. Increase the browser width or zoom out as a temporary workaround. Responsive tooltip placement should be included in browser regression testing.

## Deployment

A local private Google Cloud Run deployment guide may be available at `documentation/GCP_CLOUD_RUN_DEPLOYMENT_GUIDE.md`; it is deliberately excluded from public source.

The recommended production posture is a private Cloud Run service protected by Identity-Aware Proxy. The application does not currently provide its own authentication layer.

Before deploying, ensure the runtime workbook is included securely. Because `InvestmentDetails.xlsx` is ignored by Git, deployment packaging must handle it deliberately without exposing it in source control.

## Security and privacy

- Keep `InvestmentDetails.xlsx`, `Expenses.csv`, `.env`, and other private exports out of Git.
- Do not expose the Streamlit service publicly unless the data is suitable for public access.
- Prefer private hosting with identity-based access control.
- Validate spreadsheet content if workbooks can be supplied by untrusted users.
- Treat downloaded CSV files as potentially unsafe in spreadsheet software if cells begin with formula characters such as `=`, `+`, `-`, or `@`.
- Rotate any credential accidentally committed to source control; deleting it from the latest commit is not sufficient.
- Review data-quality warnings before sharing reports or making financial decisions.

## Contributing

1. Create a focused branch from `main`.
2. Keep financial data and secrets outside the commit.
3. Add or update tests for calculation changes.
4. Run the test suite and syntax checks.
5. Perform a browser smoke test for presentation changes.
6. Commit with a concise description of the behavior changed.
7. Open a pull request describing the change, user impact, validation, and known limitations.

When changing business terminology, keep the displayed labels, hover definitions, calculation rules, workbook documentation, and tests synchronized.

## Public-source publication check

Before publishing, follow [the publication boundary and staged-file checks](documentation/PUBLICATION.md). The reviewed source snapshot is recorded in `publication-manifest.json`; run `python scripts/check_publication.py` and, after staging, `python scripts/check_publication.py --staged`.
