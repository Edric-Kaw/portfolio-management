import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Asset Portfolio Analytics",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS FOR PREMIUM LOOK & FEEL ---
st.markdown("""
<style>
    /* Import modern font */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    /* General styles */
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Title banner styling */
    .title-container {
        background: linear-gradient(135deg, #102a43 0%, #1e4620 100%);
        padding: 2.5rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
    }
    .title-text {
        color: #e0f2fe;
        font-weight: 700;
        font-size: 2.8rem;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .subtitle-text {
        color: #38bdf8;
        font-weight: 300;
        font-size: 1.2rem;
        margin-top: 0.5rem;
        margin-bottom: 0;
    }
    
    /* Glassmorphic Metric Cards */
    .metric-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 20px 0 rgba(0, 0, 0, 0.15);
        transition: transform 0.3s ease, border-color 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-4px);
        border-color: rgba(56, 189, 248, 0.4);
        box-shadow: 0 8px 30px 0 rgba(56, 189, 248, 0.1);
    }
    .metric-title {
        color: #94a3b8;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.5rem;
    }
    .metric-value {
        color: #f8fafc;
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
    }
    .metric-delta {
        font-size: 0.9rem;
        font-weight: 500;
    }
    .delta-up {
        color: #4ade80;
    }
    .delta-down {
        color: #f87171;
    }
    
    /* Card Subtext */
    .metric-sub {
        color: #64748b;
        font-size: 0.8rem;
        margin-top: 0.25rem;
    }
    
    /* Custom tab headers */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        color: #94a3b8;
        padding: 0.5rem 1.25rem;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #38bdf8;
        background-color: rgba(30, 41, 59, 0.8);
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #0284c7;
        color: white;
        border-color: #0284c7;
        box-shadow: 0 0 12px rgba(2, 132, 199, 0.3);
    }
    
    /* Correction Info banner */
    .correction-banner {
        background-color: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.25);
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# --- HELPER DATA PROCESSING FUNCTIONS ---
@st.cache_data
def get_reporting_dates(file_path):
    try:
        df = pd.read_excel(file_path, sheet_name='Asset')
        dates = pd.to_datetime(df['ReportingDate']).dt.date.unique()
        return sorted(list(dates), reverse=True)
    except Exception as e:
        return []

def find_year_end_comparison_date(reporting_dates, as_of_date):
    """Return the best available snapshot on or before the prior year end."""
    as_of_date = pd.Timestamp(as_of_date).date()
    prior_year_end = pd.Timestamp(
        year=as_of_date.year - 1,
        month=12,
        day=31
    ).date()
    eligible_dates = [
        pd.Timestamp(reporting_date).date()
        for reporting_date in reporting_dates
        if pd.Timestamp(reporting_date).date() <= prior_year_end
    ]

    if not eligible_dates:
        return None, False

    comparison_date = max(eligible_dates)
    return comparison_date, comparison_date == prior_year_end

def format_change_percent(change_pct, current_value):
    """Format a percentage change, including zero-baseline cases."""
    if pd.notna(change_pct):
        return f"{change_pct:+,.2f}%"
    return "New" if current_value > 0 else "N/A"

@st.cache_data
def load_and_clean_asset_data(file_path, apply_correction=True):
    try:
        # Load assets
        df = pd.read_excel(file_path, sheet_name='Asset')
        df['ReportingDate'] = pd.to_datetime(df['ReportingDate']).dt.date
        
        # Load references
        ref_df = pd.read_excel(file_path, sheet_name='Reference')
        ref_df['ReportingDate'] = pd.to_datetime(ref_df['ReportingDate']).dt.date
        
        # Clean numeric cols
        df['Balance'] = pd.to_numeric(df['Balance'], errors='coerce').fillna(0.0)
        df['BalanceInMYR_Excel'] = pd.to_numeric(df['BalanceInMYR'], errors='coerce').fillna(0.0)
        df['InterestRate'] = pd.to_numeric(df['InterestRate'], errors='coerce').fillna(0.0)
        df['CashLiquidity'] = df['CashLiquidity'].fillna('N/A')
        
        corrected_rows = []
        df['BalanceInMYR'] = df['BalanceInMYR_Excel'].copy()
        
        if apply_correction:
            for idx, row in df.iterrows():
                if row['Currency'] == 'MYR':
                    df.at[idx, 'BalanceInMYR'] = row['Balance']
                elif row['Currency'] != 'MYR' and abs(row['BalanceInMYR_Excel']) < 1e-4 and abs(row['Balance']) > 1e-4:
                    currency = row['Currency']
                    date = row['ReportingDate']
                    
                    ref_cur = ref_df[ref_df['Currency'] == currency]
                    if not ref_cur.empty:
                        # 1. Exact date match
                        exact_match = ref_cur[ref_cur['ReportingDate'] == date]
                        if not exact_match.empty:
                            rate = exact_match.iloc[0]['Rate']
                            ref_date = exact_match.iloc[0]['ReportingDate']
                        else:
                            # 2. Year-agnostic month/day match (typo correction)
                            m_d_match = ref_cur[(pd.to_datetime(ref_cur['ReportingDate']).dt.month == date.month) & 
                                                (pd.to_datetime(ref_cur['ReportingDate']).dt.day == date.day)]
                            if not m_d_match.empty:
                                rate = m_d_match.iloc[0]['Rate']
                                ref_date = m_d_match.iloc[0]['ReportingDate']
                            else:
                                # 3. Fallback to closest date
                                abs_diff = (ref_cur['ReportingDate'] - date).abs()
                                closest_idx = abs_diff.idxmin()
                                rate = ref_cur.loc[closest_idx, 'Rate']
                                ref_date = ref_cur.loc[closest_idx, 'ReportingDate']
                        
                        corrected_val = row['Balance'] * rate
                        df.at[idx, 'BalanceInMYR'] = corrected_val
                        corrected_rows.append({
                            'Account': row['Account'],
                            'Date': date.strftime('%Y-%m-%d'),
                            'Currency': currency,
                            'Balance': row['Balance'],
                            'Excel Value': row['BalanceInMYR_Excel'],
                            'Corrected Value': corrected_val,
                            'Rate Used': rate,
                            'Reference Date': ref_date.strftime('%Y-%m-%d')
                        })
                        
        return df, corrected_rows
    except Exception as e:
        st.error(f"Error loading Excel sheet: {e}")
        return pd.DataFrame(), []

# --- APPLICATION LAYOUT ---

# File and top-level dashboard navigation
excel_file = "InvestmentDetails.xlsx"

if not os.path.exists(excel_file):
    st.error(f"Could not find the Excel file '{excel_file}' in the workspace. Please check the file name or location.")
    st.stop()

st.sidebar.title("Portfolio Analytics")
dashboard_view = st.sidebar.radio(
    "Dashboard",
    options=["Asset Analysis", "Trade Analysis", "Expense Analysis"],
    help="Review reporting snapshots, investment transactions, or spending patterns.",
)

if dashboard_view == "Trade Analysis":
    from trade_dashboard import render_trade_dashboard

    if st.sidebar.button("Reload Trade Data"):
        st.cache_data.clear()
        st.toast("Trade data reloaded")
    render_trade_dashboard(excel_file)
    st.stop()

if dashboard_view == "Expense Analysis":
    from expense_dashboard import render_expense_dashboard

    if st.sidebar.button("Reload Expense Data"):
        st.cache_data.clear()
        st.toast("Expense data reloaded")
    render_expense_dashboard(excel_file)
    st.stop()

# Header Section
st.markdown("""
<div class="title-container">
    <h1 class="title-text">💰 Asset Portfolio Analytics</h1>
    <p class="subtitle-text">Interactive intelligence dashboard for your net asset allocation, growth, and liquidity profile</p>
</div>
""", unsafe_allow_html=True)

# Sidebar Setup
st.sidebar.image("https://img.icons8.com/color/96/000000/dashboard.png", width=60)
st.sidebar.subheader("Asset Configuration")

# Manual reload button
if st.sidebar.button("🔄 Reload Data"):
    st.cache_data.clear()
    st.toast("Cache cleared & data reloaded!", icon="🔄")

# Error Correction Switch
enable_correction = st.sidebar.toggle("Enable Excel Correction", value=True, 
                                      help="Automatically recalculates zero MYR values for foreign assets using Reference sheet exchange rates.")

# Load Data
df_all, corrections = load_and_clean_asset_data(excel_file, enable_correction)

if df_all.empty:
    st.error("No data found in the Asset sheet.")
    st.stop()

# Dates available
available_dates = sorted(list(df_all['ReportingDate'].unique()))
if len(available_dates) == 0:
    st.error("No reporting dates found in the Asset sheet.")
    st.stop()

latest_date = available_dates[-1]

# Selected Date Radio
selected_date = st.sidebar.selectbox(
    "Select Reporting Snapshot",
    options=sorted(available_dates, reverse=True),
    format_func=lambda d: d.strftime('%Y-%m-%d') + (" (Latest)" if d == latest_date else "")
)

# Multi-select filters in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("Filters (Active Snapshot)")

# Filter dataset based on selected date
df_snapshot = df_all[df_all['ReportingDate'] == selected_date]

# Filter options
all_types = sorted(df_snapshot['Type'].dropna().unique().tolist())
selected_types = st.sidebar.multiselect("Asset Type", options=all_types, default=all_types)

all_categories = sorted(df_snapshot['Category'].dropna().unique().tolist())
selected_categories = st.sidebar.multiselect("Asset Category", options=all_categories, default=all_categories)

all_currencies = sorted(df_snapshot['Currency'].dropna().unique().tolist())
selected_currencies = st.sidebar.multiselect("Currency", options=all_currencies, default=all_currencies)

all_liquidities = sorted(df_snapshot['CashLiquidity'].dropna().unique().tolist())
selected_liquidities = st.sidebar.multiselect("Liquidity Rating", options=all_liquidities, default=all_liquidities)

# Filtered data
filtered_df = df_snapshot[
    (df_snapshot['Type'].isin(selected_types)) &
    (df_snapshot['Category'].isin(selected_categories)) &
    (df_snapshot['Currency'].isin(selected_currencies)) &
    (df_snapshot['CashLiquidity'].isin(selected_liquidities))
]

if filtered_df.empty:
    st.warning("⚠️ No data matches the selected filters. Please adjust your filters in the sidebar.")
    st.stop()

# --- DISPLAY WARNING ABOUT CORRECTIONS ---
if enable_correction and corrections:
    # Filter corrections applicable to the selected date
    selected_corrections = [c for c in corrections if c['Date'] == selected_date.strftime('%Y-%m-%d')]
    if selected_corrections:
        corrected_sum = sum(c['Corrected Value'] for c in selected_corrections)
        with st.container():
            st.markdown(f"""
            <div class="correction-banner">
                <span style="font-size:1.2rem; margin-right:5px;">⚠️</span> 
                <strong>Excel Formulations Audit:</strong> Recalculated <strong>{len(selected_corrections)} foreign assets</strong> where converted values were zero in Excel. 
                Using the exchange rate in Reference sheet, your total assets increased by <strong>+{corrected_sum:,.2f} MYR</strong> for this snapshot.
            </div>
            """, unsafe_allow_html=True)
            with st.expander("Show audit details"):
                st.write(pd.DataFrame(selected_corrections).drop(columns=['Date']))

# --- CALCULATE METRICS ---

# Current snapshot totals
total_assets_current = filtered_df['BalanceInMYR'].sum()

# Period over Period Growth (compare with previous reporting date if exists)
prev_date = None
df_prev = pd.DataFrame(columns=df_all.columns)
date_index = available_dates.index(selected_date)
if date_index > 0:
    prev_date = available_dates[date_index - 1]
    # Filter dataset for previous date
    df_prev = df_all[df_all['ReportingDate'] == prev_date]
    # Filter using same sidebar criteria
    filtered_prev = df_prev[
        (df_prev['Type'].isin(selected_types)) &
        (df_prev['Category'].isin(selected_categories)) &
        (df_prev['Currency'].isin(selected_currencies)) &
        (df_prev['CashLiquidity'].isin(selected_liquidities))
    ]
    total_assets_prev = filtered_prev['BalanceInMYR'].sum()
    delta_myr = total_assets_current - total_assets_prev
    delta_pct = (delta_myr / total_assets_prev * 100) if total_assets_prev > 0 else 0.0
else:
    total_assets_prev = 0.0
    delta_myr = 0.0
    delta_pct = 0.0

# Weighted Yield
interest_bearing = filtered_df[filtered_df['InterestRate'] > 0]
if not interest_bearing.empty:
    weighted_yield = (interest_bearing['BalanceInMYR'] * interest_bearing['InterestRate']).sum() / interest_bearing['BalanceInMYR'].sum()
else:
    weighted_yield = 0.0

# Liquid assets ratio
liquid_assets_sum = filtered_df[filtered_df['CashLiquidity'].isin(['Very High', 'High'])]['BalanceInMYR'].sum()
liquidity_ratio = (liquid_assets_sum / total_assets_current * 100) if total_assets_current > 0 else 0.0

# Render KPIs
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    delta_class = "delta-up" if delta_myr >= 0 else "delta-down"
    delta_symbol = "+" if delta_myr >= 0 else ""
    delta_text = f"{delta_symbol}{delta_myr:,.2f} MYR ({delta_symbol}{delta_pct:.2f}%)" if prev_date else "First recorded snapshot"
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Total Portfolio Assets</div>
        <div class="metric-value">{total_assets_current:,.2f} <span style="font-size:1.1rem; font-weight:400; color:#38bdf8;">MYR</span></div>
        <div class="metric-delta {delta_class}">
            {'↑' if delta_myr >= 0 else '↓'} {delta_text}
        </div>
        <div class="metric-sub">Base currency evaluation</div>
    </div>
    """, unsafe_allow_html=True)

