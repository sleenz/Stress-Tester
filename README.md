# Bahana Stress Tester

A scoped fork of PortfolioOptimizer, built for Bahana TCW: **Portfolio Input + Stress Testing + Risk Analytics.** Multi-source price ingestion, historical crisis replay, DCC-GARCH/Student-t-copula/HMM-regime sector shock propagation, Leontief macro contagion, and a baseline VaR/Sharpe/GARCH risk dashboard — with meaningful support for both US equities and the Indonesian market (IDX, `.JK` tickers).

Optimization, Portfolio Builder, Factor Analysis, Reports, and Stock Valuation are **out of scope** for this fork and have been removed. Risk Analytics was originally a documented Phase 6 fast-follow with its backing modules (`src/risk/metrics.py`, `var.py`, `garch.py`) kept dormant in the tree rather than deleted — Phase 6 has since restored `3_Risk_Analytics.py` against them, so they're active now, not dormant. `src/portfolio_builder/cache.py` and `network.py` are still kept dormant for a Phase 7 correlation-network companion view on the Stress Testing page.

> **Disclaimer:** This tool is a calculation-assistance aid. It is not intended as the sole basis for financial decisions. Always do your own research (DYOR).

For internals — module-by-module design detail, formulas, and the reasoning behind non-obvious choices — see [`docs/architecture.md`](docs/architecture.md). That document (and its companion [`CLAUDE.md`](CLAUDE.md)) is aimed at whoever is next modifying the code; this README is aimed at getting the app running. The build/production-readiness plan this fork is being executed against lives at [`docs/BUILD_SPEC.md`](docs/BUILD_SPEC.md).

---

## Quick Start

### 1. Configure API keys

Copy `.env.example` to `.env` and fill in your keys:

```env
ALPHA_VANTAGE_KEY=your_key_here
TWELVE_DATA_KEY=your_key_here
FMP_KEY=your_key_here
```

yfinance (the primary data source) works without any key. The other sources are fallbacks used only if yfinance fails. Macro data additionally benefits from a Trading Economics key (`TE_API_KEY`) and a FRED key (`FRED_API_KEY`) — both optional, with reduced coverage if omitted.

### 2. Install dependencies

Python 3.11 or 3.12 required (pinned in `runtime.txt` — `hmmlearn`'s wheel availability on Streamlit Community Cloud is the reason; the Sector Shock stress test's HMM regime-conditioning does not run without it).

```bash
pip install -r requirements.txt
```

### 3. Launch the web interface

```bash
streamlit run app/Home.py
```

### Lint / test

```bash
pytest tests/ -v
```

No separate lint config is checked in; `python -m py_compile $(git ls-files '*.py')` is the minimum sanity check before committing.

---

## Features

| Capability | Description |
|---|---|
| Data Ingestion | Multi-source fallback: yfinance → Alpha Vantage → Twelve Data → FMP, with disk caching |
| Portfolio Input | Holdings entry (tickers + shares) or manual ticker list; diversity metrics (HHI, Gini, effective stocks); Presets tab (save/load/rename named portfolio snapshots) |
| Historical Stress Testing | 7 crisis scenarios replayed with actual per-stock returns; beta-scaled proxy for stocks that predate the event |
| Sector Shock Stress Test | Per-stock sector-relative beta (ETF OLS with circularity correction); DCC-GARCH dynamic correlations; Student-t copula tail dependence; HMM regime-conditioned correlation selection |
| Macro Contagion Stress Test | Leontief input-output contagion model; macro sensitivity matrix (Trading Economics/FRED/yfinance); spectral-radius cascade risk |
| Monte Carlo Simulation | 4 methods: GBM, block bootstrap, Student-t, jump-diffusion |
| Hedging Effectiveness | Beta classification against portfolio returns, stress-period vs. full-period fallback, hedge-effectiveness scoring |
| Risk Analytics | VaR/CVaR (historical, parametric, Cornish-Fisher), GARCH/EWMA volatility, drawdown family, Sharpe/Sortino/Calmar/Omega |
| Deep Risk Analysis | Tail risk (Jarque-Bera, QQ plot), Monte Carlo VaR, component/marginal VaR, Effective Number of Bets via PCA |

---

## Repository Layout

```
Stress-Tester/
|
+-- app/                                  # Streamlit multi-page application
|   +-- Home.py                           # Landing page, session state init
|   +-- pages/
|       +-- 1_Portfolio_Input.py          # Holdings entry, manual tickers, and Presets (3 tabs)
|       +-- 2_Stress_Testing.py           # Historical, Sector Shock, Macro Contagion, Monte Carlo
|       +-- 3_Risk_Analytics.py           # VaR/CVaR, drawdowns, correlations, volatility, tail risk, PCA (Phase 6)
|
+-- src/                                  # Core library
|   +-- data/                             # Multi-source fetch, cache, sector/macro data
|   +-- risk/                             # DCC-GARCH, copula, regime detection, sector/stock beta, contagion, macro sensitivity
|   |                                     # metrics.py / var.py / garch.py — used by 3_Risk_Analytics.py (Phase 6)
|   +-- simulation/                       # Monte Carlo, historical/sector/macro stress engines
|   +-- portfolio/                        # holdings.py only — calculator.py/rebalancer.py removed (Optimization/Monitoring out of scope)
|   +-- portfolio_builder/                # cache.py / network.py kept but DORMANT — Phase 7 correlation-network companion view
|   +-- utils/                            # Presets, settings, logging, helpers
|
+-- tests/                                # pytest suite (preset manager, stock-sector beta)
+-- docs/architecture.md                  # Full module-by-module design detail
+-- docs/BUILD_SPEC.md                    # This fork's phased build/production-readiness plan
+-- CLAUDE.md                             # AI-agent-facing index (load-bearing decisions, known placeholders)
+-- requirements.txt                      # Python dependencies (trimmed to retained scope)
+-- runtime.txt                           # Pinned Python version (3.11.9)
+-- .env.example                          # API key template
+-- README.md                             # This file
```

Removed entirely (not dormant): `src/optimization/`, `src/factors/`, `src/reports/`, `src/valuation/`, `src/portfolio/calculator.py`, `src/portfolio/rebalancer.py`, `src/portfolio_builder/{fetch,ranking,metrics,heat_color,ff5_overlay}.py`, and six out-of-scope pages (`2_Optimization.py`, `5_Monitoring.py`, `6_Factor_Analysis.py`, `7_Reports.py`, `8_Stock_Valuation.py`, `10_Portfolio_Builder.py`). `3_Risk_Analytics.py` was deleted in the initial trim and restored in Phase 6 — it is active, not removed.

If you're importing from `src/portfolio_builder/` and hit something unexpected: check whether the module you want is `cache.py`/`network.py` before assuming it's dead code — those two are kept in place on purpose for a documented Phase 7 fast-follow, not an oversight.

---

## License / Contributing

No license file is present in this repository as of this writing — confirm usage terms with the repository owner before redistributing.
