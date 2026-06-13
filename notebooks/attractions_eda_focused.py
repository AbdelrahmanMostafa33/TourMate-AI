"""
Focused Attractions EDA - Subtype Distribution, Missing Values, Rating & Review Analysis
With Visualizations
"""
import json
import os
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

# -- Style --
sns.set_theme(style="whitegrid", font_scale=1.1)
PALETTE = sns.color_palette("viridis", 6)
ACCENT = "#2c7bb6"
ACCENT2 = "#d7191c"

# -- Load Data --
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "cairo_places.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "outputs", "figures")
os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(DATA_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

attractions = [d for d in data if d.get("category") == "attractions"]
print(f"Total attractions in dataset: {len(attractions)}")
print("=" * 60)


# Build a DataFrame for easy plotting
rows = []
for a in attractions:
    rows.append({
        "name": a.get("name", ""),
        "subtype": a.get("subtype", "Unknown"),
        "rating": a.get("rating"),
        "review_count": a.get("review_count"),
        "description": a.get("description", ""),
        "neighborhood": a.get("neighborhood", "Unknown"),
        "hours": a.get("hours"),
        "city": a.get("city", ""),
    })
df = pd.DataFrame(rows)

# ======================================================================
# 1. SUBTYPE DISTRIBUTION
# ======================================================================
print("\n[1] SUBTYPE DISTRIBUTION")
print("-" * 40)

subtype_counts = df["subtype"].value_counts()
for label, count in subtype_counts.head(20).items():
    pct = count / len(df) * 100
    bar = "#" * int(pct / 2)
    print(f"  {label:>25}: {count:>4} ({pct:5.1f}%)  {bar}")

# --- Plot: Subtype Distribution ---
top_n = 15
top_subtypes = subtype_counts.head(top_n)

fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# Bar chart
colors = sns.color_palette("viridis", len(top_subtypes))
bars = axes[0].barh(top_subtypes.index[::-1], top_subtypes.values[::-1], color=colors[::-1], edgecolor="white", linewidth=0.8)
axes[0].set_title("Attraction Subtype Distribution (Top 15)", fontsize=14, fontweight="bold")
axes[0].set_xlabel("Number of Attractions")
for bar_obj, val in zip(bars, top_subtypes.values[::-1]):
    axes[0].text(bar_obj.get_width() + 3, bar_obj.get_y() + bar_obj.get_height() / 2,
                 str(val), ha="left", va="center", fontsize=10, fontweight="bold")

# Pie chart (top 10 + other)
top10 = subtype_counts.head(10)
pie_labels = list(top10.index) + ["Other"]
pie_values = list(top10.values) + [subtype_counts.iloc[10:].sum()]
pie_colors = sns.color_palette("viridis", len(pie_labels))
axes[1].pie(pie_values, labels=pie_labels, autopct="%1.1f%%", colors=pie_colors, startangle=90, pctdistance=0.8)
centre_circle = plt.Circle((0, 0), 0.50, fc="white")
axes[1].add_artist(centre_circle)
axes[1].set_title("Subtype Share (Top 10 + Other)", fontsize=14, fontweight="bold")

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "attraction_focused_subtype_distribution.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  -> Saved attraction_focused_subtype_distribution.png")

# ======================================================================
# 2. MISSING VALUES
# ======================================================================
print("\n\n[2] MISSING VALUES")
print("-" * 40)

key_fields = ["subtype", "rating", "review_count", "description", "neighborhood", "hours"]
missing = {}
for field in key_fields:
    if field in df.columns:
        if field == "hours":
            m = df["hours"].apply(lambda x: not x or (isinstance(x, dict) and not any(x.values()))).sum()
        elif field == "neighborhood":
            m = (df["neighborhood"] == "Unknown").sum()
        else:
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
ax.set_title("Missing Values by Field", fontsize=14, fontweight="bold")
ax.set_xlabel("Number of Missing Values")
for bar_obj, val in zip(bars, counts):
    ax.text(bar_obj.get_width() + 5, bar_obj.get_y() + bar_obj.get_height() / 2,
            str(val), ha="left", va="center", fontsize=11, fontweight="bold")
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "attraction_focused_missing_values.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  -> Saved attraction_focused_missing_values.png")

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
axes[0].set_title("Rating Distribution", fontsize=14, fontweight="bold")
axes[0].set_xlabel("Rating")
axes[0].set_ylabel("Count")
axes[0].legend()