with kpi2:
    usd_val = filtered_df[filtered_df['Currency'] == 'USD']['Balance'].sum()
    myr_val = filtered_df[filtered_df['Currency'] == 'MYR']['Balance'].sum()
    usd_percent = (filtered_df[filtered_df['Currency'] == 'USD']['BalanceInMYR'].sum() / total_assets_current * 100) if total_assets_current > 0 else 0.0
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Currency Exposure</div>
        <div class="metric-value" style="font-size: 1.7rem;">USD: {usd_percent:.1f}%</div>
        <div class="metric-delta" style="color: #94a3b8;">
            Original USD: ${usd_val:,.2f} <br/> Original MYR: {myr_val:,.2f}
        </div>
        <div class="metric-sub">Exposure by converted value</div>
    </div>
    """, unsafe_allow_html=True)

with kpi3:
    interest_bearing_sum = interest_bearing['BalanceInMYR'].sum()
    interest_bearing_percent = (interest_bearing_sum / total_assets_current * 100) if total_assets_current > 0 else 0.0
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Weighted Portfolio Yield</div>
        <div class="metric-value" style="color: #67e8f9;">{weighted_yield * 100:.2f}%</div>
        <div class="metric-delta" style="color: #94a3b8;">
            Active on {interest_bearing_percent:.1f}% of assets ({interest_bearing_sum:,.0f} MYR)
        </div>
        <div class="metric-sub">Weighted on interest-bearing assets</div>
    </div>
    """, unsafe_allow_html=True)

