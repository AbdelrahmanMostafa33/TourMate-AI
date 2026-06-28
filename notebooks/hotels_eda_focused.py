"""
Focused Hotel EDA - Star Class Distribution, Missing Values, and Nightly Rate Analysis
With Visualizations

Usage:
    python notebooks/hotels_eda_focused.py cairo
    python notebooks/hotels_eda_focused.py alexandria
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
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Config ──────────────────────────────────────────────────────────────────

if len(sys.argv) < 2:
    print("Usage: python notebooks/hotels_eda_focused.py <city>")
    print("Example: python notebooks/hotels_eda_focused.py cairo")
    print("         python notebooks/hotels_eda_focused.py alexandria")
    sys.exit(1)

CITY = sys.argv[1].lower().strip()
CITY_LABEL = CITY.title()

# ── Style ──────────────────────────────────────────────────────────────────
sns.set_theme(style="whitegrid", font_scale=1.1)
PALETTE = sns.color_palette("viridis", 6)
ACCENT = "#2c7bb6"
ACCENT2 = "#d7191c"

# ── Load Data ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "..", "data", CITY, f"{CITY}_places.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "outputs", "figures")
os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(DATA_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

hotels = [d for d in data if d.get("category", "").lower() == "hotel"]
print(f"Total hotels in {CITY_LABEL} dataset: {len(hotels)}")
print("=" * 60)


def parse_rate(hd):
    """Parse nightly_rate string to float, return None if invalid."""
    raw = hd.get("nightly_rate") if hd else None
    if raw:
        try:
            return float(raw.replace("$", "").replace(",", ""))
        except (ValueError, TypeError):
            return None
    return None


# Build a DataFrame for easy plotting
rows = []
for h in hotels:
    hd = h.get("hotel_details") or {}
    rows.append({
        "name": h.get("name", ""),
        "star_class": hd.get("star_class"),
        "nightly_rate": parse_rate(hd),
        "rating": h.get("rating"),
        "review_count": h.get("review_count"),
        "description": h.get("description", ""),
        "amenities": hd.get("amenities", []),
        "city": h.get("city", ""),
    })
df = pd.DataFrame(rows)

# ═══════════════════════════════════════════════════════════════════════════
# 1. STAR CLASS DISTRIBUTION
# ═══════════════════════════════════════════════════════════════════════════
print("\n[1] STAR CLASS DISTRIBUTION")
print("-" * 40)

star_counts = df["star_class"].value_counts(dropna=False).sort_index()
star_counts.index = star_counts.index.map(
    lambda x: f"{int(x)}-star" if pd.notna(x) else "Unknown"
)

for label, count in star_counts.items():
    pct = count / len(df) * 100
    bar = "#" * int(pct / 2)
    print(f"  {label:>12}: {count:>4} hotels ({pct:5.1f}%)  {bar}")

# --- Plot: Star Class Distribution Bar Chart ---
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Bar chart
colors = sns.color_palette("viridis", len(star_counts))
bars = axes[0].bar(star_counts.index, star_counts.values, color=colors, edgecolor="white", linewidth=0.8)
axes[0].set_title(f"{CITY_LABEL} — Star Class Distribution", fontsize=14, fontweight="bold")
axes[0].set_xlabel("Star Class")
axes[0].set_ylabel("Number of Hotels")
for bar_obj, val in zip(bars, star_counts.values):
    axes[0].text(bar_obj.get_x() + bar_obj.get_width() / 2, bar_obj.get_height() + 3,
                 str(val), ha="center", va="bottom", fontsize=11, fontweight="bold")

# Pie chart
axes[1].pie(star_counts.values, labels=star_counts.index, autopct="%1.1f%%",
            colors=colors, startangle=90, pctdistance=0.75)
centre_circle = plt.Circle((0, 0), 0.50, fc="white")
axes[1].add_artist(centre_circle)
axes[1].set_title(f"{CITY_LABEL} — Star Class Share", fontsize=14, fontweight="bold")

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_hotel_focused_star_class_distribution.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_hotel_focused_star_class_distribution.png")

# ═══════════════════════════════════════════════════════════════════════════
# 2. MISSING VALUES
# ═══════════════════════════════════════════════════════════════════════════
print("\n\n[2] MISSING VALUES")
print("-" * 40)

key_fields = ["star_class", "nightly_rate", "rating", "review_count", "description"]
missing = {}
for field in key_fields:
    if field == "nightly_rate":
        m = df["nightly_rate"].isna().sum()
    elif field == "star_class":
        m = df["star_class"].isna().sum()
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
    ax.text(bar_obj.get_width() + 2, bar_obj.get_y() + bar_obj.get_height() / 2,
            str(val), ha="left", va="center", fontsize=11, fontweight="bold")
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_hotel_focused_missing_values.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_hotel_focused_missing_values.png")

# ═══════════════════════════════════════════════════════════════════════════
# 3. NIGHTLY RATE ANALYSIS (Overall)
# ═══════════════════════════════════════════════════════════════════════════
print("\n\n[3] NIGHTLY RATE ANALYSIS (Overall)")
print("-" * 40)

rates_valid = df["nightly_rate"].dropna()
print(f"  Hotels with rate data: {len(rates_valid)}/{len(df)}")
if len(rates_valid) > 0:
    print(f"  Min    : ${rates_valid.min():>10.2f}")
    print(f"  Max    : ${rates_valid.max():>10.2f}")
    print(f"  Mean   : ${rates_valid.mean():>10.2f}")
    print(f"  Median : ${rates_valid.median():>10.2f}")
    print(f"  Std Dev: ${rates_valid.std():>10.2f}")

# --- Plot: Nightly Rate Histogram ---
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Histogram
axes[0].hist(rates_valid, bins=50, color=ACCENT, edgecolor="white", linewidth=0.5, alpha=0.85)
axes[0].axvline(rates_valid.mean(), color=ACCENT2, linestyle="--", linewidth=2, label=f"Mean: ${rates_valid.mean():.0f}")
axes[0].axvline(rates_valid.median(), color="#fdae61", linestyle="--", linewidth=2, label=f"Median: ${rates_valid.median():.0f}")
axes[0].set_title(f"{CITY_LABEL} — Nightly Rate Distribution", fontsize=14, fontweight="bold")
axes[0].set_xlabel("Nightly Rate ($)")
axes[0].set_ylabel("Count")
axes[0].legend()

# Box plot (overall)
axes[1].boxplot(rates_valid, vert=True, patch_artist=True,
                boxprops=dict(facecolor=ACCENT, alpha=0.6),
                medianprops=dict(color=ACCENT2, linewidth=2))
axes[1].set_title(f"{CITY_LABEL} — Nightly Rate Box Plot", fontsize=14, fontweight="bold")
axes[1].set_ylabel("Nightly Rate ($)")
axes[1].set_xticklabels(["All Hotels"])

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_hotel_focused_nightly_rate_distribution.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_hotel_focused_nightly_rate_distribution.png")

# ═══════════════════════════════════════════════════════════════════════════
# 4. AVERAGE NIGHTLY RATE PER STAR CLASS
# ═══════════════════════════════════════════════════════════════════════════
print("\n\n[4] AVERAGE NIGHTLY RATE PER STAR CLASS")
print("-" * 40)

df_rate = df.dropna(subset=["nightly_rate", "star_class"])
if len(df_rate) > 0:
    rate_stats = df_rate.groupby("star_class")["nightly_rate"].agg(["count", "mean", "median", "min", "max", "std"])
    rate_stats.index = rate_stats.index.map(lambda x: f"{int(x)}")

    for star, row in rate_stats.iterrows():
        print(f"\n  {star}-STAR HOTELS (n={int(row['count'])}):")
        print(f"    Avg   : ${row['mean']:>10.2f}")
        print(f"    Median: ${row['median']:>10.2f}")
        print(f"    Min   : ${row['min']:>10.2f}")
        print(f"    Max   : ${row['max']:>10.2f}")

    # --- Plot: Nightly Rate by Star Class (Box Plot + Strip) ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Box plot with strip
    order = sorted(df_rate["star_class"].unique())
    sns.boxplot(data=df_rate, x="star_class", y="nightly_rate", order=order,
                palette="viridis", ax=axes[0], fliersize=3, linewidth=1.2)
    sns.stripplot(data=df_rate, x="star_class", y="nightly_rate", order=order,
                  color="black", alpha=0.3, size=4, ax=axes[0])
    axes[0].set_title(f"{CITY_LABEL} — Nightly Rate by Star Class", fontsize=14, fontweight="bold")
    axes[0].set_xlabel("Star Class")
    axes[0].set_ylabel("Nightly Rate ($)")
    axes[0].set_xticklabels([f"{int(s)}-star" for s in order])

    # Bar chart of means
    means = df_rate.groupby("star_class")["nightly_rate"].mean()
    means.index = means.index.map(lambda x: f"{int(x)}-star")
    bars = axes[1].bar(means.index, means.values, color=sns.color_palette("viridis", len(means)),
                       edgecolor="white", linewidth=0.8)
    axes[1].set_title(f"{CITY_LABEL} — Average Nightly Rate by Star Class", fontsize=14, fontweight="bold")
    axes[1].set_xlabel("Star Class")
    axes[1].set_ylabel("Average Nightly Rate ($)")
    for bar_obj, val in zip(bars, means.values):
        axes[1].text(bar_obj.get_x() + bar_obj.get_width() / 2, bar_obj.get_height() + 2,
                     f"${val:.0f}", ha="center", va="bottom", fontsize=11, fontweight="bold")

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_hotel_focused_rate_by_star_class.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  -> Saved {CITY}_hotel_focused_rate_by_star_class.png")

# ═══════════════════════════════════════════════════════════════════════════
# 5. RATING BY STAR CLASS
# ═══════════════════════════════════════════════════════════════════════════
print("\n\n[5] RATING BY STAR CLASS")
print("-" * 40)

df_rating = df.dropna(subset=["rating", "star_class"])
if len(df_rating) > 0:
    rating_stats = df_rating.groupby("star_class")["rating"].agg(["mean", "median", "count"])
    rating_stats.index = rating_stats.index.map(lambda x: f"{int(x)}")

    for star, row in rating_stats.iterrows():
        print(f"  {star}-star: avg rating = {row['mean']:.2f}  (n={int(row['count'])})")

    # --- Plot: Rating by Star Class ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Box plot
    order_r = sorted(df_rating["star_class"].unique())
    sns.boxplot(data=df_rating, x="star_class", y="rating", order=order_r,
                palette="viridis", ax=axes[0], fliersize=3, linewidth=1.2)
    axes[0].set_title(f"{CITY_LABEL} — Rating Distribution by Star Class", fontsize=14, fontweight="bold")
    axes[0].set_xlabel("Star Class")
    axes[0].set_ylabel("Rating")
    axes[0].set_xticklabels([f"{int(s)}-star" for s in order_r])

    # Bar chart of means
    r_means = df_rating.groupby("star_class")["rating"].mean()
    r_means.index = r_means.index.map(lambda x: f"{int(x)}-star")
    bars = axes[1].bar(r_means.index, r_means.values, color=sns.color_palette("viridis", len(r_means)),
                       edgecolor="white", linewidth=0.8)
    axes[1].set_title(f"{CITY_LABEL} — Average Rating by Star Class", fontsize=14, fontweight="bold")
    axes[1].set_xlabel("Star Class")
    axes[1].set_ylabel("Average Rating")
    axes[1].set_ylim(3.5, 4.8)
    for bar_obj, val in zip(bars, r_means.values):
        axes[1].text(bar_obj.get_x() + bar_obj.get_width() / 2, bar_obj.get_height() + 0.02,
                     f"{val:.2f}", ha="center", va="bottom", fontsize=11, fontweight="bold")

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_hotel_focused_rating_by_star_class.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  -> Saved {CITY}_hotel_focused_rating_by_star_class.png")

# ═══════════════════════════════════════════════════════════════════════════
# 6. REVIEW COUNT BY STAR CLASS
# ═══════════════════════════════════════════════════════════════════════════
print("\n\n[6] REVIEW COUNT BY STAR CLASS")
print("-" * 40)

df_reviews = df.dropna(subset=["review_count", "star_class"])
if len(df_reviews) > 0:
    rev_stats = df_reviews.groupby("star_class")["review_count"].agg(["mean", "median", "count"])
    rev_stats.index = rev_stats.index.map(lambda x: f"{int(x)}")

    for star, row in rev_stats.iterrows():
        print(f"  {star}-star: avg reviews = {row['mean']:,.0f}  (n={int(row['count'])})")

    # --- Plot: Review Count by Star Class ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Box plot (log scale)
    order_rev = sorted(df_reviews["star_class"].unique())
    sns.boxplot(data=df_reviews, x="star_class", y="review_count", order=order_rev,
                palette="viridis", ax=axes[0], fliersize=3, linewidth=1.2)
    axes[0].set_yscale("log")
    axes[0].set_title(f"{CITY_LABEL} — Review Count by Star Class (log)", fontsize=14, fontweight="bold")
    axes[0].set_xlabel("Star Class")
    axes[0].set_ylabel("Review Count")
    axes[0].set_xticklabels([f"{int(s)}-star" for s in order_rev])

    # Bar chart of means
    rv_means = df_reviews.groupby("star_class")["review_count"].mean()
    rv_means.index = rv_means.index.map(lambda x: f"{int(x)}-star")
    bars = axes[1].bar(rv_means.index, rv_means.values, color=sns.color_palette("viridis", len(rv_means)),
                       edgecolor="white", linewidth=0.8)
    axes[1].set_title(f"{CITY_LABEL} — Average Review Count by Star Class", fontsize=14, fontweight="bold")
    axes[1].set_xlabel("Star Class")
    axes[1].set_ylabel("Average Review Count")
    for bar_obj, val in zip(bars, rv_means.values):
        axes[1].text(bar_obj.get_x() + bar_obj.get_width() / 2, bar_obj.get_height() + 100,
                     f"{val:,.0f}", ha="center", va="bottom", fontsize=10, fontweight="bold")

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_hotel_focused_reviews_by_star_class.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  -> Saved {CITY}_hotel_focused_reviews_by_star_class.png")

# ═══════════════════════════════════════════════════════════════════════════
# 7. PRICE DISTRIBUTION BY STAR CLASS (Violin + Strip)
# ═══════════════════════════════════════════════════════════════════════════
print("\n\n[7] PRICE DISTRIBUTION BY STAR CLASS (percentiles)")
print("-" * 40)

if len(df_rate) > 0:
    for star, row in rate_stats.iterrows():
        star_int = int(star)
        vals = sorted(df_rate[df_rate["star_class"] == star_int]["nightly_rate"].values)
        n = len(vals)
        p25 = vals[int(n * 0.25)] if n > 0 else 0
        p50 = vals[int(n * 0.50)] if n > 0 else 0
        p75 = vals[int(n * 0.75)] if n > 0 else 0
        print(f"  {star}-star: P25=${p25:.0f}  P50=${p50:.0f}  P75=${p75:.0f}  (n={n})")

    # --- Plot: Violin Plot ---
    fig, ax = plt.subplots(figsize=(10, 6))
    order_v = sorted(df_rate["star_class"].unique())
    sns.violinplot(data=df_rate, x="star_class", y="nightly_rate", order=order_v,
                   palette="viridis", inner="quartile", linewidth=1.2, ax=ax)
    ax.set_title(f"{CITY_LABEL} — Nightly Rate Distribution by Star Class (Violin)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Star Class")
    ax.set_ylabel("Nightly Rate ($)")
    ax.set_xticklabels([f"{int(s)}-star" for s in order_v])
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_hotel_focused_rate_violin.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  -> Saved {CITY}_hotel_focused_rate_violin.png")

# ═══════════════════════════════════════════════════════════════════════════
# 8. AMENITIES HEATMAP BY STAR CLASS
# ═══════════════════════════════════════════════════════════════════════════
print("\n\n[8] AMENITIES BY STAR CLASS")
print("-" * 40)

# Collect all amenities and star classes
all_amenities = set()
for h in hotels:
    amenities = (h.get("hotel_details") or {}).get("amenities", [])
    if amenities:
        all_amenities.update(amenities)

all_amenities = sorted(all_amenities)
star_classes = sorted([s for s in df["star_class"].dropna().unique()])

if len(star_classes) > 0 and len(all_amenities) > 0:
    # Build amenity presence matrix
    amenity_matrix = np.zeros((len(all_amenities), len(star_classes)))
    for i, amenity in enumerate(all_amenities):
        for j, star in enumerate(star_classes):
            subset = df[df["star_class"] == star]
            count = subset["amenities"].apply(lambda x: amenity in x if isinstance(x, list) else False).sum()
            amenity_matrix[i, j] = count / len(subset) * 100 if len(subset) > 0 else 0

    # Filter to amenities that appear in at least 10% of any star class
    mask = amenity_matrix.max(axis=1) >= 10
    filtered_amenities = [a for a, m in zip(all_amenities, mask) if m]
    filtered_matrix = amenity_matrix[mask]

    print("  Top amenities per star class:")
    for i, star in enumerate(star_classes):
        top_idx = filtered_matrix[:, i].argsort()[-5:][::-1]
        top = [(filtered_amenities[idx], filtered_matrix[idx, i]) for idx in top_idx]
        print(f"    {int(star)}-star: {', '.join(f'{a} ({v:.0f}%)' for a, v in top)}")

    # --- Plot: Amenities Heatmap ---
    fig, ax = plt.subplots(figsize=(12, max(8, len(filtered_amenities) * 0.35)))
    sns.heatmap(filtered_matrix, annot=True, fmt=".0f", cmap="YlOrRd",
                xticklabels=[f"{int(s)}-star" for s in star_classes],
                yticklabels=filtered_amenities, linewidths=0.5, linecolor="white",
                cbar_kws={"label": "% of Hotels"}, ax=ax)
    ax.set_title(f"{CITY_LABEL} — Amenity Availability by Star Class (%)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Star Class")
    ax.set_ylabel("Amenity")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_hotel_focused_amenities_heatmap.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  -> Saved {CITY}_hotel_focused_amenities_heatmap.png")

# ═══════════════════════════════════════════════════════════════════════════
# 9. INTERACTIVE PLOTLY: Rate vs Rating by Star Class
# ═══════════════════════════════════════════════════════════════════════════
df_interactive = df.dropna(subset=["nightly_rate", "rating", "star_class"]).copy()
if len(df_interactive) > 0:
    df_interactive["star_label"] = df_interactive["star_class"].apply(lambda x: f"{int(x)}-star")

    fig = px.scatter(
        df_interactive, x="nightly_rate", y="rating", color="star_label",
        hover_data=["name", "review_count"],
        title=f"{CITY_LABEL} — Nightly Rate vs Rating by Star Class",
        labels={"nightly_rate": "Nightly Rate ($)", "rating": "Rating", "star_label": "Star Class"},
        color_continuous_scale="viridis",
        template="plotly_white",
        opacity=0.7,
    )
    fig.update_layout(width=900, height=600)
    fig.write_html(os.path.join(OUTPUT_DIR, f"{CITY}_hotel_focused_rate_vs_rating_interactive.html"))
    print(f"  -> Saved {CITY}_hotel_focused_rate_vs_rating_interactive.html")

# ═══════════════════════════════════════════════════════════════════════════
# 10. SUMMARY DASHBOARD (Multi-panel)
# ═══════════════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# Panel 1: Star class distribution
star_counts_sorted = df["star_class"].value_counts(dropna=False).sort_index()
labels = [f"{int(s)}-star" if pd.notna(s) else "Unknown" for s in star_counts_sorted.index]
axes[0, 0].bar(labels, star_counts_sorted.values, color=sns.color_palette("viridis", len(labels)),
               edgecolor="white", linewidth=0.8)
axes[0, 0].set_title(f"{CITY_LABEL} — Star Class Distribution", fontsize=13, fontweight="bold")
axes[0, 0].set_ylabel("Count")
for i, v in enumerate(star_counts_sorted.values):
    axes[0, 0].text(i, v + 3, str(v), ha="center", fontweight="bold")

if len(df_rate) > 0:
    # Panel 2: Nightly rate box plot by star
    sns.boxplot(data=df_rate, x="star_class", y="nightly_rate",
                palette="viridis", ax=axes[0, 1], fliersize=3)
    axes[0, 1].set_title(f"{CITY_LABEL} — Rate Distribution by Star Class", fontsize=13, fontweight="bold")
    axes[0, 1].set_xlabel("Star Class")
    axes[0, 1].set_ylabel("Nightly Rate ($)")
    axes[0, 1].set_xticklabels([f"{int(s)}" for s in sorted(df_rate["star_class"].unique())])

# Panel 3: Missing values
miss_vals = [missing[f] for f in key_fields]
colors_m = ["#d7191c" if v > 0 else "#2c7bb6" for v in miss_vals]
axes[1, 0].barh(key_fields, miss_vals, color=colors_m, edgecolor="white")
axes[1, 0].set_title(f"{CITY_LABEL} — Missing Values", fontsize=13, fontweight="bold")
axes[1, 0].set_xlabel("Count")
axes[1, 0].invert_yaxis()
for i, v in enumerate(miss_vals):
    axes[1, 0].text(v + 1, i, str(v), va="center", fontweight="bold")

if len(df_rating) > 0:
    # Panel 4: Rating by star class
    sns.boxplot(data=df_rating, x="star_class", y="rating",
                palette="viridis", ax=axes[1, 1], fliersize=3)
    axes[1, 1].set_title(f"{CITY_LABEL} — Rating Distribution by Star Class", fontsize=13, fontweight="bold")
    axes[1, 1].set_xlabel("Star Class")
    axes[1, 1].set_ylabel("Rating")
    axes[1, 1].set_xticklabels([f"{int(s)}" for s in sorted(df_rating["star_class"].unique())])

fig.suptitle(f"{CITY_LABEL} Hotel EDA Dashboard", fontsize=16, fontweight="bold", y=1.01)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"{CITY}_hotel_focused_dashboard.png"), dpi=150, bbox_inches="tight")
plt.close()
print(f"  -> Saved {CITY}_hotel_focused_dashboard.png")

print(f"\n{'=' * 60}")
print(f"EDA Complete for {CITY_LABEL}! All visualizations saved to outputs/figures/")
