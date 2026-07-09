# CLAUDE.md

> Last verified against the codebase: 2026-07-09, Bahana Stress Tester Phase 1 (fork trim complete).
> This file is not self-maintaining. If you change a module described below, re-verify the relevant line before trusting it — a stale entry here is worse than no entry.
> The phased build/production-readiness plan this fork is executed against lives at [`docs/BUILD_SPEC.md`](docs/BUILD_SPEC.md) — read it before starting any phase's work.

## What this is

**Bahana Stress Tester** is a scoped fork of PortfolioOptimizer for Bahana TCW: a Streamlit web app + Python library covering **Portfolio Input + Stress Testing only** — multi-source price ingestion, historical crisis replay (actual per-stock returns with beta-scaled proxy fallback), DCC-GARCH/Student-t-copula/HMM-regime sector shock propagation, Leontief macro contagion, and Monte Carlo simulation. It has meaningful Indonesian-market (IDX, `.JK` tickers) support alongside US equities. Built for a solo/small-team quant workflow, not a regulated production trading system — treat it as a calculation-assistance tool (see README.md's disclaimer).

Optimization, Portfolio Builder (ranking/correlation-network), Factor Analysis, Reports, and Stock Valuation are **out of scope** and have been removed from this fork — see `docs/BUILD_SPEC.md` Phase 0/1 for the dependency audit that confirmed what could be deleted cleanly. Risk Analytics (VaR/Sharpe/GARCH) is a documented Phase 6 fast-follow; its backing modules are kept dormant rather than deleted (see below).

## Directory map

| Path | Purpose |
|---|---|
| `app/Home.py`, `app/pages/1_Portfolio_Input.py`, `app/pages/2_Stress_Testing.py` | The entire retained Streamlit UI. Page 1 also owns Presets as a tab. Page 2 has four tabs: Historical Scenarios, Monte Carlo, Sector Shock, Macro Contagion. |
| `src/data/` | Multi-source price fetch (yfinance→AlphaVantage→TwelveData→FMP), pickle cache, sector classification (TRBC/GICS, incl. IDX overrides in `lseg_sectors.py`), FRED/Trading-Economics macro data. |
| `src/risk/` | `DCCGARCHModel` (sector-level), `StudentTCopula`, `MarketRegimeDetector` (HMM), `LeontifContagionEngine`, sector/stock beta, macro sensitivity. **`metrics.py`, `var.py`, `garch.py` are present but DORMANT** — kept in place per `docs/BUILD_SPEC.md` Phase 6, not imported by any active page. Don't mistake them for dead code, and don't wire them into a page without re-reading Phase 6's scope first. |
| `src/simulation/` | `MonteCarloSimulator` (4 methods), legacy uniform-shock `StressTester` (`scenarios.py`), real-per-stock `HistoricalStressor` (`historical_scenarios.py`), `SectorStressEngine`, `MacroStressEngine` (Leontief). |
| `src/portfolio/` | `HoldingsTracker` only. `calculator.py`/`rebalancer.py` were deleted in the fork trim (Optimization/Monitoring out of scope) — `src/portfolio/__init__.py` was edited accordingly; don't re-add imports of those two names without restoring the files. |
| `src/portfolio_builder/` | **`cache.py` + `network.py` only, both DORMANT** — kept per `docs/BUILD_SPEC.md` Phase 7 (a future correlation-network companion tab on Stress Testing). `fetch.py`, `ranking.py`, `metrics.py`, `heat_color.py`, `ff5_overlay.py` were deleted — do not re-import them; if Phase 7 needs scoring/ranking logic, that's a signal the phase's scope has grown beyond what was planned. `network.py` has an unconditional top-level import of `UniverseCache` from `cache.py` (not just a lazy one) — that's why `cache.py` had to stay too even though nothing calls its `fetch.py`-dependent `run_nightly_refresh()` path. |
| `src/utils/` | `preset_manager.py` (portfolio preset persistence, no network dependency), `settings_manager.py`, logging, helpers. |
| `docs/architecture.md` | Full module-by-module detail for the ORIGINAL (pre-fork) PortfolioOptimizer codebase — still useful for understanding *why* a retained module (e.g. DCC-GARCH, sector beta) is built the way it is, but describes several modules (Optimization, Portfolio Builder ranking, Factor Analysis, Reports, Valuation) that no longer exist in this fork. Read it for retained-module context only; don't use it to relocate a deleted feature. |
| `docs/BUILD_SPEC.md` | This fork's phase-by-phase build/production-readiness plan — the authoritative source for what's done, what's dormant-on-purpose, and what's still pending. |

## Load-bearing decisions

- **`src/risk/sector_beta.py` is load-bearing from two different call sites** — `SectorStressEngine.fit()` (`sector_stress.py`) uses `SectorBetaAnalyzer.compute()` for the cross-sector beta matrix shown in the UI, while the actual per-stock betas used for P&L come from `compute_all_stock_betas()` in `stock_sector_beta.py`. Separately, `MacroStressEngine.fit()` (`macro_stress.py`) lazily imports `SectorBetaAnalyzer` again for sector-return construction (Step 3 of its fit) — a real, core-path usage, not a fallback. Neither `sector_beta.py` nor `stock_sector_beta.py` can be merged or deleted. `sector_beta.py`'s own docstring on `compute_stock_betas_vs_portfolio_sectors()` claiming to be the primary path `SectorStressEngine.fit()` uses is stale — see `docs/BUILD_SPEC.md` Phase 3 item 1.
- **Two package `__init__.py` landmines exist in this codebase's history — watch for a third.** Deleting a module that a sibling module's package `__init__.py` still imports breaks *every* consumer of that package, not just the deleted module's own callers (Python runs a package's `__init__.py` on any submodule import). This is exactly how `src/portfolio/__init__.py` would have broken Portfolio Input if `calculator.py`/`rebalancer.py` had been deleted without also trimming `__init__.py`'s imports (now fixed — `__init__.py` only exports `holdings.py` names). `src/risk/__init__.py` still imports from `metrics.py`/`var.py`/`garch.py`, but since those three files are being kept (dormant, not deleted — see Phase 6), that package's `__init__.py` needed no change. Before deleting any module in a package with siblings, check the package's `__init__.py` first.
- **Preset loading populates `current_holdings` via a live price fetch, not just `weights`/`portfolio_value`** — `src/utils/preset_manager.py::apply_preset_to_state()` only ever sets `tickers`/`weights`/`portfolio_value`/`settings`/`loaded_preset_id`; it deliberately still does not touch `current_holdings`. `app/pages/1_Portfolio_Input.py`'s `_load_preset_and_populate_holdings()` wraps it and additionally derives `shares = weight * portfolio_value / current_price` — kept out of `preset_manager.py` on purpose to keep that module free of a network/`DataManager` dependency.
- **Portfolio Presets is a tab on Portfolio Input, not a separate page** — merged in because preset-loading and holdings-editing are the same workflow.

