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

---

**Delivery note:** save this file at the repo root (or `docs/`) and
reference it from `CLAUDE.md` rather than re-pasting it fresh each
session — Claude Code will pick it up as persistent project context, and
Rule 3's per-phase context clearing works better against a file it can
re-read than a wall of text it has to remember.