axes[1].boxplot(ratings_valid, vert=True, patch_artist=True,
                boxprops=dict(facecolor=ACCENT, alpha=0.6),
                medianprops=dict(color=ACCENT2, linewidth=2))
axes[1].set_title("Rating Box Plot", fontsize=14, fontweight="bold")
axes[1].set_ylabel("Rating")
axes[1].set_xticklabels(["All Attractions"])

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "attraction_focused_rating_distribution.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  -> Saved attraction_focused_rating_distribution.png")

# ======================================================================
# 4. RATING BY SUBTYPE
# ======================================================================
print("\n\n[4] RATING BY SUBTYPE (Top 10)")
print("-" * 40)

top10_subtypes = subtype_counts.head(10).index.tolist()
df_top = df[df["subtype"].isin(top10_subtypes)]
rating_stats = df_top.groupby("subtype")["rating"].agg(["mean", "median", "count"]).sort_values("mean", ascending=False)

for subtype, row in rating_stats.iterrows():
    print(f"  {subtype:>25}: avg={row['mean']:.2f}  (n={int(row['count'])})")

# --- Plot: Rating by Subtype ---
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

order_r = rating_stats.index.tolist()
sns.boxplot(data=df_top, x="subtype", y="rating", order=order_r,
            palette="viridis", ax=axes[0], fliersize=3, linewidth=1.2)
axes[0].set_title("Rating Distribution by Subtype", fontsize=14, fontweight="bold")
axes[0].set_xlabel("Subtype")
axes[0].set_ylabel("Rating")
axes[0].tick_params(axis="x", rotation=45)

means = rating_stats["mean"]
bars = axes[1].bar(range(len(means)), means.values, color=sns.color_palette("viridis", len(means)),
                   edgecolor="white", linewidth=0.8)
