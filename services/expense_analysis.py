"""Expense extraction, validation, normalization, and dashboard aggregations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import numpy as np
import pandas as pd


REQUIRED_EXPENSE_COLUMNS = [
    "Type",
    "Currency",
    "Amount",
    "Currency rate (Relative standard currency)",
    "Category",
    "Parent Category",
    "Account",
    "Date time",
    "Author",
]
OPTIONAL_EXPENSE_COLUMNS = [
    "Project",
    "Payment account",
    "Account receivable",
    "Merchant",
    "Address",
    "Tags",
    "Note",
    "Image 1",
    "Image 2",
    "Image 3",
]
SOURCE_EXPENSE_COLUMNS = REQUIRED_EXPENSE_COLUMNS + OPTIONAL_EXPENSE_COLUMNS
VALID_EXPENSE_TYPES = {"Expense", "Refund"}
WEEKDAY_ORDER = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]

CATEGORY_MAPPING = {
    "Breakfast": ("Breakfast", "Dining"),
    "Lunch": ("Lunch", "Dining"),
    "Dinner": ("Dinner", "Dining"),
    "Dining": ("Other Dining", "Dining"),
    "Snack": ("Snacks & Drinks", "Dining"),
    "Vegetables": ("Groceries", "Food & Groceries"),
    "Grocery": ("Groceries", "Food & Groceries"),
    "House": ("Mortgage / Housing Fees", "Housing"),
    "House maintenance": ("Home Maintenance", "Housing"),
    "Water and Electricity": ("Utilities", "Housing"),
    "Telco": ("Phone & Internet", "Utilities & Communication"),
    "Digi Postpaid": ("Phone & Internet", "Utilities & Communication"),
    "Traffic": ("Local Transport", "Transport"),
    "Petrol": ("Fuel", "Transport"),
    "Transport": ("Public Transport / Tolls", "Transport"),
    "Travel": ("Travel", "Travel"),
    "Shopping": ("General Shopping", "Shopping & Household"),
    "Daily Use": ("Personal & Household Supplies", "Shopping & Household"),
    "Clothing": ("Clothing & Accessories", "Shopping & Household"),
    "Beauty": ("Personal Care", "Health & Personal Care"),
    "Medical": ("Medical", "Health & Personal Care"),
    "Sports": ("Sports & Fitness", "Leisure"),
    "Entertainment": ("Entertainment", "Leisure"),
    "Event": ("Events", "Leisure"),
    "Gifts": ("Gifts & Donations", "Gifts & Family"),
    "Parents": ("Family Support", "Gifts & Family"),
    "Insurance": ("Insurance", "Financial Commitments"),
    "Installment": ("Instalments / BNPL", "Financial Commitments"),
    "Monthly Recurring Expenses": ("Instalments / Transfers", "Financial Commitments"),
    "Nirvana": ("Funeral Plan", "Financial Commitments"),
}

NOTE_RULES = [
    (r"\b(house loan|mortgage)\b", "Mortgage / Housing Fees", "Housing", "housing loan keyword"),
    (r"\b(maintenance fee|access card|cukai taksiran)\b", "Housing Fees", "Housing", "housing fee keyword"),
    (r"\b(air\s*cond service|locksmith|water filter|plumb(?:ing|er)|home repair)\b", "Home Maintenance", "Housing", "home maintenance keyword"),
    (r"\b(car maintenance|tyre|tire|car battery|engine oil)\b", "Vehicle Maintenance", "Transport", "vehicle maintenance keyword"),
    (r"\b(water bill|electricity|tnb)\b", "Utilities", "Housing", "utility keyword"),
    (r"\b(digi|unifi|postpaid|internet|broadband)\b", "Phone & Internet", "Utilities & Communication", "communication keyword"),
    (r"\b(petrol|petronas|fuel|shell station)\b", "Fuel", "Transport", "fuel keyword"),
    (r"\b(parking|car park|grab|my50|touch n go|tng|rapidkl|lrt|mrt|toll)\b", "Local/Public Transport", "Transport", "local transport keyword"),
    (r"\b(ets|flight|hotel|airbnb|trip|border insurance)\b", "Travel", "Travel", "travel keyword"),
    (r"\b(hair\s*cut|haircut|grooming)\b", "Personal Care", "Health & Personal Care", "personal-care keyword"),
    (r"\b(blood test|dental|dentist|medical|clinic|treatment)\b", "Medical", "Health & Personal Care", "medical keyword"),
    (r"\b(insurance|aia)\b", "Insurance", "Financial Commitments", "insurance keyword"),
    (r"\b(spaylater|\d{1,2}\s*/\s*\d{1,2})\b", "Instalments / BNPL", "Financial Commitments", "instalment pattern"),
    (r"\b(parents?|allowance|family support)\b", "Family Support", "Gifts & Family", "family-support keyword"),
    (r"\b(pickleball|badminton|gym|fitness)\b", "Sports & Fitness", "Leisure", "sports keyword"),
    (r"\b(dimsum|sushi|lunch meal|restaurant|kopitiam|nasi|noodle|mee|coffee|mamak|chicken rice)\b", "Other Dining", "Dining", "dining keyword"),
]

AMBIGUOUS_NOTES = {"apple", "drink", "grocery", "maintenance"}
RECURRING_PATTERN = re.compile(
    r"\b(monthly|recurring|postpaid|mortgage|house loan|insurance|aia|unifi|digi|parents?|allowance|nirvana|spaylater)\b|\b\d{1,2}\s*/\s*\d{1,2}\b"
)


def _normalize_note(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"touch\s*(?:and|&|'n)\s*go", "touch n go", text)
    text = re.sub(r"[^a-z0-9/&'\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _map_expense_classification(row: pd.Series) -> dict:
    """Apply the approved taxonomy and high-confidence note rules."""
    original_category = "" if pd.isna(row["Category"]) else str(row["Category"]).strip()
    original_parent = "" if pd.isna(row["Parent Category"]) else str(row["Parent Category"]).strip()
    note = row["Normalized Note"]
    clean_category = original_category
    clean_parent = original_parent
    reason = "Approved source category-parent pair"
    result = "Valid"

    note_match = None
    for pattern, category, parent, rule_reason in NOTE_RULES:
        if re.search(pattern, note):
            if rule_reason == "dining keyword" and original_category in {
                "Breakfast", "Lunch", "Dinner", "Dining", "Snack", "Grocery", "Vegetables"
            }:
                continue
            note_match = (category, parent, rule_reason)
            break

    if note_match:
        clean_category, clean_parent, rule_reason = note_match
        if (clean_category, clean_parent) != (original_category, original_parent):
            result = "Remap"
            reason = f"High-confidence {rule_reason}"
    elif original_category in CATEGORY_MAPPING:
        clean_category, clean_parent = CATEGORY_MAPPING[original_category]
        if (clean_category, clean_parent) != (original_category, original_parent):
            result = "Standardize"
            reason = "Approved current-category mapping"
    elif original_category == "Maintenance":
        result = "Missing information" if not note else "Review"
        reason = "Maintenance requires a home, vehicle, or personal context in Note"
    else:
        result = "Missing information" if not note else "Review"
        reason = "Category is not present in the approved mapping"

    if note in AMBIGUOUS_NOTES and result not in {"Remap", "Missing information"}:
        result = "Review"
        reason = "Note is too ambiguous to validate the classification"

    meal_status = "Not applicable"
    hour = row["Date time"].hour if pd.notna(row["Date time"]) else None
    if clean_category in {"Breakfast", "Lunch", "Dinner"} and hour is not None:
        valid = (
            (clean_category == "Breakfast" and hour < 11)
            or (clean_category == "Lunch" and 11 <= hour < 16)
            or (clean_category == "Dinner" and hour >= 16)
        )
        meal_status = "Valid" if valid else "Review"
        if not valid and result not in {"Remap", "Missing information"}:
            result = "Review"
            reason = f"{clean_category} is outside its suggested meal-time window"

    recurring = "Recurring / Instalment" if RECURRING_PATTERN.search(note) else "Not identified"
    if clean_category in {"Mortgage / Housing Fees", "Insurance", "Phone & Internet", "Family Support", "Funeral Plan", "Instalments / BNPL"}:
        recurring = "Recurring / Instalment"

    return {
        "Clean Category": clean_category,
        "Clean Parent Category": clean_parent or "Uncategorized",
        "Mapping Result": result,
        "Mapping Reason": reason,
        "Meal Period Status": meal_status,
        "Recurring Status": recurring,
    }


@dataclass
class ExpenseAnalysisResult:
    transactions: pd.DataFrame
    daily_summary: pd.DataFrame
    monthly_summary: pd.DataFrame
    quarterly_summary: pd.DataFrame
    category_summary: pd.DataFrame
    weekday_summary: pd.DataFrame
    asset_period_summary: pd.DataFrame
    issues: pd.DataFrame


def _issue(row, level: str, code: str, message: str) -> dict:
    return {"Source Row": row, "Level": level, "Code": code, "Message": message}


def extract_expense_source(
    file_path: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read approved expense fields, FX reference data, and asset snapshot data."""
    header = pd.read_excel(file_path, sheet_name="Expenses", nrows=0)
    missing = [column for column in REQUIRED_EXPENSE_COLUMNS if column not in header.columns]
    if missing:
        raise ValueError(
            f"Expenses worksheet is missing required columns: {', '.join(missing)}"
        )

    available = [column for column in SOURCE_EXPENSE_COLUMNS if column in header.columns]
    expenses = pd.read_excel(file_path, sheet_name="Expenses", usecols=available)
    for column in OPTIONAL_EXPENSE_COLUMNS:
        if column not in expenses.columns:
            expenses[column] = pd.NA
    expenses = expenses[SOURCE_EXPENSE_COLUMNS]

    reference = pd.read_excel(
        file_path,
        sheet_name="Reference",
        usecols=["ReportingDate", "Currency", "Rate"],
    )
    try:
        assets = pd.read_excel(
            file_path,
            sheet_name="Asset",
            usecols=["ReportingDate", "BalanceInMYR", "CashLiquidity"],
        )
    except (ValueError, KeyError):
        assets = pd.DataFrame(columns=["ReportingDate", "BalanceInMYR", "CashLiquidity"])
    return expenses, reference, assets


