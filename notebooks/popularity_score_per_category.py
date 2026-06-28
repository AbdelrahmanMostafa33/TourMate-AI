"""
Per-Category Popularity Score — Bayesian Formula
=================================================
Computes a tourist popularity score for each place, normalized per category
(ATTRACTION, HOTEL, RESTAURANT) so that v_max is category-specific.

Usage:
    python notebooks/popularity_score_per_category.py cairo
    python notebooks/popularity_score_per_category.py alexandria

Formula
-------
  WR   = (v / (v + m)) * R  +  (m / (v + m)) * C
  Quality = WR / 5
  Volume  = ln(1 + v) / ln(1 + v_max_per_category)
  Score   = 100 * (0.6 * Quality + 0.4 * Volume)

Constants
---------
  C = 4.333   Global average rating
  m = 50      Bayesian prior weight (smooths small-sample noise)
  v_max       Computed per CATEGORY within the city

Outputs
-------
  - Updated JSON (popularity_score overwritten in place)
  - Console summary with old vs new scores
  - Interactive HTML charts saved to outputs/figures/
"""

import json
import math
import os
import statistics
import sys
import warnings
from collections import defaultdict

warnings.filterwarnings("ignore")

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Config ──────────────────────────────────────────────────────────

if len(sys.argv) < 2:
    print("Usage: python notebooks/popularity_score_per_category.py <city>")
    print("Example: python notebooks/popularity_score_per_category.py cairo")
    print("         python notebooks/popularity_score_per_category.py alexandria")
    sys.exit(1)

CITY = sys.argv[1].lower().strip()
CITY_LABEL = CITY.title()

# ── Style ──────────────────────────────────────────────────────────
sns.set_theme(style="whitegrid", font_scale=1.1)
ACCENT = "#6366f1"   # indigo
ACCENT2 = "#f59e0b"  # amber
ACCENT3 = "#10b981"  # emerald

