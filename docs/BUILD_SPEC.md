# Bahana Stress Tester — Fork & Production-Readiness Build Spec

> This is the current, revised spec (Phase 1 revised to keep `src/risk/{metrics,var,garch}.py`
> and a minimal slice of `src/portfolio_builder/` dormant rather than deleted, to add
> Phase 6/Phase 7 fast-follows, and Phase 7 itself later revised mid-implementation into a
> P&L-colored stress-testing view rather than a generic Portfolio-Builder-style network).
> Referenced from `CLAUDE.md`. Status as of this version: Phase 0, 1, 3 done; Phase 2 skipped
> by explicit user directive (still outstanding); Phase 4 and 5 skipped by explicit user
> directive, out of sequence, to prioritize Phase 6 and 7; Phase 6 done; Phase 7a and 7b
> (stretch goal) both done. See git history / PR description for the phase-by-phase
> handoff notes.

## Context (read once, don't re-derive)
Forked from PortfolioOptimizer to ship a scoped stress-testing product for
Bahana TCW. Original target scope for v1: **Portfolio Input + Stress
Testing only**, with Risk Analytics as an optional Phase 6 fast-follow.
Optimization, Portfolio Builder, Factor Analysis, Reports, and Stock
Valuation are OUT of scope for this fork — do not port, fix, or reference
them beyond what's needed to cleanly remove them. Risk Analytics has since
shipped (Phase 6, done, out of sequence ahead of Phase 4/5 per explicit
user directive), and Stress Testing gained a Correlation Network tab
(Phase 7a, done, same out-of-sequence directive) — current scope is
**Portfolio Input + Stress Testing (incl. Correlation Network) + Risk
Analytics**.

---

## GLOBAL RULES — apply to every phase below, read before starting Phase 0

### RULE 1 — Stop, verify by a second party, wait
After completing each phase: STOP. Do not start the next phase.
Verification must NOT be self-reported by the same session that made the
change. Run the bundled `/code-review` skill (or spawn a fresh verification
subagent) against that phase's CHECK criteria — a fresh reviewer, not the
implementer, grades the work.

Tell the reviewer to flag only gaps that affect correctness or the phase's
stated requirements — not everything it can find. A reviewer instructed to
find problems will always find some; chasing all of them produces
unnecessary abstraction and defensive code nobody asked for.

Report back: (1) what you built/changed, (2) the CHECK result with actual
evidence — command run, real output, real numbers, not "it works" —
(3) what the independent reviewer found, (4) a final list of every file
changed and every command run. Wait for my explicit confirmation before
proceeding.

If a CHECK fails: rewind to before the failed attempt — don't layer a fix
on top of the failed one, that pollutes context for everything after it —
then retry with what you learned.

### RULE 2 — Smoke test is mandatory and separate from the functional CHECK
Standing, previously-observed failure mode in this project: tests confirmed
code ran without confirming every imported name actually exists, verbatim,
in the module it's imported from — this is exactly how the
`apply_preset_to_state` ImportError shipped before. Before reporting ANY
phase's CHECK:
- Import every module/function touched this phase — new, reused, AND
  anything downstream that might reference something this phase deleted or
  renamed — in a clean process, not the dev session's warm state.
- For deletion phases specifically: also confirm nothing retained still
  imports from a deleted module.
- Confirm every name resolves — no ImportError, no AttributeError.
- This precedes and is separate from the functional CHECK. A phase cannot
  pass CHECK on functional grounds while this is unverified.

### RULE 3 — Context hygiene between phases
Don't run multiple phases in one unbroken session. At the end of each
phase, write a short structured handoff: what was built/removed, exact
file paths touched, what's still pending, what the next phase needs to
know. Then clear/compact context before starting the next phase. Later
phases depend on earlier ones being right — they shouldn't also inherit a
degraded context window.

### RULE 4 — Verify the docs, don't trust them blindly
This repo's existing architecture docs (`CLAUDE.md`, `docs/architecture.md`)
describe module dependencies — e.g., the claim that Stress Testing has zero
dependency on Optimization, Risk Analytics, or Portfolio Builder. Treat
that as a strong prior, not a fact. Before deleting any module in Phase
0/1, grep the actual import graph and confirm it. These docs have already
been found stale once: their own stated reason for a design decision in
`network.py`/`fetch.py` didn't trace to anything in the code it cited.

---

