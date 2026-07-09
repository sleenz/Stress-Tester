# Bahana Stress Tester — Fork & Production-Readiness Build Spec

> This is the current, revised spec (Phase 1 revised to keep `src/risk/{metrics,var,garch}.py`
> and a minimal slice of `src/portfolio_builder/` dormant rather than deleted, and to add
> Phase 6/Phase 7 fast-follows). Referenced from `CLAUDE.md`. Status as of this version:
> Phase 0, 1, 3 done; Phase 2 skipped by explicit user directive (still outstanding); Phase 4
> and 5 skipped by explicit user directive, out of sequence, to prioritize Phase 6; Phase 6
> done. See git history / PR description for the phase-by-phase handoff notes.

## Context (read once, don't re-derive)
Forked from PortfolioOptimizer to ship a scoped stress-testing product for
Bahana TCW. Target scope: **Portfolio Input + Stress Testing only.**
Optimization, Portfolio Builder, Factor Analysis, Reports, and Stock
Valuation are OUT of scope for this fork — do not port, fix, or reference
them beyond what's needed to cleanly remove them. Risk Analytics is a
documented Phase 6 candidate, not required for v1.

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
Only start after Phase 5 ships. Rewires `3_Risk_Analytics.py` against
`src/risk/metrics.py` / `var.py` / `garch.py`, which Phase 1 left in place
dormant rather than deleted — for baseline VaR/Sharpe context alongside
stress scenario results.

## PHASE 7 (optional, not required for v1) — Correlation network companion view
Only start after Phase 5 ships, independently of Phase 6. Adds a
correlation-network tab — most naturally on the Stress Testing page, given
the multi-tab precedent already there (Historical/Sector Shock/Macro
Contagion) — built from `src/portfolio_builder/network.py`, which Phase 1
left in place dormant for exactly this. Feed it a live correlation matrix
computed from price data Stress Testing already pulls; do not route it
through `UniverseCache`/`fetch.py`/the SQLite cache layer — the current
Portfolio Builder page's own cold-cache path already proves this works.
This is a static companion view, not integrated with the stress engines'
own correlation logic (DCC-GARCH/copula) — don't try to unify them.

Before wiring it in: `network.py`'s docstring justifies staying at
ticker-level `.corr()` instead of DCC-GARCH by citing an "unresolved
convergence-misreport issue" in `dcc_garch.py`. Architecture.md's own audit
found that claim doesn't trace to anything in `dcc_garch.py`'s actual code.
The ticker-level decision is still fine — leave it — but correct the
comment so it doesn't keep citing an unverified reason.

---

**Delivery note:** save this file at the repo root (or `docs/`) and
reference it from `CLAUDE.md` rather than re-pasting it fresh each
session — Claude Code will pick it up as persistent project context, and
Rule 3's per-phase context clearing works better against a file it can
re-read than a wall of text it has to remember.
