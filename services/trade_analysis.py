"""Trade extraction, validation, and weighted-average cost calculations.

Only source transaction fields are read from the workbook. All cash-flow,
position, FX, and profit/loss fields are generated in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_TRADE_COLUMNS = [
    "Seq",
    "Platform",
    "Trade Date",
    "Ticker",
    "Market",
    "Trade Type",
    "Quantity",
    "Price",
    "Fees",
    "Currency",
]
OPTIONAL_TRADE_COLUMNS = ["Notes"]
SOURCE_TRADE_COLUMNS = REQUIRED_TRADE_COLUMNS + OPTIONAL_TRADE_COLUMNS
VALID_TRADE_TYPES = {"Buy", "Sell"}
REQUIRED_PRICE_COLUMNS = ["Ticker", "Current Price", "Price Date", "Currency"]
OPTIONAL_PRICE_COLUMNS = ["Sector", "Industry", "Notes"]


@dataclass
class TradeAnalysisResult:
    transactions: pd.DataFrame
    positions: pd.DataFrame
    issues: pd.DataFrame


def extract_trade_source(file_path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read only approved source fields from Trade plus FX reference data."""
    trade_header = pd.read_excel(file_path, sheet_name="Trade", nrows=0)
    missing = [c for c in REQUIRED_TRADE_COLUMNS if c not in trade_header.columns]
    if missing:
        raise ValueError(f"Trade worksheet is missing required columns: {', '.join(missing)}")

    available = [c for c in SOURCE_TRADE_COLUMNS if c in trade_header.columns]
    trades = pd.read_excel(file_path, sheet_name="Trade", usecols=available)
    if "Notes" not in trades.columns:
        trades["Notes"] = pd.NA
    reference = pd.read_excel(
        file_path,
        sheet_name="Reference",
        usecols=["ReportingDate", "Currency", "Rate"],
    )
    return trades[SOURCE_TRADE_COLUMNS], reference


def extract_price_source(file_path: str | Path) -> pd.DataFrame:
    """Read the minimal price source plus optional classification fields."""
    header = pd.read_excel(file_path, sheet_name="Prices", nrows=0)
    missing = [c for c in REQUIRED_PRICE_COLUMNS if c not in header.columns]
    if missing:
        raise ValueError(f"Prices worksheet is missing required columns: {', '.join(missing)}")
    available = [c for c in REQUIRED_PRICE_COLUMNS + OPTIONAL_PRICE_COLUMNS if c in header.columns]
    prices = pd.read_excel(file_path, sheet_name="Prices", usecols=available)
    for column in OPTIONAL_PRICE_COLUMNS:
        if column not in prices.columns:
            prices[column] = pd.NA
    return prices[REQUIRED_PRICE_COLUMNS + OPTIONAL_PRICE_COLUMNS]


def _issue(seq, level: str, code: str, message: str) -> dict:
    return {"Seq": seq, "Level": level, "Code": code, "Message": message}


def _prepare_reference(reference: pd.DataFrame) -> pd.DataFrame:
    ref = reference.copy()
    ref["ReportingDate"] = pd.to_datetime(ref["ReportingDate"], errors="coerce")
    ref["Currency"] = ref["Currency"].astype("string").str.strip().str.upper()
    ref["Rate"] = pd.to_numeric(ref["Rate"], errors="coerce")
    return ref.dropna(subset=["ReportingDate", "Currency", "Rate"]).sort_values(
        ["Currency", "ReportingDate"]
    )


def _lookup_fx(currency: str, trade_date: pd.Timestamp, reference: pd.DataFrame):
    if currency == "MYR":
        return 1.0, trade_date, "Base currency"
    candidates = reference[reference["Currency"] == currency]
    if candidates.empty:
        return np.nan, pd.NaT, "Missing"
    prior = candidates[candidates["ReportingDate"] <= trade_date]
    if not prior.empty:
        row = prior.iloc[-1]
        method = "Exact" if row["ReportingDate"] == trade_date else "Latest prior"
    else:
        row = candidates.iloc[0]
        method = "Earliest available"
    return float(row["Rate"]), row["ReportingDate"], method