## Known placeholders — do not mistake these for real, load-bearing values

- **`src/data/lseg_sectors.py::IDX_SECTOR_OVERRIDES["TLKM.JK"]`**: applied unconditionally in code, but carries an inline `# Confirm vs LSEG assignment` comment — i.e. shipped before the override was actually confirmed correct. Given IDX names are core to this product, this is `docs/BUILD_SPEC.md` Phase 2 item 3 — confirm or correct before relying on it.
- **`src/risk/sector_beta.py::compute_stock_betas_vs_portfolio_sectors()` is NOT on `SectorStressEngine.fit()`'s path** — grep-verified: it's called nowhere in the codebase outside its own definition. Its docstring used to claim otherwise (fixed, `docs/BUILD_SPEC.md` Phase 3 item 1); the real per-stock-beta path is `compute_all_stock_betas()` in `src/risk/stock_sector_beta.py`.
- **`scenarios.py`'s legacy uniform-shock dict is `UNIFORM_SHOCK_SCENARIOS`; `historical_scenarios.py`'s actual-per-stock-returns list is `PER_STOCK_CRISIS_SCENARIOS`** — previously both were named `HISTORICAL_SCENARIOS` (a naming collision fixed in `docs/BUILD_SPEC.md` Phase 3 item 2). Both are still live and used for different things — don't conflate them.
- **`sector_stress.py` reporting `converged=False` for a fit `dcc_garch.py` logged as `converged=True`** — a known, not-yet-fixed bookkeeping bug. `docs/BUILD_SPEC.md` Phase 2 item 1 — deferred, not yet addressed in this fork.

## Absolute constraints

- Streamlit + the existing Python backend only. No React, Redis, graph database, WebSockets, or 3D rendering anywhere in this codebase (confirmed: no `package.json`, no such dependencies in `requirements.txt`, no matching imports).
- Do not modify the existing DCC-GARCH or sector-normalization modules' core algorithms as a side effect of unrelated work — extend via new config fields/functions, not by rewriting what's already reviewed and merged.
- Do not re-import from a deleted module (`src/optimization/`, `src/factors/`, `src/reports/`, `src/valuation/`, `src/portfolio/{calculator,rebalancer}.py`, `src/portfolio_builder/{fetch,ranking,metrics,heat_color,ff5_overlay}.py`) or a deleted page (`2_Optimization.py`, `3_Risk_Analytics.py`, `5_Monitoring.py`, `6_Factor_Analysis.py`, `7_Reports.py`, `8_Stock_Valuation.py`, `10_Portfolio_Builder.py`) — these are gone, not just unlinked from nav.
- Python 3.11 or 3.12 only (pinned in `runtime.txt`) — required for `hmmlearn` wheel availability on Streamlit Community Cloud; the Sector Shock stress test's HMM regime-conditioning does not run on other versions.

## Where to go next

For full module-by-module detail on the modules this fork retained — dataclass listings, exact function signatures, and the reasoning behind each non-obvious choice (e.g. why HRP-vs-ticker-level-DCC-GARCH tradeoffs were made the way they were) — see [`docs/architecture.md`](docs/architecture.md), keeping in mind it also documents several now-deleted modules. For what's done, pending, or intentionally dormant in this fork, [`docs/BUILD_SPEC.md`](docs/BUILD_SPEC.md) is authoritative. Read the relevant section before touching a module; this file is an index, not a substitute for reading the code you're changing.