## PLAN-FIRST — Phases 0, 1, 2
State your plan (files you'll touch or delete, 4-6 bullets) and wait for my
go-ahead BEFORE making changes in Phases 0-2. These are foundational — a
wrong deletion or a misdiagnosed bug here wastes every phase after it.
Phases 3-5 can proceed straight to implementation once their CHECK criteria
are clear.

---

## PHASE 0 — Real dependency audit (no deletions, no fixes yet) — DONE
1. Trace the real import graph for `app/Home.py`,
   `app/pages/1_Portfolio_Input.py`, and `app/pages/4_Stress_Testing.py` —
   every module, transitively, that these actually import. Use grep/AST
   inspection as the source of truth, not the architecture docs (Rule 4).
2. Produce a table: every file in the repo, whether it's on the real
   dependency path of the two retained pages, and a delete/keep
   recommendation.
3. Flag anything surprising — e.g. if Stress Testing turns out to import
   anything from `src/optimization/` or `src/portfolio_builder/` despite
   the docs saying otherwise.

**CHECK:** present the dependency table and proposed delete list. Do not
delete anything until I confirm it's accurate.

## PHASE 1 — Trim to scope — DONE
1. Delete confirmed out-of-scope pages — `2_Optimization.py`,
   `3_Risk_Analytics.py` (see Phase 6), `5_Monitoring.py`,
   `6_Factor_Analysis.py`, `7_Reports.py`, `8_Stock_Valuation.py`,
   `10_Portfolio_Builder.py` — per Phase 0's confirmed list.
2. Delete their exclusively-used backing `src/` modules — EXCEPT the
   modules earmarked for a fast-follow phase below. Leave these in place,
   unimported by any active page, rather than deleting and re-sourcing them
   later:
   - `src/risk/metrics.py`, `var.py`, `garch.py` (Phase 6)
   - `src/portfolio_builder/network.py`, and whatever minimal slice of
     `src/portfolio_builder/` it actually imports per Phase 0's audit —
     network.py is documented to work directly off a supplied correlation
     DataFrame, so this should NOT require keeping `fetch.py`, `cache.py`,
     or `ranking.py` (Phase 7)

   **Correction found during execution:** `network.py` has an
   *unconditional, module-level* `from src.portfolio_builder.cache import
   UniverseCache` (used as a type annotation on `build_correlation_matrix`/
   `build_semantic_zoom_network`). Even with `from __future__ import
   annotations`, the import statement itself still runs at module load —
   deleting `cache.py` would break `network.py`'s import, not just some
   unused branch. `cache.py` itself is fully self-contained at import time
   (only imports `src.utils.logger`; its one reference to `fetch.py` is
   inside `run_nightly_refresh()`, lazily imported and never called by
   anything `network.py` uses). So the actual minimal dormant slice kept
   is **`cache.py` + `network.py`** together — `fetch.py`, `ranking.py`,
   `metrics.py`, `heat_color.py`, `ff5_overlay.py` were still deleted.
   `src/portfolio_builder/__init__.py` is docstring-only (no re-exports),
   so no edit was needed there.

3. Renumber the retained pages sequentially (currently 1 and 4).
4. Trim `requirements.txt` to only what the retained scope needs.
5. Pin `runtime.txt` to Python 3.11 or 3.12 — fixes the `hmmlearn`
   wheel-incompatibility failure already observed in production
   (`MarketRegimeDetector.fit()` failing on Streamlit Cloud), required for
   Sector Shock Stress Test's regime-conditioning to run at all here.
6. Update `CLAUDE.md` and `README.md`: new scope statement, build/lint/test
   commands, folder-level warning on anything still imported from a
   since-trimmed area — including a note that `network.py` and the Phase 6
   risk modules are intentionally dormant, not dead code.

**CHECK + smoke test (Rule 2):** fresh process, both retained pages import
and load without error, app boots end to end with a real test portfolio.

## PHASE 2 — Fix the known launch blockers — SKIPPED (explicit user directive; still outstanding)
Each of these was previously observed in actual runtime logs, not inferred
from docs — reproduce and confirm root cause before fixing, don't assume
the prior diagnosis without checking it against current code:
1. `sector_stress.py` reporting `converged=False` for a fit `dcc_garch.py`
   logged as `converged=True` — a silent data-integrity bug in the exact
   engine this product ships. Reproduce it, fix the bookkeeping, confirm
   with a real fit that converges and is reported correctly end to end.
2. `apply_preset_to_state` ImportError on Portfolio Input — most likely
   cause per prior diagnosis is uncommitted/unpushed changes to
   `preset_manager.py`; confirm the actual cause (name mismatch vs.
   missing implementation vs. sync issue) before fixing.
3. `IDX_SECTOR_OVERRIDES["TLKM.JK"]` in `lseg_sectors.py` carries an
   unconfirmed-vs-LSEG comment — given IDX names are core to this product,
   confirm or correct this classification.

**CHECK:** for each item, show the reproduced failure, the fix, and a
rerun proving the failure mode no longer occurs — not a description of
the fix.

## PHASE 3 — Code-accuracy cleanup within the trimmed scope — DONE
1. Fix `sector_beta.py`'s docstring on
   `compute_stock_betas_vs_portfolio_sectors()` — it claims to be the path
   `SectorStressEngine.fit()` uses; it isn't
   (`stock_sector_beta.py::compute_all_stock_betas()` is).
2. Rename `scenarios.py::HISTORICAL_SCENARIOS` and
   `historical_scenarios.py`'s scenario list to remove the naming collision
   (e.g. `UNIFORM_SHOCK_SCENARIOS` / `PER_STOCK_CRISIS_SCENARIOS`) — both
   are live, don't delete either.
3. Grep for any remaining reference to a deleted module (Portfolio
   Builder, Optimization) anywhere in the retained code path and
   remove/update it.

**CHECK:** grep-verified zero dangling references; both renamed
collections still resolve correctly where used.

## PHASE 4 — Production hardening — SKIPPED (explicit user directive, out of sequence; still outstanding)
1. Confirm no API keys or secrets are committed; `.env.example` reflects
   only what this trimmed scope actually needs.
2. Add/confirm explicit logging at each of `sector_stress.py`'s four
   chained sub-model fits, distinguishing "sub-model failed" from
   "sub-model succeeded on degraded inputs" — silent failures are the
   priority category here, not visible errors.
3. Confirm `DataManager`'s fallback-chain behavior when the primary source
   (yfinance) is rate-limited or down.
4. Add a real automated test pass for both retained pages — assertions
   against known values (e.g. a benchmark ticker's known return in a known
   crisis window), not just "does it run."

**CHECK:** test suite run with actual pasted output.

## PHASE 5 — Deploy — SKIPPED (explicit user directive, out of sequence; still outstanding)
1. Two-page nav only (Portfolio Input, Stress Testing) — no
   `st.navigation()` sectioning needed at this size, don't over-build it.
2. Deploy to Streamlit Community Cloud from the fork.
3. End-to-end check with a real test portfolio against all three stress
   engines (Historical, Sector Shock, Macro Contagion).

**CHECK:** deployed URL loads clean; all three stress engines produce
results for a real multi-ticker IDX+US portfolio.

## PHASE 6 (optional, not required for v1) — Risk Analytics fast-follow — DONE
Originally planned to start only after Phase 5 shipped; done ahead of
Phase 4/5 by explicit user directive instead. Rewires `3_Risk_Analytics.py` against
`src/risk/metrics.py` / `var.py` / `garch.py`, which Phase 1 left in place
dormant rather than deleted — for baseline VaR/Sharpe context alongside
stress scenario results.

## PHASE 7 (optional, not required for v1) — Correlation network as a stress-tester view — 7a DONE, 7b DONE
Originally planned to start only after Phase 5 shipped; 7a done ahead of
Phase 4/5 by explicit user directive instead, independently of Phase 6.
Revised mid-implementation (see below) from a generic Portfolio-Builder-
style correlation network into a P&L-colored stress-testing view — two
sub-targets, in order, the second a stretch goal not required to close
this phase.

**7a — P&L-colored ticker network (v1 target) — DONE.** Added a
Correlation Network tab on the Stress Testing page (fifth tab, alongside
Historical/Monte Carlo/Sector Shock/Macro Contagion). Reuses
`src/portfolio_builder/network.py`'s ticker-level MST and color-gradient
code unmodified (`compute_distance_matrix`, `build_ticker_mst`,
`filter_edges_by_threshold`, `edge_color_for_correlation`,
`node_color_for_percentile`) — the node-coloring input is per-ticker P&L
for a user-selected scenario instead of the composite-ranking percentile
`node_color_for_percentile()` was originally written for; same function,
different input dimension. Fed a live `returns.corr()` matrix computed
from price data Stress Testing already pulls — `UniverseCache`/
`fetch.py`/the SQLite cache layer are bypassed entirely, not routed
through at all.

Historical and Sector Shock both produce real per-ticker P&L and are
wired as selectable sources (`HistoricalScenarioResult.pnl_by_stock`;
`SectorStressResult.to_dataframe()`'s `pnl_contribution_beta` column).
Macro Contagion is excluded, not silently interpolated: audited
`MacroStressEngine.run_stress()` and confirmed its per-ticker
`direct`/`total` return is looked up by **sector only**
(`contagion.h_initial.get(sector, ...)` / `contagion.leontief_total.get(sector, ...)`)
— every ticker sharing a sector gets an identical return, scaled only by
that ticker's own weight for the dollar P&L. Real position-sized P&L, not
real per-ticker differentiation; coloring nodes by it would look like a
differentiated signal that doesn't exist. Macro Contagion scenarios are
simply never added to the tab's selectable P&L-source list (not offered
disabled-with-a-message — there's nothing to click that could produce a
wrong number).

**CHECK (7a) result:** ran a live portfolio (AAPL, MSFT, JPM, BBCA.JK)
through Historical Scenarios (actual-returns mode) and Sector Shock (fit
+ all 7 scenarios), then confirmed the Correlation Network tab's P&L
source dropdown lists both a Historical and a Sector Shock entry, no
Macro Contagion entry ever appears (confirmed both by live UI check and
by grepping the source: `_cn_pnl_sources` is populated only from
`historical_actual_results` and `ss_all_results`/`ss_result`), and
switching between "Historical: COVID-19 Crash" and "Sector Shock: Tech
Selloff" produces visibly different node colors reflecting each
scenario's own real P&L ranking (e.g. JPM colored green under Tech
Selloff — unaffected, top-third — while AAPL/MSFT both orange, hit by
the sector-specific shock).

