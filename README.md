# Bahana Stress Tester

> **Disclaimer:** This tool is a calculation-assistance aid. It is not intended as the sole basis for financial decisions. Always do your own research (DYOR).

For internals — module-by-module design detail, formulas, and the reasoning behind non-obvious choices — see [`docs/architecture.md`](docs/architecture.md). That document (and its companion [`CLAUDE.md`](CLAUDE.md)) is aimed at whoever is next modifying the code; this README is aimed at getting the app running. The build/production-readiness plan this fork is being executed against lives at [`docs/BUILD_SPEC.md`](docs/BUILD_SPEC.md).

---

## Quick Start

### 1. Configure API keys

Copy `.env.example` to `.env` and fill in your keys:

```env
LSEG_APP_KEY=your_lseg_app_key_here
```

LSEG Data Library is the primary price source; yfinance is the only fallback and works without any key, so the app runs with zero configuration if you don't have LSEG access — `DataManager` automatically falls back to yfinance if no LSEG session/app key is configured or a fetch fails. Macro data additionally benefits from a Trading Economics key (`TE_API_KEY`) and a FRED key (`FRED_API_KEY`) — both optional, with reduced coverage if omitted.

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
| Data Ingestion | LSEG Data Library (primary) → yfinance (fallback), with disk caching |
| Portfolio Input | Holdings entry (tickers + shares) or manual ticker list; diversity metrics (HHI, Gini, effective stocks); Presets tab (save/load/rename named portfolio snapshots) |
| Historical Stress Testing | 7 crisis scenarios replayed with actual per-stock returns; beta-scaled proxy for stocks that predate the event |
| Sector Shock Stress Test | Per-stock sector-relative beta (ETF OLS with circularity correction); DCC-GARCH dynamic correlations; Student-t copula tail dependence; HMM regime-conditioned correlation selection |
| Macro Contagion Stress Test | Leontief input-output contagion model; macro sensitivity matrix (Trading Economics/FRED/yfinance); spectral-radius cascade risk |
| Monte Carlo Simulation | 4 methods: GBM, block bootstrap, Student-t, jump-diffusion |
| Hedging Effectiveness | Beta classification against portfolio returns, stress-period vs. full-period fallback, hedge-effectiveness scoring |
| Risk Analytics | VaR/CVaR (historical, parametric, Cornish-Fisher), GARCH/EWMA volatility, drawdown family, Sharpe/Sortino/Calmar/Omega |
| Deep Risk Analysis | Tail risk (Jarque-Bera, QQ plot), Monte Carlo VaR, component/marginal VaR, Effective Number of Bets via PCA |
| Correlation Network | Ticker-level Minimum Spanning Tree, colored by real per-ticker P&L from a selected Historical or Sector Shock scenario; plus a sector-supernode calm-vs-crisis regime-correlation overlay (requires Sector Shock's models fitted first) |

---

## Repository Layout

```
Stress-Tester/
|
+-- app/                                  # Streamlit multi-page application
|   +-- Home.py                           # Landing page, session state init
|   +-- pages/
|       +-- 1_Portfolio_Input.py          # Holdings entry, manual tickers, and Presets (3 tabs)
|       +-- 2_Stress_Testing.py           # Historical, Sector Shock, Macro Contagion, Monte Carlo, Correlation Network
|       +-- 3_Risk_Analytics.py           # VaR/CVaR, drawdowns, correlations, volatility, tail risk, PCA (Phase 6)
|
+-- src/                                  # Core library
|   +-- data/                             # Multi-source fetch, cache, sector/macro data
|   +-- risk/                             # DCC-GARCH, copula, regime detection, sector/stock beta, contagion, macro sensitivity
|   |                                     # metrics.py / var.py / garch.py — used by 3_Risk_Analytics.py (Phase 6)
|   +-- simulation/                       # Monte Carlo, historical/sector/macro stress engines
|   +-- portfolio/                        # holdings.py only — calculator.py/rebalancer.py removed (Optimization/Monitoring out of scope)
|   +-- portfolio_builder/                # network.py — used by Stress Testing's Correlation Network tab (Phase 7a+7b)
|   |                                     # cache.py stays dormant (network.py's build_semantic_zoom_network()/
|   |                                     # build_correlation_matrix() need it, but neither 7a nor 7b calls those)
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

If you're importing from `src/portfolio_builder/cache.py` and hit something unexpected: it's kept in place on purpose (a `network.py` type-annotation dependency), not dead code, even though nothing calls its `run_nightly_refresh()`/SQLite-cache path.