with kpi4:
    liq_level = "Very High" if liquidity_ratio > 40 else "High" if liquidity_ratio > 25 else "Moderate" if liquidity_ratio > 10 else "Low"
    liq_color = "#4ade80" if liquidity_ratio > 25 else "#f59e0b" if liquidity_ratio > 10 else "#f87171"
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Liquid Capital Ratio</div>
        <div class="metric-value" style="color: {liq_color};">{liquidity_ratio:.1f}%</div>
        <div class="metric-delta" style="color: #94a3b8;">
            Liquidity rating: <strong style="color:{liq_color};">{liq_level}</strong> ({liquid_assets_sum:,.0f} MYR)
        </div>
        <div class="metric-sub">Assets rating Very High / High liquidity</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br/>", unsafe_allow_html=True)

# --- MAIN PAGE TABS ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Asset Allocation & Hierarchy", 
    "📈 Historical Growth Trends", 
    "💧 Liquidity & Currency Profile", 
    "📋 Interactive Assets Ledger"
])

# --- TAB 1: ALLOCATION & HIERARCHY ---
with tab1:
    st.subheader("Asset Allocation Hierarchies")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("**Hierarchical Sunburst Drilldown** *(Click center to return, outer rings to zoom)*")
        if not filtered_df.empty:
            # Build sunburst path
            fig_sun = px.sunburst(
                filtered_df,
                path=['Type', 'Category', 'SubCategory', 'Account'],
                values='BalanceInMYR',
                color='Type',
                color_discrete_map={
                    'Cash': '#14b8a6',       # Teal
                    'Retirement': '#8b5cf6', # Purple
                    'Investment': '#0ea5e9', # Light Blue
                    'Insurance': '#ec4899'  # Pink
                },
                maxdepth=3
            )
            fig_sun.update_layout(
                margin=dict(t=10, l=10, r=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=500
            )
            st.plotly_chart(fig_sun, use_container_width=True)
        else:
            st.warning("No data matches selected filter criteria.")
            
    with col2:
        st.markdown("**Asset Split by Type**")
        if not filtered_df.empty:
            type_df = filtered_df.groupby('Type')['BalanceInMYR'].sum().reset_index()
            fig_donut = px.pie(
                type_df,
                names='Type',
                values='BalanceInMYR',
                hole=0.4,
                color='Type',
                color_discrete_map={
                    'Cash': '#14b8a6',
                    'Retirement': '#8b5cf6',
                    'Investment': '#0ea5e9',
                    'Insurance': '#ec4899'
                }
            )
            fig_donut.update_layout(
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
                margin=dict(t=10, l=10, r=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                height=250
            )
            st.plotly_chart(fig_donut, use_container_width=True)
            
            st.markdown("**Asset Split by Category**")
            cat_df = filtered_df.groupby('Category')['BalanceInMYR'].sum().reset_index().sort_values('BalanceInMYR', ascending=False)
            fig_cat = px.bar(
                cat_df,
                x='BalanceInMYR',
                y='Category',
                orientation='h',
                color='Category',
                color_discrete_sequence=px.colors.sequential.GnBu_r
            )
            fig_cat.update_layout(
                showlegend=False,
                margin=dict(t=5, l=5, r=5, b=5),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis_title="Balance (MYR)",
                yaxis_title="",
                height=220
            )
            st.plotly_chart(fig_cat, use_container_width=True)

# --- TAB 2: HISTORICAL TRENDS ---
with tab2:
    st.subheader("Asset Portfolio Growth Trends")
    
    if 'drilldown_select' not in st.session_state:
        st.session_state.drilldown_select = "None (Show Overview)"
        
    if len(available_dates) > 1:
        col_t1, col_t2 = st.columns([1, 1])
        
        with col_t1:
            st.markdown("**Portfolio Total Asset Value Comparison**")
            # Calculate totals for all dates using current filters
            trend_data = []
            for date in available_dates:
                d_df = df_all[
                    (df_all['ReportingDate'] == date) &
                    (df_all['Type'].isin(selected_types)) &
                    (df_all['Category'].isin(selected_categories)) &
                    (df_all['Currency'].isin(selected_currencies)) &
                    (df_all['CashLiquidity'].isin(selected_liquidities))
                ]
                trend_data.append({
                    'Reporting Date': date.strftime('%d %b %Y'),
                    'Total Value (MYR)': d_df['BalanceInMYR'].sum()
                })
            trend_df = pd.DataFrame(trend_data)
            
            # Calculate text labels with percentage change
            text_labels = []
            for i in range(len(trend_df)):
                val = trend_df.loc[i, 'Total Value (MYR)']
                if i == 0:
                    text_labels.append(f"{val:,.2f}")
                else:
                    prev_val = trend_df.loc[i-1, 'Total Value (MYR)']
                    pct = (val - prev_val) / prev_val * 100 if prev_val > 0 else 0.0
                    text_labels.append(f"{val:,.2f}<br>({pct:+.2f}%)")
            trend_df['Text Label'] = text_labels
            
            fig_trend = px.bar(
                trend_df,
                x='Reporting Date',
                y='Total Value (MYR)',
                text='Text Label',
                color='Total Value (MYR)',
                color_continuous_scale=px.colors.sequential.Darkmint
            )
            fig_trend.update_traces(texttemplate='%{text}', textposition='outside')
            fig_trend.update_layout(
                margin=dict(t=30, l=10, r=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=400,
                coloraxis_showscale=False
            )
            fig_trend.update_xaxes(type='category')
            st.plotly_chart(fig_trend, use_container_width=True)
            
        with col_t2:
            st.markdown("**Growth by Asset Type**")
            # Group by Date and Type
            type_trend_data = []
            prev_balances = {}
            for date in available_dates:
                for t in selected_types:
                    d_df = df_all[
                        (df_all['ReportingDate'] == date) &
                        (df_all['Type'] == t) &
                        (df_all['Category'].isin(selected_categories)) &
                        (df_all['Currency'].isin(selected_currencies)) &
                        (df_all['CashLiquidity'].isin(selected_liquidities))
                    ]
                    val = d_df['BalanceInMYR'].sum()
                    
                    # Calculate label
                    if t not in prev_balances:
                        label = f"{val:,.2f}"
                    else:
                        prev_val = prev_balances[t]
                        pct = (val - prev_val) / prev_val * 100 if prev_val > 0 else 0.0
                        label = f"{val:,.2f}<br>({pct:+.2f}%)"
                        
                    type_trend_data.append({
                        'Reporting Date': date.strftime('%d %b %Y'),
                        'Type': t,
                        'Balance (MYR)': val,
                        'Text Label': label
                    })
                    
                    prev_balances[t] = val
                    
            type_trend_df = pd.DataFrame(type_trend_data)
            
            fig_type_trend = px.bar(
                type_trend_df,
                x='Reporting Date',
                y='Balance (MYR)',
                color='Type',
                text='Text Label',
                barmode='group',
                custom_data=['Type'],
                color_discrete_map={
                    'Cash': '#14b8a6',
                    'Retirement': '#8b5cf6',
                    'Investment': '#0ea5e9',
                    'Insurance': '#ec4899'
                }
            )
            fig_type_trend.update_traces(texttemplate='%{text}', textposition='outside')
            fig_type_trend.update_layout(
                margin=dict(t=30, l=10, r=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=400
            )
            fig_type_trend.update_xaxes(type='category')
            event = st.plotly_chart(fig_type_trend, use_container_width=True, on_select="rerun")
            
            # Check for click interaction on the chart
            clicked_type = None
            if event:
                points = []
                if "selection" in event and "points" in event["selection"]:
                    points = event["selection"]["points"]
                elif "points" in event:
                    points = event["points"]
                
                if points:
                    point = points[0]
                    if "customdata" in point and point["customdata"]:
                        clicked_type = point["customdata"][0]
            
            if clicked_type and clicked_type != st.session_state.drilldown_select:
                st.session_state.drilldown_select = clicked_type
                st.rerun()

        # --- YTD VS PREVIOUS YEAR-END ANALYSIS ---
        st.markdown("---")
        st.markdown("### YTD vs Previous Year-End Analysis")

        year_end_date, is_exact_year_end = find_year_end_comparison_date(
            available_dates,
            selected_date
        )

        if year_end_date is None:
            st.info(
                f"No reporting snapshot is available before {selected_date.year}. "
                "Add a prior-year snapshot to enable the YTD comparison."
            )
        else:
            ytd_df = df_all[
                (df_all['ReportingDate'] == selected_date) &
                (df_all['Type'].isin(selected_types)) &
                (df_all['Category'].isin(selected_categories)) &
                (df_all['Currency'].isin(selected_currencies)) &
                (df_all['CashLiquidity'].isin(selected_liquidities))
            ]
            year_end_df = df_all[
                (df_all['ReportingDate'] == year_end_date) &
                (df_all['Type'].isin(selected_types)) &
                (df_all['Category'].isin(selected_categories)) &
                (df_all['Currency'].isin(selected_currencies)) &
                (df_all['CashLiquidity'].isin(selected_liquidities))
            ]

            ytd_total = ytd_df['BalanceInMYR'].sum()
            year_end_total = year_end_df['BalanceInMYR'].sum()
            ytd_change = ytd_total - year_end_total
            ytd_change_pct = (
                ytd_change / year_end_total * 100
                if year_end_total > 0
                else np.nan
            )

            reference_description = (
                "exact prior year-end snapshot"
                if is_exact_year_end
                else "latest available snapshot on or before the prior year end"
            )
            st.caption(
                f"Comparing {selected_date.strftime('%d %b %Y')} with "
                f"{year_end_date.strftime('%d %b %Y')} ({reference_description}). "
                "The same sidebar filters are applied to both snapshots."
            )

            ytd_kpi1, ytd_kpi2, ytd_kpi3 = st.columns(3)
            with ytd_kpi1:
                st.metric(
                    f"YTD Portfolio ({selected_date.strftime('%d %b %Y')})",
                    f"{ytd_total:,.2f} MYR"
                )
            with ytd_kpi2:
                st.metric(
                    f"Year-End Reference ({year_end_date.strftime('%d %b %Y')})",
                    f"{year_end_total:,.2f} MYR"
                )
            with ytd_kpi3:
                pct_label = (
                    f"{ytd_change_pct:+.2f}%"
                    if pd.notna(ytd_change_pct)
                    else "N/A (zero baseline)"
                )
                st.metric(
                    "YTD Change",
                    f"{ytd_change:+,.2f} MYR",
                    pct_label
                )

            ytd_by_type = (
                ytd_df.groupby('Type')['BalanceInMYR']
                .sum()
                .reindex(selected_types, fill_value=0.0)
            )
            year_end_by_type = (
                year_end_df.groupby('Type')['BalanceInMYR']
                .sum()
                .reindex(selected_types, fill_value=0.0)
            )
            current_column = f'{selected_date.strftime("%d %b %Y")} (MYR)'
            baseline_column = f'{year_end_date.strftime("%d %b %Y")} (MYR)'
            ytd_type_comparison = pd.DataFrame({
                'Asset Type': selected_types,
                baseline_column: year_end_by_type.values,
                current_column: ytd_by_type.values
            })
            ytd_type_comparison['Net Change (MYR)'] = (
                ytd_type_comparison[current_column] -
                ytd_type_comparison[baseline_column]
            )
            ytd_type_comparison['Change (%)'] = (
                ytd_type_comparison['Net Change (MYR)']
                .div(ytd_type_comparison[baseline_column])
                .mul(100)
                .where(ytd_type_comparison[baseline_column] > 0)
            )

            change_labels = {
                row['Asset Type']: format_change_percent(
                    row['Change (%)'],
                    row[current_column]
                )
                for _, row in ytd_type_comparison.iterrows()
            }

            ytd_chart_df = ytd_type_comparison.melt(
                id_vars='Asset Type',
                value_vars=[baseline_column, current_column],
                var_name='Snapshot',
                value_name='Balance (MYR)'
            )
            ytd_chart_df['Text Label'] = ytd_chart_df.apply(
                lambda row: (
                    f"{row['Balance (MYR)']:,.2f}<br>"
                    f"({change_labels[row['Asset Type']]})"
                    if row['Snapshot'] == current_column
                    else f"{row['Balance (MYR)']:,.2f}"
                ),
                axis=1
            )
            fig_ytd = px.bar(
                ytd_chart_df,
                x='Asset Type',
                y='Balance (MYR)',
                color='Snapshot',
                text='Text Label',
                barmode='group',
                color_discrete_sequence=['#64748b', '#14b8a6']
            )
            fig_ytd.update_traces(
                texttemplate='%{text}',
                textposition='outside',
                cliponaxis=False
            )
            fig_ytd.update_layout(
                margin=dict(t=45, l=10, r=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=400,
                legend_title_text=""
            )
            st.plotly_chart(fig_ytd, width='stretch')

            with st.expander("View YTD change by asset type"):
                ytd_type_display = ytd_type_comparison.copy()
                ytd_type_display[baseline_column] = ytd_type_display[baseline_column].map(
                    lambda value: f"{value:,.2f}"
                )
                ytd_type_display[current_column] = ytd_type_display[current_column].map(
                    lambda value: f"{value:,.2f}"
                )
                ytd_type_display['Net Change (MYR)'] = ytd_type_display['Net Change (MYR)'].map(
                    lambda value: f"{value:+,.2f}"
                )
                ytd_type_display['Change (%)'] = [
                    change_labels[asset_type]
                    for asset_type in ytd_type_display['Asset Type']
                ]
                st.dataframe(
                    ytd_type_display,
                    hide_index=True,
                    width='stretch'
                )
                
        # --- DRILL DOWN SECTION ---
        st.markdown("---")
        
        # Drill-down header and selectbox control
        drill_col1, drill_col2 = st.columns([2, 1])
        with drill_col1:
            drilldown_options = ["None (Show Overview)"] + selected_types
            try:
                curr_idx = drilldown_options.index(st.session_state.drilldown_select)
            except ValueError:
                curr_idx = 0
                st.session_state.drilldown_select = "None (Show Overview)"
                
            selected_option = st.selectbox(
                "🔍 Focus Drill Down Asset Type (Click a bar above or select here):",
                options=drilldown_options,
                index=curr_idx
            )
            
            if selected_option != st.session_state.drilldown_select:
                st.session_state.drilldown_select = selected_option
                st.rerun()
                
        with drill_col2:
            if st.session_state.drilldown_select != "None (Show Overview)":
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                if st.button("🔄 Reset Drill Down", use_container_width=True):
                    st.session_state.drilldown_select = "None (Show Overview)"
                    st.rerun()

        # Render drill-down chart if focused
        if st.session_state.drilldown_select != "None (Show Overview)":
            drill_type = st.session_state.drilldown_select
            st.markdown(f"### Detailed breakdown comparison for **{drill_type}**")
            
            # Select breakdown dimension
            breakdown_dim = st.radio(
                "Select Breakdown Dimension:",
                options=["Category", "SubCategory", "Account"],
                horizontal=True
            )
            
            # Filter and group the data
            drill_df = df_all[
                (df_all['ReportingDate'].isin(available_dates)) &
                (df_all['Type'] == drill_type) &
                (df_all['Category'].isin(selected_categories)) &
                (df_all['Currency'].isin(selected_currencies)) &
                (df_all['CashLiquidity'].isin(selected_liquidities))
            ].copy()
            
            # Find unique items for breakdown
            all_items = drill_df[breakdown_dim].dropna().unique().tolist()
            
            # Find the balances on the latest date to determine order
            latest_date_in_drill = available_dates[-1]
            latest_df = drill_df[drill_df['ReportingDate'] == latest_date_in_drill]
            latest_balances = latest_df.groupby(breakdown_dim)['BalanceInMYR'].sum()
            
            # Sort items in descending order of latest balance (fallback to 0.0)
            unique_items = sorted(all_items, key=lambda x: latest_balances.get(x, 0.0), reverse=True)
            
            if unique_items:
                drill_plot_data = []
                prev_item_balances = {}
                
                for date in available_dates:
                    for item in unique_items:
                        item_df = drill_df[
                            (drill_df['ReportingDate'] == date) &
                            (drill_df[breakdown_dim] == item)
                        ]
                        val = item_df['BalanceInMYR'].sum()
                        
                        # Calculate label
                        if item not in prev_item_balances:
                            label = f"{val:,.2f}"
                        else:
                            prev_val = prev_item_balances[item]
                            if prev_val == 0:
                                label = f"{val:,.2f}<br>(New)" if val > 0 else f"{val:,.2f}"
                            else:
                                pct = (val - prev_val) / prev_val * 100
                                label = f"{val:,.2f}<br>({pct:+.2f}%)"
                                
                        drill_plot_data.append({
                            'Reporting Date': date.strftime('%d %b %Y'),
                            breakdown_dim: item,
                            'Balance (MYR)': val,
                            'Text Label': label
                        })
                        prev_item_balances[item] = val
                        
                drill_plot_df = pd.DataFrame(drill_plot_data)
                
                # Plot grouped bar chart for the drill down
                fig_drill = px.bar(
                    drill_plot_df,
                    x='Reporting Date',
                    y='Balance (MYR)',
                    color=breakdown_dim,
                    text='Text Label',
                    barmode='group',
                    category_orders={breakdown_dim: unique_items},
                    color_discrete_sequence=px.colors.qualitative.Safe
                )
                fig_drill.update_traces(texttemplate='%{text}', textposition='outside')
                fig_drill.update_layout(
                    margin=dict(t=30, l=10, r=10, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=450
                )
                fig_drill.update_xaxes(type='category')
                st.plotly_chart(fig_drill, use_container_width=True)
            else:
                st.info(f"No breakdown items found for {drill_type} under the current filters.")
        else:
            st.info("💡 **Pro-Tip**: Click on any bar in the **Growth by Asset Type** chart above (or select from the dropdown) to drill down and compare its sub-categories over time!")
            
        # Detailed comparison table
        st.markdown("---")
        current_snapshot_label = (
            "Latest Snapshot"
            if selected_date == latest_date
            else "Selected Snapshot"
        )
        if prev_date is not None:
            comparison_period_label = (
                f"{current_snapshot_label}: **{selected_date.strftime('%Y-%m-%d')}** "
                f"vs. Previous Snapshot: **{prev_date.strftime('%Y-%m-%d')}**"
            )
        else:
            comparison_period_label = (
                f"{current_snapshot_label}: **{selected_date.strftime('%Y-%m-%d')}**; "
                "no previous snapshot available"
            )
        st.markdown(
            f"**Historical Snapshot Change Ledger** ({comparison_period_label})"
        )
        
        # Merge latest and previous by Account and SubCategory
        latest_items = df_snapshot[['Type', 'Category', 'SubCategory', 'Account', 'Currency', 'BalanceInMYR']].rename(columns={'BalanceInMYR': 'Latest_MYR'})
        prev_items = df_prev[['Account', 'BalanceInMYR']].rename(columns={'BalanceInMYR': 'Previous_MYR'})
        
        comparison_df = pd.merge(latest_items, prev_items, on='Account', how='outer').fillna(0.0)
        comparison_df['Net Change (MYR)'] = comparison_df['Latest_MYR'] - comparison_df['Previous_MYR']
        comparison_df['Change (%)'] = np.nan
        has_previous_balance = comparison_df['Previous_MYR'] > 0
        if has_previous_balance.any():
            comparison_df.loc[has_previous_balance, 'Change (%)'] = (
                comparison_df.loc[has_previous_balance, 'Net Change (MYR)'] /
                comparison_df.loc[has_previous_balance, 'Previous_MYR'] * 100
            )
        
        # Filter rows where there is a change
        comparison_df = comparison_df[
            (comparison_df['Type'].isin(selected_types)) &
            (comparison_df['Category'].isin(selected_categories))
        ]
        
        # Sort numerically before applying display formatting.
        comparison_display = comparison_df.sort_values(
            by='Net Change (MYR)',
            key=abs,
            ascending=False
        ).copy()
        comparison_display['Latest_MYR'] = comparison_display['Latest_MYR'].map(
            lambda value: f"{value:,.2f}"
        )
        comparison_display['Previous_MYR'] = comparison_display['Previous_MYR'].map(
            lambda value: f"{value:,.2f}"
        )
        comparison_display['Net Change (MYR)'] = comparison_display['Net Change (MYR)'].map(
            lambda value: f"{value:+,.2f}"
        )
        comparison_display['Change (%)'] = comparison_df.loc[
            comparison_display.index
        ].apply(
            lambda row: format_change_percent(
                row['Change (%)'],
                row['Latest_MYR']
            ),
            axis=1
        )
            
        st.dataframe(
            comparison_display,
            hide_index=True,
            width='stretch'
        )
    else:
        st.info("Historical comparison requires at least 2 reporting snapshots. Add more dates to your Excel sheet to view trends!")

# --- TAB 3: LIQUIDITY & CURRENCY ---
with tab3:
    st.subheader("Liquidity & Yield Analysis")
    
    col_l1, col_l2 = st.columns([1, 1])
    
    with col_l1:
        st.markdown("**Portfolio Liquidity Split** (Emergency Cash Readiness)")
        liq_df = filtered_df.groupby('CashLiquidity')['BalanceInMYR'].sum().reset_index()

        # Business definitions use time-to-cash under normal conditions. These
        # labels make the classification rule visible in the legend, while the
        # longer terminology is shown when a user hovers over a pie segment.
        liquidity_definitions = {
            'Very High': {
                'legend': 'Very High (≤1d)',
                'definition': 'Ready cash with no material<br>withdrawal penalty.',
                'level_rule': 'Available within 1 business day.'
            },
            'High': {
                'legend': 'High (2–7d)',
                'definition': 'Easy to access with minimal<br>cost or restriction.',
                'level_rule': 'Available within 2–7 days.'
            },
            'Medium': {
                'legend': 'Medium (8–30d)',
                'definition': 'Requires notice, settlement,<br>or a moderate exit cost.',
                'level_rule': 'Available within 8–30 days.'
            },
            'Low': {
                'legend': 'Low (>30d)',
                'definition': 'Long-term or restricted;<br>early exit may cause loss or penalty.',
                'level_rule': 'Over 30 days, maturity, or sale required.'
            },
            'N/A': {
                'legend': 'N/A',
                'definition': 'Liquidity has not been assessed.',
                'level_rule': 'Assign using the time-to-cash rules.'
            }
        }
        liq_df['LiquidityDisplay'] = liq_df['CashLiquidity'].map(
            lambda level: liquidity_definitions.get(level, {}).get('legend', level)
        )
        liq_df['Definition'] = liq_df['CashLiquidity'].map(
            lambda level: liquidity_definitions.get(level, {}).get('definition', 'No definition available.')
        )
        liq_df['LevelRule'] = liq_df['CashLiquidity'].map(
            lambda level: liquidity_definitions.get(level, {}).get('level_rule', 'No classification rule available.')
        )
        fig_liq = px.pie(
            liq_df,
            names='LiquidityDisplay',
            values='BalanceInMYR',
            color='LiquidityDisplay',
            color_discrete_map={
                'Very High (≤1d)': '#22c55e',
                'High (2–7d)': '#86efac',
                'Medium (8–30d)': '#eab308',
                'Low (>30d)': '#ef4444',
                'N/A': '#94a3b8'
            },
            custom_data=['CashLiquidity', 'Definition', 'LevelRule']
        )
        fig_liq.update_traces(
            hovertemplate=(
                '<b>%{customdata[0]} Liquidity</b><br>'
                '%{customdata[1]}<br><br>'
                '<b>Cash access:</b> %{customdata[2]}<br><br>'
                '<b>Value:</b> MYR %{value:,.2f}<br>'
                '<b>Share:</b> %{percent:.1%}'
                '<extra></extra>'
            ),
            hoverlabel=dict(
                font_size=12,
                align='left'
            )
        )
        fig_liq.update_layout(
            margin=dict(t=10, l=10, r=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            height=300
        )
        st.plotly_chart(fig_liq, use_container_width=True)
        
    with col_l2:
        st.markdown("**Yield Generator Ledger** (Interest Rates by Account)")
        interest_bearing_accounts = filtered_df[filtered_df['InterestRate'] > 0][['Account', 'BalanceInMYR', 'InterestRate']].copy()
        if not interest_bearing_accounts.empty:
            interest_bearing_accounts['InterestRate_Pct'] = interest_bearing_accounts['InterestRate'] * 100
            interest_bearing_accounts['Estimated Annual Earnings (MYR)'] = interest_bearing_accounts['BalanceInMYR'] * interest_bearing_accounts['InterestRate']
            
            fig_yield = px.bar(
                interest_bearing_accounts.sort_values('InterestRate_Pct', ascending=True),
                y='Account',
                x='InterestRate_Pct',
                text='InterestRate_Pct',
                orientation='h',
                color='InterestRate_Pct',
                color_continuous_scale=px.colors.sequential.Teal
            )
            fig_yield.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
            fig_yield.update_layout(
                margin=dict(t=10, l=10, r=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis_title="Interest Rate (%)",
                yaxis_title="",
                height=300,
                coloraxis_showscale=False
            )
            st.plotly_chart(fig_yield, use_container_width=True)
        else:
            st.info("No interest bearing assets matching current filter selections.")
            
    # Yield projection summary
    if not interest_bearing_accounts.empty:
        total_projected_earnings = interest_bearing_accounts['Estimated Annual Earnings (MYR)'].sum()
        st.markdown(f"""
        <div style="background-color:rgba(14, 165, 233, 0.1); border-left:4px solid #0ea5e9; padding: 1rem; border-radius:4px; margin-top: 1rem;">
            <strong>Estimated Annual Yield:</strong> Your interest-bearing assets are projected to generate 
            <strong>{total_projected_earnings:,.2f} MYR</strong> annually, representing an overall yield of 
            <strong>{weighted_yield * 100:.2f}%</strong> on your interest-bearing capital ({interest_bearing_sum:,.2f} MYR).
        </div>
        """, unsafe_allow_html=True)

# --- TAB 4: INTERACTIVE LEDGER ---
with tab4:
    st.subheader("Asset Accounts Ledger")
    st.markdown("Search, sort, filter and analyze every asset holding in your portfolio.")
    
    # Text Search bar
    search_query = st.text_input("🔍 Search Accounts or Categories", "", placeholder="Enter keyword (e.g. GX Bank, EPF, Saving...)")
    
    ledger_df = filtered_df.copy()
    if search_query:
        ledger_df = ledger_df[
            ledger_df['Account'].str.contains(search_query, case=False, na=False) |
            ledger_df['Category'].str.contains(search_query, case=False, na=False) |
            ledger_df['SubCategory'].str.contains(search_query, case=False, na=False) |
            ledger_df['Type'].str.contains(search_query, case=False, na=False)
        ]
        
    # Standardize columns to present
    ledger_display = ledger_df[[
        'Type', 'Category', 'SubCategory', 'Account', 'Currency', 
        'Balance', 'BalanceInMYR', 'MaturityDate', 'InterestRate', 'CashLiquidity'
    ]].copy()
    
    # Clean output column formatting
    ledger_display['InterestRate'] = ledger_display['InterestRate'].map(lambda r: f"{r*100:.2f}%" if r > 0 else "-")
    ledger_display['MaturityDate'] = ledger_display['MaturityDate'].map(lambda d: d.strftime('%Y-%m-%d') if pd.notnull(d) else "-")
    
    # Render table
    st.dataframe(
        ledger_display.sort_values('BalanceInMYR', ascending=False),
        column_config={
            "Balance": st.column_config.NumberColumn("Original Balance", format="%,.2f"),
            "BalanceInMYR": st.column_config.NumberColumn("Balance in MYR", format="%,.2f"),
        },
        hide_index=True,
        width='stretch'
    )
    
    # Download Button
    csv_data = ledger_display.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Export Ledger to CSV",
        data=csv_data,
        file_name=f"asset_ledger_{selected_date.strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

# Footer
st.markdown("---")
st.markdown("<p style='text-align: center; color: #64748b; font-size: 0.85rem;'>Asset Portfolio Dashboard | Developed dynamically in Python and Streamlit | Live synchronized with InvestmentDetails.xlsx</p>", unsafe_allow_html=True)