Before wiring in: `network.py`'s docstring justified staying at
ticker-level `.corr()` instead of DCC-GARCH by citing an "unresolved
convergence-misreport issue" in `dcc_garch.py`. Architecture.md's own
audit found that claim doesn't trace to anything in `dcc_garch.py`'s
actual code — done: the docstring now describes the real mechanism (a
hard `ConvergenceError` guard plus an explicit constant-vol fallback) and
no longer cites the unverified reason. The ticker-level decision itself
was always fine — only the stated justification was wrong.

**7b — Regime-correlation overlay (stretch goal) — DONE.** Added a
"Sector Regime-Correlation Overlay" section below the ticker network on
the same Correlation Network tab — an additional mode, not a replacement
for 7a's default ticker view or its `.corr()` data source. Uses
`network.py`'s existing sector-supernode MST functions
(`build_sector_mst`, reusing `compute_distance_matrix`/
`filter_edges_by_threshold`/`edge_color_for_correlation` from 7a
unmodified) fed sector-level correlation from
`MarketRegimeDetector.get_regime_correlation()` (via the fitted Sector
Shock engine's `_dcc_result`/`_regime_result`/`_regime_detector`) for
"calm" and "crisis" side by side. `get_correlation_at_quantile()` was not
used — the CHECK explicitly requires exercising the sub-5-observation
identity-matrix fallback, which only `get_regime_correlation()` has.

`get_regime_correlation()` returns only a DataFrame, no flag distinguishing
a real average from its identity-matrix fallback. Rather than modify that
function (against this project's absolute constraints), the page
replicates its exact aligned-observation count (same date-intersection
logic against `regime_result.state_sequence` and
`dcc_result.conditional_volatilities.index`) read-only, purely to decide
whether to show the "Insufficient regime history for '<regime>'" warning
*before* rendering. Verified this replication is bit-exact with the real
function's own fallback trigger: fit real `DCCGARCHModel`/
`MarketRegimeDetector` instances on synthetic data, manufactured a
`RegimeResult` with exactly 3 aligned days for one regime, and confirmed
both the replicated count and the function's actual identity-matrix
return agreed (`n_common=3 < 5` ↔ `is_identity=True`) — and also confirmed
on a normal fit that regimes with plenty of history (277 obs) do NOT
trigger it. No node-color reuse here (7a's P&L semantics don't apply to a
regime-vs-regime edge-structure comparison) — nodes are a flat color,
sized by aggregate sector weight.

**CHECK (7b) result:** live portfolio (AAPL, MSFT, JPM, XOM, BBCA.JK)
through Sector Shock's fit, then the overlay rendered Calm Regime (555
obs) as a sparse 2-edge MST with near-neutral edge colors, and Crisis
Regime (26 obs) as a denser 3-edge triangle with strongly coral
(positive-correlated) edges — visibly tighter, more positively-correlated
structure under crisis vs. calm, the regime-conditioning effect this
overlay exists to surface. No warning fired in this run (correctly —
both regimes had well above 5 observations); the sub-5 fallback path
itself was verified via the synthetic test above, not by trying to coax
a live portfolio into a data-starved regime.

**Post-7b refinements (direct user request, done):**
1. **Edge hover.** Neither 7a's nor 7b's edges actually showed their
   correlation on hover as originally built — a Plotly `mode="lines"`
   trace only matches hover near its plotted points (the two endpoints),
   not along the interior of the line, so hovering the middle of an edge
   showed nothing. Fixed by adding one invisible (`opacity=0`) marker per
   edge at its exact midpoint, carrying the `ρ=` hover text, as a separate
   trace layered under the node trace. Verified live: hovering the
   AAPL-JPM edge in the ticker network shows "AAPL – JPM: ρ=0.29" exactly
   at the edge's midpoint.
2. **7b is now a complete graph, not an MST.** With only a handful of
   sectors, showing every pairwise correlation directly is more
   informative than reducing to a spanning tree. Both the calm and crisis
   panels now render every sector pair; no more solid-vs-dotted
   MST/non-MST distinction in that view (color alone carries strength).
   `build_sector_mst` is no longer called by the page (network.py itself
   is untouched, still exports it).
3. **Gradient color palette for all correlation networks (7a and 7b).**
   Replaced `network.py`'s 2-color coral/steelblue
   `edge_color_for_correlation()` with a page-local `_edge_color_gradient()`
   using `plotly.colors.sample_colorscale("RdBu_r", ...)` — the same
   diverging colorscale already used elsewhere in this app for correlation
   heatmaps (e.g. Sector Shock's DCC Correlation Matrix), giving a much
   richer red↔white↔blue gradient instead of a flat 2-tone interpolation.
   `network.py`'s own `edge_color_for_correlation()` was left unmodified
   (unused by the page now, not deleted) rather than rewritten, consistent
   with not touching a reviewed/merged module's function as a side effect
   of a page-level styling change.

Verified: py_compile clean, pytest 17/17, live Playwright confirmed all
three — hover tooltip at an edge midpoint, 7b's complete 3-edge triangle
on both calm and crisis panels (vs. the previous 2-edge MST), and richer
red/orange/blue gradient shades visibly replacing the old flat
coral/steelblue on both 7a and 7b.

**Second refinement round (direct user request, done) — the RdBu_r
gradient above was itself superseded:**
1. **No dashed/dotted lines anywhere.** Every edge (7a and 7b) is now a
   normal solid line. The MST-vs-additional-threshold-edge distinction in
   7a is now carried by line width alone (thick vs thin), not dash style.
2. **Turbo instead of RdBu_r.** A diverging red-white-blue scale washes
   out to near-white right around correlation ≈ 0 — exactly the range a
   lot of real correlations fall in — making weak correlations hard to
   tell apart from each other. Turbo (`plotly.colors.sample_colorscale`)
   stays vivid across the entire `[-1, 1]` range: dark purple/blue (-1) →
   cyan → green (~0) → yellow/orange → dark red (+1) — every value is
   visually distinguishable, not just the extremes.
3. **Visible colorbar legend, range -1 to +1.** Added via a dedicated
   invisible marker trace whose `marker.colorscale`/`cmin`/`cmax`/
   `colorbar` are set (Plotly's standard technique for attaching a
   colorbar to a figure built from individually-colored line traces,
   which can't carry a colorbar themselves). Labeled "Correlation (ρ)"
   with tick marks at -1, -0.5, 0, 0.5, 1 — the real range for a
   correlation coefficient, not an arbitrary 0-1 scale.

Verified: py_compile clean, pytest 17/17, live Playwright confirmed all
three on both 7a and 7b — every edge solid (no dashing), a visible
colorbar reading -1 to +1 next to each chart, and vivid, clearly
distinguishable Turbo colors even for near-zero correlations that
previously rendered as barely-visible pale lines under RdBu_r.

---

## POST-PHASE-7 — Data source consolidation: LSEG primary, yfinance-only fallback — DONE

Explicit user directive, independent of the phase sequence above: add
LSEG Data Library as the primary price data source, keep yfinance as the
only fallback, and delete the other fallback sources outright.

1. **Added `LSEGSource` to `src/data/sources.py`** — calls
   `lseg.data.get_history(universe=tickers, fields=["TRDPRC_1"],
   interval="daily", adjustments=["CCH","CRE","RTS","RPO"])`. Requesting
   a single field is deliberate, not arbitrary: the library only builds a
   `(ticker, field)` column MultiIndex when *multiple* fields are
   requested (confirmed by reading
   `lseg/data/_access_layer/_history_df_builder.py` directly against an
   installed copy of the package) — a single-field request returns a
   flat, ticker-named-column DataFrame, the same shape every other
   source in this file already produces, with no extra reshaping code
   needed. Session credentials come from `LSEG_APP_KEY` (env var) or the
   library's own `lseg-data.config.json` discovery, opened lazily on
   first use via `_ensure_session()`.
2. **Deleted `AlphaVantageSource`, `TwelveDataSource`, `FMPSource`** from
   `sources.py` entirely (not deprecated-in-place) — `DataManager`
   (`data_manager.py:54-58`) now only ever constructs
   `[LSEGSource(), YFinanceSource()]`.
3. **`requirements.txt`**: `lseg-data>=2.0.0` promoted from the
   commented-out optional line to a real dependency (it now backs a
   primary price source, not just the optional TRBC sector lookup in
   `lseg_sectors.py`).
4. **`.env.example` created** (didn't previously exist despite the README
   referencing it — see below) with `LSEG_APP_KEY` plus the pre-existing
   `TE_API_KEY`/`FRED_API_KEY`/cache/log env vars; `ALPHA_VANTAGE_KEY`/
   `TWELVE_DATA_KEY`/`FMP_KEY` removed.
5. **README.md, docs/architecture.md, CLAUDE.md updated** to describe the
   two-source LSEG→yfinance chain in place of the old four-source one —
   see CLAUDE.md's Load-bearing decisions entry on `LSEGSource` for the
   full design rationale and the sandbox-verified fallback behavior.

Verified: `python -m py_compile` clean on `sources.py`/`data_manager.py`.
End-to-end fallback behavior confirmed live in a sandbox with the real
`lseg-data` package installed but no credentials/session configured (the
expected state in most deployments, since LSEG access is a paid,
credential-gated product): `DataManager.get_price_data()` logs
`Attempting to fetch from LSEG` → `LSEG` fails gracefully (no session) →
`Attempting to fetch from YFinance` → both fail only because this
sandbox has no outbound network route to either provider's servers, an
environment limitation confirmed separately, not a code defect. The
control-flow path (try LSEG, catch `DataSourceError`, fall through to
yfinance, never crash) is exactly what was verified, independent of
real network reachability.

Known gap, not yet fixed: `_ensure_session()`'s try/except does not
catch every LSEG failure mode — `ld.open_session()` does not raise when
no local Workspace/Eikon proxy is reachable, it silently returns a
non-connected session, so `self.mark_unavailable()` is never called in
that case. The outer `fetch_prices()`/`DataManager.get_price_data()`
exception handling still catches the resulting failure correctly on
every call and falls through to yfinance, so the fallback itself is not
broken — but an unconfigured LSEG session gets retried on every single
`get_price_data()` call rather than being marked permanently unavailable
after the first failure. Functionally fine; worth revisiting only if
fetch latency from the repeated failed attempt becomes a concern.

---

## POST-PHASE-7 — Macro contagion data: migrate FRED fallback to LSEG — DONE

Explicit user directive: migrate the macro-contagion network's FRED-sourced
fallback data to the LSEG Data Library. User confirmed two open questions
before implementation: (1) delete FRED entirely rather than keep it as a
deeper fallback beneath LSEG, and (2) broaden scope beyond the 3
variables that used FRED to also add an LSEG fallback for the 2 variables
that previously had none at all.

1. **`src/data/macro_data.py::_fetch_fred()` deleted outright**, along
   with the `fredapi`/pandas_datareader-fallback logic inside it,
   `MacroDataConfig.fred_api_key`, and the module's `fredapi` import
   guard (replaced with an `lseg.data` import guard, same try/except
   pattern as `lseg_sectors.py`/`sources.py`).
2. **New `_fetch_lseg()` method**, dispatched via a new `"lseg"` source
   type in `_fetch_source()`. Mirrors `LSEGSource.fetch_prices()`'s
   single-field `get_history(fields=["TRDPRC_1"])` call (same reasoning:
   a single field avoids the (RIC, field) MultiIndex the library only
   builds for multi-field requests). Unlike `LSEGSectorFetcher`, which
   relies on a session already being open elsewhere, this fetcher manages
   its own lazy session via a new `_ensure_lseg_session()` — deliberately
   self-contained so the macro fallback doesn't silently depend on call
   order with `LSEGSource`/`LSEGSectorFetcher` elsewhere in the app.
3. **5 of 9 `DEFAULT_MACRO_VARIABLES` entries updated**:
   - US_10Y, CPO, NICKEL: `fallback_source` changed from `"fred"` to
     `"lseg"`; RICs `US10YT=RR` / `FCPOc1` / `MNI3` — standard Refinitiv
     conventions for a benchmark Treasury yield and two exchange-traded
     commodities.
   - BI_RATE, CHINA_PMI: gained a `lseg` fallback where none existed
     before; RICs `IDCBIR=ECI` / `CNPMI=ECI` — Reuters' `<code>=ECI`
     economic-indicator convention. **These two are markedly less
     certain** than the three market-instrument RICs above — economic
     indicator RIC codes are catalog-specific per country/series, and
     could not be verified against a live LSEG session in this sandbox
     (no credentials available). Flagged in CLAUDE.md's Known
     placeholders / Load-bearing decisions as needing live confirmation
     before being trusted in production, same spirit as the `TLKM.JK`
     sector-override caveat already in `lseg_sectors.py`.
4. **Vestigial `import fredapi as _fredapi` guard blocks removed** from
   `src/risk/contagion.py`, `src/risk/macro_sensitivity.py`, and
   `src/simulation/macro_stress.py` — grep-confirmed dead code in all
   three (never referenced beyond the guard itself; only
   `macro_data.py::_fetch_fred()` ever made a real FRED call).
5. **`requirements.txt`**: `fredapi>=0.5.0` removed; `pandas_datareader`
   removed too since its only use in the retained codebase was as
   `_fetch_fred()`'s own fallback-of-fallback (grep-confirmed no other
   call sites). **`.env.example`**: `FRED_API_KEY` removed, `LSEG_APP_KEY`'s
   comment updated to note it now backs both the price source and this
   macro fallback. **README.md, CLAUDE.md, docs/architecture.md,
   app/Home.py, app/pages/2_Stress_Testing.py**: FRED mentions updated to
   describe the new Trading-Economics-primary / yfinance-or-LSEG-fallback
   chain.

Verified: `python -m py_compile` clean on every tracked `.py` file;
`pytest tests/ -v` 17/17 passed. Live-verified in the same credential-less
sandbox used for `LSEGSource`: with Trading Economics unconfigured
(`tradingeconomics` not installed) and LSEG installed but with no
reachable session, a single-variable fetch (`NICKEL`) correctly tried
Trading Economics → failed → tried LSEG → session-open attempted,
failed gracefully (`Session is not opened. Can't send any request`) →
`NICKEL` landed in `missing_variables`, `source_used['NICKEL'] ==
'failed'`, and `fetch()` never raised — matches the module's documented
"never raises" contract exactly.

---

## POST-PHASE-7 — Macro contagion data: delete Trading Economics, LSEG primary everywhere — DONE

Follow-up to the FRED migration above, same explicit user directive
taken further: replace Trading Economics too, so LSEG is primary for
all 9 macro variables and yfinance is the only fallback. Before
implementing, flagged a real viability gap and got it confirmed: 4 of
9 variables (CPO, NICKEL, BI_RATE, CHINA_PMI) have **no yfinance
equivalent at all** — no Bursa Malaysia palm oil futures ticker, no LME
base metals, no central-bank-rate or PMI coverage on yfinance. User
explicitly confirmed: delete Trading Economics everywhere anyway and
accept that these 4 variables end up with zero fallback (rather than
keeping Trading Economics for just those 4).

1. **`_fetch_te_market()`/`_fetch_te_indicator()` deleted outright**
   from `src/data/macro_data.py`, along with `MacroDataConfig.te_api_key`
   and the module's `tradingeconomics` import guard. `_fetch_source()`'s
   `"te_market"`/`"te_indicator"` dispatch branches removed.
2. **All 9 `DEFAULT_MACRO_VARIABLES` entries now have `primary_source="lseg"`**:
   - 5 with a real yfinance fallback: DXY (`.DXY` → `DX-Y.NYB`), VIX
     (`.VIX` → `^VIX`), IDR_USD (`IDR=` → `IDR=X`), COAL (`MTFc1` →
     `MTF=F`), US_10Y (`US10YT=RR` → `^TNX`, newly added — yfinance does
     carry a 10Y Treasury yield ticker even though it wasn't used
     before).
   - 4 with **no fallback at all** (the confirmed, accepted gap): CPO
     (`FCPOc1`), NICKEL (`MNI3`), BI_RATE (`IDCBIR=ECI`), CHINA_PMI
     (`CNPMI=ECI`).
3. **`requirements.txt`**: `tradingeconomics>=0.3.0` removed.
   **`.env.example`**: `TE_API_KEY` removed.
4. **README.md, CLAUDE.md, docs/architecture.md, app/Home.py,
   app/pages/2_Stress_Testing.py**: updated to describe the
   LSEG-primary/yfinance-fallback (or no-fallback) chain, with the
   4-variable gap called out explicitly wherever the chain is
   described, not buried.

**Risk profile, stated plainly:** all 9 primary LSEG RIC codes are
unverified against a live session (no credentials available in this
sandbox) — this migration trades a real, working Trading Economics
integration for an unverified one across the board. The 5 variables
with a yfinance fallback degrade gracefully if their LSEG RIC is wrong
(confirmed non-crashing in the FRED-migration verification above,
same code path). The 4 without a fallback do not — a wrong RIC for
CPO/NICKEL/BI_RATE/CHINA_PMI means that variable is simply missing
from every macro contagion run until the RIC is corrected. This was
surfaced to the user before implementation (not discovered after the
fact) and the "accept the gap" option was explicitly chosen over
"keep Trading Economics for just these 4."

Verified: `python -m py_compile` clean; `pytest tests/ -v` 17/17
passed. Same graceful-degradation code path as the FRED migration
(unchanged `_fetch_lseg()`/`_ensure_lseg_session()`/`_fetch_with_cache()`/
`fetch()` machinery) — a primary-source failure with no fallback
configured lands in `missing_variables` exactly like a primary+fallback
failure does, `fetch()` still never raises.

---

## POST-PHASE-7 — Regime + DCC-GARCH correlation diagnostics panel (Sector Shock tab) — DONE

Added a diagnostic-only UI panel to `app/pages/2_Stress_Testing.py`'s
Sector Shock tab, verifying that `MarketRegimeDetector`'s HMM regime
labels visually coincide with `DCCGARCHModel` correlation spikes — a
precondition check before any future walk-forward backtesting work.
`DCCGARCHModel`, `MarketRegimeDetector`, and `SectorStressEngine`'s
stress-calculation path were not touched, per the absolute constraint
against modifying reviewed/merged core algorithm modules.

**Data-availability audit (done before writing any UI code) — all three
were already available, no plumbing needed:**
1. Full per-date HMM state sequence: already exposed via
   `RegimeResult.state_sequence` (`src/risk/regime_detection.py`),
   already threaded onto every `SectorStressResult.regime_result`
   (`src/simulation/sector_stress.py`).
2. Full per-date DCC-GARCH correlation history: already exposed via
   `DCCGARCHResult.conditional_correlations` (shape `(T, N, N)`,
   `src/risk/dcc_garch.py`), aligned to `.conditional_volatilities.index`,
   already threaded onto every `SectorStressResult.dcc_result`.
3. `SectorStressEngine._select_correlation()` does call
   `get_current_regime_correlation()` → `get_regime_correlation()`
   today, but only for the current regime, and that function's return
   type is a `pd.DataFrame` only — it computes `n_common` internally
   purely to decide its own `<5`-observation identity-matrix fallback
   and never returns it to any caller. Rather than modify
   `MarketRegimeDetector` to return it, the new page-local
   `_diag_n_common_regime_obs()` helper generalizes the pattern already
   used (and documented as verified bit-exact) by this same file's
   existing 7b regime-overlay closure — read-only, same date-
   intersection logic, extended from calm/crisis-only to every
   configured regime label.

**Built (all in `app/pages/2_Stress_Testing.py`, module-level helpers
placed before `st.set_page_config()` since tab3 executes long before the
tab5 function-definition block further down the same script):**
1. Regime timeline (`add_vrect` background bands, calm→crisis) with a
   mean-off-diagonal DCC correlation line overlaid on the same date
   axis — renders accurately, does not editorialize on whether the line
   spikes inside crisis bands.
2. Regime-conditioned correlation small multiples — one `px.imshow`
   heatmap per configured regime (2, 3, or 4 depending on the existing
   "Number of states" control), each labelled with its real
   `n_observations`.
3. Identity-fallback surfacing — any panel with `n_observations < 5` is
   rendered with a flat gray colorscale (colorbar hidden) instead of the
   real one, titled "— FALLBACK", with a visible `st.warning(...)`
   annotation, so a rare regime's trivial identity matrix can't be
   mistaken for a real "no correlation" finding.

**Deviations from the literal task brief, both deliberate:**
- The brief said to reuse `heat_color.py`'s RdYlGn approach for the
  regime heatmaps' colormap. `heat_color.py` was deleted outright in
  this fork's Phase 1 trim (see `src/portfolio_builder/` row in
  `CLAUDE.md`'s directory map) and, even before deletion, was a
  Portfolio-Builder ranking/score colormap, never used for correlation
  matrices. This file's own actual, current convention for every other
  correlation-matrix render (Beta Matrix, DCC Correlation Matrix,
  "Correlation Matrix Used in This Run") is `RdBu_r` with a zero
  midpoint — used here instead, since that is the real "consistency
  with the rest of the app" the brief was asking for.
- The brief named `app/pages/4_Stress_Testing.py`; this fork's actual
  file is `app/pages/2_Stress_Testing.py` (page files were renumbered
  during the Phase 1 trim — see `CLAUDE.md`'s directory map).
- No dedicated regime color palette exists elsewhere in the app to
  reuse for the calm→crisis severity bands (grep-checked: only a blank
  per-regime emoji dict and a uniform node color in the existing
  Correlation Network tab's regime overlay) — reused this app's
  existing green=favourable/red=adverse `RdYlGn` convention (P&L
  gradients, Sortino ratio, shock-direction text) instead of inventing
  an unrelated one.

**Verified:**
- `python -m py_compile app/pages/2_Stress_Testing.py` clean.
- `pytest tests/ -v` 17/17 passed (unaffected — no `src/` module was
  touched).
- A standalone script fit a **real** `SectorStressEngine` (real
  `DCCGARCHModel.fit()` + real `MarketRegimeDetector.fit()`, no
  mocking) on synthetic-but-realistic sector returns with an injected
  calm→crisis→calm volatility/correlation regime shift, loaded the
  actual page module via `importlib`, and exercised every new helper
  and the full `_render_regime_dcc_diagnostics()` call against that
  real fit's `dcc_result`/`regime_result` — confirmed correct
  calm→crisis label ordering, mean-off-diagonal correlation in
  `[-1, 1]`, correct `n_observations` per regime from the real
  (unmodified) `get_regime_correlation()`, and 4 well-formed Plotly
  figures (1 timeline + 3 regime heatmaps) with the expected trace/band
  counts. A second, manufactured 3-observation "crisis" regime (same
  pattern as this file's own documented manufactured-3-observation
  verification for the 7b overlay) confirmed the `<5` fallback branch
  renders correctly and agrees with the real `get_regime_correlation()`
  identity-matrix fallback.

---

## POST-PHASE-7 — Emission cluster separability diagnostic (Step 2d, Sector Shock tab) — DONE

Follow-up to the Regime + DCC-GARCH diagnostics panel above, added after
that PR (#9) had already merged — restarted this branch from `main` per
the standard "PR already merged" procedure before building this on top.
Adds a second, deliberately separate diagnostic: where the panel above
(2a-2c) checks whether regime labels align with real DCC correlation
dynamics over *time*, this one (2d) checks whether the HMM's `n_states`
Gaussian emissions are actually separable in feature space at all — a
different, non-time-ordered precondition check for the same future
walk-forward backtest work. `DCCGARCHModel`, `MarketRegimeDetector`'s
fitting algorithm, and `SectorStressEngine`'s stress-calculation logic
were not touched — only additive data capture in `regime_detection.py`.

**Data audit (grep-verified against `regime_detection.py`, not assumed):**
1. Window length: `"rolling_vol"` uses `config.rolling_vol_window`
   (default **21** trading days, a single fixed window — not a 20-60 day
   range). `"mean_return"` uses **no window** — the raw daily
   cross-sector mean return. (`"vol_of_vol"`, not in the default feature
   set, applies that same 21-day window twice.) All features are
   z-score standardised before the HMM ever sees them.
2. `.predict_proba()`'s smoothed posterior was already exposed as
   `RegimeResult.state_probabilities` — no follow-up needed there.
3. `RegimeResult` did **not** expose the standardised feature matrix or
   the fitted `GaussianHMM.means_`/`covars_` — both are computed inside
   `fit()` but were discarded once `state_sequence`/`state_probabilities`
   were derived from them. Added as new, defaulted (`= None`) fields —
   `feature_matrix`, `hmm_means`, `hmm_covars` — populated from data
   `fit()` already computes, reordered with the exact same `state_order`
   permutation already used to relabel `state_sequence`/
   `state_probabilities`/the transition matrix. No existing field,
   default, or the fitting algorithm itself changed.

**hmmlearn bug found and worked around:** the installed `hmmlearn==0.3.3`'s
public `GaussianHMM.covars_` property returns the wrong shape for
`covariance_type="spherical"` — `(n_components * n_features, n_features,
n_features)` instead of `(n_components, n_features, n_features)` —
because `hmmlearn.utils.fill_covars()` calls `np.ravel()` on the internal
`_covars_` array (which redundantly repeats each state's scalar variance
across the feature axis) without accounting for that redundancy.
`MarketRegimeDetector._full_covariances()` (new private static method)
bypasses the public property for `"spherical"` and reconstructs the
correct `(n_states, n_features, n_features)` array directly from
`model._covars_`; `"full"`/`"diag"`/`"tied"` are unaffected and unchanged.
This page (`2_Stress_Testing.py`) always fits with the default
`covariance_type="full"` (only `n_states`/`n_init` are overridden from
the UI), so this bug was not reachable through the app before this fix —
handled anyway since the config field exists and a diagnostic panel
should not silently mis-render if that ever changes.

**Built** (`_render_emission_separability_diagnostic()` in
`app/pages/2_Stress_Testing.py`, wired into its own expander — "HMM
Emission Cluster Separability (State-Quality Check)" — placed as a
sibling to, not merged into, the existing "Regime ↔ DCC-GARCH Correlation
Diagnostics" expander, per the explicit instruction not to conflate the
two):
- Scatter of `(rolling_vol, mean_return)` in the standardised feature
  space the HMM actually operates in, one point per date, colored by the
  real Viterbi hard label using the same `_regime_label_order()`/
  `_regime_diag_color()` helpers as the 2a-2c panel (consistent palette,
  not reinvented).
- One real covariance ellipse per state at 1σ and 2σ, from the actual
  fitted `hmm_means`/`hmm_covars` via eigendecomposition — genuinely
  elliptical/tilted/differently-sized, not circles.
- Boundary-point flagging: a point is flagged (black marker outline) iff
  its squared Mahalanobis distance to some *other* state's mean/covariance
  is `<= 4` (i.e. inside that state's own 2σ ellipse) — the literal
  geometric condition, not a probability-threshold proxy for it. Every
  point's hover text (not just flagged ones) shows its hard label plus
  the top-2 soft posterior probabilities from `state_probabilities`, so a
  boundary point's ambiguity is never presented as if the hard label were
  unambiguous.
- A `sqrt(det(Σ))` "area proxy" + eigenvalue range table per regime is
  rendered below the chart so degenerate or near-coincident ellipses are
  visible as numbers too, not just a picture — no threshold decides
  "degenerate" for the user; the panel does not auto-merge or otherwise
  act on what it shows, per the explicit scope boundary against using
  this to change `n_states` as a side effect.
- Graceful degradation: if the fit's configured features aren't exactly
  `rolling_vol`/`mean_return` (a non-default `RegimeConfig.features`),
  the panel shows an explanatory `st.info()` instead of rendering a wrong
  or partial 2D projection.

**Verified:**
- `python -m py_compile` clean on both changed files.
- `python -m src.risk.regime_detection` (module's own smoke test,
  extended) — new assertions on `feature_matrix`/`hmm_means`/`hmm_covars`
  shapes, symmetry, and PSD-ness, plus a dedicated `covariance_type=
  "spherical"` case confirming the hmmlearn-bug workaround produces the
  correct `(n_states, 2, 2)` diagonal-equal-variance shape. All existing
  assertions in that smoke test still pass unchanged.
- `pytest tests/ -v` 17/17 passed (unaffected).
- `python -m src.simulation.sector_stress` (module's own smoke test) —
  unaffected, still passes.
- A standalone script fit a **real** `SectorStressEngine` (real
  `DCCGARCHModel.fit()` + real `MarketRegimeDetector.fit()`) on the same
  synthetic-but-realistic calm→crisis→calm sector-return data used for
  the 2a-2c verification, loaded the actual page module via `importlib`,
  and called `_render_emission_separability_diagnostic()` directly
  against that real fit's `regime_result` — confirmed a 9-trace figure
  (3 states × [1σ ellipse, 2σ ellipse, scatter]), all 880 real feature
  points accounted for across the per-state traces, and 69 of them
  correctly flagged as boundary points by the real Mahalanobis-distance
  check. A second real fit with a non-default `features=["vol_of_vol",
  "cross_sector_dispersion"]` config confirmed the graceful-degradation
  path renders the info message and zero figures, as intended.

---

**Delivery note:** save this file at the repo root (or `docs/`) and
reference it from `CLAUDE.md` rather than re-pasting it fresh each
session — Claude Code will pick it up as persistent project context, and
Rule 3's per-phase context clearing works better against a file it can
re-read than a wall of text it has to remember.
