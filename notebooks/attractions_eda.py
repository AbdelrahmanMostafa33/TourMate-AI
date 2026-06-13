#!/usr/bin/env python
# coding: utf-8

# # Cairo Attractions - Exploratory Data Analysis (EDA)
# ## TourMate AI - Data Intelligence Report
#
# **Date:** June 2026
# **Analyst:** TourMate AI Data Science Team
# **Dataset:** `data/cairo_places_filled (11).json` - 6,600+ places across Cairo, Egypt
#
# This notebook performs a **deep-dive EDA** focused exclusively on **Attractions** in Cairo.
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
DATA_PATH = '../data/cairo_places_filled (11).json'

with open(DATA_PATH, 'r', encoding='utf-8') as f:
    raw_data = json.load(f)

df = pd.DataFrame(raw_data)

print(f'Dataset Shape: {df.shape[0]:,} rows x {df.shape[1]} columns')
print(f'Columns: {list(df.columns)}')
print(f'Memory Usage: {df.memory_usage(deep=True).sum() / 1024**2:.1f} MB')

# ---
# ## 2. Filter to Attractions

# %%
df_attr = df[df['category'] == 'attractions'].copy().reset_index(drop=True)

print(f'Filtered to Attractions: {len(df_attr):,} places out of {len(df):,} total')
print(f'\nFull dataset category breakdown:')
print(df['category'].value_counts().to_string())

# %%
df_attr.head()

# %%
df_attr.info()

# %%
hashable_cols = get_hashable_cols(df_attr)

print(f'Hashable columns: {len(hashable_cols)} of {len(df_attr.columns)}')

# %%
df_attr[hashable_cols].describe(include='all')

# ---
# ## 3. Derive Features

# %%
df_attr = derive_features(df_attr)

print('Derived features created: photo_count, review_text_count, avg_review_length, has_hours, district, area')

# ---
# ## 4. Data Quality Assessment

