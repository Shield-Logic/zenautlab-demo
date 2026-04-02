import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# ==========================================
# MODULE 1: ENTERPRISE UI & SIDEBAR
# ==========================================
st.set_page_config(
    page_title="Carbon Shield | Executive Glass", 
    page_icon="🛡️", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Custom CSS for Green Shield and Enterprise Metric Cards
st.markdown("""
    <style>
    .metric-card {
        background-color: #1E1E1E; padding: 15px; border-radius: 8px;
        border-left: 4px solid #00E676; margin-bottom: 15px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.5);
    }
    .metric-title { color: #A0A0A0; font-size: 12px; text-transform: uppercase; }
    .metric-value { color: #FFFFFF; font-size: 24px; font-weight: bold; }
    .metric-sub { color: #FF5252; font-size: 12px; }
    .ets-card { border-left: 4px solid #FFCA28; } /* Yellow for Tax */
            
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: transparent; border-radius: 4px 4px 0px 0px; padding: 10px 16px; font-weight: 600; }
    .stTabs [aria-selected="true"] { background-color: #2E2E2E; border-bottom: 2px solid #00E676; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# DATA INGESTION & MANUAL UPLOADER  DEMO
# ==========================================
# Clean Enterprise Sidebar Header
st.sidebar.markdown(
    "<h2 style='color: #FFFFFF; font-weight: 600; letter-spacing: 1px;'>🛡️ CARBON SHIELD</h2>"
    "<hr style='margin-top: 0px; margin-bottom: 20px; border: 1px solid #333;'>", 
    unsafe_allow_html=True
)

# Instead of making it the first thing they see:
with st.sidebar.expander("Dev Tools: Manual Override"):
    uploaded_file = st.file_uploader("Upload SaaS CSV", type=['csv'])

@st.cache_data
def load_platinum_data(file):
    if file is not None:
        # Use the manually uploaded file (like our test data)
        df = pd.read_csv(file)
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    else:
        # Fallback to the live production pipeline data
        try:
            df = pd.read_csv('data_platinum/saas_financial_output.csv')
        except FileNotFoundError:
            return None
            
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Sort chronologically and apply 7-day rolling average to smooth the staircase effect
    df = df.sort_values(by=['Vessel_ID', 'Date'])
    df['Smoothed_Fouling_Pct'] = df.groupby('Vessel_ID')['AI_Predicted_Fouling_Pct'].transform(
        lambda x: x.interpolate(method='linear').rolling(window=7, min_periods=1).mean()
    )
    
    return df

df = load_platinum_data(uploaded_file)

if df is None:
    st.info("Welcome to Truth Engine. Please upload your AI-processed CSV to begin.")
    st.stop()
#==================================================================================

# --- SIDEBAR: INTERACTIVE FINANCIALS & (WHAT-IF SLIDERS) ---

# Primary Fleet Router 
st.sidebar.header("Command Navigation")
# Failsafe: if df doesn't exist yet because file isn't uploaded
if 'df' in locals() and df is not None:
    vessel_list = ["Fleet Command"] + list(df['Vessel_ID'].unique())
    selected_vessel = st.sidebar.selectbox("Select Asset View", vessel_list)
else:
    selected_vessel = "Fleet Command"
st.sidebar.markdown("---")

st.sidebar.header("Market Parameters")
bunker_price = st.sidebar.slider("HFO Bunker Price ($/MT)", 300, 1200, 600, 10)

st.sidebar.header("EU ETS Compliance")
# Toggle for EU ETS. If the ship is sailing Asia to US, they toggle this OFF.
eu_ets_enabled = st.sidebar.toggle("Enable EU ETS Calculator", value=True)

tax_multiplier = 0.0
eua_price = 0.0
owned_credits = 0

if eu_ets_enabled:
    eu_tax_tier = st.sidebar.radio("Voyage Route", ["50% (EU to Non-EU)", "100% (Intra-EU)"])
    phase_in_year = st.sidebar.selectbox("ETS Phase-in Year", ["2024 (40%)", "2025 (70%)", "2026+ (100%)"], index=2)
    phase_multiplier = 0.4 if "2024" in phase_in_year else (0.7 if "2025" in phase_in_year else 1.0)
    tax_multiplier = tax_multiplier * phase_multiplier
    eua_price = st.sidebar.slider("Carbon Credit Price (€/MT)", 0, 150, 70, 5)
    owned_credits = st.sidebar.number_input("Owned Carbon Credits (EUAs in Bank)", min_value=0, value=0, step=100)
    
    if eu_tax_tier == "50% (EU to Non-EU)": tax_multiplier = 0.5
    elif eu_tax_tier == "100% (Intra-EU)": tax_multiplier = 1.0

# --- GLOBAL NAVIGATION & DATE FILTER ---
st.sidebar.markdown("---")

# 1. Global Date Range Picker
st.sidebar.header("📅 Voyage Timeline")
min_date = df['Date'].min().date()
max_date = df['Date'].max().date()
date_range = st.sidebar.date_input("Filter Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

if len(date_range) > 0:
    start_date = date_range[0]
    end_date = date_range[1] if len(date_range) > 1 else start_date
else:
    start_date, end_date = min_date, max_date
    
# Filter the MASTER dataframe based on the CFO's selected dates
df = df[(df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)]

# Filter data for the selected vessel
v_df = df[df['Vessel_ID'] == selected_vessel].copy()

# Apply the dynamic financial math from the sidebar sliders
v_df['Live_Wasted_Fuel_USD'] = v_df['Extra_Fuel_MT_Day'] * bunker_price
v_df['Live_Carbon_Tax_EUR'] = v_df['Extra_CO2_MT_Day'] * eua_price * tax_multiplier

# ==========================================
# ENTERPRISE TAB ARCHITECTURE
# ==========================================
# ==========================================
# MAIN ROUTING LOGIC (FLEET VS SINGLE SHIP)
# ==========================================

if selected_vessel == "Fleet Command":
    # ---------------------------------------------------------
    # IMPROVEMENT 1: THE FLEET LEADERBOARD
    # ---------------------------------------------------------
    st.title("Fleet Command Center")
    st.markdown("Macro-level degradation, financial leakage and ESG portfolio view.")

    # Check if we actually have data to show 
    if df.empty:
        st.warning("No data available for the selected date range.")
    else:
        # Calculate macro metrics for every ship in the fleet safely
        leaderboard_data = []
        for vid in df['Vessel_ID'].unique():
            ship_df = df[df['Vessel_ID'] == vid].copy()
            
            # Crash-proof check: Ensure the dataframe isn't empty after date filtering
            if not ship_df.empty and len(ship_df) > 0:
                # Use .values[-1] which is safer than iloc[-1] for filtered series
                latest_fouling = ship_df['Smoothed_Fouling_Pct'].values[-1] * 100
                total_wasted_usd = (ship_df['Extra_Fuel_MT_Day'] * bunker_price).sum()
                latest_cii = ship_df['CII_Daily_Rating'].values[-1]
                avg_conf = ship_df['Data_Confidence_Pct'].mean()
                avg_conf = 0.0 if pd.isna(avg_conf) else avg_conf
                # Calculate new macro metrics
                total_emissions_mt = ship_df['Extra_CO2_MT_Day'].sum()
                total_tax_eur = total_emissions_mt * eua_price * tax_multiplier
                
                # Dynamic AI Recommendation
                if latest_fouling > 8.0: action = "Clean Immediately"
                elif latest_fouling > 4.0: action = "Monitor Closely"
                else: action = "Optimal"

                leaderboard_data.append({
                    "Vessel": vid,
                    "Current Fouling": f"{latest_fouling:.1f}%",
                    "Wasted Fuel (USD)": total_wasted_usd,
                    "Carbon Penalty (EUR)": total_tax_eur,
                    "CII Rating": latest_cii,
                    "Data Quality": f"{avg_conf:.1f}%",
                    "AI Action": action
                })
            
            
        if leaderboard_data:
            board_df = pd.DataFrame(leaderboard_data).sort_values(by="Wasted Fuel (USD)", ascending=False)
            # Format the money column nicely
            board_df['Wasted Fuel (USD)'] = board_df['Wasted Fuel (USD)'].apply(lambda x: f"${x:,.0f}")
            st.markdown("### High-Risk Asset Leaderboard (Ranked by Financial Bleed)")
            def highlight_cii(val):
                color = '#FF5252' if val in ['D', 'E'] else ('#FFCA28' if val == 'C' else '#00E676')
                return f'color: {color}; font-weight: bold;'
            
            st.dataframe(board_df.style.map(highlight_cii, subset=['CII Rating']), use_container_width=True, hide_index=True)
            st.markdown("---")
            # --- IMPROVEMENT: FLEET REPORT DOWNLOAD ---
            fleet_csv = board_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Fleet Command Report (CSV)",
                data=fleet_csv,
                file_name=f"Fleet_Command_Report_{start_date}.csv",
                mime="text/csv",
                type="primary"
            )
        else:
            st.error("Error processing fleet data.")

else:
    # ---------------------------------------------------------
    # SINGLE VESSEL DEEP-DIVE (The 3 Tabs)
    # ---------------------------------------------------------
    # Filter data for the selected vessel
    v_df = df[df['Vessel_ID'] == selected_vessel].copy()
    
    # Apply the dynamic financial math from the sidebar sliders
    v_df['Live_Wasted_Fuel_USD'] = v_df['Extra_Fuel_MT_Day'] * bunker_price
    v_df['Live_Carbon_Tax_EUR'] = v_df['Extra_CO2_MT_Day'] * eua_price * tax_multiplier

    st.title(f"Fleet Intelligence: {selected_vessel}")
    st.markdown("---")

    # The 3-Tier Enterprise Tabs
    tab_finance, tab_technical, tab_commercial, tab_ops = st.tabs([
        "CFO: Financial & Exposure", 
        "SUPT: Technical Physics", 
        "DESK: Commercial & CP Legal",
        "OPS: Voyage Execution"
    ])

    # --- DYNAMIC SIDEBAR ADDITIONS ---
    st.sidebar.markdown("---")
    # ==========================================
    # TAB 1: EXECUTIVE FINANCIALS (CFO)
    # ==========================================
    with tab_finance:
        st.markdown("### Financial Leakage & Carbon Liability")
        
        # Time-Based KPIs
        latest_date = v_df['Date'].max()
        trailing_30_df = v_df[v_df['Date'] >= (latest_date - pd.Timedelta(days=30))]
        
        daily_wasted_usd = v_df['Live_Wasted_Fuel_USD'].iloc[-1]
        monthly_wasted_usd = trailing_30_df['Live_Wasted_Fuel_USD'].sum()
        annual_wasted_usd = (monthly_wasted_usd / 30) * 365
        
        # Fuel KPIs
        st.markdown("#### Fuel Waste (USD)")
        col1, col2, col3 = st.columns(3)
        col1.metric("Daily Leak", f"${daily_wasted_usd:,.0f}")
        col2.metric("Monthly Leak (30D)", f"${monthly_wasted_usd:,.0f}")
        col3.metric("Annualized Run Rate", f"${annual_wasted_usd:,.0f}")
        
        # Carbon KPIs (Only shows if EU ETS is toggled ON in sidebar)
        if eu_ets_enabled:
            st.markdown("#### EU ETS Carbon Tax Exposure")
            daily_tax = v_df['Live_Carbon_Tax_EUR'].iloc[-1]
            monthly_tax = trailing_30_df['Live_Carbon_Tax_EUR'].sum()
            net_liability = max(0, (trailing_30_df['Extra_CO2_MT_Day'].sum() * tax_multiplier) - owned_credits) * eua_price
            
            col_c1, col_c2, col_c3 = st.columns(3)
            col_c1.metric("Daily Carbon Tax", f"€{daily_tax:,.0f}")
            col_c2.metric("Monthly Tax (30D)", f"€{monthly_tax:,.0f}")
            col_c3.metric("Net Unhedged Liability", f"€{net_liability:,.0f}")
            
        st.markdown("---")
        
        # THE ROI ORACLE (Highly Visible)
        st.markdown("### Cleaning ROI Oracle")
        cleaning_cost_usd = st.number_input("Estimated Hull Cleaning Cost ($)", value=40000, step=5000)
        recent_daily_loss = trailing_30_df['Live_Wasted_Fuel_USD'].tail(7).mean()
        avg_conf = v_df['Data_Confidence_Pct'].mean() if 'Data_Confidence_Pct' in v_df.columns else 60.0
        if pd.isna(recent_daily_loss) or recent_daily_loss <= 100:
            st.success(" **OPTIMAL:** Hull is currently operating optimally. No cleaning investment recommended.")
        
        else:
            days_to_breakeven = int(cleaning_cost_usd / recent_daily_loss)
            breakeven_date = (latest_date + pd.Timedelta(days=days_to_breakeven)).strftime('%Y-%m-%d')
            st.error(f"**Averaging a loss of **${recent_daily_loss:,.0f}** per day over the last week.**")
            # 5-Tier ROI Logic
            if days_to_breakeven > 180:
                st.info(f"**MONITOR:** Losing ${recent_daily_loss:,.0f}/day. ROI is {days_to_breakeven} days. Defer cleaning until degradation worsens.")
            elif days_to_breakeven > 90:
                st.warning(f"**PLANNING PHASE:** Losing ${recent_daily_loss:,.0f}/day. ROI is {days_to_breakeven} days. Schedule underwater inspection at next convenient port call.")
            elif days_to_breakeven > 30:
                st.error(f"**ACTION REQUIRED:** Clean hull immediately. The ${cleaning_cost_usd:,.0f} investments will be recovered in *{days_to_breakeven} days* through fuel savings (Breakeven: {breakeven_date}).")
            else:
                st.error(f"**CRITICAL BLEED:** Severe drag. Losing ${recent_daily_loss:,.0f}/day. ROI is {days_to_breakeven} days. Emergency cleaning warranted to stop financial hemorrhage (Breakeven: {breakeven_date})")
            # Confidence Gate Override
            if avg_conf < 60.0 and days_to_breakeven <= 180:
                st.warning(f"**CTO BLOCK:** Data Confidence is only {avg_conf:.1f}%. Do NOT deploy divers. Mandate a sensor calibration check before authorizing capital expenditure.")
            else:
                st.success(f"**CTO BLOCK:** Data Confidence is {avg_conf:.1f}%.")
        # Financial Forward Hedging (CFO Tool)
        st.markdown("### Forward Risk Hedging Simulator")
        with st.expander("Simulate Future Market Shocks"):
            col_h1, col_h2 = st.columns(2)
            sim_bunker = col_h1.slider("Projected Future Fuel Price ($/MT)", 400, 1500, bunker_price, 50)
            sim_eua = col_h2.slider("Projected EU Carbon Tax (€/MT)", 50, 200, int(eua_price), 5)
            
            sim_fuel_risk = (annual_wasted_usd / bunker_price) * sim_bunker
            sim_tax_risk = net_liability * (sim_eua / max(eua_price, 1)) if eu_ets_enabled else 0
            
            st.warning(f"**Forecast:** If market prices hit these levels, annualized leakage will jump to **${sim_fuel_risk:,.0f}** in fuel and **€{sim_tax_risk:,.0f}** in unhedged tax liability.")

        # Cumulative Loss Chart
        # IMPROVEMENT: Month-over-Month Financial Leakage
        st.markdown("### Month-over-Month Financial Leakage")
        
        # Resample data to calculate total USD lost per calendar month
        monthly_df = v_df.set_index('Date').resample('ME')['Live_Wasted_Fuel_USD'].sum().reset_index()
        monthly_df['Month'] = monthly_df['Date'].dt.strftime('%b %Y')
        
        fig_bar = px.bar(
            monthly_df, x='Month', y='Live_Wasted_Fuel_USD', 
            title="Fuel Capital Destroyed per Month (USD)",
            text_auto='.2s' # Automatically adds formatted numbers on top of bars
        )
        fig_bar.update_traces(marker_color='#FF5252', textposition='outside')
        fig_bar.update_layout(plot_bgcolor='#1E1E1E', paper_bgcolor='#1E1E1E', font_color='#A0A0A0', yaxis_title="Wasted USD")
        st.plotly_chart(fig_bar, use_container_width=True)

        # --- IMPROVEMENT: CFO FINANCIAL EXPORT ---
        st.markdown("### Export Financial Ledger")
        st.caption("Download CFO-ready CSV with daily USD leakage and Carbon Tax liabilities.")
        finance_cols = ['Date', 'Vessel_ID', 'Normal_Fuel_MT_Day', 'Total_Fuel_MT_Day', 'Live_Wasted_Fuel_USD', 'Live_Carbon_Tax_EUR']
        finance_export = v_df[[c for c in finance_cols if c in v_df.columns]].copy()
        
        # CFO Financial Ledger DataFrame
        st.markdown("#### Daily Financial Ledger")
        ledger_df = v_df[['Date', 'Normal_Fuel_MT_Day', 'Total_Fuel_MT_Day', 'Live_Wasted_Fuel_USD', 'Live_Carbon_Tax_EUR']].copy()
        
        # Format the dataframe for the CFO (Decimals and Currency)
        st.dataframe(
            ledger_df.style.format({
                'Normal_Fuel_MT_Day': '{:.1f} MT',
                'Total_Fuel_MT_Day': '{:.1f} MT',
                'Live_Wasted_Fuel_USD': '${:,.0f}',
                'Live_Carbon_Tax_EUR': '€{:,.0f}'
            }),
            use_container_width=True, hide_index=True
        )

        st.download_button(
            label="📄 Download Financial Ledger (CSV)",
            data=finance_export.to_csv(index=False).encode('utf-8'),
            file_name=f"Financial_Ledger_{selected_vessel}_{start_date}.csv",
            mime="text/csv"
        )
        st.markdown("---")
        # --- IMPROVEMENT: IMO DCS / EU MRV COMPLIANCE EXPORT ---
        st.markdown("### Official Regulatory Compliance")
        st.caption("Export daily CO2 metrics formatted for IMO DCS and EU MRV reporting.")
        
        imo_df = v_df[['Date', 'Vessel_ID', 'Total_Fuel_MT_Day', 'Extra_CO2_MT_Day']].copy()
        # Rename columns to match government standards
        imo_df.columns = ['Reporting_Date', 'IMO_Ship_ID', 'Total_Fuel_Consumption_MT', 'CO2_Emissions_MT']
        
        imo_csv = imo_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Generate IMO DCS / EU MRV Log (CSV)",
            data=imo_csv,
            file_name=f"IMO_Compliance_Log_{selected_vessel}_{start_date}.csv",
            mime="text/csv"
        )

    # ==========================================
    # TAB 2: TECHNICAL PHYSICS (SUPERINTENDENT)
    # ==========================================
    with tab_technical:
        st.markdown("### Propeller Law Power Breakdown")

        # --- DIAGNOSTIC ALERT SYSTEM ---
        latest_cause = v_df['Degradation_Root_Cause'].iloc[-1] if 'Degradation_Root_Cause' in v_df.columns else 'Indeterminate'
        avg_confidence = v_df['Data_Confidence_Pct'].mean() if 'Data_Confidence_Pct' in v_df.columns else 100.0
        
        speed_variance = v_df['STW_Kts'].std()
        if avg_confidence < 75.0 or speed_variance > 1.5:
            st.warning(f"**DATA INTEGRITY WARNING (Confidence: {avg_confidence:.1f}%):** High variance or missing data detected. Recommend reviewing onboard Noon Report protocols for accuracy.")
            
        if latest_cause == 'Speed_Log_Sensor_Failure':
            st.error("*HARDWARE ALERT:* Severe STW vs SOG deviation. Doppler log is likely drifting. DO NOT order hull cleaning based on this data.")
        elif latest_cause == 'Engine_Mechanical_Suspected':
            st.error("*ROOT CAUSE ALERT:* High fuel burn but normal propeller slip. Suspect internal engine wear, NOT hull fouling.")
        elif latest_cause == 'Hull_Fouling_Suspected':
            st.info("*ROOT CAUSE:* Strong correlation between added drag and slip. Biological hull fouling confirmed.")
        st.markdown("---")
        
        # YOUR NEW IDEA: The Power Chart
        # We dynamically calculate the Power (kW) required to hit the user's CP speed,
        # comparing the Clean Baseline vs. the Fouled Reality.
        st.caption("Using Propeller Law (P ∝ V³) to isolate hydrodynamic drag in Kilowatts.")
        
        # Synthetic calculation for Streamlit display based on inputted speed
        target_speed = st.slider("Select Target Speed for Power Analysis (Knots)", 10.0, 16.0, 13.5, 0.5)
        current_fouling = v_df['Smoothed_Fouling_Pct'].iloc[-1]
        
        # Proxy baseline power for a generic Supramax (e.g., 6000 kW at 13.5 kts)
        clean_power_req = 6000 * ((target_speed / 13.5) ** 3)
        dirty_power_req = clean_power_req * (1 + current_fouling)
        
        col_p1, col_p2 = st.columns(2)
        col_p1.metric("Clean Hull Power Required", f"{clean_power_req:,.0f} kW")
        col_p2.metric(f"Fouled Hull Power Required (+{current_fouling*100:.1f}%)", f"{dirty_power_req:,.0f} kW", f"+{dirty_power_req - clean_power_req:,.0f} kW Wasted", delta_color="inverse")
        
        # Transparency Metrics
        st.markdown("### AI Classifier Decision Weights")
        st.caption("Transparency metric: Which physics variables drove the machine learning model's daily diagnosis.")
        
        # Synthetic feature importance for dashboard demonstration (In a full app, this comes from the ML model output)
        features = ['Speed Delta (STW - SOG)', 'Extra Fuel Burn', 'Slip Percentage', 'Draft/Ballast State', 'Wind Resistance']
        weights = [42, 35, 12, 8, 3]
        
        fig_importance = px.bar(
            x=weights, y=features, orientation='h', 
            title="Relative Importance of Hydrodynamic Features",
            labels={'x': 'Influence Weight (%)', 'y': 'Physics Feature'}
        )
        fig_importance.update_traces(marker_color='#A0A0A0')
        fig_importance.update_layout(yaxis={'categoryorder':'total ascending'}, plot_bgcolor='#1E1E1E', paper_bgcolor='#1E1E1E')
        st.plotly_chart(fig_importance, use_container_width=True)

        # The AI Degradation Curve
       # IMPROVEMENT: Sister-Ship Benchmarking & Draft Toggle
        st.markdown("---")
        st.markdown("### AI Monotonic Hull Degradation Curve & Sister-Ship Benchmarking")
        
        col_t1, col_t2 = st.columns([2, 2])
        with col_t1:
            draft_filter = st.radio("Vessel Draft State Filter", ["All", "Laden", "Ballast"], horizontal=True)
        with col_t2:
            # Multi-select allows them to choose other ships from the global 'df' to compare
            available_ships = df['Vessel_ID'].unique()
            compare_ships = st.multiselect("Benchmark against Sister Ships:", options=available_ships, default=[selected_vessel])
        
        # Filter the global dataframe for all selected ships
        benchmark_df = df[df['Vessel_ID'].isin(compare_ships)].copy()
        
        if draft_filter == "Laden":
            benchmark_df = benchmark_df[benchmark_df['Is_Ballast'] == False]
        elif draft_filter == "Ballast":
            benchmark_df = benchmark_df[benchmark_df['Is_Ballast'] == True]
            
        fig_fouling = px.line(
            benchmark_df, x='Date', y='Smoothed_Fouling_Pct', color='Vessel_ID',
            markers=True if draft_filter != "All" else False,
            title="Smoothed Hull Degradation Trend"
        )
        
        # Ensure the selected vessel is a thick, bright line
        for trace in fig_fouling.data:
            if trace.name == selected_vessel:
                trace.line.width = 4
                trace.line.color = '#00E676'
            else:
                trace.line.width = 1
                trace.line.color = '#555555'
        fig_fouling.layout.yaxis.tickformat = ',.1%'
        fig_fouling.update_layout(plot_bgcolor='#1E1E1E', paper_bgcolor='#1E1E1E', font_color='#A0A0A0')
        st.plotly_chart(fig_fouling, use_container_width=True)

        # Engineering Physics DataFrame
        st.markdown("#### Hydrodynamic & Degradation Log")
        tech_log_df = v_df[['Date', 'Is_Ballast', 'STW_Kts', 'Smoothed_Fouling_Pct', 'Degradation_Root_Cause']].copy()
        
        # Convert boolean to readable text and format percentages
        tech_log_df['Draft'] = np.where(tech_log_df['Is_Ballast'], 'Ballast', 'Laden')
        tech_log_df = tech_log_df.drop(columns=['Is_Ballast'])
        
        st.dataframe(
            tech_log_df.style.format({
                'STW_Kts': '{:.1f} kts',
                'Smoothed_Fouling_Pct': '{:.2%}'
            }),
            use_container_width=True, hide_index=True
        )

        # --- IMPROVEMENT: TECHNICAL PERFORMANCE EXPORT ---
        st.markdown("### Export Vessel Performance Data")
        st.caption("Download full thermodynamic and AI degradation logs for engineering review.")
        
        tech_export_cols = ['Date', 'Vessel_ID', 'Is_Ballast', 'STW_Kts', 'Normal_Fuel_MT_Day', 'Total_Fuel_MT_Day', 'AI_Predicted_Fouling_Pct','Smoothed_Fouling_Pct' 'Degradation_Root_Cause']
        
        final_tech_cols = [c for c in tech_export_cols if c in v_df.columns]
        tech_df = v_df[final_tech_cols].copy()
        
        # Convert Fouling % to a readable format(Uding the Smoothed Metric)
        if 'Smoothed_Fouling_Pct' in tech_df.columns:
            tech_df['Smoothed_Fouling_Pct'] = (tech_df['Smoothed_Fouling_Pct'] * 100).round(1).astype(str) + '%'
        if 'AI_Predicted_Fouling_Pct' in tech_df.columns:
            tech_df['AI_Predicted_Fouling_Pct'] = (tech_df['AI_Predicted_Fouling_Pct'] * 100).round(1).astype(str) + '%'
            
        tech_csv = tech_df.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="📄 Download Engineering Log (CSV)",
            data=tech_csv,
            file_name=f"Vessel_Performance_{selected_vessel}_{start_date}.csv",
            mime="text/csv",
            type="secondary" # Secondary type makes the button grey so it doesn't clash with the Legal Export button
        )

    # ==========================================
    # TAB 3: COMMERCIAL & CP LEGAL (FLEET DESK)
    # ==========================================
    with tab_commercial:
        # 1. NAUTILUS LABS STYLE TCE YIELD
        st.markdown("### Commercial Yield (TCE) Performance")
        daily_charter_rate = st.number_input("Input Daily Charter Revenue (TCE $/Day)", value=25000, step=1000)
        
        # 1. Calculate daily costs safely
        v_df['Baseline_Cost_USD'] = v_df['Normal_Fuel_MT_Day'] * bunker_price
        v_df['Actual_Cost_USD'] = (v_df['Total_Fuel_MT_Day'] * bunker_price) + (v_df['Live_Carbon_Tax_EUR'] if eu_ets_enabled else 0)
        
        # 2. Calculate daily profits (TCE)
        v_df['Ideal_TCE'] = daily_charter_rate - v_df['Baseline_Cost_USD']
        v_df['Actual_TCE'] = daily_charter_rate - v_df['Actual_Cost_USD']
        
        # 3. Average them across the selected timeframe
        avg_ideal = v_df['Ideal_TCE'].mean()
        avg_actual = v_df['Actual_TCE'].mean()
        
        # 4. Determine the exact Delta
        tce_delta = avg_actual - avg_ideal  
        tce_delta_pct = (abs(tce_delta) / avg_ideal) * 100 if avg_ideal > 0 else 0
        
        col_t1, col_t2 = st.columns(2)
        col_t1.metric("Ideal Profit Margin (Baseline)", f"${avg_ideal:,.0f}/day")
 
        # 5. Enterprise Logic Gate & Executive Warnings
        avg_baseline_fuel_cost = v_df['Baseline_Cost_USD'].mean()
        
        if avg_ideal < 0:
            # STOP: The revenue input doesn't even cover the physical fuel cost.
            st.warning(f"**COMMERCIAL ALERT:** At a TCE of **${daily_charter_rate:,.0f}/day**, this vessel operates at a net loss. The baseline fuel cost alone for this specific ship averages **${avg_baseline_fuel_cost:,.0f}/day**. Please input a realistic market charter rate to unlock performance metrics.")
        else:
            # PROCEED: Revenue covers baseline costs, we can accurately measure performance.
            if avg_actual >= avg_ideal:
                # OVERPERFORMING (Actual Profit is Higher / Loss is Smaller)
                col_t2.metric(
                    "Actual Profit Margin", 
                    f"${avg_actual:,.0f}/day", 
                    f"+${tce_delta:,.0f}/day (+{tce_delta_pct:.1f}% Gain)", 
                    delta_color="normal"
                )
                st.success(f"📈 **OVERPERFORMING:** Generating **${tce_delta:,.0f}/day** more than the baseline. Highly efficient hydrodynamic state.")
            else:
                # UNDERPERFORMING (Actual Profit is Lower / Loss is Heavier)
                loss = abs(tce_delta)
                col_t2.metric(
                    "Actual Profit Margin", 
                    f"${avg_actual:,.0f}/day", 
                    f"-${loss:,.0f}/day (-{tce_delta_pct:.1f}% Loss)", 
                    delta_color="normal" 
                )
                st.error(f"📉 **UNDERPERFORMING:** Hull degradation, drag, and taxes are destroying **${loss:,.0f}/day** in commercial yield.")
        st.markdown("---")
        
        # 2. STRICT LEGAL DESK: CHARTER PARTY PERFORMANCE
        st.markdown("### Strict Charter Party Performance Audit")
        col_inputs1, col_inputs2 = st.columns(2)
        default_speed = float(v_df['CP_Speed_Kts'].iloc[-1]) if 'CP_Speed_Kts' in v_df.columns else 13.5
        default_fuel = float(v_df['CP_Fuel_MT'].iloc[-1]) if 'CP_Fuel_MT' in v_df.columns else 24.0
        cp_speed_input = col_inputs1.number_input("CP Warranted Speed (Knots)", value=default_speed, step=0.1)
        cp_fuel_input = col_inputs2.number_input("CP Warranted Fuel (MT/Day)", value=default_fuel, step=0.5)
        
        # THE FIX: Drop days missing actual reported metrics (No AI hallucinations in court)
        legal_cols = ['Fuel_Consumed_MT', 'STW_Kts', 'Is_Good_Weather_CPA']
        available_cols = [c for c in legal_cols if c in v_df.columns]
        
        if len(available_cols) == len(legal_cols):
            legal_df = v_df.dropna(subset=['Fuel_Consumed_MT', 'STW_Kts']).copy()
            
            # The Propeller Law Math (with a safe denominator)
            safe_cp_speed = max(cp_speed_input, 0.1)
            legal_df['Dynamic_CP_Allowed_MT'] = cp_fuel_input * ((legal_df['STW_Kts'] / safe_cp_speed) ** 3)
            
            # THE FIX: Use strict CPA Weather (16 knots), not ML Weather
            legal_df['CP_Breach_Flag'] = np.where(
                (legal_df['Fuel_Consumed_MT'] > legal_df['Dynamic_CP_Allowed_MT']) & (legal_df['Is_Good_Weather_CPA'] == 1), 
                True, False
            )
            
            breach_days = legal_df['CP_Breach_Flag'].sum()
            if breach_days > 0:
                st.error(f"**ACTIONABLE CP CLAIM RISK:** {breach_days} days of legal overconsumption detected in STRICT contract weather.")
            else:
                st.success("**CP COMPLIANT:** Zero breach days detected in contract weather.")
                
            # Plot the Graph using legal_df
            fig_cp = go.Figure()
            fig_cp.add_trace(go.Scatter(x=legal_df['Date'], y=legal_df['Dynamic_CP_Allowed_MT'], mode='lines', name='Legal Limit (Propeller Law)', line=dict(color='#FFCA28', dash='dot')))
            fig_cp.add_trace(go.Scatter(x=legal_df['Date'], y=legal_df['Total_Fuel_MT_Day'], mode='lines', name='AI Computed Reality', line=dict(color='#29B6F6')))
            fig_cp.add_trace(go.Scatter(x=legal_df['Date'], y=legal_df['Fuel_Consumed_MT'], mode='markers', name='Raw Reported Fuel', marker=dict(color='#FFFFFF', size=4, opacity=0.5)))
            
            breach_data = legal_df[legal_df['CP_Breach_Flag'] == True]
            if not breach_data.empty:
                fig_cp.add_trace(go.Scatter(x=breach_data['Date'], y=breach_data['Fuel_Consumed_MT'], mode='markers', name='Actionable CP Breach', marker=dict(color='#FF5252', size=10, symbol='x')))
                
            fig_cp.update_layout(plot_bgcolor='#1E1E1E', paper_bgcolor='#1E1E1E', hovermode="x unified")
            st.plotly_chart(fig_cp, use_container_width=True)
            
            if breach_days > 0:
                st.markdown("#### Legal Breach Log")
                
                # Safely pull columns
                display_cols = ['Date', 'Speed_Over_Ground_Knots', 'STW_Kts', 'True_Wind_Speed_At_Structure_Kts', 'Wave_Height_M', 'Fuel_Consumed_MT', 'Dynamic_CP_Allowed_MT']
                safe_cols = [c for c in display_cols if c in breach_data.columns]
                display_df = breach_data[safe_cols].copy()
                
                # Safely rename using a dictionary (prevents length mismatch crashes)
                rename_map = {
                    'Speed_Over_Ground_Knots': 'SOG (kts)',
                    'STW_Kts': 'STW (kts)',
                    'True_Wind_Speed_At_Structure_Kts': 'Wind (kts)',
                    'Wave_Height_M': 'Waves (m)',
                    'Fuel_Consumed_MT': 'Actual Fuel (MT)',
                    'Dynamic_CP_Allowed_MT': 'CP Limit (MT)'
                }
                display_df.rename(columns=rename_map, inplace=True)
                
                if 'Actual Fuel (MT)' in display_df.columns and 'CP Limit (MT)' in display_df.columns:
                    display_df['Excess Fuel (MT)'] = display_df['Actual Fuel (MT)'] - display_df['CP Limit (MT)']
                
                st.dataframe(
                    display_df.style.format({
                        'SOG (kts)': '{:.1f}', 'STW (kts)': '{:.1f}', 
                        'Wind (kts)': '{:.1f}', 'Waves (m)': '{:.1f}',
                        'Actual Fuel (MT)': '{:.1f}', 'CP Limit (MT)': '{:.1f}', 'Excess Fuel (MT)': '{:.1f}'
                    }),
                    use_container_width=True, hide_index=True
                )
            # --- IMPROVEMENT: LEGAL EVIDENCE EXPORTER ---
            st.markdown("### Export Legal Arbitration Evidence")
            st.caption("Download court-ready CSV log including weather data and CP breaches.")
        
            # Prepare the export dataframe (Strictly factual data only)
            export_cols = [
                'Date', 'Vessel_ID', 
                'Speed_Over_Ground_Knots', 'STW_Kts', 'Current_Speed_Kts',
                'True_Wind_Speed_At_Structure_Kts', 'Wave_Height_M', 'Is_Good_Weather_CPA',
                'Fuel_Consumed_MT', 'Dynamic_CP_Allowed_MT', 'Total_Fuel_MT_Day', 
                'CP_Breach_Flag'
            ]
        
            # Ensure we only try to export columns that actually exist from Layer 4
            final_export_cols = [c for c in export_cols if c in v_df.columns]
            evidence_df = v_df[final_export_cols].copy()
        
            # Convert to CSV format in memory
            csv_data = evidence_df.to_csv(index=False).encode('utf-8')
        
            st.download_button(
                label="📄 Download CP Breach Evidence (CSV)",
                data=csv_data,
                file_name=f"CP_Arbitration_Log_{selected_vessel}_{start_date}.csv",
                mime="text/csv",
                type="primary"
            )
        else:
            st.warning("Cannot perform Legal CP Audit. Missing strict reported variables (Fuel_Consumed_MT or STW_Kts) from pipeline.")

    # ==========================================
    # TAB 4: FLEET OPERATIONS (VOYAGE EXECUTION)
    # ==========================================
    with tab_ops:
        st.markdown("### Voyage Environmental Execution")
        st.caption("Analyzing fuel leakage attributed to Master's routing decisions and ocean weather vectors.")
        
        # Failsafe: Ensure Layer 4 exported the required Layer 2 data
        required_ops_cols = ['Wave_Encounter_Angle', 'Current_Speed_Kts', 'Wind_Encounter_Angle']
        if all(col in v_df.columns for col in required_ops_cols):
            
            # --- 1. HEAD SEAS VS FOLLOWING SEAS ---
            # Head Seas: 0-45 deg | Beam Seas: 45-135 deg | Following Seas: 135-180 deg
            v_df['Sea_State_Category'] = pd.cut(
                v_df['Wave_Encounter_Angle'], 
                bins=[-1, 45, 135, 181], 
                labels=['Severe Head Seas', 'Beam/Cross Seas', 'Following Seas']
            )
            
            head_sea_days = v_df[v_df['Sea_State_Category'] == 'Severe Head Seas'].shape[0]
            total_days = len(v_df)
            
            col_o1, col_o2, col_o3 = st.columns(3)
            col_o1.metric("Total Voyage Days", total_days)
            col_o2.metric("Days Fighting Head Seas", head_sea_days, "Fuel Heavy", delta_color="inverse")
            
            # --- 2. OCEAN CURRENT ANALYTICS ---
            # If current is strong (> 0.5 knots) and ship STW > SOG, they are fighting the current.
            v_df['Fighting_Current'] = np.where(
                (v_df['Current_Speed_Kts'] > 0.5) & (v_df['STW_Kts'] > v_df['Speed_Over_Ground_Knots']),
                True, False
            )
            current_fighting_days = v_df['Fighting_Current'].sum()
            col_o3.metric("Days Fighting Ocean Currents", current_fighting_days, "Adverse Routing", delta_color="inverse")
            
            st.markdown("---")
            
            # --- 3. THE "BAD ROUTING" VISUALIZER ---
            st.markdown("#### Weather Resistance Distribution")
            # Create a pie chart showing the percentage of the voyage spent in different wave angles
            fig_waves = px.pie(
                v_df.dropna(subset=['Sea_State_Category']), 
                names='Sea_State_Category', 
                hole=0.4,
                color='Sea_State_Category',
                color_discrete_map={
                    'Severe Head Seas': '#FF5252', 
                    'Beam/Cross Seas': '#FFCA28', 
                    'Following Seas': '#00E676'
                }
            )
            fig_waves.update_layout(plot_bgcolor='#1E1E1E', paper_bgcolor='#1E1E1E', font_color='#A0A0A0')
            st.plotly_chart(fig_waves, use_container_width=True)
            
            # 4-Tier Routing Logic
            head_sea_pct = (head_sea_days / total_days) * 100 if total_days > 0 else 0
            if head_sea_pct < 10:
                st.success(f"**Execution Insight:** Excellent routing. Only {head_sea_pct:.1f}% of voyage spent fighting head seas.")
            elif head_sea_pct < 25:
                st.info(f"**Execution Insight:** Normal weather patterns. {head_sea_pct:.1f}% head seas encountered, within expected operational variance.")
            elif head_sea_pct < 40:
                st.warning(f"**Execution Insight:** Poor routing or storm evasion. {head_sea_pct:.1f}% of time spent in head seas caused notable fuel burn independent of hull condition.")
            else:
                st.error(f"**Execution Insight:** Severe route inefficiency. Over {head_sea_pct:.1f}% of the voyage faced direct head seas, destroying voyage TCE.")
            
            st.markdown("---")
            col_w1, col_w2 = st.columns(2)
            
            with col_w1:
                st.markdown("#### Wind Resistance Penalty")
                fig_scatter = px.scatter(
                    v_df, x='True_Wind_Speed_At_Structure_Kts', y='Extra_Fuel_MT_Day',
                    color='Is_Good_Weather_CPA', 
                    labels={'True_Wind_Speed_At_Structure_Kts': 'Wind Speed (Knots)', 'Extra_Fuel_MT_Day': 'Extra Fuel (MT)'},
                    color_continuous_scale='Bluered'
                )
                fig_scatter.update_layout(plot_bgcolor='#1E1E1E', paper_bgcolor='#1E1E1E', font_color='#A0A0A0')
                st.plotly_chart(fig_scatter, use_container_width=True)
                # 4-Tier Wind Penalty Logic
                avg_wind_penalty = v_df[v_df['True_Wind_Speed_At_Structure_Kts'] > 15]['Extra_Fuel_MT_Day'].mean()
                if pd.isna(avg_wind_penalty) or avg_wind_penalty < 0.5:
                    st.success("**Aerodynamic Profile:** Vessel is handling high winds with near-zero fuel penalty.")
                elif avg_wind_penalty < 2.0:
                    st.info(f"**Aerodynamic Profile:** Minor wind resistance. Average penalty of {avg_wind_penalty:.1f} MT/day in >15kt winds.")
                elif avg_wind_penalty < 5.0:
                    st.warning(f"**Aerodynamic Profile:** Moderate wind penalty. {avg_wind_penalty:.1f} MT/day lost to head/cross winds.")
                else:
                    st.error(f"**Aerodynamic Profile:** Severe windage drag. Losing {avg_wind_penalty:.1f} MT/day. Consider trim optimization for future rough weather.")
            
            with col_w2:
                st.markdown("#### Wave Height vs Speed Impact")
                fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
                fig_dual.add_trace(go.Bar(x=v_df['Date'], y=v_df['Wave_Height_M'], name="Waves (m)", marker_color='#29B6F6', opacity=0.6), secondary_y=False)
                fig_dual.add_trace(go.Scatter(x=v_df['Date'], y=v_df['Speed_Over_Ground_Knots'], name="SOG (kts)", mode='lines+markers', line=dict(color='#FFCA28')), secondary_y=True)
                fig_dual.update_layout(plot_bgcolor='#1E1E1E', paper_bgcolor='#1E1E1E', font_color='#A0A0A0', margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_dual, use_container_width=True)
                # 4-Tier Wave Impact Logic
                max_wave = v_df['Wave_Height_M'].max()
                if max_wave < 1.0:
                    st.success(f"**Hydrodynamic Impact:** Calm seas (Max {max_wave:.1f}m). No weather-induced speed loss detected.")
                elif max_wave < 2.5:
                    st.info(f"**Hydrodynamic Impact:** Moderate swells (Max {max_wave:.1f}m). Expected minor SOG fluctuations.")
                elif max_wave < 4.0:
                    st.warning(f"**Hydrodynamic Impact:** Rough seas (Max {max_wave:.1f}m). Speed drops correlate directly with wave impact, protecting hull integrity.")
                else:
                    st.error(f"**Hydrodynamic Impact:** Extreme weather events (Max {max_wave:.1f}m). Routing safety correctly prioritized over commercial speed warranties.")

            st.markdown("---")
            st.markdown("#### Voyage Execution Log (Latest to Past)")
            
            # Formatted reverse-chronological dataframe (Now including Encounter Angles)
            ops_log = v_df[['Date', 'Speed_Over_Ground_Knots', 'True_Wind_Speed_At_Structure_Kts', 'Wind_Encounter_Angle', 'Wave_Height_M', 'Wave_Encounter_Angle', 'Sea_State_Category', 'Fighting_Current']].copy()
            ops_log = ops_log.sort_values(by='Date', ascending=False)
            
            st.dataframe(
                ops_log.style.format({
                    'Speed_Over_Ground_Knots': '{:.1f} kts',
                    'True_Wind_Speed_At_Structure_Kts': '{:.1f} kts',
                    'Wind_Encounter_Angle': '{:.0f}°',
                    'Wave_Height_M': '{:.1f} m',
                    'Wave_Encounter_Angle': '{:.0f}°'
                }).map(lambda x: 'color: #FF5252; font-weight: bold;' if x is True else '', subset=['Fighting_Current']),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("Route Execution analytics require Layer 4 to export 'Wave_Encounter_Angle', 'Wind_Encounter_Angle', and 'Current_Speed_Kts'.")




