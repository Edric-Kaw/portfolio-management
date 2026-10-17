import unittest

import pandas as pd

from services.expense_analysis import (
    REQUIRED_EXPENSE_COLUMNS,
    WEEKDAY_ORDER,
    calculate_expense_analysis,
)


def reference():
    return pd.DataFrame({
        "ReportingDate": ["2026-01-01", "2026-01-01"],
        "Currency": ["MYR", "USD"],
        "Rate": [1.0, 4.0],
    })


def expense_rows(rows):
    columns = REQUIRED_EXPENSE_COLUMNS + [
        "Project", "Payment account", "Account receivable", "Merchant", "Address",
        "Tags", "Note", "Image 1", "Image 2", "Image 3",
    ]
    return pd.DataFrame(rows, columns=columns)


def row(date="2026-01-05", amount=-10.0, parent="Dining", currency="MYR", rate=1.0, category="Lunch", note="Meal"):
    return [
        "Expense", currency, amount, rate, category, parent, "Daily Expenses", date, "XXX",
        None, None, None, None, None, None, note, None, None, None,
    ]


class ExpenseAnalysisTests(unittest.TestCase):
    def test_parent_category_header_is_required(self):
        data = expense_rows([row()]).drop(columns=["Parent Category"])
        with self.assertRaisesRegex(ValueError, "Parent Category"):
            calculate_expense_analysis(data, reference())

    def test_blank_parent_category_is_valid_and_filled_by_mapping(self):
        result = calculate_expense_analysis(expense_rows([row(date="2026-01-05 12:00", parent="   ")]), reference())
        transaction = result.transactions.iloc[0]
        self.assertEqual(transaction["Original Parent Category"], "   ")
        self.assertEqual(transaction["Clean Parent Category"], "Dining")
        self.assertEqual(transaction["Mapping Result"], "Standardize")
        self.assertAlmostEqual(transaction["Net Expense (MYR)"], 10.0)

    def test_note_rule_remaps_category_before_dashboard_use(self):
        result = calculate_expense_analysis(
            expense_rows([row(category="Traffic", parent="Traffic", note="Lunch meal")]),
            reference(),
        )
        transaction = result.transactions.iloc[0]
        self.assertEqual(transaction["Clean Category"], "Other Dining")
        self.assertEqual(transaction["Clean Parent Category"], "Dining")
        self.assertEqual(transaction["Mapping Result"], "Remap")

    def test_meal_period_mismatch_is_flagged_for_review(self):
        result = calculate_expense_analysis(
            expense_rows([row(date="2026-01-05 20:00", category="Breakfast", parent="Dining", note="Meal")]),
            reference(),
        )
        transaction = result.transactions.iloc[0]
        self.assertEqual(transaction["Meal Period Status"], "Review")
        self.assertEqual(transaction["Mapping Result"], "Review")
        self.assertIn("CLASSIFICATION_REVIEW", result.issues["Code"].tolist())

    def test_recurring_indicator_is_separate_from_parent_category(self):
        result = calculate_expense_analysis(
            expense_rows([row(category="Telco", parent="Monthly Recurring Expenses", note="Digi postpaid monthly")]),
            reference(),
        )
        transaction = result.transactions.iloc[0]
        self.assertEqual(transaction["Clean Category"], "Phone & Internet")
        self.assertEqual(transaction["Clean Parent Category"], "Utilities & Communication")
        self.assertEqual(transaction["Recurring Status"], "Recurring / Instalment")

    def test_myr_expense_is_positive_dashboard_spending(self):
        result = calculate_expense_analysis(expense_rows([row(amount=-25.5)]), reference())
        transaction = result.transactions.iloc[0]
        self.assertAlmostEqual(transaction["Expense Amount (MYR)"], 25.5)
        self.assertAlmostEqual(transaction["Net Expense (MYR)"], 25.5)

    def test_foreign_currency_uses_source_rate(self):
        result = calculate_expense_analysis(
            expense_rows([row(amount=-10, currency="USD", rate=4.2)]), reference()
        )
        transaction = result.transactions.iloc[0]
        self.assertAlmostEqual(transaction["Net Expense (MYR)"], 42.0)
        self.assertEqual(transaction["FX Method"], "Source rate")

    def test_positive_expense_is_excluded(self):
        result = calculate_expense_analysis(expense_rows([row(amount=10)]), reference())
        transaction = result.transactions.iloc[0]
        self.assertEqual(transaction["Calculation Status"], "Error")
        self.assertTrue(pd.isna(transaction["Net Expense (MYR)"]))
        self.assertIn("INVALID_EXPENSE_SIGN", result.issues["Code"].tolist())

    def test_quarterly_totals_reconcile(self):
        data = expense_rows([
            row(date="2026-01-05", amount=-10, note="One"),
            row(date="2026-03-05", amount=-20, note="Two"),
            row(date="2026-04-05", amount=-30, note="Three"),
        ])
        result = calculate_expense_analysis(data, reference())
        totals = dict(zip(result.quarterly_summary["Quarter Label"], result.quarterly_summary["Net Expense (MYR)"]))
        self.assertAlmostEqual(totals["2026Q1"], 30.0)
        self.assertAlmostEqual(totals["2026Q2"], 30.0)

    def test_weekday_summary_uses_calendar_occurrences(self):
        data = expense_rows([
            row(date="2026-01-05", amount=-10, note="Monday one"),
            row(date="2026-01-12", amount=-20, note="Monday two"),
            row(date="2026-01-13", amount=-15, note="Tuesday"),
        ])
        result = calculate_expense_analysis(data, reference())
        monday = result.weekday_summary[result.weekday_summary["Weekday"] == "Monday"].iloc[0]
        self.assertEqual(monday["Calendar Occurrences"], 2)
        self.assertAlmostEqual(monday["Average per Calendar Occurrence (MYR)"], 15.0)
        self.assertEqual(result.weekday_summary["Weekday"].tolist(), WEEKDAY_ORDER)

    def test_asset_review_period_excludes_opening_snapshot_date(self):
        data = expense_rows([
            row(date="2026-01-01", amount=-10, note="Opening date"),
            row(date="2026-02-01", amount=-20, note="Inside period"),
            row(date="2026-03-31", amount=-30, note="Closing date"),
        ])
        assets = pd.DataFrame({
            "ReportingDate": ["2026-01-01", "2026-03-31"],
            "BalanceInMYR": [1000, 1200],
            "CashLiquidity": ["High", "High"],
        })
        result = calculate_expense_analysis(data, reference(), assets)
        period = result.asset_period_summary.iloc[0]
        self.assertAlmostEqual(period["Review Period Expense (MYR)"], 50.0)
        self.assertAlmostEqual(period["Expense to Assets (%)"], 50 / 1200 * 100)

    def test_exact_duplicate_is_excluded(self):
        duplicate = row()
        result = calculate_expense_analysis(expense_rows([duplicate, duplicate]), reference())
        self.assertTrue((result.transactions["Calculation Status"] == "Error").all())
        self.assertEqual((result.issues["Code"] == "EXACT_DUPLICATE").sum(), 2)


if __name__ == "__main__":
    unittest.main()
