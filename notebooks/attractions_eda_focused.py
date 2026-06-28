"""
Focused Attractions EDA - Subtype Distribution, Missing Values, Rating & Review Analysis
With Visualizations

Usage:
    python notebooks/attractions_eda_focused.py cairo
    python notebooks/attractions_eda_focused.py alexandria
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
    print("Usage: python notebooks/attractions_eda_focused.py <city>")
    print("Example: python notebooks/attractions_eda_focused.py cairo")
    print("         python notebooks/attractions_eda_focused.py alexandria")
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

attractions = [d for d in data if d.get("category", "").lower() == "attraction"]
print(f"Total attractions in {CITY_LABEL} dataset: {len(attractions)}")
print("=" * 60)


# Build a DataFrame for easy plotting
rows = []
for a in attractions:
    ad = a.get("attraction_details") or {}
    rows.append({
        "name": a.get("name", ""),
        "subcategory": ad.get("subcategory", "Unknown"),
        "rating": a.get("rating"),
        "review_count": a.get("review_count"),
        "description": a.get("description", ""),
        "city": a.get("city", ""),
    })
df = pd.DataFrame(rows)

# ======================================================================
# 1. SUBCATEGORY DISTRIBUTION
# ======================================================================
print("\n[1] SUBCATEGORY DISTRIBUTION")
print("-" * 40)

subcategory_counts = df["subcategory"].value_counts()
for label, count in subcategory_counts.head(20).items():
    pct = count / len(df) * 100
    bar = "#" * int(pct / 2)
    print(f"  {label:>25}: {count:>4} ({pct:5.1f}%)  {bar}")

# --- Plot: Subcategory Distribution ---
top_n = 15
top_subcategories = subcategory_counts.head(top_n)

fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# Bar chart
colors = sns.color_palette("viridis", len(top_subcategories))
bars = axes[0].barh(top_subcategories.index[::-1], top_subcategories.values[::-1], color=colors[::-1], edgecolor="white", linewidth=0.8)
axes[0].set_title(f"{CITY_LABEL} — Attraction Subcategory Distribution (Top 15)", fontsize=14, fontweight="bold")
axes[0].set_xlabel("Number of Attractions")
for bar_obj, val in zip(bars, top_subcategories.values[::-1]):
    axes[0].text(bar_obj.get_width() + 3, bar_obj.get_y() + bar_obj.get_height() / 2,
                 str(val), ha="left", va="center", fontsize=10, fontweight="bold")

# Pie chart (top 10 + other)
top10 = subcategory_counts.head(10)
pie_labels = list(top10.index) + ["Other"]
pie_values = list(top10.values) + [subcategory_counts.iloc[10:].sum()]
pie_colors = sns.color_palette("viridis", len(pie_labels))
axes[1].pie(pie_values, labels=pie_labels, autopct="%1.1f%%", colors=pie_colors, startangle=90, pctdistance=0.8)
centre_circle = plt.Circle((0, 0), 0.50, fc="white")
axes[1].add_artist(centre_circle)
axes[1].set_title(f"{CITY_LABEL} — Subcategory Share (Top 10 + Other)", fontsize=14, fontweight="bold")

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_attraction_focused_subcategory_distribution.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_attraction_focused_subcategory_distribution.png")

# ======================================================================
# 2. MISSING VALUES
# ======================================================================
print("\n\n[2] MISSING VALUES")
print("-" * 40)

key_fields = ["subcategory", "rating", "review_count", "description"]
missing = {}
for field in key_fields:
    if field in df.columns:
        m = df[field].isna().sum()
    else:
        m = len(df)
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
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_attraction_focused_missing_values.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_attraction_focused_missing_values.png")

# ======================================================================
# 3. RATING ANALYSIS (Overall)
# ======================================================================
print("\n\n[3] RATING ANALYSIS (Overall)")
print("-" * 40)

ratings_valid = df["rating"].dropna()
print(f"  Attractions with rating data: {len(ratings_valid)}/{len(df)}")
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
axes[1].set_xticklabels(["All Attractions"])

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_attraction_focused_rating_distribution.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_attraction_focused_rating_distribution.png")

# ======================================================================
# 4. RATING BY SUBCATEGORY
# ======================================================================
print("\n\n[4] RATING BY SUBCATEGORY (Top 10)")
print("-" * 40)

top10_subcategories = subcategory_counts.head(10).index.tolist()
df_top = df[df["subcategory"].isin(top10_subcategories)]
rating_stats = df_top.groupby("subcategory")["rating"].agg(["mean", "median", "count"]).sort_values("mean", ascending=False)

for subcategory, row in rating_stats.iterrows():
    print(f"  {subcategory:>25}: avg={row['mean']:.2f}  (n={int(row['count'])})")

# --- Plot: Rating by Subcategory ---
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

order_r = rating_stats.index.tolist()
sns.boxplot(data=df_top, x="subcategory", y="rating", order=order_r,
            palette="viridis", ax=axes[0], fliersize=3, linewidth=1.2)
axes[0].set_title(f"{CITY_LABEL} — Rating Distribution by Subcategory", fontsize=14, fontweight="bold")
axes[0].set_xlabel("Subcategory")
axes[0].set_ylabel("Rating")
axes[0].tick_params(axis="x", rotation=45)

means = rating_stats["mean"]
bars = axes[1].bar(range(len(means)), means.values, color=sns.color_palette("viridis", len(means)),
                   edgecolor="white", linewidth=0.8)
axes[1].set_title(f"{CITY_LABEL} — Average Rating by Subcategory", fontsize=14, fontweight="bold")
axes[1].set_xlabel("Subcategory")
axes[1].set_ylabel("Average Rating")
axes[1].set_xticks(range(len(means)))
axes[1].set_xticklabels(means.index, rotation=45, ha="right")
axes[1].set_ylim(3.5, 4.8)
for bar_obj, val in zip(bars, means.values):
    axes[1].text(bar_obj.get_x() + bar_obj.get_width() / 2, bar_obj.get_height() + 0.02,
                 f"{val:.2f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_attraction_focused_rating_by_subcategory.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_attraction_focused_rating_by_subcategory.png")

# ======================================================================
# 5. REVIEW COUNT ANALYSIS
# ======================================================================
print("\n\n[5] REVIEW COUNT BY SUBCATEGORY (Top 10)")
print("-" * 40)

df_reviews = df_top.dropna(subset=["review_count"])
rev_stats = df_reviews.groupby("subcategory")["review_count"].agg(["mean", "median", "count"]).sort_values("mean", ascending=False)

for subcategory, row in rev_stats.iterrows():
    print(f"  {subcategory:>25}: avg={row['mean']:>8,.0f}  (n={int(row['count'])})")

# --- Plot: Review Count by Subcategory ---
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

order_rev = rev_stats.index.tolist()
sns.boxplot(data=df_reviews, x="subcategory", y="review_count", order=order_rev,
            palette="viridis", ax=axes[0], fliersize=3, linewidth=1.2)
axes[0].set_yscale("log")
axes[0].set_title(f"{CITY_LABEL} — Review Count by Subcategory (log)", fontsize=14, fontweight="bold")
axes[0].set_xlabel("Subcategory")
axes[0].set_ylabel("Review Count")
axes[0].tick_params(axis="x", rotation=45)

rv_means = rev_stats["mean"]
bars = axes[1].bar(range(len(rv_means)), rv_means.values, color=sns.color_palette("viridis", len(rv_means)),
                   edgecolor="white", linewidth=0.8)
axes[1].set_title(f"{CITY_LABEL} — Average Review Count by Subcategory", fontsize=14, fontweight="bold")
axes[1].set_xlabel("Subcategory")
axes[1].set_ylabel("Average Review Count")
axes[1].set_xticks(range(len(rv_means)))
axes[1].set_xticklabels(rv_means.index, rotation=45, ha="right")
for bar_obj, val in zip(bars, rv_means.values):
    axes[1].text(bar_obj.get_x() + bar_obj.get_width() / 2, bar_obj.get_height() + 50,
                 f"{val:,.0f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_attraction_focused_reviews_by_subcategory.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_attraction_focused_reviews_by_subcategory.png")

# ======================================================================
# 6. INTERACTIVE PLOTLY: Rating vs Review Count
# ======================================================================
df_interactive = df.dropna(subset=["rating", "review_count", "subcategory"]).copy()
top5_subcategories = subcategory_counts.head(5).index.tolist()
df_interactive = df_interactive[df_interactive["subcategory"].isin(top5_subcategories)]

if len(df_interactive) > 0:
    fig = px.scatter(
        df_interactive, x="review_count", y="rating", color="subcategory",
        hover_data=["name"],
        title=f"{CITY_LABEL} — Rating vs Review Count by Subcategory (Top 5)",
        labels={"review_count": "Review Count", "rating": "Rating", "subcategory": "Subcategory"},
        template="plotly_white",
        opacity=0.7,
    )
    fig.update_layout(width=900, height=600)
    fig.write_html(os.path.join(OUTPUT_DIR, f"{CITY}_attraction_focused_rating_vs_reviews_interactive.html"))
    print(f"  -> Saved {CITY}_attraction_focused_rating_vs_reviews_interactive.html")

# ======================================================================
# 7. SUMMARY DASHBOARD (Multi-panel)
# ======================================================================
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# Panel 1: Subcategory distribution
top10_plot = subcategory_counts.head(10)
axes[0, 0].barh(top10_plot.index[::-1], top10_plot.values[::-1], color=sns.color_palette("viridis", len(top10_plot))[::-1],
                edgecolor="white", linewidth=0.8)
axes[0, 0].set_title(f"{CITY_LABEL} — Subcategory Distribution (Top 10)", fontsize=13, fontweight="bold")
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

# Panel 4: Rating by subcategory (top 6)
top6_rating = rating_stats.head(6)
axes[1, 1].barh(top6_rating.index[::-1], top6_rating["mean"].values[::-1],
                color=sns.color_palette("viridis", len(top6_rating))[::-1], edgecolor="white", linewidth=0.8)
axes[1, 1].set_title(f"{CITY_LABEL} — Avg Rating by Subcategory (Top 6)", fontsize=13, fontweight="bold")
axes[1, 1].set_xlabel("Average Rating")
axes[1, 1].set_xlim(3.5, 4.8)

fig.suptitle(f"{CITY_LABEL} Attractions EDA Dashboard", fontsize=16, fontweight="bold", y=1.01)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_attraction_focused_dashboard.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_attraction_focused_dashboard.png")

print(f"\n{'=' * 60}")
print(f"EDA Complete for {CITY_LABEL}! All visualizations saved to outputs/figures/")