# ── Paths ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "..", "data", CITY)
INPUT_FILE = os.path.join(DATA_DIR, f"{CITY}_places.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "outputs", "figures")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Formula Constants ──────────────────────────────────────────────
C = 4.333   # global average rating
M = 50      # Bayesian prior weight


# ====================================================================
# FORMULA FUNCTIONS
# ====================================================================

def compute_weighted_rating(rating: float, review_count: int) -> float:
    """Bayesian weighted rating (WR)."""
    v = review_count
    return (v / (v + M)) * rating + (M / (v + M)) * C


def compute_volume_score(review_count: int, v_max: int) -> float:
    """Log-scaled popularity volume, normalized to [0, 1]."""
    if v_max <= 0:
        return 0.0
    return math.log(1 + review_count) / math.log(1 + v_max)


def compute_popularity_score(rating: float, review_count: int, v_max: int) -> float:
    """Final tourist popularity score on a 0–100 scale."""
    wr = compute_weighted_rating(rating, review_count)
    quality = wr / 5.0
    volume = compute_volume_score(review_count, v_max)
    return round(100.0 * (0.6 * quality + 0.4 * volume), 1)


# ====================================================================
# 1. LOAD DATA
# ====================================================================
print("=" * 70)
print(f"  Per-Category Popularity Score — Bayesian Formula ({CITY_LABEL})")
print("=" * 70)

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    places = json.load(f)

print(f"\nLoaded {len(places)} places from {CITY_LABEL} data.\n")

# ====================================================================
# 2. COMPUTE v_max PER CATEGORY
# ====================================================================
category_reviews: dict[str, list[int]] = defaultdict(list)
for place in places:
    cat = place.get("category", "UNKNOWN")
    v = place.get("review_count", 0)
    category_reviews[cat].append(v)

v_max_per_category: dict[str, int] = {}
print("--- Per-Category v_max ---")
for cat, reviews in sorted(category_reviews.items()):
    vm = max(reviews) if reviews else 0
    v_max_per_category[cat] = vm
    print(f"  {cat:<15s}  count={len(reviews):>5d}  v_max={vm:>10,}")

# ====================================================================
# 3. COMPUTE NEW SCORES
# ====================================================================
print(f"\n--- Score Comparison (old -> new) ---")
print(f"  {'Name':<42s} {'Cat':<12s} {'R':>4s} {'v':>8s} {'Old':>6s} {'New':>6s} {'D':>6s}")
print("  " + "-" * 95)

updated_count = 0
for place in places:
    cat = place.get("category", "UNKNOWN")
    rating = place.get("rating", 0.0)
    review_count = place.get("review_count", 0)
    old_score = place.get("popularity_score", 0.0)
    v_max = v_max_per_category[cat]

    new_score = compute_popularity_score(rating, review_count, v_max)
    delta = round(new_score - old_score, 1)

    place["popularity_score"] = new_score
    updated_count += 1

    name = place.get("name", "?")[:41]
    print(f"  {name:<42s} {cat:<12s} {rating:>4.1f} {review_count:>8,} {old_score:>6.1f} {new_score:>6.1f} {delta:>+6.1f}")

# ====================================================================
# 4. SAVE UPDATED JSON
# ====================================================================
with open(INPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(places, f, indent=2, ensure_ascii=False)

print(f"\n[OK] Updated {updated_count} places in {INPUT_FILE}")

# ====================================================================
# 5. SUMMARY STATS PER CATEGORY
# ====================================================================
print("\n--- Per-Category Score Summary ---")
cat_scores: dict[str, list[float]] = defaultdict(list)
cat_reviews: dict[str, list[int]] = defaultdict(list)
for place in places:
    cat = place.get("category", "UNKNOWN")
    cat_scores[cat].append(place["popularity_score"])
    cat_reviews[cat].append(place.get("review_count", 0))

for cat in sorted(cat_scores.keys()):
    scores = cat_scores[cat]
    print(
        f"  {cat:<12s}  n={len(scores):<5d}  "
        f"v_max={max(cat_reviews[cat]):>8,}  "
        f"min={min(scores):>5.1f}  max={max(scores):>5.1f}  "
        f"mean={statistics.mean(scores):>5.1f}  "
        f"median={statistics.median(scores):>5.1f}  "
        f"std={statistics.stdev(scores):>5.1f}"
    )

# ====================================================================
# 6. BUILD DATAFRAME FOR PLOTTING
# ====================================================================
rows = []
for p in places:
    rows.append({
        "name": p.get("name", ""),
        "category": p.get("category", "UNKNOWN"),
        "rating": p.get("rating", 0.0),
        "review_count": p.get("review_count", 0),
        "popularity_score": p.get("popularity_score", 0.0),
    })
df = pd.DataFrame(rows)

COLORS = {
    "ATTRACTION": ACCENT,
    "HOTEL": ACCENT2,
    "RESTAURANT": ACCENT3,
}
cat_order = ["ATTRACTION", "HOTEL", "RESTAURANT"]

# ====================================================================
# 7. CHART: OVERLAID HISTOGRAM (Matplotlib)
# ====================================================================
print("\n--- Generating Charts ---")

fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# Left: overlaid histogram
for cat in cat_order:
    scores = df[df["category"] == cat]["popularity_score"]
    axes[0].hist(scores, bins=40, alpha=0.6, label=f"{cat} (n={len(scores)})",
                 color=COLORS.get(cat, "#888"), edgecolor="white", linewidth=0.5)

axes[0].set_title(f"{CITY_LABEL} — Popularity Score Distribution by Category", fontsize=14, fontweight="bold")
axes[0].set_xlabel("Popularity Score")
axes[0].set_ylabel("Count")
axes[0].legend(title="Category")

# Right: box plot
bp = axes[1].boxplot(
    [df[df["category"] == cat]["popularity_score"].values for cat in cat_order],
    labels=cat_order,
    patch_artist=True,
    widths=0.5,
    medianprops=dict(color="black", linewidth=2),
)
for patch, cat in zip(bp["boxes"], cat_order):
    patch.set_facecolor(COLORS.get(cat, "#888"))
    patch.set_alpha(0.7)

axes[1].set_title(f"{CITY_LABEL} — Score Box Plot by Category", fontsize=14, fontweight="bold")
axes[1].set_ylabel("Popularity Score")

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_popularity_per_category_dist.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_popularity_per_category_dist.png")

# ====================================================================
# 8. CHART: HISTOGRAM + KDE PER CATEGORY
# ====================================================================
fig, axes = plt.subplots(1, 3, figsize=(18, 5))

for i, cat in enumerate(cat_order):
    scores = df[df["category"] == cat]["popularity_score"]
    axes[i].hist(scores, bins=35, alpha=0.6, color=COLORS.get(cat, "#888"),
                 edgecolor="white", linewidth=0.5, density=True)
    # KDE overlay
    try:
        from scipy.stats import gaussian_kde
        kde = gaussian_kde(scores, bw_method=0.3)
        x_range = np.linspace(scores.min() - 2, scores.max() + 2, 200)
        axes[i].plot(x_range, kde(x_range), color="black", linewidth=2)
    except ImportError:
        pass  # skip KDE if scipy not available

    axes[i].set_title(f"{cat}\n(n={len(scores)}, v_max={v_max_per_category[cat]:,})",
                      fontsize=12, fontweight="bold")
    axes[i].set_xlabel("Popularity Score")
    axes[i].set_ylabel("Density")
    axes[i].axvline(scores.mean(), color="red", linestyle="--", linewidth=1.5,
                    label=f"Mean: {scores.mean():.1f}")
    axes[i].axvline(scores.median(), color="orange", linestyle="--", linewidth=1.5,
                    label=f"Median: {scores.median():.1f}")
    axes[i].legend(fontsize=9)

fig.suptitle(f"{CITY_LABEL} — Per-Category Popularity Score Distributions", fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_popularity_per_category_kde.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_popularity_per_category_kde.png")

# ====================================================================
# 9. CHART: SCATTER — Rating vs Review Count (colored by score)
# ====================================================================
fig, axes = plt.subplots(1, 3, figsize=(18, 5))

for i, cat in enumerate(cat_order):
    sub = df[df["category"] == cat]
    scatter = axes[i].scatter(
        sub["review_count"], sub["rating"],
        c=sub["popularity_score"], cmap="RdYlGn",
        s=30, alpha=0.7, edgecolors="white", linewidth=0.3,
        vmin=50, vmax=100,
    )
    axes[i].set_title(f"{cat} (n={len(sub)})", fontsize=12, fontweight="bold")
    axes[i].set_xlabel("Review Count")
    axes[i].set_ylabel("Rating")
    axes[i].set_xscale("log")
    plt.colorbar(scatter, ax=axes[i], label="Popularity Score")

fig.suptitle(f"{CITY_LABEL} — Rating vs Review Count (colored by Popularity Score)",
             fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_popularity_per_category_scatter.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_popularity_per_category_scatter.png")

# ====================================================================
# 10. INTERACTIVE PLOTLY: OVERLAID HISTOGRAM
# ====================================================================
fig1 = go.Figure()
for cat in cat_order:
    scores = df[df["category"] == cat]["popularity_score"].tolist()
    fig1.add_trace(go.Histogram(
        x=scores,
        name=f"{cat} ({len(scores)})",
        marker_color=COLORS.get(cat, "#888"),
        opacity=0.65,
        nbinsx=40,
    ))

fig1.update_layout(
    title=dict(text=f"{CITY_LABEL} — Popularity Score Distribution by Category", font=dict(size=20)),
    xaxis_title="Popularity Score",
    yaxis_title="Count",
    barmode="overlay",
    template="plotly_white",
    legend=dict(title="Category", font=dict(size=13)),
    width=1000, height=550,
)

fig1.write_html(os.path.join(OUTPUT_DIR, f"{CITY}_popularity_per_category_interactive.html"), include_plotlyjs="cdn")
print(f"  -> Saved {CITY}_popularity_per_category_interactive.html")

# ====================================================================
# 11. INTERACTIVE PLOTLY: DASHBOARD (histogram + stats table)
# ====================================================================
fig3 = make_subplots(
    rows=2, cols=2,
    row_heights=[0.65, 0.35],
    specs=[[{"colspan": 2}, None], [{"type": "table"}, {"type": "table"}]],
    subplot_titles=[f"{CITY_LABEL} — Score Distribution (Per-Category Normalized v_max)", "", ""],
)

for cat in cat_order:
    scores = df[df["category"] == cat]["popularity_score"].tolist()
    fig3.add_trace(
        go.Histogram(x=scores, name=cat, marker_color=COLORS.get(cat, "#888"),
                     opacity=0.7, nbinsx=35),
        row=1, col=1,
    )

# Stats tables
header_vals = ["Category", "Count", "v_max", "Min", "Max", "Mean", "Median", "Std"]
for i, cat in enumerate(cat_order):
    scores = df[df["category"] == cat]["popularity_score"].tolist()
    reviews = df[df["category"] == cat]["review_count"].tolist()
    row_vals = [
        cat, str(len(scores)), f"{max(reviews):,}",
        f"{min(scores):.1f}", f"{max(scores):.1f}",
        f"{statistics.mean(scores):.1f}", f"{statistics.median(scores):.1f}",
        f"{statistics.stdev(scores):.1f}",
    ]
    fig3.add_trace(
        go.Table(
            header=dict(values=header_vals, fill_color=COLORS.get(cat, "#888"),
                        font=dict(color="white", size=11), align="center"),
            cells=dict(values=[[v] for v in row_vals], align="center", font=dict(size=11)),
        ),
        row=2, col=1 if i == 0 else 2,
    )

fig3.update_layout(
    barmode="overlay", template="plotly_white", showlegend=True,
    legend=dict(title="Category", font=dict(size=12)),
    width=1100, height=750,
)
fig3.update_xaxes(title_text="Popularity Score", row=1, col=1)
fig3.update_yaxes(title_text="Count", row=1, col=1)

fig3.write_html(os.path.join(OUTPUT_DIR, f"{CITY}_popularity_per_category_dashboard.html"), include_plotlyjs="cdn")
print(f"  -> Saved {CITY}_popularity_per_category_dashboard.html")

# ====================================================================
# DONE
# ====================================================================
print("\n" + "=" * 70)
print(f"  Per-Category Popularity Score computation + visualization complete!")
print(f"  Updated {updated_count} places in {INPUT_FILE}")
print(f"  Charts saved to {OUTPUT_DIR}")
print("=" * 70)
