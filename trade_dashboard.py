"""Streamlit presentation for transaction and realised trade analysis."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from services.trade_analysis import load_trade_analysis


@st.cache_data
def get_trade_analysis(file_path: str):
    return load_trade_analysis(file_path)


def _money(value: float) -> str:
    return f"MYR {value:,.2f}"


def render_trade_dashboard(file_path: str) -> None:
    st.markdown("""
    <div class="title-container">
        <h1 class="title-text">Trade Analytics</h1>
        <p class="subtitle-text">Transaction cash flow, open cost basis, and realised and unrealised performance</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        result = get_trade_analysis(file_path)
    except Exception as exc:
        st.error(f"Unable to load Trade analysis: {exc}")
        return

    transactions = result.transactions
    ready = transactions[transactions["Calculation Status"] == "Ready"].copy()
    if ready.empty:
        st.error("No valid Trade rows are available for calculation.")
        if not result.issues.empty:
            st.dataframe(result.issues, hide_index=True, width="stretch")
        return

    st.sidebar.markdown("---")
    st.sidebar.subheader("Trade Filters")
    available_years = sorted(
        ready["Trade Date"].dropna().dt.year.unique().astype(int).tolist(),
        reverse=True,
    )
    selected_years = st.sidebar.multiselect(
        "Trade Year",
        options=available_years,
        default=available_years,
    )
    min_date = ready["Trade Date"].min().date()
    max_date = ready["Trade Date"].max().date()
    date_range = st.sidebar.date_input("Trade date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    start_date, end_date = (date_range if isinstance(date_range, (tuple, list)) and len(date_range) == 2 else (min_date, max_date))
    if selected_years:
        chart_start_date = max(start_date, date(min(selected_years), 1, 1))
        chart_end_date = min(end_date, date(max(selected_years), 12, 31))
    else:
        chart_start_date, chart_end_date = start_date, end_date
    st.sidebar.caption(f"Charts: {chart_start_date:%Y-%m-%d} to {chart_end_date:%Y-%m-%d}")

    def multi(label, column):
        options = sorted(ready[column].dropna().astype(str).unique().tolist())
        return st.sidebar.multiselect(label, options, default=options)

    platforms = multi("Platform", "Platform")
    markets = multi("Market", "Market")
    currencies = multi("Currency", "Currency")
    tickers = multi("Ticker", "Ticker")
    trade_types = multi("Trade Type", "Trade Type")

    position_catalog = result.positions.copy()
    position_catalog["Sector Filter"] = position_catalog["Sector"].fillna("Unclassified")
    position_catalog["Industry Filter"] = position_catalog["Industry"].fillna("Unclassified")
    year_security_keys = ready[
        ready["Trade Date"].dt.year.isin(selected_years)
    ]["Security Key"].dropna().unique()
    sector_options = sorted(position_catalog["Sector Filter"].unique().tolist())
    industry_options = sorted(position_catalog["Industry Filter"].unique().tolist())
    sectors = st.sidebar.multiselect("Sector", sector_options, default=sector_options)
    industries = st.sidebar.multiselect("Industry", industry_options, default=industry_options)

    selected_keys = position_catalog[
        position_catalog["Platform"].isin(platforms)
        & position_catalog["Market"].isin(markets)
        & position_catalog["Currency"].isin(currencies)
        & position_catalog["Ticker"].isin(tickers)
        & position_catalog["Sector Filter"].isin(sectors)
        & position_catalog["Industry Filter"].isin(industries)
        & position_catalog["Security Key"].isin(year_security_keys)
    ]["Security Key"].dropna().unique()

    filtered = ready[
        ready["Trade Date"].dt.date.between(start_date, end_date)
        & ready["Trade Date"].dt.year.isin(selected_years)
        & ready["Platform"].isin(platforms)
        & ready["Market"].isin(markets)
        & ready["Currency"].isin(currencies)
        & ready["Ticker"].isin(tickers)
        & ready["Trade Type"].isin(trade_types)
        & ready["Security Key"].isin(selected_keys)
    ].copy()

    positions = result.positions[result.positions["Security Key"].isin(selected_keys)].copy()

    if filtered.empty:
        st.warning("No transactions match the selected filters.")
        return

    buy_cost = filtered["Buy Cost (incl fees)"] * filtered["FX Rate to MYR"]
    sell_proceeds = filtered["Sell Proceeds (net fees)"] * filtered["FX Rate to MYR"]
    total_fees = filtered["Fees"] * filtered["FX Rate to MYR"]
    realised = filtered["Realised P/L (MYR)"].sum()
    sold_cost = sell_proceeds.sum() - realised
    realised_return = realised / sold_cost * 100 if sold_cost > 0 else 0.0
    open_positions = int((positions["Open Quantity"] > 1e-9).sum())
    priced_positions = positions[
        (positions["Open Quantity"] > 1e-9) & (positions["Price Status"] == "Valued")
    ]
    market_value = priced_positions["Market Value (MYR)"].sum()
    open_cost_basis = priced_positions["Remaining Cost Basis (MYR)"].sum()
    unrealised = priced_positions["Unrealised P/L (MYR)"].sum()
    unrealised_return = unrealised / open_cost_basis * 100 if open_cost_basis > 0 else 0.0
    total_pl = realised + unrealised
    has_prices = not priced_positions.empty

    cards = st.columns(4)
    cards[0].metric("Total Buy Cost", _money(buy_cost.sum()))
    cards[1].metric("Realised P/L", _money(realised), f"{realised_return:+.2f}% on realised cost")
    cards[2].metric("Unrealised P/L", _money(unrealised) if has_prices else "Unavailable", f"{unrealised_return:+.2f}% on valued open cost" if has_prices else "Prices worksheet required")
    cards[3].metric("Total P/L", _money(total_pl) if has_prices else _money(realised), "Realised + unrealised" if has_prices else "Realised only")
    cards2 = st.columns(4)
    cards2[0].metric("Latest Market Value", _money(market_value) if has_prices else "Unavailable", f"{len(priced_positions)} of {open_positions} open positions valued")
    cards2[1].metric(
        "Open Cost Basis",
        _money(open_cost_basis) if has_prices else "Unavailable",
        help=(
            "The remaining purchase cost of currently open, valued positions, "
            "shown in MYR. It excludes the cost already assigned to units sold."
        ),
    )
    cards2[2].metric("Transaction Fees", _money(total_fees.sum()))
    cards2[3].metric("Data Issues", f"{len(result.issues)}", "Errors and warnings")

    if not result.issues.empty:
        error_count = int((result.issues["Level"] == "Error").sum())
        warning_count = int((result.issues["Level"] == "Warning").sum())
        with st.expander(f"Data quality — {error_count} errors, {warning_count} warnings", expanded=error_count > 0):
            st.dataframe(result.issues, hide_index=True, width="stretch")

    tab1, tab2, tab3, tab4 = st.tabs(["Activity", "Performance", "Open Positions", "Trade Ledger"])

    with tab1:
        activity = filtered.copy()
        activity["Month"] = activity["Trade Date"].dt.to_period("M").dt.to_timestamp()
        activity["Buy Cost (MYR)"] = activity["Buy Cost (incl fees)"] * activity["FX Rate to MYR"]
        activity["Sell Proceeds (MYR)"] = activity["Sell Proceeds (net fees)"] * activity["FX Rate to MYR"]
        monthly = activity.groupby("Month", as_index=False)[["Buy Cost (MYR)", "Sell Proceeds (MYR)"]].sum()
        melted = monthly.melt("Month", var_name="Cash Flow Type", value_name="Amount (MYR)")
        date_label = f"{chart_start_date:%d %b %Y} to {chart_end_date:%d %b %Y}"
        fig = px.bar(melted, x="Month", y="Amount (MYR)", color="Cash Flow Type", barmode="group", title=f"Monthly Buy Cost vs Sell Proceeds — {date_label}")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        fig.update_xaxes(range=[chart_start_date.isoformat(), chart_end_date.isoformat()], tickformat="%b %Y", title="Selected Date Range")
        st.plotly_chart(fig, width="stretch")
        activity = activity.sort_values(["Trade Date", "Seq"])
        activity["Cumulative Net Cash Flow (MYR)"] = activity["Net Cash Flow (MYR)"].cumsum()
        fig_cash = px.line(activity, x="Trade Date", y="Cumulative Net Cash Flow (MYR)", markers=True, title=f"Cumulative Investment Cash Flow — {date_label}")
        fig_cash.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        fig_cash.update_xaxes(range=[chart_start_date.isoformat(), chart_end_date.isoformat()], tickformat="%b %Y", title="Selected Date Range")
        st.plotly_chart(fig_cash, width="stretch")

    with tab2:
        realised_rows = filtered[filtered["Trade Type"] == "Sell"].copy()
        if realised_rows.empty:
            st.info("No sell transactions match the current filters.")
        else:
            by_ticker = realised_rows.groupby("Ticker", as_index=False)["Realised P/L (MYR)"].sum().sort_values("Realised P/L (MYR)")
            fig_pl = px.bar(by_ticker, x="Realised P/L (MYR)", y="Ticker", orientation="h", color="Realised P/L (MYR)", color_continuous_scale="RdYlGn", title="Realised P/L by Ticker")
            fig_pl.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", coloraxis_showscale=False)
            st.plotly_chart(fig_pl, width="stretch")
            realised_rows = realised_rows.sort_values(["Trade Date", "Seq"])
            realised_rows["Cumulative Realised P/L (MYR) — Filtered"] = realised_rows["Realised P/L (MYR)"].cumsum()
            fig_curve = px.line(realised_rows, x="Trade Date", y="Cumulative Realised P/L (MYR) — Filtered", markers=True, title="Cumulative Realised P/L")
            fig_curve.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_curve, width="stretch")
        if priced_positions.empty:
            st.info("No open positions have a valid latest closing price.")
        else:
            unrealised_by_ticker = priced_positions.groupby("Ticker", as_index=False)["Unrealised P/L (MYR)"].sum().sort_values("Unrealised P/L (MYR)")
            fig_unrealised = px.bar(
                unrealised_by_ticker,
                x="Unrealised P/L (MYR)",
                y="Ticker",
                orientation="h",
                color="Unrealised P/L (MYR)",
                color_continuous_scale="RdYlGn",
                title="Unrealised P/L by Ticker — Latest Closing Prices",
            )
            fig_unrealised.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", coloraxis_showscale=False)
            st.plotly_chart(fig_unrealised, width="stretch")

            sector_col, industry_col = st.columns(2)
            sector_values = priced_positions.copy()
            sector_values["Sector"] = sector_values["Sector"].fillna("Unclassified")
            by_sector = sector_values.groupby("Sector", as_index=False)["Market Value (MYR)"].sum().sort_values("Market Value (MYR)", ascending=False)
            fig_sector = px.pie(
                by_sector,
                names="Sector",
                values="Market Value (MYR)",
                hole=0.45,
                title="Latest Market Value by Sector",
            )
            fig_sector.update_layout(paper_bgcolor="rgba(0,0,0,0)")
            sector_col.plotly_chart(fig_sector, width="stretch")

            industry_values = priced_positions.copy()
            industry_values["Industry"] = industry_values["Industry"].fillna("Unclassified")
            by_industry = industry_values.groupby("Industry", as_index=False)["Unrealised P/L (MYR)"].sum().sort_values("Unrealised P/L (MYR)")
            fig_industry = px.bar(
                by_industry,
                x="Unrealised P/L (MYR)",
                y="Industry",
                orientation="h",
                color="Unrealised P/L (MYR)",
                color_continuous_scale="RdYlGn",
                title="Unrealised P/L by Industry",
            )
            fig_industry.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", coloraxis_showscale=False)
            industry_col.plotly_chart(fig_industry, width="stretch")

    with tab3:
        open_df = positions[positions["Open Quantity"] > 1e-9].copy()
        if open_df.empty:
            st.info("No open positions match the selected security filters.")
        else:
            display_cols = ["Platform", "Market", "Ticker", "Currency", "Open Quantity", "Average Cost", "Current Price", "Price Currency", "Price Date", "Market Value", "Market Value (MYR)", "Remaining Cost Basis", "Remaining Cost Basis (MYR)", "Unrealised P/L", "Unrealised P/L (MYR)", "Unrealised Return (%)", "Cumulative Realised P/L (MYR)", "Price Status", "Sector", "Industry", "Last Trade Date"]
            st.dataframe(open_df[display_cols], hide_index=True, width="stretch", column_config={
                "Open Quantity": st.column_config.NumberColumn(format="%,.6f"),
                "Average Cost": st.column_config.NumberColumn(format="%,.4f"),
                "Remaining Cost Basis": st.column_config.NumberColumn(format="%,.2f"),
                "Remaining Cost Basis (MYR)": st.column_config.NumberColumn(format="%,.2f"),
                "Current Price": st.column_config.NumberColumn(format="%,.4f"),
                "Price Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "Market Value": st.column_config.NumberColumn(format="%,.2f"),
                "Market Value (MYR)": st.column_config.NumberColumn(format="%,.2f"),
                "Unrealised P/L": st.column_config.NumberColumn(format="%,.2f"),
                "Unrealised P/L (MYR)": st.column_config.NumberColumn(format="%,.2f"),
                "Unrealised Return (%)": st.column_config.NumberColumn(format="%.2f%%"),
                "Cumulative Realised P/L (MYR)": st.column_config.NumberColumn(format="%,.2f"),
                "Last Trade Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
            })

    with tab4:
        ledger_buy_amount = (
            filtered["Buy Cost (incl fees)"] * filtered["FX Rate to MYR"]
        ).sum()
        ledger_sell_amount = (
            filtered["Sell Proceeds (net fees)"] * filtered["FX Rate to MYR"]
        ).sum()
        ledger_net_amount = ledger_buy_amount - ledger_sell_amount

        st.markdown("#### Trade Ledger Summary")
        ledger_cards = st.columns(4)
        ledger_cards[0].metric("Total Trades", f"{len(filtered):,}")
        ledger_cards[1].metric("Total Buy Amount", _money(ledger_buy_amount))
        ledger_cards[2].metric("Total Sell Amount", _money(ledger_sell_amount))
        net_capital_context = "Net invested" if ledger_net_amount >= 0 else "Net capital recovered"
        ledger_cards[3].metric(
            "Net Capital Deployed",
            _money(ledger_net_amount),
            net_capital_context,
            delta_color="off",
            help=(
                "Total buy amount minus total sell amount for the selected trades. "
                "A positive value means net capital invested; a negative value means "
                "net capital recovered."
            ),
        )

        ledger_summary = pd.DataFrame({
            "Metric": ["Total Buy Amount", "Total Sell Amount", "Net Capital Deployed"],
            "Amount (MYR)": [ledger_buy_amount, ledger_sell_amount, ledger_net_amount],
        })
        fig_ledger_summary = px.bar(
            ledger_summary,
            x="Metric",
            y="Amount (MYR)",
            color="Metric",
            text="Amount (MYR)",
            title=f"Trade Amount Summary — {len(filtered):,} Trades",
            color_discrete_map={
                "Total Buy Amount": "#0ea5e9",
                "Total Sell Amount": "#22c55e",
                "Net Capital Deployed": "#f59e0b" if ledger_net_amount >= 0 else "#ef4444",
            },
        )
        fig_ledger_summary.update_traces(texttemplate="MYR %{text:,.2f}", textposition="outside")
        fig_ledger_summary.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            yaxis_title="Amount (MYR)",
        )
        st.plotly_chart(fig_ledger_summary, width="stretch")

        search = st.text_input("Search ticker, platform, market, or notes", "")
        ledger = filtered.copy()
        if search:
            mask = pd.Series(False, index=ledger.index)
            for column in ["Ticker", "Platform", "Market", "Notes"]:
                mask |= ledger[column].astype("string").str.contains(search, case=False, na=False)
            ledger = ledger[mask]
        display_cols = ["Seq", "Trade Date", "Platform", "Ticker", "Market", "Trade Type", "Quantity", "Price", "Fees", "Currency", "Trade Value", "Net Cash Flow", "Open Quantity", "Average Cost", "Realised P/L", "FX Rate to MYR", "Realised P/L (MYR)", "Calculation Status", "Notes"]
        st.dataframe(ledger[display_cols].sort_values("Seq", ascending=False), hide_index=True, width="stretch", column_config={
            "Seq": st.column_config.NumberColumn(format="%,.0f"),
            "Quantity": st.column_config.NumberColumn(format="%,.6f"),
            "Price": st.column_config.NumberColumn(format="%,.4f"),
            "Fees": st.column_config.NumberColumn(format="%,.2f"),
            "Trade Value": st.column_config.NumberColumn(format="%,.2f"),
            "Net Cash Flow": st.column_config.NumberColumn(format="%,.2f"),
            "Open Quantity": st.column_config.NumberColumn(format="%,.6f"),
            "Average Cost": st.column_config.NumberColumn(format="%,.4f"),
            "Realised P/L": st.column_config.NumberColumn(format="%,.2f"),
            "FX Rate to MYR": st.column_config.NumberColumn(format="%,.5f"),
            "Realised P/L (MYR)": st.column_config.NumberColumn(format="%,.2f"),
        })
        st.download_button("Export filtered calculated ledger", ledger[display_cols].to_csv(index=False).encode("utf-8"), "calculated_trade_ledger.csv", "text/csv")

    st.caption("Methodology: weighted-average cost by Platform + Market + Ticker + Currency. Unrealised P/L uses the latest closing price by Ticker + Currency and the latest applicable FX rate. Derived values are calculated in Python; source workbook formulas are not used as inputs.")
