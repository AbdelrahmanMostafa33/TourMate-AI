"""
Shared utility functions for Cairo Places EDA notebooks.

Contains common helper functions used across the Hotels, Restaurants,
and Attractions EDA notebooks to avoid code duplication.

Functions:
    extract_location      – Parse a meaningful district/area from an address.
    detect_outliers_iqr   – Identify outliers via the IQR method.
    derive_features       – Engineer common columns (photos, reviews, hours, area).
    get_hashable_cols     – Return columns safe for pandas aggregation.
    compute_popularity    – Build a 0‑1 popularity score from rating + reviews.
    compute_recommendation_scores – Family / budget / luxury scoring.
"""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd
from scipy.stats import zscore  # noqa: F401 – kept for notebooks that import it
from sklearn.preprocessing import MinMaxScaler


# ---------------------------------------------------------------------------
# 1. Address / location helpers
# ---------------------------------------------------------------------------

def extract_location(address: str | None, depth: int = 2) -> str:
    """Extract a meaningful location (district / neighbourhood) from an address.

    The function walks the comma‑separated parts of *address* from the end,
    skipping generic terms such as "Cairo", "Giza", "Egypt" or "... Governorate",
    and returns the first sufficiently long, specific token it finds.

    Parameters
    ----------
    address : str or None
        Full address string, e.g.
        ``"2 Omar Ibn El-Khattab, Masaken Al Mohandesin, Nasr City, Cairo Governorate"``.
    depth : int, optional
        How many address parts (from the end) to inspect before giving up.
        Default is ``2``.

    Returns
    -------
    str
        A location token such as ``"Masaken Al Mohandesin"`` or ``"Unknown"``
        when no suitable part is found.

    Examples
    --------
    >>> extract_location("15 Ebeid, Rod El Farag, Cairo Governorate")
    'Rod El Farag'
    >>> extract_location(None)
    'Unknown'
    """
    if not isinstance(address, str):
        return "Unknown"
    parts = [p.strip() for p in address.split(",")]
    skip = {
        "cairo",
        "giza",
        "egypt",
        "governorate",
        "cairo governorate",
        "giza governorate",
    }
    for p in reversed(parts[1 : depth + 2]):
        if p.lower() in skip or any(kw in p.lower() for kw in skip):
            continue
        if len(p) > 3:
            return p
    return parts[1] if len(parts) > 1 else "Unknown"


# ---------------------------------------------------------------------------
# 2. Outlier detection
# ---------------------------------------------------------------------------

def detect_outliers_iqr(series: pd.Series, name: str) -> pd.Series:
    """Detect outliers using the Interquartile Range (IQR) method.

    Computes Q1, Q3 and the IQR, then flags any value outside
    ``[Q1 − 1.5 × IQR,  Q3 + 1.5 × IQR]`` as an outlier.

    Parameters
    ----------
    series : pd.Series
        Numeric column to analyse (e.g. ``review_count`` or ``rating``).
    name : str
        Human‑readable label printed in the diagnostic output.

    Returns
    -------
    pd.Series
        Subset of *series* containing only the outlier values.

    Side effects
    -------------
    Prints a one‑line summary: Q1, Q3, IQR, bounds and outlier count.
    """
    Q1 = series.quantile(0.25)
    Q3 = series.quantile(0.75)
    IQR = Q3 - Q1
    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR
    outliers = series[(series < lower) | (series > upper)]
    print(
        f"  {name}: Q1={Q1:.1f}, Q3={Q3:.1f}, IQR={IQR:.1f}, "
        f"bounds=[{lower:.1f}, {upper:.1f}], outliers={len(outliers):,}"
    )
    return outliers


# ---------------------------------------------------------------------------
# 3. Feature engineering
# ---------------------------------------------------------------------------

