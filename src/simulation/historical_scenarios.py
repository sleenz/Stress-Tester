"""
Historical stress scenario engine using actual per-stock price data.

For each scenario window, actual adjusted-close returns are fetched from
yfinance.  Stocks that didn't exist (or had fewer than config.min_data_points
trading days) fall back to beta-scaled index returns, so the portfolio
always gets a plausible estimate instead of a hardcoded uniform shock.

The benchmark index used for that beta-scaled fallback is resolved per
ticker (``^JKSE`` for ``.JK``-suffixed IDX tickers, ``^GSPC`` for everything
else) rather than from a single scenario-wide index — a mixed US/IDX
portfolio gets each stock's beta estimated against its own home market,
not a foreign one. See ``_resolve_market_index()``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    yf = None
    _YF_AVAILABLE = False

logger = get_logger(__name__)

if not _YF_AVAILABLE:
    logger.warning(
        "yfinance is not installed. HistoricalStressor will be unavailable. "
        "Install with: pip install yfinance"
    )

IDX_TICKER_SUFFIX = ".JK"


def _resolve_market_index(ticker: str) -> str:
    """
    Resolve the benchmark index for a ticker's home market.

    IDX tickers (``.JK`` suffix) resolve to the Jakarta Composite Index;
    everything else resolves to the S&P 500. Applied per ticker so a mixed
    US/IDX portfolio never estimates an Indonesian stock's beta against
    ``^GSPC`` (or vice versa) just because the scenario happened to be
    tagged with the other market's index.
    """
    return "^JKSE" if ticker.upper().endswith(IDX_TICKER_SUFFIX) else "^GSPC"


# ──────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class HistoricalScenario:
    """Definition of a historical crisis scenario."""

    name: str
    start_date: str          # ISO "YYYY-MM-DD" — actual crisis start
    end_date: str            # ISO "YYYY-MM-DD" — actual crisis trough / end
    market_index: str
    # Informational/default label only (e.g. narrative "primary" index for
    # this crisis) — NOT used as the benchmark for return computation.
    # The actual benchmark is resolved per ticker via _resolve_market_index()
    # (^JKSE for .JK tickers, ^GSPC otherwise), since a single scenario-wide
    # index previously caused every ticker — US or IDX — to be scaled
    # against whichever index the scenario happened to be tagged with.
    description: str
    tags: list               # e.g. ["EM", "currency", "idxrelevant"]


@dataclass
class StockScenarioReturn:
    """Per-stock output from one scenario run."""

    ticker: str
    realized_return: float   # decimal, e.g. -0.231
    source: str              # "actual" | "beta_scaled"
    beta_used: float         # 1.0 when source == "actual"; computed otherwise
    data_points: int         # trading days of actual crisis data found
    warning: str             # empty string if no issue


@dataclass
class HistoricalScenarioResult:
    """Full output from HistoricalStressor.run()."""

    scenario: HistoricalScenario
    stock_returns: dict                # {ticker: StockScenarioReturn}
    index_returns: dict                # {resolved_index: actual_benchmark_return}, e.g. {"^GSPC": -0.30, "^JKSE": -0.12}
    portfolio_return: float            # weighted sum of stock realized returns
    portfolio_pnl: float               # portfolio_return × portfolio_value
    pnl_by_stock: dict                 # {ticker: dollar P&L}
    worst_stock: str
    best_stock: str
    n_actual: int
    n_beta_scaled: int
    computation_date: str


# ──────────────────────────────────────────────────────────────────────────────
# Scenario library
# ──────────────────────────────────────────────────────────────────────────────

PER_STOCK_CRISIS_SCENARIOS: list[HistoricalScenario] = [
    HistoricalScenario(
        name="COVID-19 Crash",
        start_date="2020-02-19",
        end_date="2020-03-23",
        market_index="^GSPC",
        description="Fastest 30% drawdown in US market history — 33 calendar days",
        tags=["global", "liquidity", "pandemic"],
    ),
    HistoricalScenario(
        name="2008 Financial Crisis",
        start_date="2008-09-15",
        end_date="2009-03-09",
        market_index="^GSPC",
        description="Lehman collapse to S&P trough — systemic banking failure",
        tags=["global", "credit", "systemic"],
    ),
    HistoricalScenario(
        name="1997 Asian Crisis",
        start_date="1997-07-02",
        end_date="1997-12-31",
        market_index="^JKSE",
        description="EM currency contagion from Thai baht — maximum IDX relevance",
        tags=["EM", "currency", "idxrelevant"],
    ),
    HistoricalScenario(
        name="2013 Taper Tantrum",
        start_date="2013-05-22",
        end_date="2013-06-24",
        market_index="^JKSE",
        description="Fed taper signal — EM capital outflows and rupiah weakness",
        tags=["EM", "rates", "idxrelevant"],
    ),
    HistoricalScenario(
        name="2022 Bear Market",
        start_date="2022-01-03",
        end_date="2022-10-12",
        market_index="^GSPC",
        description="Rate hike cycle — growth multiple compression",
        tags=["global", "rates", "inflation"],
    ),
    HistoricalScenario(
        name="Dot-com Bust",
        start_date="2000-03-10",
        end_date="2002-10-09",
        market_index="^GSPC",
        description="Nasdaq peak to trough — tech multiple collapse",
        tags=["global", "tech", "valuation"],
    ),
    HistoricalScenario(
        name="2018 Q4 Selloff",
        start_date="2018-10-03",
        end_date="2018-12-24",
        market_index="^GSPC",
        description="Fed hiking into slowdown — fastest Q4 drawdown since 1931",
        tags=["global", "rates"],
    ),
]


# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class HistoricalStressorConfig:
    """Configuration for HistoricalStressor."""

    min_data_points: int = field(default=5)
    # Minimum crisis-window trading days required to call a result "actual".
    beta_estimation_days: int = field(default=252)
    # Calendar days of pre-crisis history used to estimate stock beta to index.
    beta_fallback_value: float = field(default=1.0)
    # Beta assumed when pre-crisis data is also insufficient.
    beta_clip_min: float = field(default=-3.0)
    beta_clip_max: float = field(default=3.0)
    min_pre_crisis_days: int = field(default=30)
    # Minimum pre-crisis trading days needed to estimate beta.


# ──────────────────────────────────────────────────────────────────────────────
# Main class
# ──────────────────────────────────────────────────────────────────────────────

class HistoricalStressor:
    """
    Fetch actual per-stock crisis returns for historical stress scenarios.

    For each (stock, scenario) pair:
    - If ≥ config.min_data_points trading days of price data are available
      during the crisis window → ``source = "actual"``.
    - Otherwise → estimate beta from pre-crisis data and scale the index
      return: ``source = "beta_scaled"``.
    """

    def __init__(
        self, config: HistoricalStressorConfig = HistoricalStressorConfig()
    ) -> None:
        self._config = config

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _download(
        self,
        ticker: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """
        Download adjusted close prices via yfinance.

        Returns an empty DataFrame on any error.
        The end date passed to yfinance is exclusive, so we add one day.
        """
        if not _YF_AVAILABLE:
            return pd.DataFrame()
        try:
            end_dt = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            data = yf.download(
                ticker,
                start=start,
                end=end_dt,
                progress=False,
                auto_adjust=True,
            )
            if data.empty:
                return pd.DataFrame()
            # Flatten MultiIndex columns (yfinance ≥0.2 returns them for single ticker)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            close_col = "Close" if "Close" in data.columns else data.columns[0]
            return data[[close_col]].rename(columns={close_col: ticker})
        except Exception as exc:
            logger.error(f"yfinance download failed for {ticker} ({start}→{end}): {exc}")
            return pd.DataFrame()

    def _cumulative_return(self, prices: pd.DataFrame, ticker: str) -> Optional[float]:
        """Compute (last/first - 1) from a single-column price series."""
        col = prices[ticker].dropna()
        if len(col) < 2:
            return None
        return float(col.iloc[-1] / col.iloc[0]) - 1.0

    def _estimate_beta(
        self,
        ticker: str,
        scenario: HistoricalScenario,
        resolved_index: str,
        index_crisis_return: float,
    ) -> tuple[float, str]:
        """
        Estimate stock beta using pre-crisis data, against the ticker's own
        resolved home-market index (not a scenario-global index).

        Returns (beta, warning_message).
        """
        cfg = self._config
        pre_end = scenario.start_date
        pre_end_dt = pd.Timestamp(pre_end)
        pre_start_dt = pre_end_dt - pd.Timedelta(days=cfg.beta_estimation_days + 60)
        pre_start = pre_start_dt.strftime("%Y-%m-%d")

        stock_pre = self._download(ticker, pre_start, pre_end)
        index_pre = self._download(resolved_index, pre_start, pre_end)

        if stock_pre.empty or index_pre.empty:
            return (
                cfg.beta_fallback_value,
                f"No pre-crisis data for {ticker} — using default beta "
                f"{cfg.beta_fallback_value:.1f}",
            )

        # Align on common dates and compute daily returns
        combined = pd.concat([stock_pre, index_pre], axis=1).dropna()
        if len(combined) < cfg.min_pre_crisis_days:
            return (
                cfg.beta_fallback_value,
                f"Only {len(combined)} pre-crisis trading days for {ticker} "
                f"(min {cfg.min_pre_crisis_days}) — using default beta "
                f"{cfg.beta_fallback_value:.1f}",
            )

        rets = combined.pct_change().dropna()
        stock_col = rets.columns[0]
        index_col = rets.columns[1]

        idx_var = float(rets[index_col].var())
        if idx_var < 1e-12:
            return (
                cfg.beta_fallback_value,
                f"Index variance near zero for pre-crisis window — using default beta",
            )

        cov = float(rets[[stock_col, index_col]].cov().iloc[0, 1])
        beta = cov / idx_var
        beta = float(np.clip(beta, cfg.beta_clip_min, cfg.beta_clip_max))
        return beta, ""

    def _fetch_index_returns(
        self,
        scenario: HistoricalScenario,
        tickers: list[str],
    ) -> dict[str, float]:
        """
        Fetch the actual benchmark index return during the crisis window,
        for every distinct market represented among ``tickers`` (resolved
        per ticker via ``_resolve_market_index()`` — a mixed US/IDX
        portfolio fetches both ``^GSPC`` and ``^JKSE``, not just one).

        A market whose index fails to download is simply omitted from the
        returned dict — tickers needing it fall back gracefully in
        ``_fetch_crisis_returns()`` rather than zeroing out the whole run.
        """
        needed_indices = sorted({
            _resolve_market_index(str(t) if not isinstance(t, str) else t)
            for t in tickers
        })
        index_returns: dict[str, float] = {}
        for idx in needed_indices:
            prices = self._download(idx, scenario.start_date, scenario.end_date)
            if prices.empty or len(prices) < 2:
                logger.error(
                    f"Cannot fetch index data for {idx} "
                    f"({scenario.start_date} → {scenario.end_date}). "
                    "Tickers resolving to this index will lose beta-scaled fallback."
                )
                continue
            col = prices.columns[0]
            idx_ret = float(prices[col].iloc[-1] / prices[col].iloc[0]) - 1.0
            index_returns[idx] = idx_ret
            logger.info(f"  Index {idx}: {idx_ret:.2%} ({len(prices)} trading days)")
        return index_returns

    def _fetch_crisis_returns(
        self,
        tickers: list[str],
        scenario: HistoricalScenario,
        index_returns: dict[str, float],
    ) -> dict[str, StockScenarioReturn]:
        """
        Fetch per-stock crisis returns, falling back to beta-scaling.

        Algorithm per ticker
        --------------------
        1. Download adjusted close from scenario.start_date to scenario.end_date.
        2. If len(data) >= config.min_data_points:
               realized_return = last/first − 1
               source = "actual", beta_used = 1.0
        3. Else:
               Resolve the ticker's own home-market index (US vs IDX).
               Estimate beta from pre-crisis price history against that index.
               realized_return = beta × that index's crisis return
               source = "beta_scaled"
        """
        cfg = self._config
        results: dict[str, StockScenarioReturn] = {}

        for ticker in tickers:
            # Coerce to str — guards against MultiIndex tuple column names
            # propagating from returns.columns into the ticker identifier.
            ticker_str = str(ticker) if not isinstance(ticker, str) else ticker
            prices = self._download(ticker_str, scenario.start_date, scenario.end_date)

            if len(prices) >= cfg.min_data_points:
                ret = self._cumulative_return(prices, ticker_str)
                if ret is not None:
                    results[ticker_str] = StockScenarioReturn(
                        ticker=ticker_str,
                        realized_return=ret,
                        source="actual",
                        beta_used=1.0,
                        data_points=len(prices),
                        warning="",
                    )
                    logger.debug(f"  {ticker_str}: actual {ret:.2%} ({len(prices)} days)")
                    continue

            # Insufficient crisis data — use beta scaling against the
            # ticker's own resolved home-market index.
            resolved_index = _resolve_market_index(ticker_str)
            index_crisis_return = index_returns.get(resolved_index)
            logger.debug(
                f"  {ticker_str}: only {len(prices)} crisis days — using "
                f"beta-scaled fallback vs {resolved_index}"
            )

            if index_crisis_return is None:
                results[ticker_str] = StockScenarioReturn(
                    ticker=ticker_str,
                    realized_return=0.0,
                    source="beta_scaled",
                    beta_used=cfg.beta_fallback_value,
                    data_points=len(prices),
                    warning=f"Index {resolved_index} unavailable — cannot compute beta-scaled fallback",
                )
                logger.warning(f"  {ticker_str}: index {resolved_index} unavailable — return set to 0")
                continue

            beta, warn = self._estimate_beta(ticker_str, scenario, resolved_index, index_crisis_return)
            realized = beta * index_crisis_return

            results[ticker_str] = StockScenarioReturn(
                ticker=ticker_str,
                realized_return=realized,
                source="beta_scaled",
                beta_used=beta,
                data_points=len(prices),
                warning=warn,
            )
            if warn:
                logger.warning(f"  {ticker}: {warn}")

        return results

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def run(
        self,
        scenario: HistoricalScenario,
        tickers: list[str],
        weights: pd.Series,
        portfolio_value: float,
    ) -> HistoricalScenarioResult:
        """
        Run one historical scenario against a portfolio.

        Parameters
        ----------
        scenario : HistoricalScenario
        tickers : list[str]
        weights : pd.Series
            Index = tickers, values = decimal weights.
        portfolio_value : float

        Returns
        -------
        HistoricalScenarioResult
        """
        t0 = time.perf_counter()
        logger.info(
            f"HistoricalStressor.run(): scenario='{scenario.name}' "
            f"({scenario.start_date} → {scenario.end_date})"
        )

        # Step 1: Benchmark index return(s) — one per distinct market present
        # among tickers (required for the beta-scaled fallback; missing
        # individual markets degrade gracefully in _fetch_crisis_returns).
        index_returns = self._fetch_index_returns(scenario, tickers)

        # Step 2: Per-stock crisis returns
        stock_returns = self._fetch_crisis_returns(tickers, scenario, index_returns)

        # Step 3: Portfolio-level aggregation
        weights_aligned = weights.reindex(tickers, fill_value=0.0)
        portfolio_return = 0.0
        pnl_by_stock: dict[str, float] = {}

        for ticker in tickers:
            sr = stock_returns[ticker]
            w = float(weights_aligned.get(ticker, 0.0))
            contrib = w * sr.realized_return
            portfolio_return += contrib
            pnl_by_stock[ticker] = contrib * portfolio_value

        portfolio_pnl = portfolio_return * portfolio_value

        # Step 4: Best / worst
        sorted_by_ret = sorted(
            stock_returns.values(), key=lambda r: r.realized_return
        )
        worst_stock = str(sorted_by_ret[0].ticker) if sorted_by_ret else ""
        best_stock = str(sorted_by_ret[-1].ticker) if sorted_by_ret else ""

        n_actual = sum(1 for r in stock_returns.values() if r.source == "actual")
        n_beta_scaled = len(stock_returns) - n_actual

        elapsed = time.perf_counter() - t0
        logger.info(
            f"  Done in {elapsed:.2f}s — portfolio_return={portfolio_return:.2%}, "
            f"actual={n_actual}, beta_scaled={n_beta_scaled}"
        )

        return HistoricalScenarioResult(
            scenario=scenario,
            stock_returns=stock_returns,
            index_returns=index_returns,
            portfolio_return=portfolio_return,
            portfolio_pnl=portfolio_pnl,
            pnl_by_stock=pnl_by_stock,
            worst_stock=worst_stock,
            best_stock=best_stock,
            n_actual=n_actual,
            n_beta_scaled=n_beta_scaled,
            computation_date=date.today().isoformat(),
        )

    def run_all(
        self,
        tickers: list[str],
        weights: pd.Series,
        portfolio_value: float,
        scenarios: Optional[list[HistoricalScenario]] = None,
    ) -> dict[str, HistoricalScenarioResult]:
        """
        Run all scenarios.

        Parameters
        ----------
        tickers : list[str]
        weights : pd.Series
        portfolio_value : float
        scenarios : list[HistoricalScenario], optional
            Defaults to PER_STOCK_CRISIS_SCENARIOS.

        Returns
        -------
        dict[str, HistoricalScenarioResult]
            Keyed by scenario.name.
        """
        if scenarios is None:
            scenarios = PER_STOCK_CRISIS_SCENARIOS

        results: dict[str, HistoricalScenarioResult] = {}
        for i, scenario in enumerate(scenarios, 1):
            logger.info(
                f"Running scenario {i}/{len(scenarios)}: '{scenario.name}'"
            )
            try:
                results[scenario.name] = self.run(
                    scenario, tickers, weights, portfolio_value
                )
            except Exception as exc:
                logger.error(f"Scenario '{scenario.name}' failed: {exc}")

        return results

    def to_comparison_dataframe(
        self,
        results: dict[str, HistoricalScenarioResult],
    ) -> pd.DataFrame:
        """
        Wide-format summary DataFrame across all scenarios.

        Columns: Scenario, US Index Return, IDX Index Return, Portfolio Return,
                 Portfolio P&L, Worst Stock, Best Stock, N Actual, N Beta-Scaled.
        US/IDX Index Return is NaN when that market isn't present among the
        scenario's tickers (or its index failed to fetch).
        Sorted by Portfolio Return ascending (worst crisis first).
        """
        rows = []
        for name, r in results.items():
            rows.append({
                "Scenario": name,
                "US Index Return": r.index_returns.get("^GSPC", np.nan),
                "IDX Index Return": r.index_returns.get("^JKSE", np.nan),
                "Portfolio Return": r.portfolio_return,
                "Portfolio P&L": r.portfolio_pnl,
                "Worst Stock": r.worst_stock,
                "Best Stock": r.best_stock,
                "N Actual": r.n_actual,
                "N Beta-Scaled": r.n_beta_scaled,
            })
        if not rows:
            return pd.DataFrame(columns=[
                "Scenario", "US Index Return", "IDX Index Return", "Portfolio Return",
                "Portfolio P&L", "Worst Stock", "Best Stock", "N Actual", "N Beta-Scaled",
            ])
        df = pd.DataFrame(rows)
        df = df.sort_values("Portfolio Return", ascending=True).reset_index(drop=True)
        # Ensure Arrow-serialisable types: ticker fields may arrive as tuples when
        # the caller's returns.columns is a MultiIndex.
        for _col in ("Worst Stock", "Best Stock"):
            df[_col] = df[_col].apply(
                lambda v: str(v[0]) if isinstance(v, (tuple, list)) and len(v) else str(v)
            )
        return df

    def to_stock_breakdown(
        self,
        result: HistoricalScenarioResult,
    ) -> pd.DataFrame:
        """
        Per-stock breakdown DataFrame for one scenario.

        Columns: Ticker, Weight, Realized Return, Source, Beta Used, P&L ($), Warning.
        Sorted by Realized Return ascending.
        """
        rows = []
        for ticker, sr in result.stock_returns.items():
            rows.append({
                "Ticker": ticker,
                "Realized Return": sr.realized_return,
                "Source": sr.source,
                "Beta Used": sr.beta_used,
                "P&L ($)": result.pnl_by_stock.get(ticker, 0.0),
                "Warning": sr.warning,
            })
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df = df.sort_values("Realized Return", ascending=True).reset_index(drop=True)
        return df


# ──────────────────────────────────────────────────────────────────────────────
# Smoke test
# ──────────────────────────────────────────────────────────────────────────────

def _smoke_test() -> None:
    from src.utils.logger import setup_logger
    setup_logger()

    # ── _resolve_market_index(): pure unit checks, no network needed ─────────
    assert _resolve_market_index("AAPL") == "^GSPC"
    assert _resolve_market_index("JPM") == "^GSPC"
    assert _resolve_market_index("BBCA.JK") == "^JKSE"
    assert _resolve_market_index("bbca.jk") == "^JKSE"  # case-insensitive
    print("  _resolve_market_index(): US/IDX resolution correct ✓")

    # Mixed US/IDX portfolio — the whole point of this fix.
    tickers = ["AAPL", "JPM", "XOM", "BBCA.JK"]
    weights = pd.Series(
        {t: 1.0 / len(tickers) for t in tickers}
    )
    portfolio_value = 1_000_000.0

    stressor = HistoricalStressor()

    # ── COVID-19: all four existed → expect "actual" for all ─────────────────
    covid = next(s for s in PER_STOCK_CRISIS_SCENARIOS if s.name == "COVID-19 Crash")
    result = stressor.run(covid, tickers, weights, portfolio_value)

    print(f"\nScenario: {result.scenario.name}")
    print(f"  Index returns: {result.index_returns}")
    print(f"  Portfolio return: {result.portfolio_return:.2%}")
    print(f"  Portfolio P&L: ${result.portfolio_pnl:,.0f}")
    print(f"  n_actual={result.n_actual}, n_beta_scaled={result.n_beta_scaled}")

    bd = stressor.to_stock_breakdown(result)
    print("\nPer-stock breakdown:")
    print(bd.to_string(index=False))

    # All four should have actual data
    for ticker in tickers:
        sr = result.stock_returns[ticker]
        assert sr.source == "actual", (
            f"{ticker}: expected source='actual', got '{sr.source}'"
        )
        assert sr.data_points >= 5, (
            f"{ticker}: expected ≥5 data points, got {sr.data_points}"
        )
    print("\n  AAPL/JPM/XOM/BBCA.JK all 'actual' during COVID-19 ✓")

    # Returns must differ across stocks (not a uniform shock)
    rets = [result.stock_returns[t].realized_return for t in tickers]
    assert len(set(round(r, 6) for r in rets)) > 1, (
        "All stocks have identical returns — uniform shock not fixed!"
    )
    print("  Per-stock returns differ (not uniform) ✓")

    # P&L direction consistent with portfolio return
    assert (result.portfolio_pnl < 0) == (result.portfolio_return < 0), (
        "P&L sign inconsistent with portfolio return"
    )
    print("  P&L sign consistent ✓")

    # ── 1997 Asian Crisis: BBCA.JK predates its 2000 IPO → beta_scaled,
    # and must be scaled against ^JKSE, not ^GSPC (the bug this fixes) ───────
    asian = next(s for s in PER_STOCK_CRISIS_SCENARIOS if s.name == "1997 Asian Crisis")
    result_97 = stressor.run(asian, tickers, weights, portfolio_value)
    print(f"\nScenario: {result_97.scenario.name}")
    print(f"  Index returns: {result_97.index_returns}")
    for ticker in tickers:
        sr97 = result_97.stock_returns[ticker]
        print(f"  {ticker}: source={sr97.source}, beta={sr97.beta_used:.2f}, "
              f"return={sr97.realized_return:.2%}")

    assert "^JKSE" in result_97.index_returns, (
        "Portfolio contains a .JK ticker — ^JKSE must be fetched"
    )
    sr97_bbca = result_97.stock_returns["BBCA.JK"]
    assert sr97_bbca.source == "beta_scaled", (
        "BBCA.JK (IPO 2000) should not have actual data during the 1997 crisis"
    )
    print("  BBCA.JK correctly beta-scaled against ^JKSE (not ^GSPC) ✓")

    # to_comparison_dataframe
    all_results = stressor.run_all(tickers, weights, portfolio_value)
    summary = stressor.to_comparison_dataframe(all_results)
    assert not summary.empty, "Summary DataFrame should not be empty"
    assert list(summary.columns) == [
        "Scenario", "US Index Return", "IDX Index Return", "Portfolio Return",
        "Portfolio P&L", "Worst Stock", "Best Stock", "N Actual", "N Beta-Scaled",
    ], f"Unexpected columns: {list(summary.columns)}"
    print(f"\nrun_all(): {len(all_results)}/{len(PER_STOCK_CRISIS_SCENARIOS)} scenarios ✓")
    print(summary[["Scenario", "US Index Return", "IDX Index Return", "Portfolio Return"]].to_string(index=False))

    print("\n✓ historical_scenarios smoke test passed\n")


if __name__ == "__main__":
    import sys
    _smoke_test()
    sys.exit(0)