axes[1].set_title("Average Rating by Subtype", fontsize=14, fontweight="bold")
axes[1].set_xlabel("Subtype")
axes[1].set_ylabel("Average Rating")
axes[1].set_xticks(range(len(means)))
axes[1].set_xticklabels(means.index, rotation=45, ha="right")
axes[1].set_ylim(3.5, 4.8)
for bar_obj, val in zip(bars, means.values):
    axes[1].text(bar_obj.get_x() + bar_obj.get_width() / 2, bar_obj.get_height() + 0.02,
                 f"{val:.2f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "attraction_focused_rating_by_subtype.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  -> Saved attraction_focused_rating_by_subtype.png")

# ======================================================================
# 5. REVIEW COUNT ANALYSIS
# ======================================================================
print("\n\n[5] REVIEW COUNT BY SUBTYPE (Top 10)")
print("-" * 40)

df_reviews = df_top.dropna(subset=["review_count"])
rev_stats = df_reviews.groupby("subtype")["review_count"].agg(["mean", "median", "count"]).sort_values("mean", ascending=False)

for subtype, row in rev_stats.iterrows():
    print(f"  {subtype:>25}: avg={row['mean']:>8,.0f}  (n={int(row['count'])})")

# --- Plot: Review Count by Subtype ---
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

order_rev = rev_stats.index.tolist()
sns.boxplot(data=df_reviews, x="subtype", y="review_count", order=order_rev,
            palette="viridis", ax=axes[0], fliersize=3, linewidth=1.2)
axes[0].set_yscale("log")
axes[0].set_title("Review Count by Subtype (log)", fontsize=14, fontweight="bold")
axes[0].set_xlabel("Subtype")
axes[0].set_ylabel("Review Count")
axes[0].tick_params(axis="x", rotation=45)

rv_means = rev_stats["mean"]
bars = axes[1].bar(range(len(rv_means)), rv_means.values, color=sns.color_palette("viridis", len(rv_means)),
                   edgecolor="white", linewidth=0.8)
axes[1].set_title("Average Review Count by Subtype", fontsize=14, fontweight="bold")
axes[1].set_xlabel("Subtype")
axes[1].set_ylabel("Average Review Count")
axes[1].set_xticks(range(len(rv_means)))
axes[1].set_xticklabels(rv_means.index, rotation=45, ha="right")
for bar_obj, val in zip(bars, rv_means.values):
    axes[1].text(bar_obj.get_x() + bar_obj.get_width() / 2, bar_obj.get_height() + 50,
                 f"{val:,.0f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "attraction_focused_reviews_by_subtype.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  -> Saved attraction_focused_reviews_by_subtype.png")

# ======================================================================
# 6. INTERACTIVE PLOTLY: Rating vs Review Count
# ======================================================================
df_interactive = df.dropna(subset=["rating", "review_count", "subtype"]).copy()
top5_subtypes = subtype_counts.head(5).index.tolist()
df_interactive = df_interactive[df_interactive["subtype"].isin(top5_subtypes)]

fig = px.scatter(
    df_interactive, x="review_count", y="rating", color="subtype",
    hover_data=["name"],
    title="Rating vs Review Count by Subtype (Top 5)",
    labels={"review_count": "Review Count", "rating": "Rating", "subtype": "Subtype"},
    template="plotly_white",
    opacity=0.7,
)
fig.update_layout(width=900, height=600)
fig.write_html(os.path.join(OUTPUT_DIR, "attraction_focused_rating_vs_reviews_interactive.html"))
print("  -> Saved attraction_focused_rating_vs_reviews_interactive.html")

# ======================================================================
# 7. SUMMARY DASHBOARD (Multi-panel)
# ======================================================================
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# Panel 1: Subtype distribution
top10_plot = subtype_counts.head(10)
axes[0, 0].barh(top10_plot.index[::-1], top10_plot.values[::-1], color=sns.color_palette("viridis", len(top10_plot))[::-1],
                edgecolor="white", linewidth=0.8)
axes[0, 0].set_title("Subtype Distribution (Top 10)", fontsize=13, fontweight="bold")
axes[0, 0].set_xlabel("Count")

# Panel 2: Rating distribution
axes[0, 1].hist(ratings_valid, bins=30, color=ACCENT, edgecolor="white", linewidth=0.5, alpha=0.85)
axes[0, 1].axvline(ratings_valid.mean(), color=ACCENT2, linestyle="--", linewidth=2, label=f"Mean: {ratings_valid.mean():.2f}")
axes[0, 1].set_title("Rating Distribution", fontsize=13, fontweight="bold")
axes[0, 1].set_xlabel("Rating")
axes[0, 1].set_ylabel("Count")
axes[0, 1].legend()

# Panel 3: Missing values
miss_vals = [missing[f] for f in key_fields]
colors_m = ["#d7191c" if v > 0 else "#2c7bb6" for v in miss_vals]
axes[1, 0].barh(key_fields, miss_vals, color=colors_m, edgecolor="white")
axes[1, 0].set_title("Missing Values", fontsize=13, fontweight="bold")
axes[1, 0].set_xlabel("Count")
axes[1, 0].invert_yaxis()
for i, v in enumerate(miss_vals):
    axes[1, 0].text(v + 5, i, str(v), va="center", fontweight="bold")

# Panel 4: Rating by subtype (top 6)
top6_rating = rating_stats.head(6)
axes[1, 1].barh(top6_rating.index[::-1], top6_rating["mean"].values[::-1],
                color=sns.color_palette("viridis", len(top6_rating))[::-1], edgecolor="white", linewidth=0.8)
axes[1, 1].set_title("Avg Rating by Subtype (Top 6)", fontsize=13, fontweight="bold")
axes[1, 1].set_xlabel("Average Rating")
axes[1, 1].set_xlim(3.5, 4.8)

fig.suptitle("Attractions EDA Dashboard", fontsize=16, fontweight="bold", y=1.01)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "attraction_focused_dashboard.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  -> Saved attraction_focused_dashboard.png")

print("\n" + "=" * 60)
print("EDA Complete! All visualizations saved to outputs/figures/")
