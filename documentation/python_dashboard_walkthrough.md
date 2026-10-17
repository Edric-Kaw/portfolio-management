# Python Dashboard Walkthrough

The asset analysis dashboard uses Python, Streamlit, and Plotly to explore portfolio allocation, historical changes, liquidity, and estimated yield. It reads a user-supplied `InvestmentDetails.xlsx` workbook from the project directory.

This walkthrough contains no actual portfolio records or balances. Keep financial workbooks and exports out of the public repository.

## Project Files

- [app.py](../app.py): Dashboard entry point, workbook loading, data validation, and interactive views.
- [requirements.txt](../requirements.txt): Python dependencies.
- [run_dashboard.bat](../run_dashboard.bat): Windows launcher for environment setup and dashboard startup.
- [trade_dashboard.py](../trade_dashboard.py): Trade analysis interface.
- [expense_dashboard.py](../expense_dashboard.py): Expense analysis interface.
- [services](../services/): Shared analysis logic.

## Asset Dashboard Features

### Summary Metrics

The dashboard presents total assets for the selected snapshot, changes from a previous snapshot, currency exposure, and yield-related metrics. Filters allow users to focus on particular asset groups.

### Exchange-Rate Audit and Correction

The dashboard can identify missing or inconsistent converted balances and calculate MYR values using exchange rates from the workbook's `Reference` sheet.

The lookup checks for an exact reporting date, then a matching month and day regardless of year, and finally the closest available date. Fallback rates require review because they may come from a different reporting period.

Warnings and audit details help users inspect corrections. The correction toggle allows comparison with the original workbook values. Corrections are calculated in memory rather than written back to the source workbook.

### Allocation Hierarchy

Interactive charts display the hierarchy `Type → Category → SubCategory → Account`. Users can drill into groups to explore their contribution to the selected portfolio snapshot.

### Historical Comparisons

Stacked charts compare asset classes across reporting snapshots. Change tables show which accounts and categories increased or decreased between selected periods.

### Liquidity and Estimated Yield

Liquidity charts group assets by their `CashLiquidity` classification. Yield views identify interest-bearing assets and estimate annual earnings from the supplied balances and rates. These estimates depend on workbook inputs and do not guarantee future returns.

### Account Ledger

A searchable account table provides access to individual asset entries. Available filters narrow the analysis by asset type, category, currency, and liquidity.

## Run Locally

### Prerequisites

- Python with `pip` and virtual-environment support.
- Project dependencies listed in [requirements.txt](../requirements.txt).
- A compatible workbook named `InvestmentDetails.xlsx`, stored locally in the project root. Use synthetic data when demonstrating or testing the dashboard publicly.

See the [project README](../README.md) and [Asset worksheet field descriptions](Header%20description%20for%20Asset%20Worksheet.md) for workbook guidance.

### Windows Launcher

Double-click [run_dashboard.bat](../run_dashboard.bat) from the project folder. The launcher manages the virtual environment, dependency installation, and Streamlit startup.

### PowerShell

Run these commands from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the local URL printed by Streamlit, typically `http://localhost:8501`. The dashboard is available while the process is running. Stop it with `Ctrl+C` in the terminal.

## Check the Dashboard

1. Start with a synthetic workbook containing the required worksheet columns.
2. Confirm that reporting dates, balances, currencies, and rates are interpreted correctly.
3. Check allocation drill-downs, snapshot comparisons, filters, and the account ledger.
4. Inspect any validation warnings and exchange-rate fallbacks before relying on calculated totals.
5. Compare corrected and original values using the correction toggle.

## Keep Public Examples Private-Data Free

- Exclude real workbooks, expense exports, backups, and generated reports from Git.
- Use invented accounts and transactions in examples and screenshots.
- For a public template, generate a fresh workbook with neutral author metadata and no external workbook links or cached private data.
- Review staged files before committing; ignore rules do not protect files already tracked by Git.
- Run the dashboard locally for personal data. Review access controls and data handling separately before hosting it for other users.
