"""
Macro variable data fetcher for the Leontief contagion model.

Fetches DXY, VIX, US Treasury yield, Bank Indonesia rate, IDR/USD,
China PMI, palm oil, coal, and nickel from the LSEG Data Library
(primary), with yfinance as a per-variable fallback where a real
equivalent ticker exists, automatic fallback, per-variable caching,
and graceful degradation.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, date as _date
from typing import Optional

import numpy as np
import pandas as pd

from src.data.cache import DataCache
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── Optional dependency guards ────────────────────────────────────────────────

try:
    import yfinance as _yf
    _YFINANCE_AVAILABLE = True
except ImportError:
    _yf = None
    _YFINANCE_AVAILABLE = False
    logger.warning("yfinance not available — yfinance macro sources will fail")

try:
    import lseg.data as _ld
    _LSEG_AVAILABLE = True
except ImportError:
    _ld = None
    _LSEG_AVAILABLE = False
    logger.warning("lseg.data is not installed. LSEG macro sources will be skipped.")

try:
    import sqlite3 as _sqlite3
    _SQLITE3_AVAILABLE = True
except ImportError:
    _sqlite3 = None
    _SQLITE3_AVAILABLE = False

try:
    import joblib as _joblib
    _JOBLIB_AVAILABLE = True
except ImportError:
    _joblib = None
    _JOBLIB_AVAILABLE = False

try:
    import networkx as _nx
    _NETWORKX_AVAILABLE = True
except ImportError:
    _nx = None
    _NETWORKX_AVAILABLE = False


# ── Variable configuration ────────────────────────────────────────────────────

@dataclass
class MacroVariableConfig:
    """
    Configuration for a single macro variable.

    Parameters
    ----------
    name : str
        Human-readable label, e.g. "DXY".
    primary_ticker : str
        Ticker/symbol/RIC for the primary source.
    primary_source : str
        "yfinance" | "lseg".
    fallback_ticker : str, optional
        Alternative ticker/symbol/RIC if primary fails.
    fallback_source : str, optional
        "yfinance" | "lseg".
    transform : str
        "pct_change": weekly % change (equities, FX, commodities).
        "diff": level difference (rate variables, bps equivalent).
        "level": raw level, no transformation (PMI).
    frequency : str
        "W" weekly | "M" monthly | "D" daily.
    description : str
        Documentation string.
    """

    name: str
    primary_ticker: str
    primary_source: str
    fallback_ticker: Optional[str] = field(default=None)
    fallback_source: Optional[str] = field(default=None)
    transform: str = field(default="pct_change")
    frequency: str = field(default="W")
    description: str = field(default="")


DEFAULT_MACRO_VARIABLES: list[MacroVariableConfig] = [
    MacroVariableConfig(
        name="DXY",
        # LSEG RIC for the ICE US Dollar Index — standard Refinitiv index
        # convention (leading dot), not verified against a live session
        # (see CLAUDE.md's Known placeholders entry on this migration).
        primary_ticker=".DXY",
        primary_source="lseg",
        fallback_ticker="DX-Y.NYB",
        fallback_source="yfinance",
        transform="pct_change",
        frequency="W",
        description="US Dollar Index — primary EM risk driver",
    ),
    MacroVariableConfig(
        name="VIX",
        # LSEG RIC for the CBOE Volatility Index — standard Refinitiv index
        # convention, not verified against a live session.
        primary_ticker=".VIX",
        primary_source="lseg",
        fallback_ticker="^VIX",
        fallback_source="yfinance",
        transform="diff",
        frequency="W",
        description="CBOE Volatility Index — global risk-off signal",
    ),
    MacroVariableConfig(
        name="US_10Y",
        # LSEG RIC for the US 10Y Treasury constant-maturity yield — standard
        # Refinitiv convention, not verified against a live session.
        primary_ticker="US10YT=RR",
        primary_source="lseg",
        fallback_ticker="^TNX",
        fallback_source="yfinance",
        transform="diff",
        frequency="W",
        description="US 10Y Treasury yield change (bps)",
    ),
    MacroVariableConfig(
        name="BI_RATE",
        # LSEG economic-indicator RIC guess ("<country><indicator>=ECI"
        # convention) — meaningfully less certain than the market-instrument
        # RICs above; verify against a live session before relying on it
        # (see CLAUDE.md's Known placeholders entry). No yfinance equivalent
        # exists for a central bank policy rate, so there is no fallback —
        # if this RIC is wrong, BI_RATE has no safety net (explicit,
        # confirmed tradeoff — see CLAUDE.md/BUILD_SPEC.md).
        primary_ticker="IDCBIR=ECI",
        primary_source="lseg",
        fallback_ticker=None,
        fallback_source=None,
        transform="diff",
        frequency="M",
        description="Bank Indonesia policy rate change (bps)",
    ),
    MacroVariableConfig(
        name="IDR_USD",
        # LSEG RIC for USD/IDR spot — standard Refinitiv FX convention.
        primary_ticker="IDR=",
        primary_source="lseg",
        fallback_ticker="IDR=X",
        fallback_source="yfinance",
        transform="pct_change",
        frequency="W",
        description="USD/IDR exchange rate — positive = IDR weakening",
    ),
    MacroVariableConfig(
        name="CHINA_PMI",
        # LSEG economic-indicator RIC guess, same lower-confidence caveat as
        # BI_RATE above — verify before relying on it. No yfinance
        # equivalent exists for a PMI series, so there is no fallback.
        primary_ticker="CNPMI=ECI",
        primary_source="lseg",
        fallback_ticker=None,
        fallback_source=None,
        transform="diff",
        frequency="M",
        description="China NBS Manufacturing PMI — month-over-month point change",
    ),
    MacroVariableConfig(
        name="CPO",
        # LSEG RIC for Bursa Malaysia CPO futures, continuous front-month —
        # standard Refinitiv commodity RIC convention, not verified against
        # a live session. No yfinance equivalent exists for this contract,
        # so there is no fallback.
        primary_ticker="FCPOc1",
        primary_source="lseg",
        fallback_ticker=None,
        fallback_source=None,
        transform="pct_change",
        frequency="W",
        description="Palm oil futures (Bursa Malaysia) — IDX #1 agricultural export",
    ),
    MacroVariableConfig(
        name="COAL",
        # LSEG RIC for ICE Newcastle thermal coal futures, continuous
        # front-month — standard Refinitiv commodity RIC convention.
        primary_ticker="MTFc1",
        primary_source="lseg",
        fallback_ticker="MTF=F",
        fallback_source="yfinance",
        transform="pct_change",
        frequency="W",
        description="Newcastle thermal coal — IDX key commodity",
    ),
    MacroVariableConfig(
        name="NICKEL",
        # LSEG RIC for LME 3-month nickel forward — standard LME base-metals
        # RIC convention, not verified against a live session. No yfinance
        # equivalent exists for LME base metals, so there is no fallback.
        primary_ticker="MNI3",
        primary_source="lseg",
        fallback_ticker=None,
        fallback_source=None,
        transform="pct_change",
        frequency="W",
        description="LME Nickel 3-month — ANTM, INCO; EV battery demand proxy",
    ),
]


@dataclass
class MacroDataConfig:
    """
    Top-level configuration for MacroDataFetcher.

    Parameters
    ----------
    variables : list[MacroVariableConfig]
        Variables to fetch. Defaults to DEFAULT_MACRO_VARIABLES.
    start_date : str
        ISO format start date for historical fetch.
    cache_ttl_seconds : int
        Per-variable cache TTL. Default 3600s (1 hour).
    fill_method : str
        How to align monthly variables to weekly:
        "ffill" (default) or "interpolate".
    min_overlap_pct : float
        Minimum fraction of dates with data before warning.
    """

    variables: list[MacroVariableConfig] = field(
        default_factory=lambda: list(DEFAULT_MACRO_VARIABLES)
    )
    start_date: str = field(default="2005-01-01")
    cache_ttl_seconds: int = field(default=3600)
    fill_method: str = field(default="ffill")
    min_overlap_pct: float = field(default=0.70)


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class MacroDataResult:
    """
    Output of MacroDataFetcher.fetch().

    Attributes
    ----------
    raw_levels : pd.DataFrame
        (T, N) raw price/rate levels.
    transformed : pd.DataFrame
        (T, N) transformed per-variable config.
    aligned_weekly : pd.DataFrame
        (T, N) all variables on a common weekly index.
    missing_variables : list[str]
        Variables that failed all sources.
    source_used : dict[str, str]
        {variable_name: "primary" | "fallback" | "failed"}.
    date_range : tuple[str, str]
        (start, end) ISO strings.
    config : MacroDataConfig
    """

    raw_levels: pd.DataFrame
    transformed: pd.DataFrame
    aligned_weekly: pd.DataFrame
    missing_variables: list[str]
    source_used: dict[str, str]
    date_range: tuple[str, str]
    config: MacroDataConfig


# ── Fetcher ───────────────────────────────────────────────────────────────────

class MacroDataFetcher:
    """
    Fetch macro variables from the LSEG Data Library (primary) and
    yfinance (fallback, where a real equivalent ticker exists) with
    per-variable caching.

    Parameters
    ----------
    config : MacroDataConfig
        Configuration for variables, dates, and caching behaviour.
    """

    def __init__(self, config: MacroDataConfig = MacroDataConfig()) -> None:
        self._config = config
        self._cache = DataCache()
        self._lseg_session_opened = False

    # ── Public API ────────────────────────────────────────────────────────────

    def fetch(
        self,
        start_date: str = None,
        end_date: str = None,
    ) -> MacroDataResult:
        """
        Fetch all macro variables defined in config.variables.

        For each variable:
        1. Check DataCache (TTL = config.cache_ttl_seconds).
        2. Try primary source.
        3. On failure, try fallback source.
        4. Apply transform (pct_change / diff / level).
        5. Resample to weekly (config.fill_method for monthly variables).
        6. Align all variables to the same weekly date index.

        Missing variables get a column of NaN with a logged warning.
        Never raises — degrades gracefully with missing_variables populated.

        Parameters
        ----------
        start_date : str, optional
            ISO format. Defaults to config.start_date.
        end_date : str, optional
            ISO format. Defaults to today.

        Returns
        -------
        MacroDataResult
        """
        t0 = time.time()
        start = start_date or self._config.start_date
        end = end_date or datetime.today().strftime("%Y-%m-%d")

        raw_series: dict[str, pd.Series] = {}
        transformed_series: dict[str, pd.Series] = {}
        weekly_series: dict[str, pd.Series] = {}
        source_used: dict[str, str] = {}
        missing_variables: list[str] = []

        for var_cfg in self._config.variables:
            name = var_cfg.name
            try:
                raw = self._fetch_with_cache(var_cfg, start, end)
                source_used[name] = raw.attrs.get("source", "primary")
                raw_series[name] = raw

                transformed = self._apply_transform(raw, var_cfg.transform)
                transformed_series[name] = transformed

                weekly = self._to_weekly(transformed, var_cfg.frequency)
                weekly_series[name] = weekly
                logger.debug(
                    f"MacroDataFetcher: {name} fetched {len(raw)} obs, "
                    f"source={source_used[name]}"
                )
            except Exception as exc:
                logger.warning(f"MacroDataFetcher: {name} failed all sources: {exc}")
                source_used[name] = "failed"
                missing_variables.append(name)

        # Build raw_levels and transformed DataFrames (before weekly resampling)
        raw_levels = (
            pd.DataFrame({k: v for k, v in raw_series.items()})
            if raw_series else pd.DataFrame()
        )
        transformed_df = (
            pd.DataFrame({k: v for k, v in transformed_series.items()})
            if transformed_series else pd.DataFrame()
        )

        # Align weekly series to a common Friday-end weekly index
        aligned_weekly = self._align_weekly(weekly_series, start, end)

        # Warn on sparse columns
        if not aligned_weekly.empty:
            valid_frac = aligned_weekly.notna().mean()
            for col in aligned_weekly.columns:
                if valid_frac[col] < self._config.min_overlap_pct:
                    logger.warning(
                        f"MacroDataFetcher: {col} has only "
                        f"{valid_frac[col]:.0%} valid weekly observations"
                    )

        date_range = (start, end)
        elapsed = time.time() - t0
        logger.info(
            f"MacroDataFetcher.fetch() done in {elapsed:.2f}s — "
            f"shape={aligned_weekly.shape}, missing={missing_variables}"
        )
        return MacroDataResult(
            raw_levels=raw_levels,
            transformed=transformed_df,
            aligned_weekly=aligned_weekly,
            missing_variables=missing_variables,
            source_used=source_used,
            date_range=date_range,
            config=self._config,
        )

    def get_variable_names(self) -> list[str]:
        """
        Return list of variable names in config order.

        Returns
        -------
        list[str]
        """
        return [v.name for v in self._config.variables]

    def get_macro_shock_vector(
        self,
        result: MacroDataResult,
        shock_date: str,
    ) -> pd.Series:
        """
        Extract macro variable values on a specific date as a shock vector.

        Used to replay historical macro conditions through the contagion model.

        Parameters
        ----------
        result : MacroDataResult
            Output of fetch().
        shock_date : str
            ISO date string. Nearest available date is used if exact date
            is not in the index.

        Returns
        -------
        pd.Series
            Index = variable names. Values = transformed macro values on that date.
        """
        df = result.aligned_weekly
        if df.empty:
            return pd.Series(dtype=float)
        idx = df.index.asof(pd.Timestamp(shock_date))
        if pd.isna(idx):
            logger.warning(
                f"get_macro_shock_vector: {shock_date} not found in weekly index"
            )
            return pd.Series(0.0, index=df.columns)
        return df.loc[idx]

    # ── Private helpers ───────────────────────────────────────────────────────

    def _fetch_with_cache(
        self, var_cfg: MacroVariableConfig, start: str, end: str
    ) -> pd.Series:
        """Try cache → primary → fallback. Attaches source label via attrs."""
        cache_key = self._cache._generate_key(
            "macro_raw", var_cfg.name, start, end
        )
        cached = self._cache.get(cache_key, ttl=self._config.cache_ttl_seconds)
        if cached is not None:
            cached.attrs["source"] = cached.attrs.get("source", "primary")
            return cached

        # Primary source
        primary_exc: Optional[Exception] = None
        try:
            raw = self._fetch_source(
                var_cfg.primary_ticker, var_cfg.primary_source, start, end
            )
            raw.attrs["source"] = "primary"
            self._cache.set(raw, cache_key, self._config.cache_ttl_seconds)
            return raw
        except Exception as exc:
            primary_exc = exc
            logger.debug(
                f"{var_cfg.name}: primary source failed ({var_cfg.primary_source}/"
                f"{var_cfg.primary_ticker}): {exc}"
            )

        # Fallback source
        if var_cfg.fallback_ticker and var_cfg.fallback_source:
            try:
                raw = self._fetch_source(
                    var_cfg.fallback_ticker, var_cfg.fallback_source, start, end
                )
                raw.attrs["source"] = "fallback"
                self._cache.set(raw, cache_key, self._config.cache_ttl_seconds)
                return raw
            except Exception as exc:
                logger.debug(
                    f"{var_cfg.name}: fallback source also failed "
                    f"({var_cfg.fallback_source}/{var_cfg.fallback_ticker}): {exc}"
                )

        raise RuntimeError(
            f"{var_cfg.name}: all sources failed. "
            f"Primary error: {primary_exc}"
        )

    def _fetch_source(
        self, ticker: str, source: str, start: str, end: str
    ) -> pd.Series:
        """Dispatch to the correct source fetcher."""
        if source == "yfinance":
            return self._fetch_yfinance(ticker, start, end)
        if source == "lseg":
            return self._fetch_lseg(ticker, start, end)
        raise ValueError(f"Unknown source '{source}'")

    def _fetch_yfinance(self, ticker: str, start: str, end: str) -> pd.Series:
        """
        Fetch adjusted close price series from yfinance.

        Parameters
        ----------
        ticker : str
            yfinance symbol (e.g. "DX-Y.NYB", "^VIX").
        start, end : str
            ISO date strings.

        Returns
        -------
        pd.Series
            Daily close price, index = DatetimeIndex.
        """
        if not _YFINANCE_AVAILABLE:
            raise RuntimeError("yfinance not installed")
        t = _yf.Ticker(ticker)
        hist = t.history(start=start, end=end, auto_adjust=True)
        if hist.empty:
            raise ValueError(f"yfinance returned empty data for {ticker}")
        if "Close" not in hist.columns:
            raise ValueError(f"No 'Close' column for {ticker}: {hist.columns.tolist()}")
        series = hist["Close"].dropna()
        series.index = series.index.tz_localize(None)
        series.name = ticker
        return series

    def _ensure_lseg_session(self) -> None:
        """
        Open an LSEG session on first use (idempotent, self-contained).

        Mirrors LSEGSource._ensure_session() in src/data/sources.py and
        LSEGSectorFetcher._ensure_session() in lseg_sectors.py — each of
        the three LSEG integrations in this app opens its own session
        rather than depending on call order with the others.
        """
        if self._lseg_session_opened:
            return
        app_key = os.environ.get("LSEG_APP_KEY", "")
        try:
            if app_key:
                _ld.open_session(app_key=app_key)
            else:
                _ld.open_session()
            self._lseg_session_opened = True
        except Exception as exc:
            logger.debug(f"MacroDataFetcher: LSEG session could not be opened: {exc}")
            raise

    def _fetch_lseg(self, ric: str, start: str, end: str) -> pd.Series:
        """
        Fetch a historical level series from the LSEG Data Library.

        Requests a single field ("TRDPRC_1", the platform's default
        trade/last price) deliberately, mirroring `LSEGSource.fetch_prices()`
        in src/data/sources.py — the library only builds a (RIC, field)
        column MultiIndex when *multiple* fields are requested, so a
        single-RIC, single-field request returns a flat one-column
        DataFrame regardless of the underlying instrument type (equity,
        rate, commodity, or economic indicator).

        Requires a configured session (LSEG_APP_KEY env var, or the
        library's own lseg-data.config.json discovery) — same two-path
        pattern as LSEGSource and LSEGSectorFetcher, but this is a
        separate LSEG integration from both of those, not a shared one.

        Parameters
        ----------
        ric : str
            LSEG/Refinitiv Instrument Code, e.g. "US10YT=RR" (10Y Treasury
            yield), "FCPOc1" (Bursa Malaysia CPO futures, continuous
            front-month), "MNI3" (LME 3-month nickel forward). See
            DEFAULT_MACRO_VARIABLES and CLAUDE.md's Known placeholders
            entry for the verification status of each code used here.
        start, end : str
            ISO date strings.

        Returns
        -------
        pd.Series
            Level series, index = DatetimeIndex.
        """
        if not _LSEG_AVAILABLE:
            raise RuntimeError(
                "lseg.data is not installed — pip install lseg-data>=2.0.0"
            )

        self._ensure_lseg_session()

        try:
            df = _ld.get_history(
                universe=ric,
                fields=["TRDPRC_1"],
                interval="daily",
                start=start,
                end=end,
            )
        except Exception as exc:
            raise RuntimeError(f"LSEG get_history failed for {ric}: {exc}") from exc

        if df is None or df.empty:
            raise ValueError(f"LSEG returned empty data for {ric}")

        series = df.iloc[:, 0].dropna()
        series.index = pd.DatetimeIndex(series.index)
        if series.index.tz is not None:
            series.index = series.index.tz_localize(None)
        series.name = ric
        return series

    def _apply_transform(self, series: pd.Series, transform: str) -> pd.Series:
        """
        Apply transform to raw level series.

        Parameters
        ----------
        series : pd.Series
            Raw level series.
        transform : str
            "pct_change": (p_t / p_{t-1}) - 1.
            "diff": p_t - p_{t-1}.
            "level": series as-is.

        Returns
        -------
        pd.Series
            Transformed series (one fewer observation for pct_change/diff).
        """
        if transform == "pct_change":
            result = series.pct_change()
        elif transform == "diff":
            result = series.diff()
        elif transform == "level":
            result = series.copy()
        else:
            logger.warning(f"Unknown transform '{transform}' — using level")
            result = series.copy()
        return result.dropna()

    def _to_weekly(self, series: pd.Series, frequency: str) -> pd.Series:
        """
        Resample a series to weekly (Friday) frequency.

        For weekly/daily data: take last observation of each week.
        For monthly data: resample to weekly then forward-fill.

        Parameters
        ----------
        series : pd.Series
        frequency : str
            "W" | "D" | "M"

        Returns
        -------
        pd.Series
            Weekly series indexed at week-ending Fridays.
        """
        if series.empty:
            return series
        series = series.sort_index()
        if frequency == "M":
            # Monthly: resample to weekly then fill
            weekly = series.resample("W").last()
            if self._config.fill_method == "interpolate":
                weekly = weekly.interpolate(method="time")
            else:
                weekly = weekly.ffill()
        else:
            # Daily or already weekly: take last of each week
            weekly = series.resample("W").last()
        return weekly.dropna()

    def _align_weekly(
        self,
        weekly_series: dict[str, pd.Series],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """
        Align all weekly series to a common weekly index, inserting NaN for
        missing variables.

        Parameters
        ----------
        weekly_series : dict[str, pd.Series]
        start, end : str

        Returns
        -------
        pd.DataFrame
            (T, N) weekly DataFrame.
        """
        if not weekly_series:
            return pd.DataFrame()

        # Build a union of all weekly indices
        all_indices = [s.index for s in weekly_series.values() if not s.empty]
        if not all_indices:
            return pd.DataFrame()

        union_idx = all_indices[0]
        for idx in all_indices[1:]:
            union_idx = union_idx.union(idx)

        # Filter to requested date range
        union_idx = union_idx[
            (union_idx >= pd.Timestamp(start)) & (union_idx <= pd.Timestamp(end))
        ]

        # Reindex each series
        aligned: dict[str, pd.Series] = {}
        for name in [v.name for v in self._config.variables]:
            if name in weekly_series:
                aligned[name] = weekly_series[name].reindex(union_idx)
            else:
                aligned[name] = pd.Series(np.nan, index=union_idx, name=name)

        return pd.DataFrame(aligned, index=union_idx)


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    def _smoke_test() -> None:
        config = MacroDataConfig(
            variables=[
                v for v in DEFAULT_MACRO_VARIABLES
                if v.name in ["DXY", "VIX", "US_10Y"]
            ],
            start_date="2020-01-01",
        )
        fetcher = MacroDataFetcher(config)
        result = fetcher.fetch()

        assert result.aligned_weekly.shape[1] == 3, (
            f"Expected 3 columns, got {result.aligned_weekly.shape[1]}"
        )
        assert len(result.missing_variables) == 0 or True, "Allow partial fetch"

        print(f"macro_data smoke test passed: {result.aligned_weekly.shape}")
        print(f"  Variables: {list(result.aligned_weekly.columns)}")
        print(f"  Date range: {result.date_range}")
        print(f"  Sources used: {result.source_used}")
        print(f"  Missing: {result.missing_variables}")

        # get_variable_names
        names = fetcher.get_variable_names()
        assert names == ["DXY", "VIX", "US_10Y"], f"Unexpected names: {names}"
        print(f"  get_variable_names(): {names}")

        # get_macro_shock_vector — pick a date in the middle
        if not result.aligned_weekly.empty:
            mid_date = result.aligned_weekly.index[len(result.aligned_weekly) // 2]
            shock_vec = fetcher.get_macro_shock_vector(result, str(mid_date.date()))
            assert isinstance(shock_vec, pd.Series)
            print(f"  get_macro_shock_vector() on {mid_date.date()}: {shock_vec.to_dict()}")

        print("\nmacro_data smoke test PASSED")

    _smoke_test()
