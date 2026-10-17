import unittest

import pandas as pd

from services.trade_analysis import calculate_trade_analysis, enrich_positions_with_prices


def reference():
    return pd.DataFrame({"ReportingDate": ["2026-01-01"], "Currency": ["MYR"], "Rate": [1.0]})


class TradeAnalysisTests(unittest.TestCase):
    def test_weighted_average_partial_sale(self):
        trades = pd.DataFrame([
            [1, "Broker", "2026-01-01", "AAA", "MY", "Buy", 100, 10, 2, "MYR", None],
            [2, "Broker", "2026-01-02", "AAA", "MY", "Buy", 100, 20, 2, "MYR", None],
            [3, "Broker", "2026-01-03", "AAA", "MY", "Sell", 50, 18, 1, "MYR", None],
        ], columns=["Seq", "Platform", "Trade Date", "Ticker", "Market", "Trade Type", "Quantity", "Price", "Fees", "Currency", "Notes"])
        result = calculate_trade_analysis(trades, reference())
        sell = result.transactions[result.transactions["Seq"] == 3].iloc[0]
        self.assertAlmostEqual(sell["Average Cost"], 15.02)
        self.assertAlmostEqual(sell["Open Quantity"], 150.0)
        self.assertAlmostEqual(sell["Remaining Cost Basis"], 2253.0)
        self.assertAlmostEqual(sell["Realised P/L"], 148.0)

    def test_full_sale_resets_position(self):
        trades = pd.DataFrame([
            [1, "Broker", "2026-01-01", "AAA", "MY", "Buy", 10, 5, 0, "MYR", None],
            [2, "Broker", "2026-01-02", "AAA", "MY", "Sell", 10, 6, 0, "MYR", None],
        ], columns=["Seq", "Platform", "Trade Date", "Ticker", "Market", "Trade Type", "Quantity", "Price", "Fees", "Currency", "Notes"])
        result = calculate_trade_analysis(trades, reference())
        last = result.transactions.iloc[-1]
        self.assertEqual(last["Open Quantity"], 0.0)
        self.assertEqual(last["Remaining Cost Basis"], 0.0)
        self.assertEqual(last["Realised P/L"], 10.0)

    def test_oversell_is_excluded(self):
        trades = pd.DataFrame([
            [1, "Broker", "2026-01-01", "AAA", "MY", "Buy", 5, 10, 0, "MYR", None],
            [2, "Broker", "2026-01-02", "AAA", "MY", "Sell", 6, 11, 0, "MYR", None],
        ], columns=["Seq", "Platform", "Trade Date", "Ticker", "Market", "Trade Type", "Quantity", "Price", "Fees", "Currency", "Notes"])
        result = calculate_trade_analysis(trades, reference())
        sell = result.transactions[result.transactions["Seq"] == 2].iloc[0]
        self.assertEqual(sell["Calculation Status"], "Excluded: oversell")
        self.assertIn("OVERSELL", result.issues["Code"].tolist())

    def test_same_ticker_on_different_platforms_is_separate(self):
        trades = pd.DataFrame([
            [1, "A", "2026-01-01", "AAA", "MY", "Buy", 10, 1, 0, "MYR", None],
            [2, "B", "2026-01-01", "AAA", "MY", "Buy", 20, 1, 0, "MYR", None],
        ], columns=["Seq", "Platform", "Trade Date", "Ticker", "Market", "Trade Type", "Quantity", "Price", "Fees", "Currency", "Notes"])
        result = calculate_trade_analysis(trades, reference())
        self.assertEqual(len(result.positions), 2)

    def test_latest_price_calculates_unrealised_pl(self):
        trades = pd.DataFrame([
            [1, "Broker", "2026-01-01", "AAA", "MY", "Buy", 100, 10, 2, "MYR", None],
        ], columns=["Seq", "Platform", "Trade Date", "Ticker", "Market", "Trade Type", "Quantity", "Price", "Fees", "Currency", "Notes"])
        result = calculate_trade_analysis(trades, reference())
        prices = pd.DataFrame([
            ["AAA", 12.0, "2026-01-02", "MYR", "Technology", "Software", None],
        ], columns=["Ticker", "Current Price", "Price Date", "Currency", "Sector", "Industry", "Notes"])
        positions, issues = enrich_positions_with_prices(result.positions, prices, reference())
        position = positions.iloc[0]
        self.assertAlmostEqual(position["Market Value (MYR)"], 1200.0)
        self.assertAlmostEqual(position["Unrealised P/L (MYR)"], 198.0)
        self.assertAlmostEqual(position["Unrealised Return (%)"], 198.0 / 1002.0 * 100)
        self.assertEqual(position["Price Status"], "Valued")
        self.assertTrue(issues.empty)

    def test_latest_price_date_is_selected(self):
        trades = pd.DataFrame([
            [1, "Broker", "2026-01-01", "AAA", "MY", "Buy", 10, 10, 0, "MYR", None],
        ], columns=["Seq", "Platform", "Trade Date", "Ticker", "Market", "Trade Type", "Quantity", "Price", "Fees", "Currency", "Notes"])
        result = calculate_trade_analysis(trades, reference())
        prices = pd.DataFrame([
            ["AAA", 11.0, "2026-01-01", "MYR"],
            ["AAA", 12.0, "2026-01-02", "MYR"],
        ], columns=["Ticker", "Current Price", "Price Date", "Currency"])
        positions, _ = enrich_positions_with_prices(result.positions, prices, reference())
        self.assertEqual(positions.iloc[0]["Current Price"], 12.0)

    def test_missing_price_remains_visible(self):
        trades = pd.DataFrame([
            [1, "Broker", "2026-01-01", "AAA", "MY", "Buy", 10, 10, 0, "MYR", None],
        ], columns=["Seq", "Platform", "Trade Date", "Ticker", "Market", "Trade Type", "Quantity", "Price", "Fees", "Currency", "Notes"])
        result = calculate_trade_analysis(trades, reference())
        prices = pd.DataFrame(columns=["Ticker", "Current Price", "Price Date", "Currency"])
        positions, issues = enrich_positions_with_prices(result.positions, prices, reference())
        self.assertEqual(positions.iloc[0]["Price Status"], "Missing price")
        self.assertIn("MISSING_PRICE", issues["Code"].tolist())

    def test_price_currency_can_differ_from_cost_currency(self):
        trades = pd.DataFrame([
            [1, "Broker", "2026-01-01", "AAA", "US", "Buy", 2, 100, 0, "MYR", None],
        ], columns=["Seq", "Platform", "Trade Date", "Ticker", "Market", "Trade Type", "Quantity", "Price", "Fees", "Currency", "Notes"])
        result = calculate_trade_analysis(trades, reference())
        prices = pd.DataFrame([
            ["AAA", 30.0, "2026-01-02", "USD"],
        ], columns=["Ticker", "Current Price", "Price Date", "Currency"])
        fx = pd.DataFrame({
            "ReportingDate": ["2026-01-01", "2026-01-01"],
            "Currency": ["MYR", "USD"],
            "Rate": [1.0, 4.0],
        })
        positions, issues = enrich_positions_with_prices(result.positions, prices, fx)
        position = positions.iloc[0]
        self.assertEqual(position["Price Currency"], "USD")
        self.assertAlmostEqual(position["Market Value (MYR)"], 240.0)
        self.assertAlmostEqual(position["Unrealised P/L (MYR)"], 40.0)
        self.assertTrue(pd.isna(position["Unrealised P/L"]))
        self.assertIn("PRICE_CURRENCY_DIFFERENT", issues["Code"].tolist())


if __name__ == "__main__":
    unittest.main()