# %%
print('=' * 70)
print(f'  DATA QUALITY: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

cat_hashable = [c for c in hashable_cols if c in df_attr.columns]

# Missing values
missing = pd.DataFrame({
    'column': df_attr[cat_hashable].columns,
    'missing_count': df_attr[cat_hashable].isnull().sum().values,
    'missing_pct': (df_attr[cat_hashable].isnull().sum().values / len(df_attr) * 100).round(2)
}).sort_values('missing_pct', ascending=False).reset_index(drop=True)

missing = missing[missing['missing_count'] > 0]

if len(missing) > 0:
    print(f'\nColumns with Missing Values (attraction):')
    print(missing.to_string(index=False))
    fig, ax = plt.subplots(figsize=(14, 6))
    sns.heatmap(df_attr[cat_hashable].isnull(), cbar=True, yticklabels=False, cmap='YlOrRd', ax=ax)
    ax.set_title('Missing Values Heatmap - Attraction', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig('../outputs/figures/attraction_missing_values_heatmap.png', bbox_inches='tight')
    plt.show()
else:
    print('No missing values found for attraction!')

# Duplicates
exact_dups = df_attr[cat_hashable].duplicated().sum()
print(f'\nExact duplicate rows: {exact_dups}')
if 'id' in df_attr.columns:
    id_dups = df_attr['id'].duplicated().sum()
    print(f'Duplicate id values: {id_dups}')

# Consistency checks
issues = []
if 'lat' in df_attr.columns and 'lon' in df_attr.columns:
    bad_coords = df_attr[(df_attr['lat'] < 28) | (df_attr['lat'] > 32) | (df_attr['lon'] < 29) | (df_attr['lon'] > 33)]
    if len(bad_coords) > 0:
        issues.append(f'[WARN] {len(bad_coords)} rows with coordinates outside Cairo area')
if 'rating' in df_attr.columns:
    bad_ratings = df_attr[(df_attr['rating'] < 0) | (df_attr['rating'] > 5)]
    if len(bad_ratings) > 0:
        issues.append(f'[WARN] {len(bad_ratings)} rows with rating outside [0, 5]')
if 'review_count' in df_attr.columns:
    neg_reviews = df_attr[df_attr['review_count'] < 0]
    if len(neg_reviews) > 0:
        issues.append(f'[WARN] {len(neg_reviews)} rows with negative review_count')

if issues:
    print('\n'.join(issues))
else:
    print('No data consistency issues found!')

# Quality report
quality_report = {
    'Total Records': len(df_attr),
    'Total Columns': len(df_attr.columns),
    'Exact Duplicates': int(exact_dups),
    'Columns with Missing Data': int((df_attr[cat_hashable].isnull().sum() > 0).sum()),
    'Total Missing Cells': int(df_attr[cat_hashable].isnull().sum().sum()),
    'Memory Usage (MB)': round(df_attr.memory_usage(deep=True).sum() / 1024**2, 1),
}
report_df = pd.DataFrame.from_dict(quality_report, orient='index', columns=['Value'])
print(f'\nDATA QUALITY REPORT - ATTRACTION')
print('=' * 45)
print(report_df.to_string())

# ---
# ## 5. Univariate Analysis - Numerical Variables

# %%
print('=' * 70)
print(f'  UNIVARIATE NUMERICAL: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

fig, axes = plt.subplots(1, 3, figsize=(18, 5))

# Histogram
axes[0].hist(df_attr['rating'].dropna(), bins=30, color='#4C72B0', edgecolor='white', alpha=0.8)
axes[0].axvline(df_attr['rating'].mean(), color='red', linestyle='--', label=f"Mean: {df_attr['rating'].mean():.2f}")
axes[0].axvline(df_attr['rating'].median(), color='green', linestyle='--', label=f"Median: {df_attr['rating'].median():.2f}")
axes[0].set_title('Rating Distribution', fontweight='bold')
axes[0].set_xlabel('Rating')
axes[0].set_ylabel('Count')
axes[0].legend()

# KDE
df_attr['rating'].dropna().plot(kind='kde', ax=axes[1], color='#4C72B0', linewidth=2)
axes[1].set_title('Rating KDE', fontweight='bold')
axes[1].set_xlabel('Rating')

# Boxplot
axes[2].boxplot(df_attr['rating'].dropna(), vert=True, patch_artist=True,
                boxprops=dict(facecolor='#4C72B0', alpha=0.6))
axes[2].set_title('Rating Boxplot', fontweight='bold')
axes[2].set_ylabel('Rating')

plt.suptitle('Rating Distribution - Attraction', fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('../outputs/figures/attraction_rating_distribution.png', bbox_inches='tight')
plt.show()

print(f"Rating Stats: mean={df_attr['rating'].mean():.2f}, median={df_attr['rating'].median():.2f}, "
      f"std={df_attr['rating'].std():.2f}, skew={df_attr['rating'].skew():.2f}")

# %%
print('=' * 70)
print(f'  REVIEW COUNT ANALYSIS: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

fig, axes = plt.subplots(1, 3, figsize=(18, 5))

reviews = df_attr['review_count'].dropna()
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

plt.suptitle('Review Count Distribution - Attraction', fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('../outputs/figures/attraction_review_count_distribution.png', bbox_inches='tight')
plt.show()

print(f"Review Stats: mean={reviews.mean():.0f}, median={reviews.median():.0f}, "
      f"max={reviews.max():,}, places with 0 reviews: {(reviews == 0).sum()}")

# ---
# ## 6. Univariate Analysis - Categorical / Subcategory Variables

# %%
print('=' * 70)
print(f'  SUBCATEGORY DISTRIBUTION: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

fig, axes = plt.subplots(1, 2, figsize=(18, 7))

# Category label distribution
if 'category_label' in df_attr.columns:
    label_counts = df_attr['category_label'].value_counts()
    label_counts.plot(kind='barh', ax=axes[0], color=sns.color_palette('viridis', len(label_counts)))
    axes[0].set_title('Category Labels - Attraction', fontweight='bold')
    axes[0].set_xlabel('Count')
    for i, v in enumerate(label_counts.values):
        axes[0].text(v + 2, i, f'{v:,}', va='center', fontsize=10)

# Subtype distribution
if 'subtype' in df_attr.columns:
    subtype_counts = df_attr['subtype'].dropna().value_counts()
    if len(subtype_counts) > 0:
        top_n = 10
        top_subtypes = subtype_counts.head(top_n)
        other = subtype_counts[top_n:].sum() if len(subtype_counts) > top_n else 0
        pie_data = pd.concat([top_subtypes, pd.Series({'Other': other})]) if other > 0 else top_subtypes
        colors = sns.color_palette('viridis', len(pie_data))
        axes[1].pie(pie_data, labels=pie_data.index, autopct='%1.1f%%',
                    colors=colors, startangle=90, pctdistance=0.85)
        axes[1].set_title('Subtype Proportions - Attraction', fontweight='bold')

plt.suptitle('Categorical Distribution - Attraction', fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('../outputs/figures/attraction_category_distribution.png', bbox_inches='tight')
plt.show()

print('\nCategory Label Counts (attraction):')
if 'category_label' in df_attr.columns:
    for label, count in df_attr['category_label'].value_counts().items():
        print(f'  {label:40s} {count:>5,} ({count/len(df_attr)*100:.1f}%)')

if 'subtype' in df_attr.columns:
    print('\nSubtype Counts (attraction):')
    for st, count in df_attr['subtype'].value_counts().head(15).items():
        print(f'  {str(st):40s} {count:>5,} ({count/len(df_attr)*100:.1f}%)')

# %%
# District distribution
print('=' * 70)
print(f'  DISTRICT DISTRIBUTION: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

dist_counts = df_attr['district'].value_counts().head(15)

fig, ax = plt.subplots(figsize=(14, 7))
dist_counts.plot(kind='barh', ax=ax, color=sns.color_palette('rocket', len(dist_counts)))
ax.set_title('Top 15 Districts - Attraction', fontweight='bold')
ax.set_xlabel('Count')
for i, v in enumerate(dist_counts.values):
    ax.text(v + 2, i, f'{v:,}', va='center', fontsize=10)
plt.tight_layout()
plt.savefig('../outputs/figures/attraction_district_distribution.png', bbox_inches='tight')
plt.show()

# ---
# ## 7. Geographical Analysis

# %%
cairo_center = [df_attr['lat'].median(), df_attr['lon'].median()]

print('=' * 70)
print(f'  GEOGRAPHICAL ANALYSIS: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

# Interactive Folium map
sample_size = min(2000, len(df_attr))
df_sample = df_attr.sample(n=sample_size, random_state=42)

m = folium.Map(location=cairo_center, zoom_start=12, tiles='CartoDB positron')
marker_cluster = MarkerCluster().add_to(m)

for _, row in df_sample.iterrows():
    folium.CircleMarker(
        location=[row['lat'], row['lon']],
        radius=4, color='#4C72B0', fill=True, fill_opacity=0.7,
        popup=folium.Popup(
            f"<b>{row['name']}</b><br>"
            f"Category: Attraction<br>"
            f"Type: {row.get('subtype', 'N/A')}<br>"
            f"Rating: {row.get('rating', 'N/A')}<br>"
            f"Reviews: {row.get('review_count', 0):,}",
            max_width=250
        ),
    ).add_to(marker_cluster)

m.save('../outputs/figures/attraction_places_map.html')
print(f'Interactive map saved: outputs/figures/attraction_places_map.html ({sample_size:,} places)')

# Heatmap
m_heat = folium.Map(location=cairo_center, zoom_start=12, tiles='CartoDB positron')
heat_data = df_attr[['lat', 'lon']].dropna().values.tolist()
HeatMap(heat_data, radius=15, blur=20, max_zoom=13).add_to(m_heat)
m_heat.save('../outputs/figures/attraction_density_heatmap.html')
print('Density heatmap saved: outputs/figures/attraction_density_heatmap.html')

# High-rated places map
high_rated = df_attr[df_attr['rating'] >= 4.5]
if len(high_rated) > 0:
    high_rated_sample = high_rated.sample(min(1000, len(high_rated)), random_state=42)
    m_hr = folium.Map(location=cairo_center, zoom_start=12, tiles='CartoDB positron')
    for _, row in high_rated_sample.iterrows():
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=5, color='gold', fill=True, fill_opacity=0.8,
            popup=f"<b>{row['name']}</b><br>Type: {row.get('subtype', 'N/A')}<br>Rating: {row['rating']}<br>Reviews: {row.get('review_count', 0):,}",
        ).add_to(m_hr)
    m_hr.save('../outputs/figures/attraction_high_rated_map.html')
    print(f'High-rated places map saved ({len(high_rated_sample):,} places)')

# Static scatter map with Plotly
fig = px.scatter_mapbox(
    df_attr.sample(min(2000, len(df_attr)), random_state=42),
    lat='lat', lon='lon',
    size='review_count', size_max=15,
    hover_name='name',
    hover_data={'rating': True, 'review_count': True, 'subtype': True},
    mapbox_style='carto-positron',
    center={'lat': cairo_center[0], 'lon': cairo_center[1]},
    zoom=11, title='Attractions - Geographic Distribution', height=600,
)
fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
fig.write_html('../outputs/figures/attraction_plotly_map.html')
print('Plotly map saved: outputs/figures/attraction_plotly_map.html')

# ---
# ## 8. Rating & Review Analysis

# %%
print('=' * 70)
print(f'  RATING & REVIEW ANALYSIS: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

# Top reviewed
top_reviewed = df_attr.nlargest(10, 'review_count')[['name', 'rating', 'review_count', 'address', 'subtype']]
print('\nTop 10 Most Reviewed Attractions:')
print(top_reviewed.to_string(index=False))

# Rating vs Review Count scatter
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

axes[0].scatter(df_attr['rating'], df_attr['review_count'], alpha=0.3, s=10, c=df_attr['rating'], cmap='RdYlGn')
axes[0].set_xlabel('Rating')
axes[0].set_ylabel('Review Count')
axes[0].set_title('Rating vs Review Count - Attraction', fontweight='bold')
axes[0].set_yscale('log')

rating_bucket = pd.cut(df_attr['rating'], bins=[0, 2, 3, 3.5, 4, 4.5, 5],
                       labels=['<2', '2-3', '3-3.5', '3.5-4', '4-4.5', '4-5'])
valid_mask = rating_bucket.notna()
if valid_mask.sum() > 0:
    sns.violinplot(x=rating_bucket[valid_mask], y=df_attr.loc[valid_mask, 'review_count'], ax=axes[1],
                   palette='RdYlGn', inner='quartile')
axes[1].set_title('Review Count by Rating Bucket - Attraction', fontweight='bold')
axes[1].set_yscale('log')

plt.tight_layout()
plt.savefig('../outputs/figures/attraction_rating_vs_reviews.png', bbox_inches='tight')
plt.show()

print(f"\nRating Stats: mean={df_attr['rating'].mean():.2f}, median={df_attr['rating'].median():.2f}, "
      f"std={df_attr['rating'].std():.2f}")
print(f"Review Stats: mean={df_attr['review_count'].mean():.0f}, median={df_attr['review_count'].median():.0f}, "
      f"max={df_attr['review_count'].max():,}")

# ---
# ## 9. Popularity Analysis

# %%
print('=' * 70)
print(f'  POPULARITY ANALYSIS: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

df_attr = compute_popularity(df_attr)

print(f"Popularity score computed (0-1 scale)")
print(f"   Mean: {df_attr['popularity_score'].mean():.3f}")
print(f"   Std:  {df_attr['popularity_score'].std():.3f}")

# Top popular
top_popular = df_attr.nlargest(10, 'popularity_score')[['name', 'rating', 'review_count', 'popularity_score', 'subtype']]
print('\nTop 10 Most Popular Attractions:')
print(top_popular.to_string(index=False))

# District popularity
dist_pop = df_attr.groupby('district').agg(
    avg_popularity=('popularity_score', 'mean'),
    count=('name', 'count'),
    avg_rating=('rating', 'mean')
).sort_values('avg_popularity', ascending=False).head(15)

fig, ax = plt.subplots(figsize=(12, 7))
dist_pop['avg_popularity'].plot(kind='barh', ax=ax, color=sns.color_palette('YlOrRd', len(dist_pop)))
ax.set_title('Top 15 Districts by Avg Popularity - Attraction', fontweight='bold')
ax.set_xlabel('Avg Popularity Score')
for i, v in enumerate(dist_pop['avg_popularity'].values):
    ax.text(v + 0.005, i, f'{v:.3f}', va='center', fontsize=10)
plt.tight_layout()
plt.savefig('../outputs/figures/attraction_district_popularity.png', bbox_inches='tight')
plt.show()

# ---
# ## 10. Location Intelligence

# %%
print('=' * 70)
print(f'  LOCATION INTELLIGENCE: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

area_stats = df_attr.groupby('area').agg(
    num_places=('name', 'count'),
    avg_rating=('rating', 'mean'),
    total_reviews=('review_count', 'sum'),
    avg_popularity=('popularity_score', 'mean')
).sort_values('num_places', ascending=False)

significant_areas = area_stats[area_stats['num_places'] >= 3].head(15)
print(f'\nSignificant Areas for Attractions (>=3 places):')
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

    plt.suptitle('Area Comparison - Attractions', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('../outputs/figures/attraction_area_comparison.png', bbox_inches='tight')
    plt.show()

# ---
# ## 11. Correlation Analysis

# %%
print('=' * 70)
print(f'  CORRELATION ANALYSIS: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

corr_cols = ['rating', 'review_count', 'photo_count', 'review_text_count',
             'avg_review_length', 'popularity_score', 'has_hours']
corr_cols = [c for c in corr_cols if c in df_attr.columns]

corr_matrix = df_attr[corr_cols].corr()

fig, ax = plt.subplots(figsize=(12, 10))
mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
sns.heatmap(corr_matrix, mask=mask, annot=True, fmt='.3f', cmap='RdBu_r',
            center=0, vmin=-1, vmax=1, ax=ax, linewidths=0.5,
            square=True, cbar_kws={'shrink': 0.8})
ax.set_title('Correlation Matrix - Attraction', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig('../outputs/figures/attraction_correlation_heatmap.png', bbox_inches='tight')
plt.show()

print('Key Correlations (attraction):')
for pair in [('rating', 'review_count'), ('rating', 'photo_count'), ('review_count', 'photo_count')]:
    if pair[0] in df_attr.columns and pair[1] in df_attr.columns:
        corr = df_attr[pair[0]].corr(df_attr[pair[1]])
        print(f"  {pair[0]:20s} x {pair[1]:20s}: r = {corr:+.3f}")

# ---
# ## 12. Outlier Detection

# %%
print('=' * 70)
print(f'  OUTLIER DETECTION: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

print('IQR Outlier Detection (attraction):')
detect_outliers_iqr(df_attr['review_count'], 'review_count')
detect_outliers_iqr(df_attr['rating'], 'rating')

# Z-score
df_attr['review_zscore'] = zscore(df_attr['review_count'].fillna(0))
z_outliers = df_attr[df_attr['review_zscore'].abs() > 3]
print(f"Z-Score outliers (|z| > 3) in review_count: {len(z_outliers):,}")
print(f"   Max z-score: {df_attr['review_zscore'].max():.2f}")
print(f"   Min z-score: {df_attr['review_zscore'].min():.2f}")

fig, axes = plt.subplots(1, 2, figsize=(16, 6))

Q1, Q3 = df_attr['review_count'].quantile(0.25), df_attr['review_count'].quantile(0.75)
IQR = Q3 - Q1
lower, upper = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR

axes[0].boxplot(df_attr['review_count'].dropna(), vert=True, patch_artist=True,
                boxprops=dict(facecolor='#4C72B0', alpha=0.6))
axes[0].axhline(upper, color='red', linestyle='--', label=f'Upper fence: {upper:,.0f}')
axes[0].axhline(lower, color='red', linestyle='--', label=f'Lower fence: {lower:,.0f}')
axes[0].set_title('Review Count - Outliers - Attraction', fontweight='bold')
axes[0].legend()

axes[1].hist(df_attr['review_zscore'].dropna(), bins=50, color='#55A868', edgecolor='white', alpha=0.8)
axes[1].axvline(3, color='red', linestyle='--', label='z = 3')
axes[1].axvline(-3, color='red', linestyle='--', label='z = -3')
axes[1].set_title('Review Count - Z-Score Distribution - Attraction', fontweight='bold')
axes[1].set_xlabel('Z-Score')
axes[1].legend()

plt.tight_layout()
plt.savefig('../outputs/figures/attraction_outlier_detection.png', bbox_inches='tight')
plt.show()

df_attr.drop(columns=['review_zscore'], inplace=True)

# ---
# ## 13. Tourism Insights

# %%
print('=' * 70)
print(f'  TOURISM INSIGHTS: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

print('\nRating Distribution (attraction):')
for rating, count in df_attr['rating'].value_counts().head(5).items():
    print(f"  Rating {rating}: {count:,} places ({count/len(df_attr)*100:.1f}%)")

print('\nHighest-Engagement Districts (attraction):')
top_areas = df_attr.groupby('district')['review_count'].sum().sort_values(ascending=False).head(5)
for area, reviews in top_areas.items():
    print(f"  {area}: {reviews:,.0f} total reviews")

hidden_gems = df_attr[(df_attr['rating'] >= 4.5) & (df_attr['review_count'] < df_attr['review_count'].quantile(0.25))]
print(f"\nHidden Gems (rating >= 4.5, low reviews): {len(hidden_gems):,} attractions")
if len(hidden_gems) > 0:
    print('Top hidden gems:')
    for _, row in hidden_gems.nlargest(5, 'rating').iterrows():
        print(f"  Rating: {row['rating']:.1f} - {row['name']} ({row['review_count']:,} reviews) [{row.get('subtype', 'N/A')}]")

# Recommendation candidates
print('\nTop Recommendation Candidates (attraction):')
top_recs = df_attr.nlargest(10, 'rating')[['name', 'rating', 'review_count', 'popularity_score', 'subtype']]
print(top_recs.to_string(index=False))

# ---
# ## 14. Recommendation-Oriented Features

# %%
print('=' * 70)
print(f'  RECOMMENDATION SCORES: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

df_attr = compute_recommendation_scores(df_attr)

score_cols = ['family_friendly_score', 'budget_score', 'luxury_score']
print('\nRecommendation Feature Scores (attraction):')
print(df_attr[score_cols].describe().round(3).to_string())

# Top recommendations by profile
print('\nTop 5 Recommendations by Profile (attraction):')
profiles = {
    'Family Trip': 'family_friendly_score',
    'Budget Traveler': 'budget_score',
    'Luxury Seeker': 'luxury_score',
}
for profile, score_col in profiles.items():
    top = df_attr.nlargest(5, score_col)[['name', 'rating', 'review_count', score_col, 'subtype']]
    print(f"\n  {profile}:")
    for _, row in top.iterrows():
        print(f"    Rating: {row['rating']:.1f} | {row['name'][:45]:45s} | score={row[score_col]:.3f} | {row.get('subtype', 'N/A')}")

# ---
# ## 15. Attraction-Specific Deep Dive

# ---
# ### 15a. Subtype Deep Dive

# %%
print('=' * 70)
print(f'  SUBTYPE DEEP DIVE: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

subtype_data = df_attr[df_attr['subtype'].notna()].copy()
print(f'Attractions with subtype data: {len(subtype_data):,} / {len(df_attr):,} ({len(subtype_data)/len(df_attr)*100:.1f}%)')

if len(subtype_data) > 0:
    subtype_counts = subtype_data['subtype'].value_counts()
    print(f'\nSubtype Distribution (all {len(subtype_counts)} types):')
    for st, count in subtype_counts.items():
        print(f'  {st:40s} {count:>5,} ({count/len(subtype_data)*100:.1f}%)')

    fig, axes = plt.subplots(2, 2, figsize=(18, 14))

    # Top subtypes bar chart
    top_subtypes = subtype_counts.head(15)
    top_subtypes.plot(kind='barh', ax=axes[0, 0], color=sns.color_palette('viridis', len(top_subtypes)))
    axes[0, 0].set_title('Top 15 Attraction Subtypes', fontweight='bold')
    axes[0, 0].set_xlabel('Count')
    axes[0, 0].invert_yaxis()

    # Rating by subtype (top subtypes)
    top_st_names = subtype_counts.head(10).index
    subtype_rating = subtype_data[subtype_data['subtype'].isin(top_st_names)].groupby('subtype').agg(
        avg_rating=('rating', 'mean'),
        avg_reviews=('review_count', 'mean'),
        count=('name', 'count')
    ).sort_values('count', ascending=False)

    subtype_rating.sort_values('avg_rating').plot(kind='barh', y='avg_rating', ax=axes[0, 1],
                                                   color='#55A868', legend=False, xerr=subtype_rating['avg_rating'].std())
    axes[0, 1].set_title('Avg Rating by Subtype', fontweight='bold')
    axes[0, 1].set_xlabel('Avg Rating')

    # Reviews by subtype
    subtype_rating.sort_values('avg_reviews').plot(kind='barh', y='avg_reviews', ax=axes[1, 0],
                                                    color='#C44E52', legend=False)
    axes[1, 0].set_title('Avg Reviews by Subtype', fontweight='bold')
    axes[1, 0].set_xlabel('Avg Reviews')

    # Pie chart of top subtypes
    top_10 = subtype_counts.head(10)
    other = subtype_counts[10:].sum() if len(subtype_counts) > 10 else 0
    pie_data = pd.concat([top_10, pd.Series({'Other': other})]) if other > 0 else top_10
    colors = sns.color_palette('viridis', len(pie_data))
    axes[1, 1].pie(pie_data, labels=pie_data.index, autopct='%1.1f%%',
                    colors=colors, startangle=90, pctdistance=0.85)
    axes[1, 1].set_title('Subtype Proportions', fontweight='bold')

    plt.suptitle('Attraction Subtype Deep Dive', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('../outputs/figures/attraction_subtype_deep_dive.png', bbox_inches='tight')
    plt.show()

    # Detailed stats per subtype
    print('\nSubtype Stats (top 10):')
    subtype_stats = subtype_data[subtype_data['subtype'].isin(top_st_names)].groupby('subtype').agg(
        count=('name', 'count'),
        avg_rating=('rating', 'mean'),
        median_rating=('rating', 'median'),
        avg_reviews=('review_count', 'mean'),
        total_reviews=('review_count', 'sum'),
    ).sort_values('count', ascending=False)
    print(subtype_stats.round(2).to_string())

# ---
# ### 15b. Photo Analysis

# %%
print('=' * 70)
print(f'  PHOTO ANALYSIS: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

if 'photo_count' in df_attr.columns:
    print(f'\nPhoto Count Stats:')
    print(f"  Mean: {df_attr['photo_count'].mean():.1f}")
    print(f"  Median: {df_attr['photo_count'].median():.0f}")
    print(f"  Max: {df_attr['photo_count'].max():,}")
    print(f"  Attractions with 0 photos: {(df_attr['photo_count'] == 0).sum():,}")

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Distribution
    axes[0].hist(df_attr['photo_count'].dropna(), bins=30, color='#4C72B0', edgecolor='white', alpha=0.8)
    axes[0].axvline(df_attr['photo_count'].mean(), color='red', linestyle='--', label=f"Mean: {df_attr['photo_count'].mean():.1f}")
    axes[0].set_title('Photo Count Distribution', fontweight='bold')
    axes[0].set_xlabel('Number of Photos')
    axes[0].set_ylabel('Count')
    axes[0].legend()

    # Photo count vs Rating
    axes[1].scatter(df_attr['photo_count'], df_attr['rating'], alpha=0.3, s=10, c='#55A868')
    axes[1].set_xlabel('Photo Count')
    axes[1].set_ylabel('Rating')
    axes[1].set_title('Photo Count vs Rating', fontweight='bold')

    # Photo count vs Review count
    axes[2].scatter(df_attr['photo_count'], df_attr['review_count'], alpha=0.3, s=10, c='#C44E52')
    axes[2].set_xlabel('Photo Count')
    axes[2].set_ylabel('Review Count')
    axes[2].set_title('Photo Count vs Review Count')
    axes[2].set_yscale('log')

    plt.suptitle('Photo Analysis - Attractions', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('../outputs/figures/attraction_photo_analysis.png', bbox_inches='tight')
    plt.show()

    # Photo count by subtype
    if 'subtype' in df_attr.columns and df_attr['subtype'].notna().sum() > 0:
        top_st = df_attr['subtype'].value_counts().head(8).index
        photo_by_subtype = df_attr[df_attr['subtype'].isin(top_st)].groupby('subtype')['photo_count'].mean().sort_values(ascending=True)
        fig, ax = plt.subplots(figsize=(10, 6))
        photo_by_subtype.plot(kind='barh', ax=ax, color='#4C72B0')
        ax.set_title('Avg Photo Count by Subtype', fontweight='bold')
        ax.set_xlabel('Avg Photo Count')
        plt.tight_layout()
        plt.savefig('../outputs/figures/attraction_photo_by_subtype.png', bbox_inches='tight')
        plt.show()

# ---
# ### 15c. Review Text Analysis

# %%
print('=' * 70)
print(f'  REVIEW TEXT ANALYSIS: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

if 'review_text_count' in df_attr.columns and 'avg_review_length' in df_attr.columns:
    print(f'\nReview Text Stats:')
    print(f"  Avg review text count per attraction: {df_attr['review_text_count'].mean():.1f}")
    print(f"  Avg review length (chars): {df_attr['avg_review_length'].mean():.0f}")

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # Review text count distribution
    axes[0].hist(df_attr['review_text_count'].dropna(), bins=30, color='#8172B2', edgecolor='white', alpha=0.8)
    axes[0].set_title('Review Text Count Distribution', fontweight='bold')
    axes[0].set_xlabel('Number of Review Texts')
    axes[0].set_ylabel('Count')

    # Avg review length vs Rating
    axes[1].scatter(df_attr['avg_review_length'], df_attr['rating'], alpha=0.3, s=10, c='#8172B2')
    axes[1].set_xlabel('Avg Review Length (chars)')
    axes[1].set_ylabel('Rating')
    axes[1].set_title('Avg Review Length vs Rating', fontweight='bold')

    plt.suptitle('Review Text Analysis - Attractions', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('../outputs/figures/attraction_review_text_analysis.png', bbox_inches='tight')
    plt.show()

    # Review metrics by subtype
    if 'subtype' in df_attr.columns and df_attr['subtype'].notna().sum() > 0:
        top_st = df_attr['subtype'].value_counts().head(8).index
        review_by_subtype = df_attr[df_attr['subtype'].isin(top_st)].groupby('subtype').agg(
            avg_review_count=('review_text_count', 'mean'),
            avg_review_length=('avg_review_length', 'mean'),
            avg_rating=('rating', 'mean')
        ).sort_values('avg_review_count', ascending=False)

        print('\nReview Metrics by Subtype:')
        print(review_by_subtype.round(2).to_string())

# ---
# ### 15d. Operating Hours Analysis

# %%
print('=' * 70)
print(f'  OPERATING HOURS ANALYSIS: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

hours_data = df_attr[df_attr['hours'].notna() & df_attr['hours'].apply(lambda x: isinstance(x, dict) and len(x) > 0)].copy()
print(f'Attractions with hours data: {len(hours_data):,} / {len(df_attr):,} ({len(hours_data)/len(df_attr)*100:.1f}%)')

if len(hours_data) > 0:
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

        plt.suptitle('Operating Hours Analysis - Attractions', fontsize=15, fontweight='bold', y=1.02)
        plt.tight_layout()
        plt.savefig('../outputs/figures/attraction_operating_hours.png', bbox_inches='tight')
        plt.show()

        print(f'Most common opening hour: {Counter(opening_hours).most_common(3)}')
        print(f'Most common closing hour: {Counter(closing_hours).most_common(3)}')
        avg_hours = np.mean([c - o if c > o else c + 24 - o for o, c in zip(opening_hours, closing_hours)])
        print(f'Average operating hours: {avg_hours:.1f} hours')

# ---
# ### 15e. Description Length Analysis

# %%
print('=' * 70)
print(f'  DESCRIPTION ANALYSIS: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

df_attr['desc_length'] = df_attr['description'].apply(lambda x: len(str(x)) if pd.notna(x) else 0)
df_attr['desc_word_count'] = df_attr['description'].apply(lambda x: len(str(x).split()) if pd.notna(x) else 0)

print(f'\nDescription Stats:')
print(f"  Mean char length: {df_attr['desc_length'].mean():.0f}")
print(f"  Mean word count: {df_attr['desc_word_count'].mean():.0f}")
print(f"  Attractions with no description: {(df_attr['desc_length'] == 0).sum():,}")

fig, axes = plt.subplots(1, 2, figsize=(16, 6))

axes[0].hist(df_attr['desc_length'].dropna(), bins=30, color='#4C72B0', edgecolor='white', alpha=0.8)
axes[0].set_title('Description Length Distribution (chars)', fontweight='bold')
axes[0].set_xlabel('Character Count')
axes[0].set_ylabel('Count')

axes[1].scatter(df_attr['desc_length'], df_attr['rating'], alpha=0.3, s=10, c='#55A868')
axes[1].set_xlabel('Description Length (chars)')
axes[1].set_ylabel('Rating')
axes[1].set_title('Description Length vs Rating', fontweight='bold')

plt.suptitle('Description Analysis - Attractions', fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('../outputs/figures/attraction_description_analysis.png', bbox_inches='tight')
plt.show()

# Description by subtype
if 'subtype' in df_attr.columns and df_attr['subtype'].notna().sum() > 0:
    top_st = df_attr['subtype'].value_counts().head(8).index
    desc_by_subtype = df_attr[df_attr['subtype'].isin(top_st)].groupby('subtype')['desc_word_count'].mean().sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    desc_by_subtype.plot(kind='barh', ax=ax, color='#4C72B0')
    ax.set_title('Avg Description Word Count by Subtype', fontweight='bold')
    ax.set_xlabel('Avg Word Count')
    plt.tight_layout()
    plt.savefig('../outputs/figures/attraction_desc_by_subtype.png', bbox_inches='tight')
    plt.show()

# ---
# ## 16. Interactive Dashboard Elements

# %%
print('=' * 70)
print(f'  INTERACTIVE DASHBOARD: ATTRACTION ({len(df_attr):,} places)')
print('=' * 70)

# Rating distribution box plot
fig = px.box(
    df_attr, y='rating',
    title='Attraction - Rating Distribution (Interactive)',
    hover_data=['name', 'review_count', 'subtype'], height=500
)
fig.write_html('../outputs/figures/attraction_interactive_rating_boxplot.html')

# Scatter by subtype
if 'subtype' in df_attr.columns and df_attr['subtype'].notna().sum() > 0:
    fig = px.scatter(
        df_attr.sample(min(2000, len(df_attr)), random_state=42),
        x='subtype', y='rating', color='district',
        size='review_count', size_max=20, hover_name='name',
        hover_data={'subtype': True, 'rating': True, 'review_count': True, 'district': True},
        title='Attractions - Subtype x Rating x District', height=600,
    )
    fig.update_layout(xaxis_tickangle=-45)
    fig.write_html('../outputs/figures/attraction_interactive_subtype_rating.html')
    print('Subtype scatter saved: attraction_interactive_subtype_rating.html')

# Subtype box plot interactive
if 'subtype' in df_attr.columns and df_attr['subtype'].notna().sum() > 0:
    top_st = df_attr['subtype'].value_counts().head(10).index
    fig = px.box(
        df_attr[df_attr['subtype'].isin(top_st)],
        x='subtype', y='rating',
        title='Attractions - Rating by Subtype (Interactive)',
        hover_data=['name', 'review_count'], height=500
    )
    fig.update_layout(xaxis_tickangle=-45)
    fig.write_html('../outputs/figures/attraction_interactive_subtype_boxplot.html')
    print('Subtype boxplot saved: attraction_interactive_subtype_boxplot.html')

print('Dashboard saved for attraction')

# ---
# ## 17. Automated Report Generation

# %%
report_data = {
    'Total Attractions': f"{len(df_attr):,}",
    'Avg Rating': f"{df_attr['rating'].mean():.2f}",
    'Median Review Count': f"{df_attr['review_count'].median():,.0f}",
    'Total Reviews': f"{df_attr['review_count'].sum():,.0f}",
    'Unique Districts': f"{df_attr['district'].nunique():,}",
    'Unique Subtypes': f"{df_attr['subtype'].nunique() if 'subtype' in df_attr.columns else 0}",
    'Hidden Gems': len(df_attr[(df_attr['rating'] >= 4.5) & (df_attr['review_count'] < df_attr['review_count'].quantile(0.25))]),
    'With Hours': f"{df_attr['has_hours'].sum():,}" if 'has_hours' in df_attr.columns else "N/A",
}

html_report = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Cairo Attractions EDA Report - TourMate AI</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; background: #f8f9fa; color: #333; }}
        .header {{ background: linear-gradient(135deg, #e65100, #f57c00); color: white; padding: 40px; border-radius: 12px; margin-bottom: 30px; }}
        .header h1 {{ margin: 0; font-size: 2.2em; }}
        .header p {{ margin: 8px 0 0; opacity: 0.9; font-size: 1.1em; }}
        .section {{ background: white; border-radius: 10px; padding: 25px 30px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .section h2 {{ color: #e65100; border-bottom: 2px solid #fff3e0; padding-bottom: 8px; }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .kpi {{ background: #fff3e0; border-radius: 8px; padding: 20px; text-align: center; }}
        .kpi .value {{ font-size: 2em; font-weight: bold; color: #e65100; }}
        .kpi .label {{ font-size: 0.9em; color: #555; margin-top: 5px; }}
        .insight {{ background: #e8f5e9; border-left: 4px solid #4caf50; padding: 12px 18px; margin: 10px 0; border-radius: 0 8px 8px 0; }}
        .footer {{ text-align: center; color: #999; padding: 20px; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Cairo Attractions - EDA Report</h1>
        <p>TourMate AI - Data Intelligence - Generated June 2026</p>
    </div>
    <div class="section">
        <h2>Executive Summary</h2>
        <div class="kpi-grid">
            <div class="kpi"><div class="value">{report_data['Total Attractions']}</div><div class="label">Total Attractions</div></div>
            <div class="kpi"><div class="value">{report_data['Avg Rating']}</div><div class="label">Avg Rating</div></div>
            <div class="kpi"><div class="value">{report_data['Total Reviews']}</div><div class="label">Total Reviews</div></div>
            <div class="kpi"><div class="value">{report_data['Unique Districts']}</div><div class="label">Districts</div></div>
            <div class="kpi"><div class="value">{report_data['Unique Subtypes']}</div><div class="label">Subtypes</div></div>
            <div class="kpi"><div class="value">{report_data['Hidden Gems']}</div><div class="label">Hidden Gems</div></div>
            <div class="kpi"><div class="value">{report_data['With Hours']}</div><div class="label">With Hours Data</div></div>
        </div>
    </div>
    <div class="section">
        <h2>Key Findings</h2>
        <div class="insight"><b>Subtype Diversity:</b> Comprehensive analysis of {report_data['Unique Subtypes']} attraction types from malls to archaeological sites.</div>
        <div class="insight"><b>Photo Patterns:</b> Analysis of visual content and its correlation with visitor engagement.</div>
        <div class="insight"><b>Review Depth:</b> Review text length analysis reveals engagement patterns across attraction types.</div>
        <div class="insight"><b>Operating Hours:</b> Patterns in attraction opening/closing times for trip planning.</div>
    </div>
    <div class="section">
        <h2>Recommendations for TourMate AI</h2>
        <ul>
            <li>Use subtype data for experience-based attraction recommendations (culture, shopping, history).</li>
            <li>Leverage photo and review analysis for visual content quality scoring.</li>
            <li>Highlight hidden gems with high ratings but low review counts for discovery.</li>
            <li>Use operating hours data for itinerary planning and time-sensitive recommendations.</li>
        </ul>
    </div>
    <div class="footer">
        <p>Generated by TourMate AI Data Science Team - June 2026</p>
    </div>
</body>
</html>
"""

with open('../outputs/reports/attractions_eda_report.html', 'w', encoding='utf-8') as f:
    f.write(html_report)

print('HTML report saved to outputs/reports/attractions_eda_report.html')

# ---
# ## 18. Notebook Summary

# %%
print('=' * 70)
print('CAIRO ATTRACTIONS EDA - COMPLETED SUCCESSFULLY')
print('=' * 70)
print(f'\nTotal Attractions Analyzed: {len(df_attr):,}')
print(f'Avg Rating: {df_attr["rating"].mean():.2f} | Avg Reviews: {df_attr["review_count"].mean():.0f}')
if 'subtype' in df_attr.columns:
    print(f'Subtypes: {df_attr["subtype"].nunique()}')
print(f'\nOutput Files:')
print(f'  outputs/figures/ - attraction-specific visualizations saved')
print(f'  outputs/reports/ - HTML report')
print('\nAll analyses complete. Notebook ready for review.')

# ---
# *This notebook was generated by TourMate AI Data Science Team - June 2026*
# *Attractions-focused EDA for Cairo, Egypt*
