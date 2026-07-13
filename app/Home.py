"""
Bahana Stress Tester - Streamlit Web Interface

Main entry point for the Streamlit application.
"""

import streamlit as st
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.utils.settings_manager import load_settings

# Page configuration
st.set_page_config(
    page_title="Bahana Stress Tester",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        padding-bottom: 2rem;
    }
    .feature-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 0.5rem 0;
    }
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Main header
st.markdown('<p class="main-header">Bahana Stress Tester</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Portfolio stress testing and scenario analysis for US and Indonesian (IDX) equities</p>', unsafe_allow_html=True)

# Introduction
st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### Welcome")
    st.markdown("""
    This application stress-tests a portfolio against historical crises,
    sector-level shocks, and macroeconomic contagion scenarios, with a
    baseline risk dashboard alongside. Navigate through the pages using
    the sidebar to:

    1. **Input** your portfolio holdings or tickers
    2. **Stress test** under historical, sector, and macro scenarios
    3. **Analyze** baseline risk — VaR, drawdowns, correlations, volatility
    """)

with col2:
    st.markdown("### Quick Start")
    st.markdown("""
    **Step 1:** Go to *Portfolio Input* and enter your holdings or tickers

    **Step 2:** Set your time period and capital

    **Step 3:** Go to *Stress Testing* and choose a scenario tab

    **Step 4:** Check *Risk Analytics* for VaR/Sharpe/drawdown context

    **Step 5:** Review portfolio impact, P&L, and hedging effectiveness
    """)

st.markdown("---")

# Feature overview
st.markdown("### Key Features")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### Historical Scenarios")
    st.markdown("""
    - 7 crisis scenarios (2008, COVID-19, ...)
    - Actual per-stock returns, beta-scaled proxy fallback
    - Hedging effectiveness analysis
    """)

with col2:
    st.markdown("#### Sector Shock")
    st.markdown("""
    - DCC-GARCH dynamic correlations
    - Student-t copula tail dependence
    - HMM regime-conditioned correlation selection
    """)

with col3:
    st.markdown("#### Macro Contagion")
    st.markdown("""
    - Leontief input-output contagion model
    - LSEG / yfinance macro factors
    - Monte Carlo simulation (GBM, bootstrap, Student-t, jump-diffusion)
    """)

st.markdown("#### Risk Analytics")
st.markdown("""
- VaR/CVaR (historical, parametric, Cornish-Fisher), GARCH, drawdown family
- Sharpe/Sortino/Calmar/Omega, tail risk (Jarque-Bera, QQ plot)
- Risk contribution, hedge classification, Effective Number of Bets via PCA
""")

st.markdown("---")

# Session state initialization
if 'portfolio_data' not in st.session_state:
    st.session_state.portfolio_data = None
if 'optimization_result' not in st.session_state:
    st.session_state.optimization_result = None
if 'tickers' not in st.session_state:
    st.session_state.tickers = []

if "settings" not in st.session_state:
    saved = load_settings()
    st.session_state.settings = {
        "total_capital":       saved["portfolio"]["total_capital"],
        "optimization_method": saved["optimization"]["method"],
        "risk_free_rate":      saved["optimization"]["risk_free_rate"],
        "max_weight":          saved["optimization"]["max_weight"],
        "min_weight":          saved["optimization"]["min_weight"],
        "target_volatility":   saved["optimization"]["target_volatility"],
        "allow_fractional":    saved["optimization"]["allow_fractional"],
    }
    if saved["portfolio"]["tickers"] and "tickers" not in st.session_state:
        st.session_state.tickers = saved["portfolio"]["tickers"]

def main():
    """Main function for CLI entry point."""
    import subprocess
    import sys
    subprocess.run([sys.executable, "-m", "streamlit", "run", __file__])


if __name__ == "__main__":
    pass
