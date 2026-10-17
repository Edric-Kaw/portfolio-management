"""Streamlit presentation for expense and spending-pattern analysis."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from services.expense_analysis import WEEKDAY_ORDER, load_expense_analysis


@st.cache_data
def get_expense_analysis(file_path: str):
    return load_expense_analysis(file_path)


def _money(value: float) -> str:
    return f"MYR {value:,.2f}"


def _format_amount(value) -> str:
    return "" if pd.isna(value) else f"{float(value):,.2f}"


def _format_percent(value) -> str:
    return "" if pd.isna(value) else f"{float(value):+,.1f}%"


def _join_unique_notes(values: pd.Series) -> str:
    notes = []
    for value in values:
        if pd.isna(value):
            continue
        note = str(value).strip()
        if note and note not in notes:
            notes.append(note)
    return "; ".join(notes)


def _transparent(fig):
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def _period_change_chart(data: pd.DataFrame, x: str, title: str, change_name: str):
    """Show spending bars with previous-period percentage change on a second axis."""
    chart = data.copy()
    chart["Previous Period (MYR)"] = chart["Net Expense (MYR)"].shift(1)
    chart[change_name] = np.where(
        chart["Previous Period (MYR)"].abs() > 1e-9,
        (chart["Net Expense (MYR)"] / chart["Previous Period (MYR)"] - 1) * 100,
        np.nan,
    )
    amount_labels = [f"{value / 1000:.1f}k" if abs(value) >= 1000 else f"{value:,.0f}" for value in chart["Net Expense (MYR)"]]
    change_labels = [f"{value:+.1f}%" if pd.notna(value) else "" for value in chart[change_name]]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=chart[x], y=chart["Net Expense (MYR)"], name="Net Expense (MYR)",
            text=amount_labels, textposition="inside",
            hovertemplate="%{x}<br>Net expense: MYR %{y:,.2f}<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=chart[x], y=chart[change_name], name=change_name, mode="lines+markers+text",
            text=change_labels, textposition="top center", connectgaps=False,
            hovertemplate=f"%{{x}}<br>{change_name}: %{{y:+.1f}}%<extra></extra>",
        ),
        secondary_y=True,
    )
    fig.update_yaxes(title_text="Net Expense (MYR)", secondary_y=False)
    fig.update_yaxes(title_text="Change vs previous (%)", ticksuffix="%", zeroline=True, secondary_y=True)
    fig.update_layout(title=title, legend_title_text="Measure", hovermode="x unified")
    return _transparent(fig), chart


def render_expense_dashboard(file_path: str) -> None:
    st.markdown("""
    <div class="title-container">
        <h1 class="title-text">Expense Analytics</h1>
        <p class="subtitle-text">Monthly, quarterly, weekday, and wealth-sustainability analysis</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        result = get_expense_analysis(file_path)
    except Exception as exc:
        st.error(f"Unable to load Expense analysis: {exc}")
        return

    transactions = result.transactions
    ready = transactions[transactions["Calculation Status"] != "Error"].copy()
    if ready.empty:
        st.error("No valid Expense rows are available for calculation.")
        if not result.issues.empty:
            st.dataframe(result.issues, hide_index=True, width="stretch")
        return

    st.sidebar.markdown("---")
    st.sidebar.subheader("Expense Filters")
    min_date = ready["Transaction Date"].min().date()
    max_date = ready["Transaction Date"].max().date()
    selected_dates = st.sidebar.date_input(
        "Expense date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
    )
    if isinstance(selected_dates, (tuple, list)) and len(selected_dates) == 2:
        start_date, end_date = selected_dates
    else:
        start_date, end_date = min_date, max_date
    granularity = st.sidebar.radio("Trend granularity", ["Monthly", "Quarterly"], horizontal=True)

    def multi(label: str, column: str):
        options = sorted(ready[column].dropna().astype(str).unique().tolist())
        return st.sidebar.multiselect(label, options, default=options)

    parent_categories = multi("Parent Category", "Clean Parent Category")
    categories = multi("Category", "Clean Category")
    accounts = multi("Account", "Account")
    authors = multi("Author", "Author")
    payment_options = sorted(ready["Payment account"].dropna().astype(str).unique().tolist())
    payment_accounts = (
        st.sidebar.multiselect("Payment account", payment_options, default=payment_options)
        if payment_options else []
    )
    search = st.sidebar.text_input("Search merchant or note")

    filtered = ready[
        ready["Transaction Date"].dt.date.between(start_date, end_date)
        & ready["Clean Parent Category"].isin(parent_categories)
        & ready["Clean Category"].isin(categories)
        & ready["Account"].isin(accounts)
        & ready["Author"].isin(authors)
    ].copy()
    if payment_options:
        filtered = filtered[filtered["Payment account"].isin(payment_accounts)]
    if search:
        query = search.casefold()
        filtered = filtered[
            filtered["Merchant Display"].fillna("").str.casefold().str.contains(query, regex=False)
            | filtered["Note"].fillna("").str.casefold().str.contains(query, regex=False)
        ]
    if filtered.empty:
        st.warning("No expense transactions match the selected filters.")
        return

    total_expense = filtered["Net Expense (MYR)"].sum()
    transaction_count = len(filtered)
    average_transaction = total_expense / transaction_count if transaction_count else 0.0
    selected_quarter = filtered["Quarter"].max()
    current_quarter = filtered[filtered["Quarter"] == selected_quarter]
    quarter_expense = current_quarter["Net Expense (MYR)"].sum()
    previous_quarter = selected_quarter - 1
    previous_expense = ready[ready["Quarter"] == previous_quarter]["Net Expense (MYR)"].sum()
    qoq = (quarter_expense / previous_expense - 1) * 100 if abs(previous_expense) > 1e-9 else np.nan
    category_totals = filtered.groupby("Clean Category")["Net Expense (MYR)"].sum().sort_values(ascending=False)
    top_category = category_totals.index[0] if not category_totals.empty else "Unavailable"

    cards = st.columns(5)
    cards[0].metric("Selected-period spending", _money(total_expense))
    cards[1].metric(f"{selected_quarter} spending", _money(quarter_expense), f"{qoq:+.1f}% QoQ" if pd.notna(qoq) else "No prior-quarter baseline")
    cards[2].metric("Average transaction", _money(average_transaction))
    cards[3].metric("Transactions", f"{transaction_count:,}")
    cards[4].metric("Largest category", top_category, _money(category_totals.iloc[0]) if not category_totals.empty else None)

    if not result.issues.empty:
        error_count = int((result.issues["Level"] == "Error").sum())
        warning_count = int((result.issues["Level"] == "Warning").sum())
        with st.expander(f"Data quality — {error_count} errors, {warning_count} warnings", expanded=error_count > 0):
            st.dataframe(result.issues, hide_index=True, width="stretch")

    quality_counts = (
        transactions.groupby("Mapping Result", as_index=False)
        .agg(Records=("Source Row", "count"), **{"Net Expense (MYR)": ("Net Expense (MYR)", "sum")})
        .sort_values("Records", ascending=False)
    )
    with st.expander("Classification mapping outcomes", expanded=False):
        st.caption("Dashboard charts use Clean Category and Clean Parent Category. Original source values remain available in the ledger.")
        quality_display = quality_counts.copy()
        quality_display["Records"] = quality_display["Records"].map(lambda value: f"{int(value):,}")
        quality_display["Net Expense (MYR)"] = quality_display["Net Expense (MYR)"].map(_format_amount)
        st.dataframe(quality_display, hide_index=True, width="stretch")

    overview, quarterly_tab, patterns, categories_tab, asset_tab, ledger_tab = st.tabs([
        "Spending Overview", "Quarterly Review", "Spending Patterns",
        "Category Analysis", "Assets vs Expenses", "Expense Ledger",
    ])

    with overview:
        if granularity == "Monthly":
            trend = filtered.groupby("Month", as_index=False)["Net Expense (MYR)"].sum().sort_values("Month")
            x, title, change_name = "Month", "Monthly Spending and Month-over-Month Change", "MoM Change (%)"
        else:
            trend = filtered.groupby(["Quarter", "Quarter Label"], as_index=False)["Net Expense (MYR)"].sum().sort_values("Quarter")
            x, title, change_name = "Quarter Label", "Quarterly Spending and Quarter-over-Quarter Change", "QoQ Change (%)"
        fig, _ = _period_change_chart(trend, x, title, change_name)
        st.plotly_chart(fig, width="stretch")

        col1, col2 = st.columns(2)
        parent = filtered.groupby("Clean Parent Category", as_index=False)["Net Expense (MYR)"].sum().sort_values("Net Expense (MYR)", ascending=False)
        col1.plotly_chart(_transparent(px.bar(parent, x="Net Expense (MYR)", y="Clean Parent Category", orientation="h", title="Spending by Parent Category")), width="stretch")
        cumulative = filtered.groupby("Transaction Date", as_index=False)["Net Expense (MYR)"].sum().sort_values("Transaction Date")
        cumulative["Cumulative Spending (MYR)"] = cumulative["Net Expense (MYR)"].cumsum()
        col2.plotly_chart(_transparent(px.line(cumulative, x="Transaction Date", y="Cumulative Spending (MYR)", title="Cumulative Spending", markers=True)), width="stretch")

    with quarterly_tab:
        quarterly = filtered.groupby(["Quarter", "Quarter Label"], as_index=False)["Net Expense (MYR)"].sum().sort_values("Quarter")
        quarterly_fig, quarterly = _period_change_chart(
            quarterly, "Quarter Label", "Quarterly Spending Trend and Percentage Change", "QoQ Change (%)"
        )
        quarterly = quarterly.rename(columns={"Previous Period (MYR)": "Previous Quarter (MYR)"})
        st.plotly_chart(quarterly_fig, width="stretch")

        quarter_values = sorted(filtered["Quarter"].dropna().unique())
        parent_values = sorted(filtered["Clean Parent Category"].dropna().unique())
        parent_index = pd.MultiIndex.from_product(
            [quarter_values, parent_values], names=["Quarter", "Clean Parent Category"]
        )
        quarter_parent = (
            filtered.groupby(["Quarter", "Clean Parent Category"])["Net Expense (MYR)"]
            .sum().reindex(parent_index, fill_value=0.0).reset_index()
        )
        quarter_parent["Quarter Label"] = quarter_parent["Quarter"].astype(str)
        quarter_parent["Parent QoQ Change (%)"] = (
            quarter_parent.groupby("Clean Parent Category")["Net Expense (MYR)"]
            .pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan) * 100
        )

        parent_measure = st.radio(
            "Parent-category comparison measure",
            ["Spending amount", "QoQ percentage change"], horizontal=True,
        )
        if parent_measure == "Spending amount":
            parent_fig = px.bar(
                quarter_parent, x="Quarter Label", y="Net Expense (MYR)",
                color="Clean Parent Category", barmode="stack",
                title="Quarterly Parent Category Comparison",
                custom_data=["Clean Parent Category", "Parent QoQ Change (%)"],
            )
            parent_fig.update_traces(
                hovertemplate=(
                    "%{x}<br>%{customdata[0]}<br>Expense: MYR %{y:,.2f}"
                    "<br>QoQ change: %{customdata[1]:+.1f}%<extra></extra>"
                )
            )
        else:
            parent_fig = px.line(
                quarter_parent, x="Quarter Label", y="Parent QoQ Change (%)",
                color="Clean Parent Category", markers=True,
                title="Quarterly Parent Category Percentage Change",
                custom_data=["Clean Parent Category", "Net Expense (MYR)"],
            )
            parent_fig.update_traces(
                hovertemplate=(
                    "%{x}<br>%{customdata[0]}<br>QoQ change: %{y:+.1f}%"
                    "<br>Expense: MYR %{customdata[1]:,.2f}<extra></extra>"
                )
            )
            parent_fig.update_yaxes(ticksuffix="%", zeroline=True)

        if "expense_parent_drilldown" not in st.session_state:
            st.session_state.expense_parent_drilldown = None
        if "expense_parent_chart_version" not in st.session_state:
            st.session_state.expense_parent_chart_version = 0

        control_col, status_col = st.columns([1, 3])
        if control_col.button(
            "Show all categories", disabled=st.session_state.expense_parent_drilldown is None,
            key="expense_show_all_categories",
        ):
            st.session_state.expense_parent_drilldown = None
            st.session_state.expense_parent_chart_version += 1
        status_placeholder = status_col.empty()

        parent_event = st.plotly_chart(
            _transparent(parent_fig), width="stretch",
            key=f"expense_quarter_parent_{st.session_state.expense_parent_chart_version}_{parent_measure}",
            on_select="rerun", selection_mode="points",
        )
        selected_points = parent_event.selection.get("points", []) if hasattr(parent_event, "selection") else []
        if selected_points:
            custom_data = selected_points[0].get("customdata", [])
            clicked_parent = custom_data[0] if custom_data else None
            if clicked_parent:
                st.session_state.expense_parent_drilldown = clicked_parent

        selected_parent = st.session_state.expense_parent_drilldown
        status_placeholder.caption(f"Selected parent category: {selected_parent or 'All'}")
        category_source = filtered[
            filtered["Clean Parent Category"] == selected_parent
        ] if selected_parent else filtered
        comparison_source = category_source.copy()
        category_totals_for_chart = (
            category_source.groupby("Clean Category")["Net Expense (MYR)"].sum()
            .sort_values(ascending=False)
        )
        visible_categories = category_totals_for_chart.index.tolist()
        if selected_parent is None:
            visible_categories = visible_categories[:12]
        category_source = category_source[category_source["Clean Category"].isin(visible_categories)]
        category_index = pd.MultiIndex.from_product(
            [quarter_values, visible_categories], names=["Quarter", "Clean Category"]
        )
        quarter_detail = (
            category_source.groupby(["Quarter", "Clean Category"])["Net Expense (MYR)"]
            .sum().reindex(category_index, fill_value=0.0).reset_index()
        )
        quarter_detail["Quarter Label"] = quarter_detail["Quarter"].astype(str)
        quarter_detail["Category QoQ Change (%)"] = (
            quarter_detail.groupby("Clean Category")["Net Expense (MYR)"]
            .pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan) * 100
        )
        detail_title = (
            f"Quarterly Category Comparison — {selected_parent}"
            if selected_parent else "Quarterly Category Comparison — Top 12 Categories"
        )
        detail_fig = px.bar(
            quarter_detail, x="Quarter Label", y="Net Expense (MYR)", color="Clean Category",
            barmode="stack", title=detail_title,
            custom_data=["Clean Category", "Category QoQ Change (%)"],
        )
        detail_fig.update_traces(
            hovertemplate=(
                "%{x}<br>%{customdata[0]}<br>Expense: MYR %{y:,.2f}"
                "<br>QoQ change: %{customdata[1]:+.1f}%<extra></extra>"
            )
        )
        st.plotly_chart(_transparent(detail_fig), width="stretch", key="expense_quarter_category_detail")

        category_pairs = comparison_source[
            ["Clean Parent Category", "Clean Category"]
        ].drop_duplicates()
        quarter_grid = pd.DataFrame({"Quarter": quarter_values})
        comparison_grid = category_pairs.merge(quarter_grid, how="cross")
        comparison_actual = (
            comparison_source.groupby(
                ["Clean Parent Category", "Clean Category", "Quarter"], as_index=False
            )["Net Expense (MYR)"].sum()
        )
        comparison_notes = (
            comparison_source.groupby(
                ["Clean Parent Category", "Clean Category", "Quarter"], as_index=False
            )["Original Note"].agg(_join_unique_notes).rename(columns={"Original Note": "Notes"})
        )
        comparison_table = comparison_grid.merge(
            comparison_actual,
            on=["Clean Parent Category", "Clean Category", "Quarter"],
            how="left",
        )
        comparison_table = comparison_table.merge(
            comparison_notes,
            on=["Clean Parent Category", "Clean Category", "Quarter"],
            how="left",
        )
        comparison_table["Notes"] = comparison_table["Notes"].fillna("")
        comparison_table["Net Expense (MYR)"] = comparison_table["Net Expense (MYR)"].fillna(0.0)
        comparison_table = comparison_table.sort_values(
            ["Clean Parent Category", "Clean Category", "Quarter"]
        )
        comparison_table["Previous Quarter (MYR)"] = comparison_table.groupby(
            ["Clean Parent Category", "Clean Category"]
        )["Net Expense (MYR)"].shift(1)
        comparison_table["QoQ Change (%)"] = np.where(
            comparison_table["Previous Quarter (MYR)"].abs() > 1e-9,
            (
                comparison_table["Net Expense (MYR)"]
                / comparison_table["Previous Quarter (MYR)"]
                - 1
            ) * 100,
            np.nan,
        )
        comparison_table = comparison_table[
            (comparison_table["Net Expense (MYR)"].abs() > 1e-9)
            | (comparison_table["Previous Quarter (MYR)"].fillna(0).abs() > 1e-9)
        ].copy()
        comparison_table["Quarter Label"] = comparison_table["Quarter"].astype(str)
        comparison_table = comparison_table.sort_values(
            ["Quarter", "Clean Parent Category", "Clean Category"],
            ascending=[False, True, True],
        )
        st.markdown("**Quarterly Parent Category and Category Comparison**")
        show_comparison_notes = st.toggle(
            "Expand table to show notes", value=False, key="expense_quarter_table_notes"
        )
        comparison_columns = [
            "Clean Parent Category", "Clean Category", "Quarter Label",
            "Net Expense (MYR)", "Previous Quarter (MYR)", "QoQ Change (%)",
        ]
        if show_comparison_notes:
            comparison_columns.append("Notes")
        comparison_display = comparison_table[comparison_columns].copy()
        comparison_display["Net Expense (MYR)"] = comparison_display["Net Expense (MYR)"].map(_format_amount)
        comparison_display["Previous Quarter (MYR)"] = comparison_display["Previous Quarter (MYR)"].map(_format_amount)
        comparison_display["QoQ Change (%)"] = comparison_display["QoQ Change (%)"].map(_format_percent)
        st.dataframe(
            comparison_display,
            hide_index=True,
            width="stretch",
            column_config={
                "Clean Parent Category": "Parent Category",
                "Clean Category": "Category",
                "Quarter Label": "Quarter",
            },
        )
        st.markdown("**Overall Quarterly Totals**")
        quarterly_display = quarterly[["Quarter Label", "Net Expense (MYR)", "Previous Quarter (MYR)", "QoQ Change (%)"]].copy()
        quarterly_display["Net Expense (MYR)"] = quarterly_display["Net Expense (MYR)"].map(_format_amount)
        quarterly_display["Previous Quarter (MYR)"] = quarterly_display["Previous Quarter (MYR)"].map(_format_amount)
        quarterly_display["QoQ Change (%)"] = quarterly_display["QoQ Change (%)"].map(_format_percent)
        st.dataframe(quarterly_display, hide_index=True, width="stretch")

    with patterns:
        daily = filtered.groupby(["Transaction Date", "Weekday", "Weekend Flag"], as_index=False).agg(
            **{"Net Expense (MYR)": ("Net Expense (MYR)", "sum"), "Transaction Count": ("Source Row", "count")}
        )
        calendar = pd.DataFrame({"Transaction Date": pd.date_range(start_date, end_date, freq="D")})
        calendar["Weekday"] = calendar["Transaction Date"].dt.day_name()
        occurrences = calendar.groupby("Weekday").size().rename("Calendar Occurrences")
        weekday = daily.groupby("Weekday").agg(
            **{
                "Total Expense (MYR)": ("Net Expense (MYR)", "sum"),
                "Transaction Count": ("Transaction Count", "sum"),
                "Active Spending Days": ("Transaction Date", "nunique"),
                "Median Daily Expense (MYR)": ("Net Expense (MYR)", "median"),
            }
        ).join(occurrences).reindex(WEEKDAY_ORDER).fillna(0).reset_index()
        weekday["Average per Calendar Occurrence (MYR)"] = np.where(
            weekday["Calendar Occurrences"] > 0,
            weekday["Total Expense (MYR)"] / weekday["Calendar Occurrences"], 0.0,
        )
        metric = st.radio("Weekday measure", ["Average per Calendar Occurrence (MYR)", "Total Expense (MYR)", "Transaction Count"], horizontal=True)
        fig_weekday = px.bar(
            weekday, x="Weekday", y=metric, category_orders={"Weekday": WEEKDAY_ORDER},
            title="Spending by Weekday", hover_data=["Total Expense (MYR)", "Transaction Count", "Median Daily Expense (MYR)", "Calendar Occurrences"],
        )
        st.plotly_chart(_transparent(fig_weekday), width="stretch")

        weekday_weekend = daily.groupby("Weekend Flag", as_index=False)["Net Expense (MYR)"].sum()
        st.plotly_chart(_transparent(px.bar(weekday_weekend, x="Weekend Flag", y="Net Expense (MYR)", title="Weekday vs Weekend Spending")), width="stretch")
        heatmap = filtered.groupby(["Clean Parent Category", "Weekday"], as_index=False)["Net Expense (MYR)"].sum()
        heatmap_pivot = heatmap.pivot(index="Clean Parent Category", columns="Weekday", values="Net Expense (MYR)").reindex(columns=WEEKDAY_ORDER).fillna(0)
        fig_heatmap = px.imshow(heatmap_pivot, aspect="auto", color_continuous_scale="Blues", labels={"color": "MYR"}, title="Category by Weekday")
        st.plotly_chart(_transparent(fig_heatmap), width="stretch")

    with categories_tab:
        category = filtered.groupby(["Clean Parent Category", "Clean Category"], as_index=False).agg(
            **{"Net Expense (MYR)": ("Net Expense (MYR)", "sum"), "Transaction Count": ("Source Row", "count")}
        ).sort_values("Net Expense (MYR)", ascending=True)
        st.plotly_chart(_transparent(px.bar(category, x="Net Expense (MYR)", y="Clean Category", color="Clean Parent Category", orientation="h", title="Spending by Category")), width="stretch")
        merchant = filtered.groupby("Merchant Display", as_index=False)["Net Expense (MYR)"].sum().nlargest(20, "Net Expense (MYR)")
        st.plotly_chart(_transparent(px.bar(merchant.sort_values("Net Expense (MYR)"), x="Net Expense (MYR)", y="Merchant Display", orientation="h", title="Top Merchants / Notes")), width="stretch")

    with asset_tab:
        periods = result.asset_period_summary
        if periods.empty:
            st.info("At least two valid Asset reporting snapshots are required for Asset vs Expenses analysis.")
        else:
            period_options = periods["Review End"].tolist()
            selected_end = st.selectbox("Asset review snapshot", period_options, index=len(period_options) - 1, format_func=lambda value: pd.Timestamp(value).strftime("%d %b %Y"))
            period = periods[periods["Review End"] == selected_end].iloc[0]
            pcols = st.columns(4)
            pcols[0].metric("Closing assets", _money(period["Closing Assets (MYR)"]))
            pcols[1].metric("Asset change", _money(period["Asset Change (MYR)"]))
            pcols[2].metric("Review-period expenses", _money(period["Review Period Expense (MYR)"]))
            pcols[3].metric("Expense-to-assets", f"{period['Expense to Assets (%)']:.2f}%")
            st.caption(f"Expense interval: after {period['Review Start']:%d %b %Y} through {period['Review End']:%d %b %Y}. Asset changes also include income, transfers, market movement, and other untracked activity.")
            latest_year = int(filtered["Year"].max())
            quarters = pd.period_range(f"{latest_year}Q1", f"{latest_year}Q4", freq="Q")
            comparison = pd.DataFrame({"Quarter": quarters})
            comparison["Quarter Label"] = comparison["Quarter"].astype(str)
            expense_by_quarter = (
                filtered[filtered["Year"] == latest_year]
                .groupby("Quarter")["Net Expense (MYR)"].sum()
            )
            asset_by_quarter = periods.copy()
            asset_by_quarter["Quarter"] = pd.to_datetime(asset_by_quarter["Review End"]).dt.to_period("Q")
            asset_by_quarter = asset_by_quarter.groupby("Quarter")["Asset Change (MYR)"].last()
            comparison["Quarterly Expense (MYR)"] = comparison["Quarter"].map(expense_by_quarter).fillna(0.0)
            comparison["Asset Change (MYR)"] = comparison["Quarter"].map(asset_by_quarter)

            latest_fig = go.Figure()
            latest_fig.add_bar(
                x=comparison["Quarter Label"], y=comparison["Asset Change (MYR)"],
                name="Asset Change (MYR)",
                text=[f"{value / 1000:.1f}k" if pd.notna(value) else "" for value in comparison["Asset Change (MYR)"]],
                textposition="auto", hovertemplate="%{x}<br>Asset change: MYR %{y:,.2f}<extra></extra>",
            )
            latest_fig.add_bar(
                x=comparison["Quarter Label"], y=comparison["Quarterly Expense (MYR)"],
                name="Quarterly Expense (MYR)",
                text=[f"{value / 1000:.1f}k" if abs(value) >= 1000 else f"{value:,.0f}" for value in comparison["Quarterly Expense (MYR)"]],
                textposition="auto", hovertemplate="%{x}<br>Expense: MYR %{y:,.2f}<extra></extra>",
            )
            latest_fig.update_layout(
                barmode="group", title=f"{latest_year} Quarterly Asset Change vs Expenses",
                xaxis_title="Quarter", yaxis_title="Amount (MYR)", legend_title_text="Measure",
            )
            st.plotly_chart(_transparent(latest_fig), width="stretch")
            st.caption("A blank Asset Change bar means expenses exist for the quarter but no corresponding Asset review snapshot is available yet.")

    with ledger_tab:
        display_columns = [
            "Date time", "Type", "Original Parent Category", "Original Category",
            "Clean Parent Category", "Clean Category", "Mapping Result", "Mapping Reason",
            "Recurring Status", "Meal Period Status", "Merchant Display",
            "Amount", "Currency", "Net Expense (MYR)", "Account", "Payment account",
            "Author", "Original Note", "Normalized Note", "Calculation Status", "Source Row",
        ]
        ledger = transactions[
            transactions["Transaction Date"].dt.date.between(start_date, end_date)
        ][display_columns].sort_values("Date time", ascending=False).copy()
        ledger_export = ledger.copy()
        ledger_text_columns = [
            "Original Parent Category", "Original Category", "Clean Parent Category", "Clean Category",
            "Mapping Result", "Mapping Reason", "Recurring Status", "Meal Period Status",
            "Merchant Display", "Account", "Payment account", "Author", "Original Note",
            "Normalized Note", "Calculation Status",
        ]
        for column in ledger_text_columns:
            ledger[column] = ledger[column].astype("string").fillna("")
        ledger["Amount"] = ledger["Amount"].map(_format_amount)
        ledger["Net Expense (MYR)"] = ledger["Net Expense (MYR)"].map(_format_amount)
        st.dataframe(ledger, hide_index=True, width="stretch")
        st.download_button(
            "Download filtered expense ledger",
            data=ledger_export.to_csv(index=False).encode("utf-8"),
            file_name=f"expense_ledger_{start_date:%Y%m%d}_{end_date:%Y%m%d}.csv",
            mime="text/csv",
        )