def calculate_trade_analysis(
    trades: pd.DataFrame, reference: pd.DataFrame
) -> TradeAnalysisResult:
    """Validate transactions and calculate positions using weighted-average cost."""
    df = trades.copy()
    for column in SOURCE_TRADE_COLUMNS:
        if column not in df.columns:
            if column in OPTIONAL_TRADE_COLUMNS:
                df[column] = pd.NA
            else:
                raise ValueError(f"Missing required trade column: {column}")

    df = df[SOURCE_TRADE_COLUMNS]
    df["Trade Date"] = pd.to_datetime(df["Trade Date"], errors="coerce")
    for column in ["Seq", "Quantity", "Price", "Fees"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    for column in ["Platform", "Ticker", "Market", "Trade Type", "Currency"]:
        df[column] = df[column].astype("string").str.strip()
    df["Trade Type"] = df["Trade Type"].str.title()
    df["Market"] = df["Market"].str.upper()
    df["Currency"] = df["Currency"].str.upper()
    df["Fees"] = df["Fees"].fillna(0.0)
    df["Source Row"] = np.arange(2, len(df) + 2)

    issues: list[dict] = []
    duplicate_seq = df["Seq"].notna() & df["Seq"].duplicated(keep=False)
    for _, row in df[duplicate_seq].iterrows():
        issues.append(_issue(row["Seq"], "Error", "DUPLICATE_SEQ", "Seq must be unique."))

    required_text = ["Platform", "Ticker", "Market", "Trade Type", "Currency"]
    valid = pd.Series(True, index=df.index)
    for idx, row in df.iterrows():
        seq = row["Seq"]
        row_errors = []
        if pd.isna(seq):
            row_errors.append(("MISSING_SEQ", "Seq is required."))
        if duplicate_seq.loc[idx]:
            valid.loc[idx] = False
        if pd.isna(row["Trade Date"]):
            row_errors.append(("INVALID_DATE", "Trade Date is missing or invalid."))
        for column in required_text:
            if pd.isna(row[column]) or not str(row[column]).strip():
                row_errors.append(("MISSING_VALUE", f"{column} is required."))
        if row["Trade Type"] not in VALID_TRADE_TYPES:
            row_errors.append(("INVALID_TRADE_TYPE", "Trade Type must be Buy or Sell."))
        if pd.isna(row["Quantity"]) or row["Quantity"] <= 0:
            row_errors.append(("INVALID_QUANTITY", "Quantity must be greater than zero."))
        if pd.isna(row["Price"]) or row["Price"] < 0:
            row_errors.append(("INVALID_PRICE", "Price must be zero or greater."))
        if pd.isna(row["Fees"]) or row["Fees"] < 0:
            row_errors.append(("INVALID_FEES", "Fees must be zero or greater."))
        if row_errors:
            valid.loc[idx] = False
            for code, message in row_errors:
                issues.append(_issue(seq, "Error", code, message))

    df["Calculation Status"] = np.where(valid, "Ready", "Excluded: source error")
    ref = _prepare_reference(reference)
    df = df.sort_values(["Trade Date", "Seq", "Source Row"], na_position="last").reset_index(drop=True)

    output_columns = {
        "Security Key": pd.NA,
        "Trade Value": np.nan,
        "Net Cash Flow": np.nan,
        "Buy Cost (incl fees)": np.nan,
        "Sell Proceeds (net fees)": np.nan,
        "Cumulative Buy Qty": np.nan,
        "Cumulative Sell Qty": np.nan,
        "Open Quantity": np.nan,
        "Remaining Cost Basis": np.nan,
        "Remaining Cost Basis (MYR)": np.nan,
        "Average Cost": np.nan,
        "Realised P/L": np.nan,
        "Cumulative Realised P/L": np.nan,
        "FX Rate to MYR": np.nan,
        "FX Reference Date": pd.NaT,
        "FX Method": pd.NA,
        "Net Cash Flow (MYR)": np.nan,
        "Realised P/L (MYR)": np.nan,
        "Cumulative Realised P/L (MYR)": np.nan,
    }
    for column, value in output_columns.items():
        df[column] = value

    states: dict[str, dict] = {}
    for idx, row in df.iterrows():
        if row["Calculation Status"] != "Ready":
            continue
        key = " | ".join(
            [str(row["Platform"]), str(row["Market"]), str(row["Ticker"]), str(row["Currency"])]
        )
        state = states.setdefault(
            key,
            {"buy_qty": 0.0, "sell_qty": 0.0, "open_qty": 0.0, "cost": 0.0, "cost_myr": 0.0, "realised": 0.0, "realised_myr": 0.0},
        )
        qty = float(row["Quantity"])
        price = float(row["Price"])
        fees = float(row["Fees"])
        trade_value = qty * price
        fx_rate, fx_date, fx_method = _lookup_fx(row["Currency"], row["Trade Date"], ref)
        if pd.isna(fx_rate):
            issues.append(_issue(row["Seq"], "Error", "MISSING_FX", f"No FX rate for {row['Currency']}."))
            df.at[idx, "Calculation Status"] = "Excluded: missing FX"
            continue
        if fx_method == "Earliest available":
            issues.append(
                _issue(
                    row["Seq"],
                    "Warning",
                    "FUTURE_FX_FALLBACK",
                    f"No prior {row['Currency']} FX rate; used earliest available rate dated {fx_date:%Y-%m-%d}.",
                )
            )

        buy_cost = sell_proceeds = realised = 0.0
        if row["Trade Type"] == "Buy":
            buy_cost = trade_value + fees
            net_cash_flow = -buy_cost
            state["buy_qty"] += qty
            state["open_qty"] += qty
            state["cost"] += buy_cost
            state["cost_myr"] += buy_cost * fx_rate
        else:
            if qty > state["open_qty"] + 1e-9:
                issues.append(
                    _issue(
                        row["Seq"],
                        "Error",
                        "OVERSELL",
                        f"Sell quantity {qty:g} exceeds available quantity {state['open_qty']:g} for {key}.",
                    )
                )
                df.at[idx, "Calculation Status"] = "Excluded: oversell"
                continue
            average_cost = state["cost"] / state["open_qty"] if state["open_qty"] else 0.0
            sell_proceeds = trade_value - fees
            removed_cost = average_cost * qty
            removed_cost_myr = (state["cost_myr"] / state["open_qty"] if state["open_qty"] else 0.0) * qty
            realised = sell_proceeds - removed_cost
            net_cash_flow = sell_proceeds
            state["sell_qty"] += qty
            state["open_qty"] -= qty
            state["cost"] -= removed_cost
            state["cost_myr"] -= removed_cost_myr
            state["realised"] += realised
            state["realised_myr"] += realised * fx_rate
            if abs(state["open_qty"]) < 1e-9:
                state["open_qty"] = 0.0
                state["cost"] = 0.0
                state["cost_myr"] = 0.0

        average_cost = state["cost"] / state["open_qty"] if state["open_qty"] else 0.0
        values = {
            "Security Key": key,
            "Trade Value": trade_value,
            "Net Cash Flow": net_cash_flow,
            "Buy Cost (incl fees)": buy_cost,
            "Sell Proceeds (net fees)": sell_proceeds,
            "Cumulative Buy Qty": state["buy_qty"],
            "Cumulative Sell Qty": state["sell_qty"],
            "Open Quantity": state["open_qty"],
            "Remaining Cost Basis": state["cost"],
            "Remaining Cost Basis (MYR)": state["cost_myr"],
            "Average Cost": average_cost,
            "Realised P/L": realised,
            "Cumulative Realised P/L": state["realised"],
            "FX Rate to MYR": fx_rate,
            "FX Reference Date": fx_date,
            "FX Method": fx_method,
            "Net Cash Flow (MYR)": net_cash_flow * fx_rate,
            "Realised P/L (MYR)": realised * fx_rate,
        }
        values["Cumulative Realised P/L (MYR)"] = state["realised_myr"]
        for column, value in values.items():
            df.at[idx, column] = value

    calculated = df[df["Calculation Status"] == "Ready"].copy()
    if calculated.empty:
        positions = pd.DataFrame(
            columns=["Security Key", "Platform", "Market", "Ticker", "Currency", "Open Quantity", "Remaining Cost Basis", "Remaining Cost Basis (MYR)", "Average Cost", "Cumulative Realised P/L", "Cumulative Realised P/L (MYR)", "Last Trade Date"]
        )
    else:
        last_rows = calculated.sort_values(["Trade Date", "Seq"]).groupby("Security Key", as_index=False).tail(1)
        positions = last_rows[[
            "Security Key", "Platform", "Market", "Ticker", "Currency", "Open Quantity",
            "Remaining Cost Basis", "Remaining Cost Basis (MYR)", "Average Cost", "Cumulative Realised P/L",
            "Cumulative Realised P/L (MYR)", "FX Rate to MYR", "Trade Date",
        ]].rename(columns={"Trade Date": "Last Trade Date"})
        positions = positions.sort_values("Remaining Cost Basis (MYR)", ascending=False).reset_index(drop=True)

    issues_df = pd.DataFrame(issues, columns=["Seq", "Level", "Code", "Message"])
    return TradeAnalysisResult(df, positions, issues_df)


def enrich_positions_with_prices(
    positions: pd.DataFrame,
    prices: pd.DataFrame,
    reference: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add latest closing-price valuation and unrealised P/L to positions."""
    valued = positions.copy()
    price_issues: list[dict] = []
    output_defaults = {
        "Current Price": np.nan,
        "Price Date": pd.NaT,
        "Price Currency": pd.NA,
        "Sector": pd.NA,
        "Industry": pd.NA,
        "Price FX Rate to MYR": np.nan,
        "Market Value": np.nan,
        "Market Value (MYR)": np.nan,
        "Unrealised P/L": np.nan,
        "Unrealised P/L (MYR)": np.nan,
        "Unrealised Return (%)": np.nan,
        "Price Status": "Missing price",
    }
    for column, default in output_defaults.items():
        valued[column] = default
    if positions.empty:
        return valued, pd.DataFrame(columns=["Seq", "Level", "Code", "Message"])

    px = prices.copy()
    for column in REQUIRED_PRICE_COLUMNS:
        if column not in px.columns:
            raise ValueError(f"Missing required price column: {column}")
    px["Ticker"] = px["Ticker"].astype("string").str.strip()
    px["Currency"] = px["Currency"].astype("string").str.strip().str.upper()
    px["Current Price"] = pd.to_numeric(px["Current Price"], errors="coerce")
    px["Price Date"] = pd.to_datetime(px["Price Date"], errors="coerce")
    for column in ["Sector", "Industry", "Notes"]:
        if column not in px.columns:
            px[column] = pd.NA

    invalid = px[
        px["Ticker"].isna()
        | px["Currency"].isna()
        | px["Price Date"].isna()
        | px["Current Price"].isna()
        | (px["Current Price"] < 0)
    ]
    for _, row in invalid.iterrows():
        price_issues.append(
            _issue(
                pd.NA,
                "Warning",
                "INVALID_PRICE_ROW",
                f"Price row for {row.get('Ticker', 'unknown')} is incomplete or invalid and was ignored.",
            )
        )
    px = px.drop(invalid.index)
    if not px.empty:
        duplicate_keys = px.duplicated(["Ticker", "Currency", "Price Date"], keep=False)
        for _, row in px[duplicate_keys].iterrows():
            price_issues.append(
                _issue(
                    pd.NA,
                    "Warning",
                    "DUPLICATE_PRICE",
                    f"Duplicate closing price for {row['Ticker']} {row['Currency']} on {row['Price Date']:%Y-%m-%d}; the last row was used.",
                )
            )
        px = (
            px.sort_values(["Ticker", "Currency", "Price Date"])
            .drop_duplicates(["Ticker", "Currency", "Price Date"], keep="last")
            .groupby(["Ticker", "Currency"], as_index=False)
            .tail(1)
        )

    ref = _prepare_reference(reference)
    lookup: dict[str, list[pd.Series]] = {}
    for _, price_row in px.iterrows():
        lookup.setdefault(price_row["Ticker"], []).append(price_row)
    for idx, row in valued.iterrows():
        candidates = lookup.get(row["Ticker"], [])
        matching_currency = [candidate for candidate in candidates if candidate["Currency"] == row["Currency"]]
        if matching_currency:
            price_row = matching_currency[0]
        elif len(candidates) == 1:
            price_row = candidates[0]
            price_issues.append(
                _issue(
                    pd.NA,
                    "Warning",
                    "PRICE_CURRENCY_DIFFERENT",
                    f"{row['Ticker']} cost is recorded in {row['Currency']} while its closing price is quoted in {price_row['Currency']}; MYR values were used for comparison.",
                )
            )
        else:
            price_row = None
        if price_row is None:
            if row["Open Quantity"] <= 1e-9:
                valued.at[idx, "Price Status"] = "Closed position"
                continue
            price_issues.append(
                _issue(
                    pd.NA,
                    "Warning",
                    "MISSING_PRICE",
                    f"No unambiguous closing price for {row['Ticker']}.",
                )
            )
            continue
        price = float(price_row["Current Price"])
        price_date = price_row["Price Date"]
        price_currency = price_row["Currency"]
        for column, value in {
            "Current Price": price,
            "Price Date": price_date,
            "Price Currency": price_currency,
            "Sector": price_row["Sector"],
            "Industry": price_row["Industry"],
        }.items():
            valued.at[idx, column] = value
        if row["Open Quantity"] <= 1e-9:
            valued.at[idx, "Price Status"] = "Closed position"
            continue
        price_fx_rate, _, _ = _lookup_fx(price_currency, price_date, ref)
        if pd.isna(price_fx_rate):
            price_issues.append(
                _issue(pd.NA, "Error", "MISSING_PRICE_FX", f"No FX rate for valuing {row['Ticker']} closing price in {price_currency}.")
            )
            valued.at[idx, "Price Status"] = "Missing valuation FX"
            continue
        market_value = float(row["Open Quantity"]) * price
        same_currency = price_currency == row["Currency"]
        unrealised = market_value - float(row["Remaining Cost Basis"]) if same_currency else np.nan
        cost_basis = float(row["Remaining Cost Basis"])
        market_value_myr = market_value * price_fx_rate
        cost_basis_myr = float(row["Remaining Cost Basis (MYR)"])
        unrealised_myr = market_value_myr - cost_basis_myr
        unrealised_return = unrealised_myr / cost_basis_myr * 100 if cost_basis_myr > 0 else np.nan
        for column, value in {
            "Price FX Rate to MYR": price_fx_rate,
            "Market Value": market_value,
            "Market Value (MYR)": market_value_myr,
            "Unrealised P/L": unrealised,
            "Unrealised P/L (MYR)": unrealised_myr,
            "Unrealised Return (%)": unrealised_return,
            "Price Status": "Valued",
        }.items():
            valued.at[idx, column] = value
    return valued, pd.DataFrame(price_issues, columns=["Seq", "Level", "Code", "Message"])


def load_trade_analysis(file_path: str | Path) -> TradeAnalysisResult:
    trades, reference = extract_trade_source(file_path)
    result = calculate_trade_analysis(trades, reference)
    try:
        prices = extract_price_source(file_path)
    except (ValueError, FileNotFoundError) as exc:
        positions, price_issues = enrich_positions_with_prices(result.positions, pd.DataFrame(columns=REQUIRED_PRICE_COLUMNS), reference)
        missing_issue = pd.DataFrame([
            _issue(pd.NA, "Warning", "PRICES_UNAVAILABLE", f"Unrealised P/L is unavailable: {exc}")
        ])
        issues = pd.concat([result.issues, price_issues, missing_issue], ignore_index=True)
        return TradeAnalysisResult(result.transactions, positions, issues)
    positions, price_issues = enrich_positions_with_prices(result.positions, prices, reference)
    issues = pd.concat([result.issues, price_issues], ignore_index=True)
    return TradeAnalysisResult(result.transactions, positions, issues)