def _prepare_reference(reference: pd.DataFrame) -> pd.DataFrame:
    ref = reference.copy()
    ref["ReportingDate"] = pd.to_datetime(ref["ReportingDate"], errors="coerce")
    ref["Currency"] = ref["Currency"].astype("string").str.strip().str.upper()
    ref["Rate"] = pd.to_numeric(ref["Rate"], errors="coerce")
    return ref.dropna(subset=["ReportingDate", "Currency", "Rate"]).sort_values(
        ["Currency", "ReportingDate"]
    )


def _lookup_reference_fx(currency: str, transaction_date: pd.Timestamp, reference: pd.DataFrame):
    if currency == "MYR":
        return 1.0, transaction_date, "Base currency"
    candidates = reference[reference["Currency"] == currency]
    if candidates.empty or pd.isna(transaction_date):
        return np.nan, pd.NaT, "Missing"
    prior = candidates[candidates["ReportingDate"] <= transaction_date]
    if prior.empty:
        return np.nan, pd.NaT, "Missing"
    row = prior.iloc[-1]
    method = "Reference exact" if row["ReportingDate"] == transaction_date.normalize() else "Reference latest prior"
    return float(row["Rate"]), row["ReportingDate"], method


def _empty_summary(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def calculate_expense_analysis(
    expenses: pd.DataFrame,
    reference: pd.DataFrame,
    assets: pd.DataFrame | None = None,
) -> ExpenseAnalysisResult:
    """Validate transactions and calculate reusable expense aggregates."""
    missing = [column for column in REQUIRED_EXPENSE_COLUMNS if column not in expenses.columns]
    if missing:
        raise ValueError(f"Missing required expense column: {', '.join(missing)}")

    df = expenses.copy()
    for column in OPTIONAL_EXPENSE_COLUMNS:
        if column not in df.columns:
            df[column] = pd.NA
    df = df[SOURCE_EXPENSE_COLUMNS]
    df["Source Row"] = np.arange(2, len(df) + 2)
    df["Date time"] = pd.to_datetime(df["Date time"], errors="coerce")
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df["Source Currency Rate"] = pd.to_numeric(
        df["Currency rate (Relative standard currency)"], errors="coerce"
    )
    df["Original Category"] = df["Category"]
    df["Original Parent Category"] = df["Parent Category"]
    df["Original Note"] = df["Note"]

    text_columns = [
        "Type", "Currency", "Category", "Parent Category", "Account", "Author",
        "Project", "Payment account", "Account receivable", "Merchant", "Tags", "Note",
    ]
    for column in text_columns:
        df[column] = df[column].astype("string").str.strip()
    df["Type"] = df["Type"].str.title()
    df["Currency"] = df["Currency"].str.upper()
    df["Normalized Note"] = df["Original Note"].map(_normalize_note)
    mapping = df.apply(_map_expense_classification, axis=1, result_type="expand")
    df = pd.concat([df, mapping], axis=1)
    df["Parent Category Display"] = df["Clean Parent Category"]
    df["Merchant Display"] = (
        df["Merchant"].replace("", pd.NA).fillna(df["Note"].replace("", pd.NA)).fillna("Unspecified")
    )

    ref = _prepare_reference(reference)
    fx_values = []
    issues: list[dict] = []
    today = pd.Timestamp.now().normalize()
    for _, row in df.iterrows():
        source_row = row["Source Row"]
        row_errors = []
        if pd.isna(row["Date time"]):
            row_errors.append(("INVALID_DATE", "Date time is missing or invalid."))
        if pd.isna(row["Amount"]):
            row_errors.append(("INVALID_AMOUNT", "Amount is missing or non-numeric."))
        if row["Type"] not in VALID_EXPENSE_TYPES:
            row_errors.append(("INVALID_TYPE", "Type must be Expense or Refund."))
        if pd.isna(row["Currency"]) or not str(row["Currency"]).strip():
            row_errors.append(("MISSING_CURRENCY", "Currency is required."))
        for column, code in [("Category", "MISSING_CATEGORY"), ("Account", "MISSING_ACCOUNT"), ("Author", "MISSING_AUTHOR")]:
            if pd.isna(row[column]) or not str(row[column]).strip():
                row_errors.append((code, f"{column} is required."))
        if row["Type"] == "Expense" and pd.notna(row["Amount"]) and row["Amount"] > 0:
            row_errors.append(("INVALID_EXPENSE_SIGN", "Expense amounts must be zero or negative."))
        if row["Type"] == "Refund" and pd.notna(row["Amount"]) and row["Amount"] < 0:
            row_errors.append(("INVALID_REFUND_SIGN", "Refund amounts must be zero or positive."))

        currency = "" if pd.isna(row["Currency"]) else str(row["Currency"])
        source_rate = row["Source Currency Rate"]
        if currency == "MYR":
            fx_rate, fx_date, fx_method = 1.0, row["Date time"], "Base currency"
        elif pd.notna(source_rate) and source_rate > 0:
            fx_rate, fx_date, fx_method = float(source_rate), row["Date time"], "Source rate"
        else:
            fx_rate, fx_date, fx_method = _lookup_reference_fx(currency, row["Date time"], ref)
        if pd.isna(fx_rate):
            row_errors.append(("MISSING_FX", f"No MYR conversion rate is available for {currency or 'the transaction currency'}."))
        fx_values.append((fx_rate, fx_date, fx_method))

        for code, message in row_errors:
            issues.append(_issue(source_row, "Error", code, message))
        if pd.notna(row["Date time"]) and row["Date time"].normalize() > today:
            issues.append(_issue(source_row, "Warning", "FUTURE_DATE", "Transaction is dated in the future."))
        if pd.notna(row["Amount"]) and row["Amount"] == 0:
            issues.append(_issue(source_row, "Warning", "ZERO_AMOUNT", "Transaction amount is zero."))
        if row["Parent Category Display"] == "Uncategorized":
            issues.append(_issue(source_row, "Warning", "UNCLASSIFIED_PARENT_CATEGORY", "Parent Category is blank; grouped as Uncategorized."))
        if row["Mapping Result"] == "Review":
            issues.append(_issue(source_row, "Warning", "CLASSIFICATION_REVIEW", row["Mapping Reason"]))
        elif row["Mapping Result"] == "Missing information":
            issues.append(_issue(source_row, "Warning", "MISSING_CLASSIFICATION_CONTEXT", row["Mapping Reason"]))

    missing_payment = df["Payment account"].isna() | df["Payment account"].astype("string").str.strip().eq("")
    if missing_payment.all() and len(df):
        issues.append(_issue(0, "Warning", "MISSING_PAYMENT_ACCOUNT", "Dataset-level check: Payment account is blank for all transactions; account-level reconciliation is unavailable."))
    elif missing_payment.any():
        for source_row in df.loc[missing_payment, "Source Row"]:
            issues.append(_issue(source_row, "Warning", "MISSING_PAYMENT_ACCOUNT", "Payment account is blank; account-level reconciliation is unavailable."))

    df[["FX Rate to MYR", "FX Rate Date", "FX Method"]] = pd.DataFrame(fx_values, index=df.index)

    duplicate_columns = ["Type", "Currency", "Amount", "Category", "Account", "Date time", "Author", "Note"]
    duplicate_mask = df.duplicated(subset=duplicate_columns, keep=False)
    df["Duplicate Status"] = np.where(duplicate_mask, "Exact duplicate", "Unique")
    for source_row in df.loc[duplicate_mask, "Source Row"]:
        issues.append(_issue(source_row, "Error", "EXACT_DUPLICATE", "Transaction duplicates another source row."))

    issue_df = pd.DataFrame(issues, columns=["Source Row", "Level", "Code", "Message"])
    error_rows = set(issue_df.loc[issue_df["Level"] == "Error", "Source Row"]) if not issue_df.empty else set()
    warning_rows = set(issue_df.loc[issue_df["Level"] == "Warning", "Source Row"]) if not issue_df.empty else set()
    df["Calculation Status"] = df["Source Row"].map(
        lambda row: "Error" if row in error_rows else ("Warning" if row in warning_rows else "Ready")
    )

    amount_myr = df["Amount"] * df["FX Rate to MYR"]
    df["Expense Amount (MYR)"] = np.where(df["Type"] == "Expense", -amount_myr, 0.0)
    df["Refund Amount (MYR)"] = np.where(df["Type"] == "Refund", amount_myr, 0.0)
    df["Net Expense (MYR)"] = df["Expense Amount (MYR)"] - df["Refund Amount (MYR)"]
    df.loc[df["Calculation Status"] == "Error", ["Expense Amount (MYR)", "Refund Amount (MYR)", "Net Expense (MYR)"]] = np.nan

    df["Transaction Date"] = df["Date time"].dt.normalize()
    df["Month"] = df["Date time"].dt.to_period("M").dt.to_timestamp()
    df["Month Label"] = df["Date time"].dt.strftime("%b %Y")
    df["Quarter"] = df["Date time"].dt.to_period("Q")
    df["Quarter Label"] = df["Quarter"].astype("string")
    df["Quarter Start"] = df["Quarter"].dt.start_time
    df["Quarter End"] = df["Quarter"].dt.end_time.dt.normalize()
    df["Year"] = df["Date time"].dt.year.astype("Int64")
    df["Weekday Number"] = df["Date time"].dt.weekday + 1
    df["Weekday"] = df["Date time"].dt.day_name()
    df["Weekend Flag"] = np.where(df["Weekday Number"].isin([6, 7]), "Weekend", "Weekday")

    ready = df[df["Calculation Status"] != "Error"].copy()
    if ready.empty:
        empty = _empty_summary([])
        return ExpenseAnalysisResult(df, empty, empty, empty, empty, empty, empty, issue_df)

    daily = ready.groupby(["Transaction Date", "Weekday", "Weekend Flag"], as_index=False).agg(
        **{"Net Expense (MYR)": ("Net Expense (MYR)", "sum"), "Transaction Count": ("Source Row", "count")}
    )
    monthly = ready.groupby("Month", as_index=False).agg(
        **{
            "Gross Expense (MYR)": ("Expense Amount (MYR)", "sum"),
            "Refund (MYR)": ("Refund Amount (MYR)", "sum"),
            "Net Expense (MYR)": ("Net Expense (MYR)", "sum"),
            "Transaction Count": ("Source Row", "count"),
        }
    )
    quarterly = ready.groupby(["Quarter", "Quarter Label"], as_index=False).agg(
        **{
            "Gross Expense (MYR)": ("Expense Amount (MYR)", "sum"),
            "Refund (MYR)": ("Refund Amount (MYR)", "sum"),
            "Net Expense (MYR)": ("Net Expense (MYR)", "sum"),
            "Transaction Count": ("Source Row", "count"),
        }
    ).sort_values("Quarter")
    quarterly["Previous Quarter (MYR)"] = quarterly["Net Expense (MYR)"].shift(1)
    quarterly["QoQ Change (MYR)"] = quarterly["Net Expense (MYR)"] - quarterly["Previous Quarter (MYR)"]
    quarterly["QoQ Change (%)"] = np.where(
        quarterly["Previous Quarter (MYR)"].abs() > 1e-9,
        quarterly["QoQ Change (MYR)"] / quarterly["Previous Quarter (MYR)"] * 100,
        np.nan,
    )
    latest_date = ready["Transaction Date"].max()
    latest_quarter = latest_date.to_period("Q")
    quarterly["Quarter Status"] = np.where(quarterly["Quarter"] == latest_quarter, "Quarter to date", "Complete")

    category = ready.groupby(["Clean Parent Category", "Clean Category"], as_index=False).agg(
        **{"Net Expense (MYR)": ("Net Expense (MYR)", "sum"), "Transaction Count": ("Source Row", "count")}
    ).sort_values("Net Expense (MYR)", ascending=False)

    min_date, max_date = ready["Transaction Date"].min(), ready["Transaction Date"].max()
    calendar = pd.DataFrame({"Transaction Date": pd.date_range(min_date, max_date, freq="D")})
    calendar["Weekday"] = calendar["Transaction Date"].dt.day_name()
    occurrences = calendar.groupby("Weekday").size().rename("Calendar Occurrences")
    weekday_daily = daily.groupby("Weekday").agg(
        **{
            "Total Expense (MYR)": ("Net Expense (MYR)", "sum"),
            "Transaction Count": ("Transaction Count", "sum"),
            "Active Spending Days": ("Transaction Date", "nunique"),
            "Median Daily Expense (MYR)": ("Net Expense (MYR)", "median"),
        }
    ).join(occurrences).reindex(WEEKDAY_ORDER).fillna(0).reset_index()
    weekday_daily["Average per Calendar Occurrence (MYR)"] = np.where(
        weekday_daily["Calendar Occurrences"] > 0,
        weekday_daily["Total Expense (MYR)"] / weekday_daily["Calendar Occurrences"], 0.0,
    )
    weekday_daily["Average per Active Day (MYR)"] = np.where(
        weekday_daily["Active Spending Days"] > 0,
        weekday_daily["Total Expense (MYR)"] / weekday_daily["Active Spending Days"], 0.0,
    )
    total = weekday_daily["Total Expense (MYR)"].sum()
    weekday_daily["Share of Spending (%)"] = np.where(total != 0, weekday_daily["Total Expense (MYR)"] / total * 100, 0.0)

    asset_period = build_asset_period_summary(ready, assets)
    return ExpenseAnalysisResult(df, daily, monthly, quarterly, category, weekday_daily, asset_period, issue_df)


def build_asset_period_summary(expenses: pd.DataFrame, assets: pd.DataFrame | None) -> pd.DataFrame:
    """Aggregate expenses between consecutive Asset reporting snapshots."""
    columns = [
        "Review Start", "Review End", "Opening Assets (MYR)", "Closing Assets (MYR)",
        "Asset Change (MYR)", "Review Period Expense (MYR)", "Expense to Assets (%)",
        "Liquid Assets (MYR)",
    ]
    if assets is None or assets.empty:
        return pd.DataFrame(columns=columns)
    asset_df = assets.copy()
    asset_df["ReportingDate"] = pd.to_datetime(asset_df["ReportingDate"], errors="coerce").dt.normalize()
    asset_df["BalanceInMYR"] = pd.to_numeric(asset_df["BalanceInMYR"], errors="coerce").fillna(0.0)
    snapshots = asset_df.groupby("ReportingDate", as_index=False)["BalanceInMYR"].sum().sort_values("ReportingDate")
    liquid = asset_df[asset_df["CashLiquidity"].isin(["Very High", "High"])].groupby("ReportingDate")["BalanceInMYR"].sum()
    rows = []
    for index in range(1, len(snapshots)):
        start = snapshots.iloc[index - 1]
        end = snapshots.iloc[index]
        period_expense = expenses.loc[
            (expenses["Transaction Date"] > start["ReportingDate"])
            & (expenses["Transaction Date"] <= end["ReportingDate"]),
            "Net Expense (MYR)",
        ].sum()
        closing = float(end["BalanceInMYR"])
        opening = float(start["BalanceInMYR"])
        rows.append({
            "Review Start": start["ReportingDate"],
            "Review End": end["ReportingDate"],
            "Opening Assets (MYR)": opening,
            "Closing Assets (MYR)": closing,
            "Asset Change (MYR)": closing - opening,
            "Review Period Expense (MYR)": float(period_expense),
            "Expense to Assets (%)": period_expense / closing * 100 if closing else np.nan,
            "Liquid Assets (MYR)": float(liquid.get(end["ReportingDate"], 0.0)),
        })
    return pd.DataFrame(rows, columns=columns)


def load_expense_analysis(file_path: str | Path) -> ExpenseAnalysisResult:
    expenses, reference, assets = extract_expense_source(file_path)
    return calculate_expense_analysis(expenses, reference, assets)
