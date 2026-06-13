#!/usr/bin/env python
# coding: utf-8

# # Cairo Restaurants - Exploratory Data Analysis (EDA)
# ## TourMate AI - Data Intelligence Report
#
# **Date:** June 2026
# **Analyst:** TourMate AI Data Science Team
# **Dataset:** `data/cairo_places_filled (9).json` - 6,600+ places across Cairo, Egypt
#
# This notebook performs a **deep-dive EDA** focused exclusively on **Restaurants** in Cairo.
#
# ---

# ## 0. Environment Setup & Imports

# %%
import warnings
warnings.filterwarnings('ignore')

import os, json, math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns
from scipy import stats
from scipy.stats import zscore
from collections import Counter

# Plotly
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Folium
import folium
from folium.plugins import HeatMap, MarkerCluster

# Sklearn
from sklearn.preprocessing import MinMaxScaler
from utils import (
    extract_location, detect_outliers_iqr, derive_features,
    get_hashable_cols, compute_popularity, compute_recommendation_scores,
)

# Display settings
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', 100)
pd.set_option('display.width', 200)
pd.set_option('display.float_format', lambda x: f'{x:.3f}')

sns.set_theme(style='whitegrid', palette='muted', font_scale=1.1)
plt.rcParams['figure.dpi'] = 120
plt.rcParams['savefig.dpi'] = 150
plt.rcParams['figure.figsize'] = (14, 7)

os.makedirs('../outputs/figures', exist_ok=True)
os.makedirs('../outputs/reports', exist_ok=True)

print('[OK] All libraries loaded successfully.')

# ---
# ## 1. Data Loading & Initial Inspection

# %%
DATA_PATH = '../data/cairo_places_filled (9).json'

with open(DATA_PATH, 'r', encoding='utf-8') as f:
    raw_data = json.load(f)

df = pd.DataFrame(raw_data)

print(f'Dataset Shape: {df.shape[0]:,} rows x {df.shape[1]} columns')
print(f'Columns: {list(df.columns)}')
print(f'Memory Usage: {df.memory_usage(deep=True).sum() / 1024**2:.1f} MB')

# ---
# ## 2. Filter to Restaurants

# %%
df_rest = df[df['category'] == 'restaurant'].copy().reset_index(drop=True)

print(f'Filtered to Restaurants: {len(df_rest):,} places out of {len(df):,} total')
print(f'\nFull dataset category breakdown:')
print(df['category'].value_counts().to_string())

# %%
df_rest.head()

# %%
df_rest.info()

# %%
hashable_cols = get_hashable_cols(df_rest)

print(f'Hashable columns: {len(hashable_cols)} of {len(df_rest.columns)}')

# %%
df_rest[hashable_cols].describe(include='all')

# ---
# ## 3. Derive Features

# %%
df_rest = derive_features(df_rest)

print('Derived features created: photo_count, review_text_count, avg_review_length, has_hours, district, area')

# ---
# ## 4. Data Quality Assessment

