"""
Focused Restaurant EDA - Subtype Distribution, Missing Values, Rating & Cost Analysis
With Visualizations

Usage:
    python notebooks/restaurants_eda_focused.py cairo
    python notebooks/restaurants_eda_focused.py alexandria
"""
import json
import os
import sys
from collections import Counter, defaultdict
import warnings
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Config ──────────────────────────────────────────────────────────────────

if len(sys.argv) < 2:
    print("Usage: python notebooks/restaurants_eda_focused.py <city>")
    print("Example: python notebooks/restaurants_eda_focused.py cairo")
    print("         python notebooks/restaurants_eda_focused.py alexandria")
    sys.exit(1)

CITY = sys.argv[1].lower().strip()
CITY_LABEL = CITY.title()

# -- Style --
sns.set_theme(style="whitegrid", font_scale=1.1)
PALETTE = sns.color_palette("viridis", 6)
ACCENT = "#2c7bb6"
ACCENT2 = "#d7191c"

# -- Load Data --
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "..", "data", CITY, f"{CITY}_places.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "outputs", "figures")
os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(DATA_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

restaurants = [d for d in data if d.get("category", "").lower() == "restaurant"]
print(f"Total restaurants in {CITY_LABEL} dataset: {len(restaurants)}")
print("=" * 60)


def parse_cost(rd):
    """Parse avg_cost_per_person string to float, return None if invalid."""
    raw = rd.get("avg_cost_per_person") if rd else None
    if raw:
        try:
            return float(raw.replace("$", "").replace(",", ""))
        except (ValueError, TypeError):
            return None
    return None


# Build a DataFrame for easy plotting
rows = []
for r in restaurants:
    rd = r.get("restaurant_details") or {}
    rows.append({
        "name": r.get("name", ""),
        "cuisine_type": rd.get("cuisine_type", "Unknown"),
        "avg_cost": parse_cost(rd),
        "rating": r.get("rating"),
        "review_count": r.get("review_count"),
        "description": r.get("description", ""),
        "city": r.get("city", ""),
    })
df = pd.DataFrame(rows)

# ======================================================================
# 1. CUISINE TYPE DISTRIBUTION
# ======================================================================
print("\n[1] CUISINE TYPE DISTRIBUTION")
print("-" * 40)

cuisine_counts = df["cuisine_type"].value_counts()
for label, count in cuisine_counts.head(20).items():
    pct = count / len(df) * 100
    bar = "#" * int(pct / 2)
    print(f"  {label:>30}: {count:>4} ({pct:5.1f}%)  {bar}")

# --- Plot: Cuisine Distribution (Top 15) ---
top_n = 15
top_cuisines = cuisine_counts.head(top_n)

fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# Bar chart
colors = sns.color_palette("viridis", len(top_cuisines))
bars = axes[0].barh(top_cuisines.index[::-1], top_cuisines.values[::-1], color=colors[::-1], edgecolor="white", linewidth=0.8)
axes[0].set_title(f"{CITY_LABEL} — Cuisine Type Distribution (Top 15)", fontsize=14, fontweight="bold")
axes[0].set_xlabel("Number of Restaurants")
for bar_obj, val in zip(bars, top_cuisines.values[::-1]):
    axes[0].text(bar_obj.get_width() + 5, bar_obj.get_y() + bar_obj.get_height() / 2,
                 str(val), ha="left", va="center", fontsize=10, fontweight="bold")

# Pie chart (top 10 + other)
top10 = cuisine_counts.head(10)
pie_labels = list(top10.index) + ["Other"]
pie_values = list(top10.values) + [cuisine_counts.iloc[10:].sum()]
pie_colors = sns.color_palette("viridis", len(pie_labels))
axes[1].pie(pie_values, labels=pie_labels, autopct="%1.1f%%", colors=pie_colors, startangle=90, pctdistance=0.8)
centre_circle = plt.Circle((0, 0), 0.50, fc="white")
axes[1].add_artist(centre_circle)
axes[1].set_title(f"{CITY_LABEL} — Cuisine Share (Top 10 + Other)", fontsize=14, fontweight="bold")

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_restaurant_focused_cuisine_distribution.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_restaurant_focused_cuisine_distribution.png")

# ======================================================================
# 2. MISSING VALUES
# ======================================================================
print("\n\n[2] MISSING VALUES")
print("-" * 40)

key_fields = ["cuisine_type", "rating", "review_count", "description", "avg_cost"]
missing = {}
for field in key_fields:
    if field == "avg_cost":
        m = df["avg_cost"].isna().sum()
    else:
        m = df[field].isna().sum()
    missing[field] = m
    pct = m / len(df) * 100
    print(f"  {field:<16}: {m:>4} missing ({pct:5.1f}%)")

# --- Plot: Missing Values ---
fig, ax = plt.subplots(figsize=(10, 5))
fields = list(missing.keys())
counts = [missing[f] for f in fields]
colors_miss = ["#d7191c" if c > 0 else "#2c7bb6" for c in counts]
bars = ax.barh(fields, counts, color=colors_miss, edgecolor="white", linewidth=0.8)
ax.set_title(f"{CITY_LABEL} — Missing Values by Field", fontsize=14, fontweight="bold")
ax.set_xlabel("Number of Missing Values")
for bar_obj, val in zip(bars, counts):
    ax.text(bar_obj.get_width() + 5, bar_obj.get_y() + bar_obj.get_height() / 2,
            str(val), ha="left", va="center", fontsize=11, fontweight="bold")
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_restaurant_focused_missing_values.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_restaurant_focused_missing_values.png")

# ======================================================================
# 3. RATING ANALYSIS (Overall)
# ======================================================================
print("\n\n[3] RATING ANALYSIS (Overall)")
print("-" * 40)

ratings_valid = df["rating"].dropna()
print(f"  Restaurants with rating data: {len(ratings_valid)}/{len(df)}")
if len(ratings_valid) > 0:
    print(f"  Min    : {ratings_valid.min():>6.2f}")
    print(f"  Max    : {ratings_valid.max():>6.2f}")
    print(f"  Mean   : {ratings_valid.mean():>6.2f}")
    print(f"  Median : {ratings_valid.median():>6.2f}")
    print(f"  Std Dev: {ratings_valid.std():>6.2f}")

# --- Plot: Rating Distribution ---
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

axes[0].hist(ratings_valid, bins=30, color=ACCENT, edgecolor="white", linewidth=0.5, alpha=0.85)
axes[0].axvline(ratings_valid.mean(), color=ACCENT2, linestyle="--", linewidth=2, label=f"Mean: {ratings_valid.mean():.2f}")
axes[0].axvline(ratings_valid.median(), color="#fdae61", linestyle="--", linewidth=2, label=f"Median: {ratings_valid.median():.2f}")
axes[0].set_title(f"{CITY_LABEL} — Rating Distribution", fontsize=14, fontweight="bold")
axes[0].set_xlabel("Rating")
axes[0].set_ylabel("Count")
axes[0].legend()

axes[1].boxplot(ratings_valid, vert=True, patch_artist=True,
                boxprops=dict(facecolor=ACCENT, alpha=0.6),
                medianprops=dict(color=ACCENT2, linewidth=2))
axes[1].set_title(f"{CITY_LABEL} — Rating Box Plot", fontsize=14, fontweight="bold")
axes[1].set_ylabel("Rating")
axes[1].set_xticklabels(["All Restaurants"])

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_restaurant_focused_rating_distribution.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_restaurant_focused_rating_distribution.png")

# ======================================================================
# 4. RATING BY CUISINE TYPE
# ======================================================================
print("\n\n[4] RATING BY CUISINE TYPE (Top 10)")
print("-" * 40)

top10_cuisines = cuisine_counts.head(10).index.tolist()
df_top = df[df["cuisine_type"].isin(top10_cuisines)]
rating_stats = df_top.groupby("cuisine_type")["rating"].agg(["mean", "median", "count"]).sort_values("mean", ascending=False)

for cuisine, row in rating_stats.iterrows():
    print(f"  {cuisine:>30}: avg={row['mean']:.2f}  (n={int(row['count'])})")

# --- Plot: Rating by Cuisine Type ---
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

order_r = rating_stats.index.tolist()
sns.boxplot(data=df_top, x="cuisine_type", y="rating", order=order_r,
            palette="viridis", ax=axes[0], fliersize=3, linewidth=1.2)
axes[0].set_title(f"{CITY_LABEL} — Rating Distribution by Cuisine Type", fontsize=14, fontweight="bold")
axes[0].set_xlabel("Cuisine Type")
axes[0].set_ylabel("Rating")
axes[0].tick_params(axis="x", rotation=45)

means = rating_stats["mean"]
bars = axes[1].bar(range(len(means)), means.values, color=sns.color_palette("viridis", len(means)),
                   edgecolor="white", linewidth=0.8)
axes[1].set_title(f"{CITY_LABEL} — Average Rating by Cuisine Type", fontsize=14, fontweight="bold")
axes[1].set_xlabel("Cuisine Type")
axes[1].set_ylabel("Average Rating")
axes[1].set_xticks(range(len(means)))
axes[1].set_xticklabels(means.index, rotation=45, ha="right")
axes[1].set_ylim(3.5, 4.8)
for bar_obj, val in zip(bars, means.values):
    axes[1].text(bar_obj.get_x() + bar_obj.get_width() / 2, bar_obj.get_height() + 0.02,
                 f"{val:.2f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_restaurant_focused_rating_by_cuisine.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_restaurant_focused_rating_by_cuisine.png")

# ======================================================================
# 5. REVIEW COUNT ANALYSIS
# ======================================================================
print("\n\n[5] REVIEW COUNT BY CUISINE TYPE (Top 10)")
print("-" * 40)

df_reviews = df_top.dropna(subset=["review_count"])
rev_stats = df_reviews.groupby("cuisine_type")["review_count"].agg(["mean", "median", "count"]).sort_values("mean", ascending=False)

for cuisine, row in rev_stats.iterrows():
    print(f"  {cuisine:>30}: avg={row['mean']:>8,.0f}  (n={int(row['count'])})")

# --- Plot: Review Count by Cuisine Type ---
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

order_rev = rev_stats.index.tolist()
sns.boxplot(data=df_reviews, x="cuisine_type", y="review_count", order=order_rev,
            palette="viridis", ax=axes[0], fliersize=3, linewidth=1.2)
axes[0].set_yscale("log")
axes[0].set_title(f"{CITY_LABEL} — Review Count by Cuisine Type (log)", fontsize=14, fontweight="bold")
axes[0].set_xlabel("Cuisine Type")
axes[0].set_ylabel("Review Count")
axes[0].tick_params(axis="x", rotation=45)

rv_means = rev_stats["mean"]
bars = axes[1].bar(range(len(rv_means)), rv_means.values, color=sns.color_palette("viridis", len(rv_means)),
                   edgecolor="white", linewidth=0.8)
axes[1].set_title(f"{CITY_LABEL} — Average Review Count by Cuisine Type", fontsize=14, fontweight="bold")
axes[1].set_xlabel("Cuisine Type")
axes[1].set_ylabel("Average Review Count")
axes[1].set_xticks(range(len(rv_means)))
axes[1].set_xticklabels(rv_means.index, rotation=45, ha="right")
for bar_obj, val in zip(bars, rv_means.values):
    axes[1].text(bar_obj.get_x() + bar_obj.get_width() / 2, bar_obj.get_height() + 50,
                 f"{val:,.0f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_restaurant_focused_reviews_by_cuisine.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_restaurant_focused_reviews_by_cuisine.png")

# ======================================================================
# 6. AVG COST PER PERSON
# ======================================================================
print("\n\n[6] AVG COST PER PERSON")
print("-" * 40)

costs_valid = df["avg_cost"].dropna()
print(f"  Restaurants with cost data: {len(costs_valid)}/{len(df)}")
if len(costs_valid) > 0:
    print(f"  Min    : ${costs_valid.min():>8.2f}")
    print(f"  Max    : ${costs_valid.max():>8.2f}")
    print(f"  Mean   : ${costs_valid.mean():>8.2f}")
    print(f"  Median : ${costs_valid.median():>8.2f}")

# Cost by cuisine type
df_cost = df.dropna(subset=["avg_cost"])
df_cost_top = df_cost[df_cost["cuisine_type"].isin(top10_cuisines)]
if len(df_cost_top) > 0:
    cost_stats = df_cost_top.groupby("cuisine_type")["avg_cost"].agg(["mean", "median", "count"]).sort_values("mean", ascending=False)

    print("\n  Avg cost by cuisine type:")
    for cuisine, row in cost_stats.iterrows():
        print(f"    {cuisine:>30}: ${row['mean']:>6.2f}  (n={int(row['count'])})")

    # --- Plot: Cost Distribution ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].hist(costs_valid, bins=50, color=ACCENT, edgecolor="white", linewidth=0.5, alpha=0.85)
    axes[0].axvline(costs_valid.mean(), color=ACCENT2, linestyle="--", linewidth=2, label=f"Mean: ${costs_valid.mean():.2f}")
    axes[0].axvline(costs_valid.median(), color="#fdae61", linestyle="--", linewidth=2, label=f"Median: ${costs_valid.median():.2f}")
    axes[0].set_title(f"{CITY_LABEL} — Avg Cost Per Person Distribution", fontsize=14, fontweight="bold")
    axes[0].set_xlabel("Avg Cost ($)")
    axes[0].set_ylabel("Count")
    axes[0].legend()

    order_c = cost_stats.index.tolist()
    sns.boxplot(data=df_cost_top, x="cuisine_type", y="avg_cost", order=order_c,
                palette="viridis", ax=axes[1], fliersize=3, linewidth=1.2)
    axes[1].set_title(f"{CITY_LABEL} — Avg Cost by Cuisine Type", fontsize=14, fontweight="bold")
    axes[1].set_xlabel("Cuisine Type")
    axes[1].set_ylabel("Avg Cost ($)")
    axes[1].tick_params(axis="x", rotation=45)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_restaurant_focused_cost_distribution.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  -> Saved {CITY}_restaurant_focused_cost_distribution.png")

# ======================================================================
# 7. RATING vs COST SCATTER
# ======================================================================
print("\n\n[7] RATING vs COST ANALYSIS")
print("-" * 40)

df_both = df.dropna(subset=["rating", "avg_cost"]).copy()
if len(df_both) > 0:
    corr = df_both["rating"].corr(df_both["avg_cost"])
    print(f"  Correlation between rating and cost: {corr:.4f}")
    print(f"  Data points: {len(df_both)}")

    # --- Plot: Rating vs Cost Scatter ---
    fig, ax = plt.subplots(figsize=(10, 7))
    scatter = ax.scatter(df_both["avg_cost"], df_both["rating"], alpha=0.3, s=20, c=df_both["rating"],
                         cmap="viridis", edgecolors="white", linewidth=0.3)
    ax.set_title(f"{CITY_LABEL} — Rating vs Avg Cost Per Person (r={corr:.3f})", fontsize=14, fontweight="bold")
    ax.set_xlabel("Avg Cost Per Person ($)")
    ax.set_ylabel("Rating")
    plt.colorbar(scatter, label="Rating")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_restaurant_focused_rating_vs_cost.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  -> Saved {CITY}_restaurant_focused_rating_vs_cost.png")

# ======================================================================
# 8. INTERACTIVE PLOTLY: Rating vs Cost by Cuisine Type
# ======================================================================
df_interactive = df.dropna(subset=["rating", "avg_cost", "cuisine_type"]).copy()
top5_cuisines = cuisine_counts.head(5).index.tolist()
df_interactive = df_interactive[df_interactive["cuisine_type"].isin(top5_cuisines)]

if len(df_interactive) > 0:
    fig = px.scatter(
        df_interactive, x="avg_cost", y="rating", color="cuisine_type",
        hover_data=["name", "review_count"],
        title=f"{CITY_LABEL} — Rating vs Avg Cost by Cuisine Type (Top 5)",
        labels={"avg_cost": "Avg Cost ($)", "rating": "Rating", "cuisine_type": "Cuisine Type"},
        template="plotly_white",
        opacity=0.7,
    )
    fig.update_layout(width=900, height=600)
    fig.write_html(os.path.join(OUTPUT_DIR, f"{CITY}_restaurant_focused_rating_vs_cost_interactive.html"))
    print(f"  -> Saved {CITY}_restaurant_focused_rating_vs_cost_interactive.html")

# ======================================================================
# 9. SUMMARY DASHBOARD (Multi-panel)
# ======================================================================
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# Panel 1: Cuisine type distribution
top10_plot = cuisine_counts.head(10)
axes[0, 0].barh(top10_plot.index[::-1], top10_plot.values[::-1], color=sns.color_palette("viridis", len(top10_plot))[::-1],
                edgecolor="white", linewidth=0.8)
axes[0, 0].set_title(f"{CITY_LABEL} — Cuisine Type Distribution (Top 10)", fontsize=13, fontweight="bold")
axes[0, 0].set_xlabel("Count")

# Panel 2: Rating distribution
axes[0, 1].hist(ratings_valid, bins=30, color=ACCENT, edgecolor="white", linewidth=0.5, alpha=0.85)
axes[0, 1].axvline(ratings_valid.mean(), color=ACCENT2, linestyle="--", linewidth=2, label=f"Mean: {ratings_valid.mean():.2f}")
axes[0, 1].set_title(f"{CITY_LABEL} — Rating Distribution", fontsize=13, fontweight="bold")
axes[0, 1].set_xlabel("Rating")
axes[0, 1].set_ylabel("Count")
axes[0, 1].legend()

# Panel 3: Missing values
miss_vals = [missing[f] for f in key_fields]
colors_m = ["#d7191c" if v > 0 else "#2c7bb6" for v in miss_vals]
axes[1, 0].barh(key_fields, miss_vals, color=colors_m, edgecolor="white")
axes[1, 0].set_title(f"{CITY_LABEL} — Missing Values", fontsize=13, fontweight="bold")
axes[1, 0].set_xlabel("Count")
axes[1, 0].invert_yaxis()
for i, v in enumerate(miss_vals):
    axes[1, 0].text(v + 5, i, str(v), va="center", fontweight="bold")

# Panel 4: Cost by cuisine type
if len(df_cost_top) > 0:
    cost_means = cost_stats["mean"].head(8)
    axes[1, 1].barh(cost_means.index[::-1], cost_means.values[::-1], color=sns.color_palette("viridis", len(cost_means))[::-1],
                    edgecolor="white", linewidth=0.8)
    axes[1, 1].set_title(f"{CITY_LABEL} — Avg Cost by Cuisine Type", fontsize=13, fontweight="bold")
    axes[1, 1].set_xlabel("Avg Cost ($)")

fig.suptitle(f"{CITY_LABEL} Restaurant EDA Dashboard", fontsize=16, fontweight="bold", y=1.01)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_restaurant_focused_dashboard.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_restaurant_focused_dashboard.png")

print(f"\n{'=' * 60}")
print(f"EDA Complete for {CITY_LABEL}! All visualizations saved to outputs/figures/")
