"""Individual data source implementations with retry logic."""

import os
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd
import requests
from dotenv import load_dotenv
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..utils.logger import get_logger
from ..utils.helpers import chunk_list

# Load environment variables
load_dotenv()

logger = get_logger(__name__)

# LSEG Data Library is an optional, credential-gated dependency (same pattern
# as lseg_sectors.py) — its absence or an un-opened session must degrade to
# the yfinance fallback, never crash DataManager's source loop.
try:
    import lseg.data as ld
    from lseg.data.errors import LDError
    _LSEG_AVAILABLE = True
except ImportError:
    ld = None
    LDError = Exception
    _LSEG_AVAILABLE = False


class DataSourceError(Exception):
    """Custom exception for data source errors."""
    pass


class RateLimitError(DataSourceError):
    """Exception for rate limit errors."""
    pass


class BaseDataSource(ABC):
    """Abstract base class for data sources."""

    def __init__(self, name: str):
        """
        Initialize the data source.

        Args:
            name: Name of the data source
        """
        self.name = name
        self._is_available = True

    @abstractmethod
    def fetch_prices(
        self,
        tickers: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """
        Fetch price data for given tickers.

        Args:
            tickers: List of ticker symbols
            start_date: Start date for data
            end_date: End date for data

        Returns:
            DataFrame with prices (index=dates, columns=tickers)
        """
        pass

    @property
    def is_available(self) -> bool:
        """Check if the data source is available."""
        return self._is_available

    def mark_unavailable(self):
        """Mark this source as unavailable."""
        self._is_available = False
        logger.warning(f"{self.name} marked as unavailable")


class LSEGSource(BaseDataSource):
    """
    Refinitiv/LSEG Data Library price source (primary).

    Uses `lseg.data.get_history()` with the single field "TRDPRC_1" (the
    platform's default trade/last price), which returns a flat
    date-indexed DataFrame whose columns are the requested RICs directly
    (LSEG only builds a (ticker, field) MultiIndex when *multiple* fields
    are requested — see `lseg/data/content/_historical_df_builder.py`).
    `adjustments` requests the four CORAX corporate-action codes so
    splits/dividends are reflected, mirroring `auto_adjust=True` on the
    yfinance fallback below.

    Requires a configured session (a `lseg-data.config.json` discovered
    via the `LD_LIB_CONFIG_PATH` env var / cwd, or an app key passed
    directly). Neither is available in most deployments of this app, so
    this source is expected to mark itself unavailable and let
    `DataManager` fall through to `YFinanceSource` — that fallback is the
    normal path, not an error state.
    """

    def __init__(self, batch_size: int = 50, app_key: str = None):
        """
        Initialize the LSEG source.

        Args:
            batch_size: Number of tickers to request per get_history() call
            app_key: LSEG/Refinitiv app key (or from env var LSEG_APP_KEY;
                falls back to the library's own config-file discovery if unset)
        """
        super().__init__("LSEG")
        self.batch_size = batch_size
        self.app_key = app_key or os.getenv("LSEG_APP_KEY")
        self._session_opened = False

        if not _LSEG_AVAILABLE:
            logger.warning(
                "lseg.data is not installed. LSEG price source will be skipped. "
                "Install with: pip install lseg-data>=2.0.0"
            )
            self._is_available = False

    def _ensure_session(self) -> None:
        """Open an LSEG session on first use; mark unavailable if it can't open."""
        if self._session_opened:
            return

        try:
            if self.app_key:
                ld.open_session(app_key=self.app_key)
            else:
                ld.open_session()
            self._session_opened = True
        except Exception as e:
            logger.warning(f"LSEG session could not be opened, falling back: {e}")
            self.mark_unavailable()
            raise DataSourceError(f"LSEG session unavailable: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True,
    )
    def _fetch_batch(
        self,
        tickers: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Fetch a batch of tickers via get_history() with retry logic."""
        try:
            df = ld.get_history(
                universe=tickers,
                fields=["TRDPRC_1"],
                interval="daily",
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                adjustments=["CCH", "CRE", "RTS", "RPO"],
            )
        except LDError as e:
            raise DataSourceError(f"LSEG get_history failed for {tickers}: {e}") from e

        if df is None or df.empty:
            raise DataSourceError(f"No data returned for {tickers}")

        return df

    def fetch_prices(
        self,
        tickers: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """
        Fetch price data from the LSEG Data Library.

        Args:
            tickers: List of ticker symbols (RICs)
            start_date: Start date for data
            end_date: End date for data

        Returns:
            DataFrame with closing prices
        """
        if not self._is_available:
            raise DataSourceError(f"{self.name} is not available (not installed/configured)")

        logger.info(f"Fetching {len(tickers)} tickers from {self.name}")
        self._ensure_session()

        all_data = []
        batches = chunk_list(tickers, self.batch_size)

        for i, batch in enumerate(batches):
            try:
                logger.debug(f"Fetching batch {i+1}/{len(batches)}: {batch}")
                batch_data = self._fetch_batch(batch, start_date, end_date)
                all_data.append(batch_data)

            except Exception as e:
                logger.error(f"Error fetching batch {batch} from {self.name}: {e}")
                continue

        if not all_data:
            raise DataSourceError(f"Failed to fetch any data from {self.name}")

        result = pd.concat(all_data, axis=1)
        logger.info(f"Successfully fetched {len(result.columns)} tickers from {self.name}")

        return result


class YFinanceSource(BaseDataSource):
    """Yahoo Finance data source using yfinance library."""

    def __init__(self, batch_size: int = 5):
        """
        Initialize YFinance source.

        Args:
            batch_size: Number of tickers to fetch per batch
        """
        super().__init__("YFinance")
        self.batch_size = batch_size

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
        reraise=True,
    )
    def _fetch_batch(
        self,
        tickers: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Fetch a batch of tickers with retry logic."""
        import yfinance as yf

        # Add random jitter to avoid rate limits
        time.sleep(random.uniform(0.1, 0.5))

        ticker_str = " ".join(tickers)
        data = yf.download(
            ticker_str,
            start=start_date,
            end=end_date,
            progress=False,
            threads=False,
            auto_adjust=True,
        )

        if data.empty:
            raise DataSourceError(f"No data returned for {tickers}")

        # Handle single ticker vs multiple tickers
        if len(tickers) == 1:
            if "Close" in data.columns:
                return data[["Close"]].rename(columns={"Close": tickers[0]})
        else:
            if "Close" in data.columns.get_level_values(0):
                return data["Close"]

        return data

    def fetch_prices(
        self,
        tickers: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """
        Fetch price data from Yahoo Finance.

        Args:
            tickers: List of ticker symbols
            start_date: Start date for data
            end_date: End date for data

        Returns:
            DataFrame with closing prices
        """
        logger.info(f"Fetching {len(tickers)} tickers from {self.name}")

        all_data = []
        batches = chunk_list(tickers, self.batch_size)

        for i, batch in enumerate(batches):
            try:
                logger.debug(f"Fetching batch {i+1}/{len(batches)}: {batch}")
                batch_data = self._fetch_batch(batch, start_date, end_date)
                all_data.append(batch_data)

                # Add delay between batches
                if i < len(batches) - 1:
                    time.sleep(random.uniform(0.5, 1.5))

            except Exception as e:
                logger.error(f"Error fetching batch {batch}: {e}")
                # Continue with remaining batches
                continue

        if not all_data:
            raise DataSourceError(f"Failed to fetch any data from {self.name}")

        # Combine all batches
        result = pd.concat(all_data, axis=1)
        logger.info(f"Successfully fetched {len(result.columns)} tickers from {self.name}")

        return result