# %%
print('=' * 70)
print(f'  DATA QUALITY: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

cat_hashable = [c for c in hashable_cols if c in df_rest.columns]

# Missing values
missing = pd.DataFrame({
    'column': df_rest[cat_hashable].columns,
    'missing_count': df_rest[cat_hashable].isnull().sum().values,
    'missing_pct': (df_rest[cat_hashable].isnull().sum().values / len(df_rest) * 100).round(2)
}).sort_values('missing_pct', ascending=False).reset_index(drop=True)

missing = missing[missing['missing_count'] > 0]

if len(missing) > 0:
    print(f'\nColumns with Missing Values (restaurant):')
    print(missing.to_string(index=False))
    fig, ax = plt.subplots(figsize=(14, 6))
    sns.heatmap(df_rest[cat_hashable].isnull(), cbar=True, yticklabels=False, cmap='YlOrRd', ax=ax)
    ax.set_title('Missing Values Heatmap - Restaurant', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig('../outputs/figures/restaurant_missing_values_heatmap.png', bbox_inches='tight')
    plt.show()
else:
    print('No missing values found for restaurant!')

# Duplicates
exact_dups = df_rest[cat_hashable].duplicated().sum()
print(f'\nExact duplicate rows: {exact_dups}')
if 'id' in df_rest.columns:
    id_dups = df_rest['id'].duplicated().sum()
    print(f'Duplicate id values: {id_dups}')

# Consistency checks
issues = []
if 'lat' in df_rest.columns and 'lon' in df_rest.columns:
    bad_coords = df_rest[(df_rest['lat'] < 28) | (df_rest['lat'] > 32) | (df_rest['lon'] < 29) | (df_rest['lon'] > 33)]
    if len(bad_coords) > 0:
        issues.append(f'[WARN] {len(bad_coords)} rows with coordinates outside Cairo area')
if 'rating' in df_rest.columns:
    bad_ratings = df_rest[(df_rest['rating'] < 0) | (df_rest['rating'] > 5)]
    if len(bad_ratings) > 0:
        issues.append(f'[WARN] {len(bad_ratings)} rows with rating outside [0, 5]')
if 'review_count' in df_rest.columns:
    neg_reviews = df_rest[df_rest['review_count'] < 0]
    if len(neg_reviews) > 0:
        issues.append(f'[WARN] {len(neg_reviews)} rows with negative review_count')

if issues:
    print('\n'.join(issues))
else:
    print('No data consistency issues found!')

# Quality report
quality_report = {
    'Total Records': len(df_rest),
    'Total Columns': len(df_rest.columns),
    'Exact Duplicates': int(exact_dups),
    'Columns with Missing Data': int((df_rest[cat_hashable].isnull().sum() > 0).sum()),
    'Total Missing Cells': int(df_rest[cat_hashable].isnull().sum().sum()),
    'Memory Usage (MB)': round(df_rest.memory_usage(deep=True).sum() / 1024**2, 1),
}
report_df = pd.DataFrame.from_dict(quality_report, orient='index', columns=['Value'])
print(f'\nDATA QUALITY REPORT - RESTAURANT')
print('=' * 45)
print(report_df.to_string())

# ---
# ## 5. Univariate Analysis - Numerical Variables

# %%
print('=' * 70)
print(f'  UNIVARIATE NUMERICAL: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

fig, axes = plt.subplots(1, 3, figsize=(18, 5))

# Histogram
axes[0].hist(df_rest['rating'].dropna(), bins=30, color='#4C72B0', edgecolor='white', alpha=0.8)
axes[0].axvline(df_rest['rating'].mean(), color='red', linestyle='--', label=f"Mean: {df_rest['rating'].mean():.2f}")
axes[0].axvline(df_rest['rating'].median(), color='green', linestyle='--', label=f"Median: {df_rest['rating'].median():.2f}")
axes[0].set_title('Rating Distribution', fontweight='bold')
axes[0].set_xlabel('Rating')
axes[0].set_ylabel('Count')
axes[0].legend()

# KDE
df_rest['rating'].dropna().plot(kind='kde', ax=axes[1], color='#4C72B0', linewidth=2)
axes[1].set_title('Rating KDE', fontweight='bold')
axes[1].set_xlabel('Rating')

# Boxplot
axes[2].boxplot(df_rest['rating'].dropna(), vert=True, patch_artist=True,
                boxprops=dict(facecolor='#4C72B0', alpha=0.6))
axes[2].set_title('Rating Boxplot', fontweight='bold')
axes[2].set_ylabel('Rating')

plt.suptitle('Rating Distribution - Restaurant', fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('../outputs/figures/restaurant_rating_distribution.png', bbox_inches='tight')
plt.show()

print(f"Rating Stats: mean={df_rest['rating'].mean():.2f}, median={df_rest['rating'].median():.2f}, "
      f"std={df_rest['rating'].std():.2f}, skew={df_rest['rating'].skew():.2f}")

# %%
print('=' * 70)
print(f'  REVIEW COUNT ANALYSIS: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

fig, axes = plt.subplots(1, 3, figsize=(18, 5))

reviews = df_rest['review_count'].dropna()
reviews_positive = reviews[reviews > 0]

axes[0].hist(reviews_positive, bins=50, color='#55A868', edgecolor='white', alpha=0.8, log=True)
axes[0].set_title('Review Count Distribution (Log Scale)', fontweight='bold')
axes[0].set_xlabel('Review Count')
axes[0].set_ylabel('Frequency (log)')

log_reviews = np.log10(reviews_positive)
log_reviews.plot(kind='kde', ax=axes[1], color='#55A868', linewidth=2)
axes[1].set_title('Log10(Review Count) KDE', fontweight='bold')
axes[1].set_xlabel('Log10(Review Count)')

axes[2].boxplot(reviews_positive, vert=True, patch_artist=True,
                boxprops=dict(facecolor='#55A868', alpha=0.6))
axes[2].set_title('Review Count Boxplot', fontweight='bold')
axes[2].set_ylabel('Review Count')

plt.suptitle('Review Count Distribution - Restaurant', fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('../outputs/figures/restaurant_review_count_distribution.png', bbox_inches='tight')
plt.show()

print(f"Review Stats: mean={reviews.mean():.0f}, median={reviews.median():.0f}, "
      f"max={reviews.max():,}, places with 0 reviews: {(reviews == 0).sum()}")

# ---
# ## 6. Univariate Analysis - Categorical / Subcategory Variables

# %%
print('=' * 70)
print(f'  SUBCATEGORY DISTRIBUTION: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

fig, axes = plt.subplots(1, 2, figsize=(18, 7))

# Category label distribution
if 'category_label' in df_rest.columns:
    label_counts = df_rest['category_label'].value_counts()
    label_counts.plot(kind='barh', ax=axes[0], color=sns.color_palette('viridis', len(label_counts)))
    axes[0].set_title('Category Labels - Restaurant', fontweight='bold')
    axes[0].set_xlabel('Count')
    for i, v in enumerate(label_counts.values):
        axes[0].text(v + 2, i, f'{v:,}', va='center', fontsize=10)

# Subtype distribution
if 'subtype' in df_rest.columns:
    subtype_counts = df_rest['subtype'].dropna().value_counts()
    if len(subtype_counts) > 0:
        top_n = 10
        top_subtypes = subtype_counts.head(top_n)
        other = subtype_counts[top_n:].sum() if len(subtype_counts) > top_n else 0
        pie_data = pd.concat([top_subtypes, pd.Series({'Other': other})]) if other > 0 else top_subtypes
        colors = sns.color_palette('viridis', len(pie_data))
        axes[1].pie(pie_data, labels=pie_data.index, autopct='%1.1f%%',
                    colors=colors, startangle=90, pctdistance=0.85)
        axes[1].set_title('Subtype Proportions - Restaurant', fontweight='bold')

plt.suptitle('Categorical Distribution - Restaurant', fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('../outputs/figures/restaurant_category_distribution.png', bbox_inches='tight')
plt.show()

print('\nCategory Label Counts (restaurant):')
if 'category_label' in df_rest.columns:
    for label, count in df_rest['category_label'].value_counts().items():
        print(f'  {label:40s} {count:>5,} ({count/len(df_rest)*100:.1f}%)')

if 'subtype' in df_rest.columns:
    print('\nSubtype Counts (restaurant):')
    for st, count in df_rest['subtype'].value_counts().head(15).items():
        print(f'  {str(st):40s} {count:>5,} ({count/len(df_rest)*100:.1f}%)')

# %%
# District distribution
print('=' * 70)
print(f'  DISTRICT DISTRIBUTION: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

dist_counts = df_rest['district'].value_counts().head(15)

fig, ax = plt.subplots(figsize=(14, 7))
dist_counts.plot(kind='barh', ax=ax, color=sns.color_palette('rocket', len(dist_counts)))
ax.set_title('Top 15 Districts - Restaurant', fontweight='bold')
ax.set_xlabel('Count')
for i, v in enumerate(dist_counts.values):
    ax.text(v + 2, i, f'{v:,}', va='center', fontsize=10)
plt.tight_layout()
plt.savefig('../outputs/figures/restaurant_district_distribution.png', bbox_inches='tight')
plt.show()

# ---
# ## 7. Geographical Analysis

# %%
cairo_center = [df_rest['lat'].median(), df_rest['lon'].median()]

print('=' * 70)
print(f'  GEOGRAPHICAL ANALYSIS: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

# Interactive Folium map
sample_size = min(2000, len(df_rest))
df_sample = df_rest.sample(n=sample_size, random_state=42)

m = folium.Map(location=cairo_center, zoom_start=12, tiles='CartoDB positron')
marker_cluster = MarkerCluster().add_to(m)

for _, row in df_sample.iterrows():
    folium.CircleMarker(
        location=[row['lat'], row['lon']],
        radius=4, color='#4C72B0', fill=True, fill_opacity=0.7,
        popup=folium.Popup(
            f"<b>{row['name']}</b><br>"
            f"Category: Restaurant<br>"
            f"Rating: {row.get('rating', 'N/A')}<br>"
            f"Reviews: {row.get('review_count', 0):,}",
            max_width=250
        ),
    ).add_to(marker_cluster)

m.save('../outputs/figures/restaurant_places_map.html')
print(f'Interactive map saved: outputs/figures/restaurant_places_map.html ({sample_size:,} places)')

# Heatmap
m_heat = folium.Map(location=cairo_center, zoom_start=12, tiles='CartoDB positron')
heat_data = df_rest[['lat', 'lon']].dropna().values.tolist()
HeatMap(heat_data, radius=15, blur=20, max_zoom=13).add_to(m_heat)
m_heat.save('../outputs/figures/restaurant_density_heatmap.html')
print('Density heatmap saved: outputs/figures/restaurant_density_heatmap.html')

# High-rated places map
high_rated = df_rest[df_rest['rating'] >= 4.5]
if len(high_rated) > 0:
    high_rated_sample = high_rated.sample(min(1000, len(high_rated)), random_state=42)
    m_hr = folium.Map(location=cairo_center, zoom_start=12, tiles='CartoDB positron')
    for _, row in high_rated_sample.iterrows():
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=5, color='gold', fill=True, fill_opacity=0.8,
            popup=f"<b>{row['name']}</b><br>Rating: {row['rating']}<br>Reviews: {row.get('review_count', 0):,}",
        ).add_to(m_hr)
    m_hr.save('../outputs/figures/restaurant_high_rated_map.html')
    print(f'High-rated places map saved ({len(high_rated_sample):,} places)')

# Static scatter map with Plotly
fig = px.scatter_mapbox(
    df_rest.sample(min(2000, len(df_rest)), random_state=42),
    lat='lat', lon='lon',
    size='review_count', size_max=15,
    hover_name='name',
    hover_data={'rating': True, 'review_count': True},
    mapbox_style='carto-positron',
    center={'lat': cairo_center[0], 'lon': cairo_center[1]},
    zoom=11, title='Restaurants - Geographic Distribution', height=600,
)
fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
fig.write_html('../outputs/figures/restaurant_plotly_map.html')
print('Plotly map saved: outputs/figures/restaurant_plotly_map.html')

# ---
# ## 8. Rating & Review Analysis

# %%
print('=' * 70)
print(f'  RATING & REVIEW ANALYSIS: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

# Top reviewed
top_reviewed = df_rest.nlargest(10, 'review_count')[['name', 'rating', 'review_count', 'address']]
print('\nTop 10 Most Reviewed Restaurants:')
print(top_reviewed.to_string(index=False))

# Rating vs Review Count scatter
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

axes[0].scatter(df_rest['rating'], df_rest['review_count'], alpha=0.3, s=10, c=df_rest['rating'], cmap='RdYlGn')
axes[0].set_xlabel('Rating')
axes[0].set_ylabel('Review Count')
axes[0].set_title('Rating vs Review Count - Restaurant', fontweight='bold')
axes[0].set_yscale('log')

rating_bucket = pd.cut(df_rest['rating'], bins=[0, 2, 3, 3.5, 4, 4.5, 5],
                       labels=['<2', '2-3', '3-3.5', '3.5-4', '4-4.5', '4-5'])
valid_mask = rating_bucket.notna()
if valid_mask.sum() > 0:
    sns.violinplot(x=rating_bucket[valid_mask], y=df_rest.loc[valid_mask, 'review_count'], ax=axes[1],
                   palette='RdYlGn', inner='quartile')
axes[1].set_title('Review Count by Rating Bucket - Restaurant', fontweight='bold')
axes[1].set_yscale('log')

plt.tight_layout()
plt.savefig('../outputs/figures/restaurant_rating_vs_reviews.png', bbox_inches='tight')
plt.show()

print(f"\nRating Stats: mean={df_rest['rating'].mean():.2f}, median={df_rest['rating'].median():.2f}, "
      f"std={df_rest['rating'].std():.2f}")
print(f"Review Stats: mean={df_rest['review_count'].mean():.0f}, median={df_rest['review_count'].median():.0f}, "
      f"max={df_rest['review_count'].max():,}")

# ---
# ## 9. Popularity Analysis

# %%
print('=' * 70)
print(f'  POPULARITY ANALYSIS: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

df_rest = compute_popularity(df_rest)

print(f"Popularity score computed (0-1 scale)")
print(f"   Mean: {df_rest['popularity_score'].mean():.3f}")
print(f"   Std:  {df_rest['popularity_score'].std():.3f}")

# Top popular
top_popular = df_rest.nlargest(10, 'popularity_score')[['name', 'rating', 'review_count', 'popularity_score']]
print('\nTop 10 Most Popular Restaurants:')
print(top_popular.to_string(index=False))

# District popularity
dist_pop = df_rest.groupby('district').agg(
    avg_popularity=('popularity_score', 'mean'),
    count=('name', 'count'),
    avg_rating=('rating', 'mean')
).sort_values('avg_popularity', ascending=False).head(15)

fig, ax = plt.subplots(figsize=(12, 7))
dist_pop['avg_popularity'].plot(kind='barh', ax=ax, color=sns.color_palette('YlOrRd', len(dist_pop)))
ax.set_title('Top 15 Districts by Avg Popularity - Restaurant', fontweight='bold')
ax.set_xlabel('Avg Popularity Score')
for i, v in enumerate(dist_pop['avg_popularity'].values):
    ax.text(v + 0.005, i, f'{v:.3f}', va='center', fontsize=10)
plt.tight_layout()
plt.savefig('../outputs/figures/restaurant_district_popularity.png', bbox_inches='tight')
plt.show()

# ---
# ## 10. Location Intelligence

# %%
print('=' * 70)
print(f'  LOCATION INTELLIGENCE: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

area_stats = df_rest.groupby('area').agg(
    num_places=('name', 'count'),
    avg_rating=('rating', 'mean'),
    total_reviews=('review_count', 'sum'),
    avg_popularity=('popularity_score', 'mean')
).sort_values('num_places', ascending=False)

significant_areas = area_stats[area_stats['num_places'] >= 10].head(15)
print(f'\nSignificant Areas for Restaurants (>=10 places):')
print(significant_areas.round(2).to_string())

if len(significant_areas) >= 2:
    fig, axes = plt.subplots(2, 2, figsize=(18, 14))

    significant_areas['num_places'].plot(kind='barh', ax=axes[0, 0], color='#4C72B0')
    axes[0, 0].set_title('Number of Places', fontweight='bold')

    significant_areas.sort_values('avg_rating').plot(kind='barh', y='avg_rating', ax=axes[0, 1],
                                                      color='#55A868', legend=False)
    axes[0, 1].set_title('Average Rating', fontweight='bold')

    significant_areas['total_reviews'].plot(kind='barh', ax=axes[1, 0], color='#C44E52')
    axes[1, 0].set_title('Total Reviews', fontweight='bold')
    axes[1, 0].set_xscale('log')

    significant_areas.sort_values('avg_popularity').plot(kind='barh', y='avg_popularity', ax=axes[1, 1],
                                                          color='#8172B2', legend=False)
    axes[1, 1].set_title('Average Popularity Score', fontweight='bold')

    plt.suptitle('Area Comparison - Restaurants', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('../outputs/figures/restaurant_area_comparison.png', bbox_inches='tight')
    plt.show()

# ---
# ## 11. Correlation Analysis

# %%
print('=' * 70)
print(f'  CORRELATION ANALYSIS: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

corr_cols = ['rating', 'review_count', 'photo_count', 'review_text_count',
             'avg_review_length', 'popularity_score', 'has_hours']
corr_cols = [c for c in corr_cols if c in df_rest.columns]

corr_matrix = df_rest[corr_cols].corr()

fig, ax = plt.subplots(figsize=(12, 10))
mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
sns.heatmap(corr_matrix, mask=mask, annot=True, fmt='.3f', cmap='RdBu_r',
            center=0, vmin=-1, vmax=1, ax=ax, linewidths=0.5,
            square=True, cbar_kws={'shrink': 0.8})
ax.set_title('Correlation Matrix - Restaurant', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig('../outputs/figures/restaurant_correlation_heatmap.png', bbox_inches='tight')
plt.show()

print('Key Correlations (restaurant):')
for pair in [('rating', 'review_count'), ('rating', 'photo_count'), ('review_count', 'photo_count')]:
    if pair[0] in df_rest.columns and pair[1] in df_rest.columns:
        corr = df_rest[pair[0]].corr(df_rest[pair[1]])
        print(f"  {pair[0]:20s} x {pair[1]:20s}: r = {corr:+.3f}")

# ---
# ## 12. Outlier Detection

# %%
print('=' * 70)
print(f'  OUTLIER DETECTION: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

print('IQR Outlier Detection (restaurant):')
detect_outliers_iqr(df_rest['review_count'], 'review_count')
detect_outliers_iqr(df_rest['rating'], 'rating')

# Z-score
df_rest['review_zscore'] = zscore(df_rest['review_count'].fillna(0))
z_outliers = df_rest[df_rest['review_zscore'].abs() > 3]
print(f"Z-Score outliers (|z| > 3) in review_count: {len(z_outliers):,}")
print(f"   Max z-score: {df_rest['review_zscore'].max():.2f}")
print(f"   Min z-score: {df_rest['review_zscore'].min():.2f}")

fig, axes = plt.subplots(1, 2, figsize=(16, 6))

Q1, Q3 = df_rest['review_count'].quantile(0.25), df_rest['review_count'].quantile(0.75)
IQR = Q3 - Q1
lower, upper = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR

axes[0].boxplot(df_rest['review_count'].dropna(), vert=True, patch_artist=True,
                boxprops=dict(facecolor='#4C72B0', alpha=0.6))
axes[0].axhline(upper, color='red', linestyle='--', label=f'Upper fence: {upper:,.0f}')
axes[0].axhline(lower, color='red', linestyle='--', label=f'Lower fence: {lower:,.0f}')
axes[0].set_title('Review Count - Outliers - Restaurant', fontweight='bold')
axes[0].legend()

axes[1].hist(df_rest['review_zscore'].dropna(), bins=50, color='#55A868', edgecolor='white', alpha=0.8)
axes[1].axvline(3, color='red', linestyle='--', label='z = 3')
axes[1].axvline(-3, color='red', linestyle='--', label='z = -3')
axes[1].set_title('Review Count - Z-Score Distribution - Restaurant', fontweight='bold')
axes[1].set_xlabel('Z-Score')
axes[1].legend()

plt.tight_layout()
plt.savefig('../outputs/figures/restaurant_outlier_detection.png', bbox_inches='tight')
plt.show()

df_rest.drop(columns=['review_zscore'], inplace=True)

# ---
# ## 13. Tourism Insights

# %%
print('=' * 70)
print(f'  TOURISM INSIGHTS: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

print('\nRating Distribution (restaurant):')
for rating, count in df_rest['rating'].value_counts().head(5).items():
    print(f"  Rating {rating}: {count:,} places ({count/len(df_rest)*100:.1f}%)")

print('\nHighest-Engagement Districts (restaurant):')
top_areas = df_rest.groupby('district')['review_count'].sum().sort_values(ascending=False).head(5)
for area, reviews in top_areas.items():
    print(f"  {area}: {reviews:,.0f} total reviews")

hidden_gems = df_rest[(df_rest['rating'] >= 4.5) & (df_rest['review_count'] < df_rest['review_count'].quantile(0.25))]
print(f"\nHidden Gems (rating >= 4.5, low reviews): {len(hidden_gems):,} restaurants")
if len(hidden_gems) > 0:
    print('Top hidden gems:')
    for _, row in hidden_gems.nlargest(5, 'rating').iterrows():
        print(f"  Rating: {row['rating']:.1f} - {row['name']} ({row['review_count']:,} reviews)")

# Recommendation candidates
print('\nTop Recommendation Candidates (restaurant):')
top_recs = df_rest.nlargest(10, 'rating')[['name', 'rating', 'review_count', 'popularity_score']]
print(top_recs.to_string(index=False))

# ---
# ## 14. Recommendation-Oriented Features

# %%
print('=' * 70)
print(f'  RECOMMENDATION SCORES: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

df_rest = compute_recommendation_scores(df_rest)

score_cols = ['family_friendly_score', 'budget_score', 'luxury_score']
print('\nRecommendation Feature Scores (restaurant):')
print(df_rest[score_cols].describe().round(3).to_string())

# Top recommendations by profile
print('\nTop 5 Recommendations by Profile (restaurant):')
profiles = {
    'Family Trip': 'family_friendly_score',
    'Budget Traveler': 'budget_score',
    'Luxury Seeker': 'luxury_score',
}
for profile, score_col in profiles.items():
    top = df_rest.nlargest(5, score_col)[['name', 'rating', 'review_count', score_col]]
    print(f"\n  {profile}:")
    for _, row in top.iterrows():
        print(f"    Rating: {row['rating']:.1f} | {row['name'][:45]:45s} | score={row[score_col]:.3f}")

# ---
# ## 15. Restaurant-Specific Deep Dive

# ---
# ### 15a. Cuisine Type Analysis

# %%
print('=' * 70)
print(f'  CUISINE TYPE ANALYSIS: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

cuisine_data = df_rest[df_rest['cuisine_type'].notna()].copy()
print(f'Restaurants with cuisine data: {len(cuisine_data):,} / {len(df_rest):,} ({len(cuisine_data)/len(df_rest)*100:.1f}%)')

if len(cuisine_data) > 0:
    cuisine_counts = cuisine_data['cuisine_type'].value_counts()
    print(f'\nCuisine Type Distribution (top 20):')
    for cuisine, count in cuisine_counts.head(20).items():
        print(f'  {cuisine:40s} {count:>5,} ({count/len(cuisine_data)*100:.1f}%)')

    fig, axes = plt.subplots(1, 2, figsize=(18, 10))

    top_cuisines = cuisine_counts.head(15)
    top_cuisines.plot(kind='barh', ax=axes[0], color=sns.color_palette('Set2', len(top_cuisines)))
    axes[0].set_title('Top 15 Cuisine Types', fontweight='bold')
    axes[0].set_xlabel('Count')
    axes[0].invert_yaxis()

    # Rating by cuisine
    cuisine_rating = cuisine_data.groupby('cuisine_type').agg(
        avg_rating=('rating', 'mean'),
        count=('name', 'count')
    ).sort_values('count', ascending=False).head(15)

    cuisine_rating.sort_values('avg_rating').plot(kind='barh', y='avg_rating', ax=axes[1],
                                                   color='#55A868', legend=False)
    axes[1].set_title('Avg Rating by Cuisine Type', fontweight='bold')
    axes[1].set_xlabel('Avg Rating')

    plt.suptitle('Cuisine Type Analysis - Restaurants', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('../outputs/figures/restaurant_cuisine_type_analysis.png', bbox_inches='tight')
    plt.show()

    # Cuisine stats
    print('\nCuisine Stats (top 10 by count):')
    top_cuisine_stats = cuisine_data[cuisine_data['cuisine_type'].isin(cuisine_counts.head(10).index)]
    print(top_cuisine_stats.groupby('cuisine_type')[['rating', 'review_count']].agg(['mean', 'median', 'count']).round(2).to_string())

# ---
# ### 15b. Price Level Analysis

# %%
print('=' * 70)
print(f'  PRICE LEVEL ANALYSIS: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

price_data = df_rest[df_rest['price_level'].notna()].copy()
print(f'Restaurants with price level data: {len(price_data):,} / {len(df_rest):,} ({len(price_data)/len(df_rest)*100:.1f}%)')

if len(price_data) > 0:
    price_counts = price_data['price_level'].value_counts().sort_index()
    print(f'\nPrice Level Distribution:')
    for level, count in price_counts.items():
        print(f'  {level}: {count:,} ({count/len(price_data)*100:.1f}%)')

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    price_counts.plot(kind='bar', ax=axes[0], color=sns.color_palette('YlOrRd', len(price_counts)))
    axes[0].set_title('Price Level Distribution', fontweight='bold')
    axes[0].set_xlabel('Price Level')
    axes[0].set_ylabel('Count')

    # Rating by price level
    price_rating = price_data.groupby('price_level')['rating'].agg(['mean', 'median', 'count'])
    price_rating['mean'].plot(kind='bar', ax=axes[1], color='#4C72B0', alpha=0.8)
    axes[1].set_title('Avg Rating by Price Level', fontweight='bold')
    axes[1].set_xlabel('Price Level')
    axes[1].set_ylabel('Rating')

    plt.suptitle('Price Level Analysis - Restaurants', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('../outputs/figures/restaurant_price_level_analysis.png', bbox_inches='tight')
    plt.show()

    print('\nPrice Level Stats:')
    print(price_data.groupby('price_level')[['rating', 'review_count']].agg(['mean', 'median', 'count']).round(2).to_string())

# ---
# ### 15c. Cost Per Person Analysis

# %%
print('=' * 70)
print(f'  COST PER PERSON ANALYSIS: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

cost_data = df_rest[df_rest['avg_cost_per_person'].notna()].copy()
print(f'Restaurants with cost data: {len(cost_data):,} / {len(df_rest):,} ({len(cost_data)/len(df_rest)*100:.1f}%)')

if len(cost_data) > 0:
    # Parse cost (remove $ and convert to float)
    cost_data['cost_numeric'] = cost_data['avg_cost_per_person'].str.replace('$', '', regex=False).str.replace(',', '', regex=False).astype(float)

    print(f'\nCost Per Person Stats (parsed):')
    print(f"  Mean: ${cost_data['cost_numeric'].mean():.2f}")
    print(f"  Median: ${cost_data['cost_numeric'].median():.2f}")
    print(f"  Min: ${cost_data['cost_numeric'].min():.2f}")
    print(f"  Max: ${cost_data['cost_numeric'].max():.2f}")

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Distribution
    axes[0].hist(cost_data['cost_numeric'].dropna(), bins=40, color='#E6A817', edgecolor='white', alpha=0.8)
    axes[0].axvline(cost_data['cost_numeric'].mean(), color='red', linestyle='--', label=f"Mean: ${cost_data['cost_numeric'].mean():.2f}")
    axes[0].axvline(cost_data['cost_numeric'].median(), color='green', linestyle='--', label=f"Median: ${cost_data['cost_numeric'].median():.2f}")
    axes[0].set_title('Cost Per Person Distribution', fontweight='bold')
    axes[0].set_xlabel('Cost ($)')
    axes[0].set_ylabel('Count')
    axes[0].legend()

    # Cost vs Rating
    axes[1].scatter(cost_data['cost_numeric'], cost_data['rating'], alpha=0.3, s=10, c='#4C72B0')
    axes[1].set_xlabel('Cost Per Person ($)')
    axes[1].set_ylabel('Rating')
    axes[1].set_title('Cost vs Rating', fontweight='bold')

    # Cost by cuisine (top cuisines)
    top_cuisines = cost_data['cuisine_type'].value_counts().head(8).index
    cost_by_cuisine = cost_data[cost_data['cuisine_type'].isin(top_cuisines)].groupby('cuisine_type')['cost_numeric'].median().sort_values(ascending=True)
    cost_by_cuisine.plot(kind='barh', ax=axes[2], color='#E6A817', alpha=0.8)
    axes[2].set_title('Median Cost by Cuisine Type', fontweight='bold')
    axes[2].set_xlabel('Median Cost ($)')

    plt.suptitle('Cost Per Person Analysis - Restaurants', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('../outputs/figures/restaurant_cost_analysis.png', bbox_inches='tight')
    plt.show()

    # Budget tiers
    cost_data['budget_tier'] = pd.cut(cost_data['cost_numeric'],
                                       bins=[0, 5, 10, 20, 50, float('inf')],
                                       labels=['Street Food (<$5)', 'Cheap Eats ($5-10)', 'Mid-Range ($10-20)', 'Premium ($20-50)', 'Fine Dining ($50+)'])
    print('\nBudget Tier Distribution:')
    tier_counts = cost_data['budget_tier'].value_counts().sort_index()
    for tier, count in tier_counts.items():
        print(f'  {tier}: {count:,} ({count/len(cost_data)*100:.1f}%)')

    print('\nBudget Tier Stats:')
    print(cost_data.groupby('budget_tier')[['rating', 'review_count', 'cost_numeric']].agg(['mean', 'median', 'count']).round(2).to_string())

# ---
# ### 15d. Operating Hours Analysis

# %%
print('=' * 70)
print(f'  OPERATING HOURS ANALYSIS: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

hours_data = df_rest[df_rest['hours'].notna() & df_rest['hours'].apply(lambda x: isinstance(x, dict) and len(x) > 0)].copy()
print(f'Restaurants with hours data: {len(hours_data):,} / {len(df_rest):,} ({len(hours_data)/len(df_rest)*100:.1f}%)')

if len(hours_data) > 0:
    # Analyze opening/closing times for each day
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    opening_hours = []
    closing_hours = []

    for _, row in hours_data.iterrows():
        for day in days:
            if day in row['hours'] and isinstance(row['hours'][day], str):
                try:
                    time_str = row['hours'][day]
                    parts = time_str.split(' – ')
                    if len(parts) == 2:
                        open_time = parts[0].strip()
                        close_time = parts[1].strip()
                        # Parse hours
                        open_h = int(open_time.split(':')[0])
                        close_h = int(close_time.split(':')[0])
                        if close_h == 0:
                            close_h = 24
                        opening_hours.append(open_h)
                        closing_hours.append(close_h)
                except (ValueError, IndexError):
                    pass

    if opening_hours:
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))

        axes[0].hist(opening_hours, bins=24, color='#4C72B0', edgecolor='white', alpha=0.8, range=(0, 24))
        axes[0].set_title('Opening Time Distribution', fontweight='bold')
        axes[0].set_xlabel('Hour of Day')
        axes[0].set_ylabel('Frequency')

        axes[1].hist(closing_hours, bins=24, color='#C44E52', edgecolor='white', alpha=0.8, range=(0, 28))
        axes[1].set_title('Closing Time Distribution', fontweight='bold')
        axes[1].set_xlabel('Hour of Day')
        axes[1].set_ylabel('Frequency')

        plt.suptitle('Operating Hours Analysis - Restaurants', fontsize=15, fontweight='bold', y=1.02)
        plt.tight_layout()
        plt.savefig('../outputs/figures/restaurant_operating_hours.png', bbox_inches='tight')
        plt.show()

        print(f'Most common opening hour: {Counter(opening_hours).most_common(3)}')
        print(f'Most common closing hour: {Counter(closing_hours).most_common(3)}')
        avg_hours = np.mean([c - o if c > o else c + 24 - o for o, c in zip(opening_hours, closing_hours)])
        print(f'Average operating hours: {avg_hours:.1f} hours')

# ---
# ### 15e. Cuisine x Price Cross-Analysis

# %%
print('=' * 70)
print(f'  CUISINE x PRICE CROSS-ANALYSIS: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

cross_data = df_rest[df_rest['cuisine_type'].notna() & df_rest['price_level'].notna()].copy()
print(f'Restaurants with both cuisine & price data: {len(cross_data):,} / {len(df_rest):,} ({len(cross_data)/len(df_rest)*100:.1f}%)')

if len(cross_data) > 0:
    cross_ct = pd.crosstab(cross_data['cuisine_type'], cross_data['price_level'])

    # Top cuisines only
    top_cuisines = cross_ct.sum(axis=1).sort_values(ascending=False).head(10).index
    cross_top = cross_ct.loc[top_cuisines]

    fig, ax = plt.subplots(figsize=(14, 8))
    sns.heatmap(cross_top, annot=True, fmt='d', cmap='YlOrRd', ax=ax, linewidths=0.5)
    ax.set_title('Cuisine Type x Price Level - Restaurant Count', fontsize=14, fontweight='bold')
    ax.set_xlabel('Price Level')
    ax.set_ylabel('Cuisine Type')
    plt.tight_layout()
    plt.savefig('../outputs/figures/restaurant_cuisine_price_heatmap.png', bbox_inches='tight')
    plt.show()

    print('\nCuisine x Price Crosstab (top 10 cuisines):')
    print(cross_top.to_string())

# ---
# ## 16. Interactive Dashboard Elements

# %%
print('=' * 70)
print(f'  INTERACTIVE DASHBOARD: RESTAURANT ({len(df_rest):,} places)')
print('=' * 70)

# Rating distribution box plot
fig = px.box(
    df_rest, y='rating',
    title='Restaurant - Rating Distribution (Interactive)',
    hover_data=['name', 'review_count'], height=500
)
fig.write_html('../outputs/figures/restaurant_interactive_rating_boxplot.html')

# Scatter by cuisine type
if 'cuisine_type' in df_rest.columns and df_rest['cuisine_type'].notna().sum() > 0:
    fig = px.scatter(
        df_rest.sample(min(2000, len(df_rest)), random_state=42),
        x='cuisine_type', y='rating', color='district',
        size='review_count', size_max=20, hover_name='name',
        hover_data={'cuisine_type': True, 'rating': True, 'review_count': True, 'district': True},
        title='Restaurants - Cuisine x Rating x District', height=600,
    )
    fig.update_layout(xaxis_tickangle=-45)
    fig.write_html('../outputs/figures/restaurant_interactive_cuisine_rating.html')
    print('Cuisine scatter saved: restaurant_interactive_cuisine_rating.html')

# Price level interactive chart
if 'price_level' in df_rest.columns and df_rest['price_level'].notna().sum() > 0:
    fig = px.box(
        df_rest[df_rest['price_level'].notna()],
        x='price_level', y='rating',
        title='Restaurants - Rating by Price Level (Interactive)',
        hover_data=['name', 'review_count', 'avg_cost_per_person'], height=500
    )
    fig.write_html('../outputs/figures/restaurant_interactive_price_rating.html')
    print('Price level interactive chart saved: restaurant_interactive_price_rating.html')

print('Dashboard saved for restaurant')

# ---
# ## 17. Automated Report Generation

# %%
report_data = {
    'Total Restaurants': f"{len(df_rest):,}",
    'Avg Rating': f"{df_rest['rating'].mean():.2f}",
    'Median Review Count': f"{df_rest['review_count'].median():,.0f}",
    'Total Reviews': f"{df_rest['review_count'].sum():,.0f}",
    'Unique Districts': f"{df_rest['district'].nunique():,}",
    'Unique Cuisine Types': f"{df_rest['cuisine_type'].nunique() if 'cuisine_type' in df_rest.columns else 0}",
    'Hidden Gems': len(df_rest[(df_rest['rating'] >= 4.5) & (df_rest['review_count'] < df_rest['review_count'].quantile(0.25))]),
    'With Price Level': len(df_rest[df_rest['price_level'].notna()]),
}

html_report = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Cairo Restaurants EDA Report - TourMate AI</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; background: #f8f9fa; color: #333; }}
        .header {{ background: linear-gradient(135deg, #1b5e20, #2e7d32); color: white; padding: 40px; border-radius: 12px; margin-bottom: 30px; }}
        .header h1 {{ margin: 0; font-size: 2.2em; }}
        .header p {{ margin: 8px 0 0; opacity: 0.9; font-size: 1.1em; }}
        .section {{ background: white; border-radius: 10px; padding: 25px 30px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .section h2 {{ color: #1b5e20; border-bottom: 2px solid #e8f5e9; padding-bottom: 8px; }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .kpi {{ background: #e8f5e9; border-radius: 8px; padding: 20px; text-align: center; }}
        .kpi .value {{ font-size: 2em; font-weight: bold; color: #1b5e20; }}
        .kpi .label {{ font-size: 0.9em; color: #555; margin-top: 5px; }}
        .insight {{ background: #fff3e0; border-left: 4px solid #ff9800; padding: 12px 18px; margin: 10px 0; border-radius: 0 8px 8px 0; }}
        .footer {{ text-align: center; color: #999; padding: 20px; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Cairo Restaurants - EDA Report</h1>
        <p>TourMate AI - Data Intelligence - Generated June 2026</p>
    </div>
    <div class="section">
        <h2>Executive Summary</h2>
        <div class="kpi-grid">
            <div class="kpi"><div class="value">{report_data['Total Restaurants']}</div><div class="label">Total Restaurants</div></div>
            <div class="kpi"><div class="value">{report_data['Avg Rating']}</div><div class="label">Avg Rating</div></div>
            <div class="kpi"><div class="value">{report_data['Total Reviews']}</div><div class="label">Total Reviews</div></div>
            <div class="kpi"><div class="value">{report_data['Unique Districts']}</div><div class="label">Districts</div></div>
            <div class="kpi"><div class="value">{report_data['Unique Cuisine Types']}</div><div class="label">Cuisine Types</div></div>
            <div class="kpi"><div class="value">{report_data['Hidden Gems']}</div><div class="label">Hidden Gems</div></div>
            <div class="kpi"><div class="value">{report_data['With Price Level']}</div><div class="label">With Price Level</div></div>
        </div>
    </div>
    <div class="section">
        <h2>Key Findings</h2>
        <div class="insight"><b>Cuisine Diversity:</b> Comprehensive analysis of {report_data['Unique Cuisine Types']} cuisine types across Cairo's restaurant scene.</div>
        <div class="insight"><b>Price Tiers:</b> Cost analysis reveals budget-friendly to fine dining options with rating correlations.</div>
        <div class="insight"><b>Operating Hours:</b> Patterns in restaurant opening/closing times across the city.</div>
        <div class="insight"><b>Cuisine x Price:</b> Cross-analysis showing which cuisines dominate each price tier.</div>
    </div>
    <div class="section">
        <h2>Recommendations for TourMate AI</h2>
        <ul>
            <li>Use cuisine type preferences for personalized restaurant recommendations.</li>
            <li>Leverage price level and cost data for budget-aware suggestions.</li>
            <li>Highlight hidden gems with high ratings but low review counts.</li>
            <li>Use operating hours data for time-sensitive dining recommendations.</li>
        </ul>
    </div>
    <div class="footer">
        <p>Generated by TourMate AI Data Science Team - June 2026</p>
    </div>
</body>
</html>
"""

with open('../outputs/reports/restaurants_eda_report.html', 'w', encoding='utf-8') as f:
    f.write(html_report)

print('HTML report saved to outputs/reports/restaurants_eda_report.html')

# ---
# ## 18. Notebook Summary

# %%
print('=' * 70)
print('CAIRO RESTAURANTS EDA - COMPLETED SUCCESSFULLY')
print('=' * 70)
print(f'\nTotal Restaurants Analyzed: {len(df_rest):,}')
print(f'Avg Rating: {df_rest["rating"].mean():.2f} | Avg Reviews: {df_rest["review_count"].mean():.0f}')
if 'cuisine_type' in df_rest.columns:
    print(f'Cuisine Types: {df_rest["cuisine_type"].nunique()}')
print(f'\nOutput Files:')
print(f'  outputs/figures/ - restaurant-specific visualizations saved')
print(f'  outputs/reports/ - HTML report')
print('\nAll analyses complete. Notebook ready for review.')

# ---
# *This notebook was generated by TourMate AI Data Science Team - June 2026*
# *Restaurants-focused EDA for Cairo, Egypt*