def derive_features(df: pd.DataFrame) -> pd.DataFrame:
    """Engineer common derived columns used across every category notebook.

    The following columns are created **in place** (and the frame is returned):

    * ``photo_count``      – Number of photos (from the ``photos`` list column).
    * ``review_text_count`` – Number of review texts (from the ``reviews`` list).
    * ``avg_review_length`` – Mean character length of review texts.
    * ``has_hours``        – 1 if opening‑hours data exists, else 0.
    * ``district``         – Short district name extracted from ``address``.
    * ``area``             – Slightly deeper area name extracted from ``address``.

    Parameters
    ----------
    df : pd.DataFrame
        Raw or partially cleaned places DataFrame.  Must contain at least
        an ``address`` column; ``photos``, ``reviews`` and ``hours`` are
        optional (column is simply skipped when absent).

    Returns
    -------
    pd.DataFrame
        The same frame, now augmented with the columns listed above.
    """
    if "photos" in df.columns:
        df["photo_count"] = df["photos"].apply(
            lambda x: len(x) if isinstance(x, list) else 0
        )

    if "reviews" in df.columns:
        df["review_text_count"] = df["reviews"].apply(
            lambda x: len(x) if isinstance(x, list) else 0
        )
        df["avg_review_length"] = df["reviews"].apply(
            lambda x: (
                np.mean([len(r) for r in x]) if isinstance(x, list) and len(x) > 0 else 0
            )
        )

    if "hours" in df.columns:
        df["has_hours"] = df["hours"].apply(
            lambda x: 1 if isinstance(x, dict) and len(x) > 0 else 0
        )

    df["district"] = df["address"].apply(extract_location)
    df["area"] = df["address"].apply(lambda x: extract_location(x, depth=3))

    return df


def get_hashable_cols(df: pd.DataFrame) -> List[str]:
    """Return column names that are safe for standard pandas aggregation.

    Columns are excluded when:

    * they belong to the known nested set (``photos``, ``reviews``, ``hours``), **or**
    * their dtype is ``object`` **and** at least one value is a ``list`` or ``dict``.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame whose columns should be inspected.

    Returns
    -------
    list of str
        Column names suitable for ``groupby``, ``describe``, ``corr``, etc.
    """
    nested_fields = {"photos", "reviews", "hours"}
    cols = [c for c in df.columns if c not in nested_fields]
    for c in list(cols):
        if df[c].dtype == "object" and df[c].apply(
            lambda x: isinstance(x, (list, dict))
        ).any():
            cols.remove(c)
    return cols


# ---------------------------------------------------------------------------
# 4. Scoring helpers
# ---------------------------------------------------------------------------

def compute_popularity(
    df: pd.DataFrame,
    rating_weight: float = 0.6,
    review_weight: float = 0.4,
) -> pd.DataFrame:
    """Compute a 0‑1 popularity score from normalised rating and review count.

    Both components are min‑max scaled.  Reviews are log‑transformed
    (``log1p``) before scaling to tame the heavy right skew typical of
    review counts.

    New columns added
    -----------------
    * ``rating_norm``     – Min‑max scaled rating (0‑1).
    * ``review_norm``     – Min‑max scaled log‑review count (0‑1).
    * ``popularity_score`` – Weighted combination, rounded to 4 decimals.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ``rating`` (float) and ``review_count`` (int) columns.
    rating_weight : float, optional
        Weight given to the rating component.  Default ``0.6``.
    review_weight : float, optional
        Weight given to the review component.  Default ``0.4``.

    Returns
    -------
    pd.DataFrame
        The same frame with three new columns appended.
    """
    scaler = MinMaxScaler()
    df["rating_norm"] = scaler.fit_transform(
        df[["rating"]].fillna(df["rating"].median())
    )
    df["review_norm"] = scaler.fit_transform(
        df[["review_count"]].fillna(df["review_count"].median()).apply(np.log1p)
    )
    df["popularity_score"] = (
        rating_weight * df["rating_norm"] + review_weight * df["review_norm"]
    ).round(4)
    return df


def compute_recommendation_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Build three recommendation‑oriented scores for traveller profiling.

    Scores are derived from ``rating_norm`` and ``review_norm`` (added by
    :func:`compute_popularity` if not already present).

    New columns added
    -----------------
    * ``family_friendly_score`` – Equal blend of rating and review popularity.
    * ``budget_score``          – Favourable to high‑review, mid‑rating spots.
    * ``luxury_score``          – Favourable to high‑rating, low‑review spots.

    All scores are clipped to [0, 1] and rounded to 4 decimal places.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ``rating_norm`` and ``review_norm`` (or ``rating`` and
        ``review_count`` so that :func:`compute_popularity` can be called).

    Returns
    -------
    pd.DataFrame
        The same frame with three new score columns appended.
    """
    if "rating_norm" not in df.columns:
        df = compute_popularity(df)

    df["family_friendly_score"] = (
        0.5 * df["rating_norm"] + 0.5 * df["review_norm"]
    ).round(4)

    df["budget_score"] = (
        1.0 - df["rating_norm"] * 0.3 + df["review_norm"] * 0.2
    ).clip(0, 1).round(4)

    df["luxury_score"] = (
        0.7 * df["rating_norm"] + 0.3 * (1 - df["review_norm"])
    ).clip(0, 1).round(4)

    return df
