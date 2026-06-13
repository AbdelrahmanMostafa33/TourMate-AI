#!/usr/bin/env python
# coding: utf-8

# # Cairo Hotels - Exploratory Data Analysis (EDA)
# ## TourMate AI - Data Intelligence Report
#
# **Date:** June 2026
# **Analyst:** TourMate AI Data Science Team
# **Dataset:** `data/cairo_places_filled (9).json` - 6,600+ places across Cairo, Egypt
#
# This notebook performs a **deep-dive EDA** focused exclusively on **Hotels** in Cairo.
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
# ## 2. Filter to Hotels

# %%
df_hotel = df[df['category'] == 'hotel'].copy().reset_index(drop=True)

print(f'Filtered to Hotels: {len(df_hotel):,} places out of {len(df):,} total')
print(f'\nFull dataset category breakdown:')
print(df['category'].value_counts().to_string())

# %%
df_hotel.head()

# %%
df_hotel.info()

# %%
hashable_cols = get_hashable_cols(df_hotel)

print(f'Hashable columns: {len(hashable_cols)} of {len(df_hotel.columns)}')

# %%
df_hotel[hashable_cols].describe(include='all')

# ---
# ## 3. Derive Features

# %%
df_hotel = derive_features(df_hotel)

print('Derived features created: photo_count, review_text_count, avg_review_length, has_hours, district, area')

# ---
# ## 4. Data Quality Assessment

# %%
print('=' * 70)
print(f'  DATA QUALITY: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

cat_hashable = [c for c in hashable_cols if c in df_hotel.columns]

# Missing values
missing = pd.DataFrame({
    'column': df_hotel[cat_hashable].columns,
    'missing_count': df_hotel[cat_hashable].isnull().sum().values,
    'missing_pct': (df_hotel[cat_hashable].isnull().sum().values / len(df_hotel) * 100).round(2)
}).sort_values('missing_pct', ascending=False).reset_index(drop=True)

missing = missing[missing['missing_count'] > 0]

if len(missing) > 0:
    print(f'\nColumns with Missing Values (hotel):')
    print(missing.to_string(index=False))
    fig, ax = plt.subplots(figsize=(14, 6))
    sns.heatmap(df_hotel[cat_hashable].isnull(), cbar=True, yticklabels=False, cmap='YlOrRd', ax=ax)
    ax.set_title('Missing Values Heatmap - Hotel', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig('../outputs/figures/hotel_missing_values_heatmap.png', bbox_inches='tight')
    plt.show()
else:
    print('No missing values found for hotel!')

# Duplicates
exact_dups = df_hotel[cat_hashable].duplicated().sum()
print(f'\nExact duplicate rows: {exact_dups}')
if 'id' in df_hotel.columns:
    id_dups = df_hotel['id'].duplicated().sum()
    print(f'Duplicate id values: {id_dups}')

# Consistency checks
issues = []
if 'lat' in df_hotel.columns and 'lon' in df_hotel.columns:
    bad_coords = df_hotel[(df_hotel['lat'] < 28) | (df_hotel['lat'] > 32) | (df_hotel['lon'] < 29) | (df_hotel['lon'] > 33)]
    if len(bad_coords) > 0:
        issues.append(f'[WARN] {len(bad_coords)} rows with coordinates outside Cairo area')
if 'rating' in df_hotel.columns:
    bad_ratings = df_hotel[(df_hotel['rating'] < 0) | (df_hotel['rating'] > 5)]
    if len(bad_ratings) > 0:
        issues.append(f'[WARN] {len(bad_ratings)} rows with rating outside [0, 5]')
if 'review_count' in df_hotel.columns:
    neg_reviews = df_hotel[df_hotel['review_count'] < 0]
    if len(neg_reviews) > 0:
        issues.append(f'[WARN] {len(neg_reviews)} rows with negative review_count')

if issues:
    print('\n'.join(issues))
else:
    print('No data consistency issues found!')

# Quality report
quality_report = {
    'Total Records': len(df_hotel),
    'Total Columns': len(df_hotel.columns),
    'Exact Duplicates': int(exact_dups),
    'Columns with Missing Data': int((df_hotel[cat_hashable].isnull().sum() > 0).sum()),
    'Total Missing Cells': int(df_hotel[cat_hashable].isnull().sum().sum()),
    'Memory Usage (MB)': round(df_hotel.memory_usage(deep=True).sum() / 1024**2, 1),
}
report_df = pd.DataFrame.from_dict(quality_report, orient='index', columns=['Value'])
print(f'\nDATA QUALITY REPORT - HOTEL')
print('=' * 45)
print(report_df.to_string())

# ---
# ## 5. Univariate Analysis - Numerical Variables

# %%
print('=' * 70)
print(f'  UNIVARIATE NUMERICAL: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

fig, axes = plt.subplots(1, 3, figsize=(18, 5))

# Histogram
axes[0].hist(df_hotel['rating'].dropna(), bins=30, color='#4C72B0', edgecolor='white', alpha=0.8)
axes[0].axvline(df_hotel['rating'].mean(), color='red', linestyle='--', label=f"Mean: {df_hotel['rating'].mean():.2f}")
axes[0].axvline(df_hotel['rating'].median(), color='green', linestyle='--', label=f"Median: {df_hotel['rating'].median():.2f}")
axes[0].set_title('Rating Distribution', fontweight='bold')
axes[0].set_xlabel('Rating')
axes[0].set_ylabel('Count')
axes[0].legend()

# KDE
df_hotel['rating'].dropna().plot(kind='kde', ax=axes[1], color='#4C72B0', linewidth=2)
axes[1].set_title('Rating KDE', fontweight='bold')
axes[1].set_xlabel('Rating')

# Boxplot
axes[2].boxplot(df_hotel['rating'].dropna(), vert=True, patch_artist=True,
                boxprops=dict(facecolor='#4C72B0', alpha=0.6))
axes[2].set_title('Rating Boxplot', fontweight='bold')
axes[2].set_ylabel('Rating')

plt.suptitle('Rating Distribution - Hotel', fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('../outputs/figures/hotel_rating_distribution.png', bbox_inches='tight')
plt.show()

print(f"Rating Stats: mean={df_hotel['rating'].mean():.2f}, median={df_hotel['rating'].median():.2f}, "
      f"std={df_hotel['rating'].std():.2f}, skew={df_hotel['rating'].skew():.2f}")

# %%
print('=' * 70)
print(f'  REVIEW COUNT ANALYSIS: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

fig, axes = plt.subplots(1, 3, figsize=(18, 5))

reviews = df_hotel['review_count'].dropna()
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

plt.suptitle('Review Count Distribution - Hotel', fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('../outputs/figures/hotel_review_count_distribution.png', bbox_inches='tight')
plt.show()

print(f"Review Stats: mean={reviews.mean():.0f}, median={reviews.median():.0f}, "
      f"max={reviews.max():,}, places with 0 reviews: {(reviews == 0).sum()}")

# ---
# ## 6. Univariate Analysis - Categorical / Subcategory Variables

# %%
print('=' * 70)
print(f'  SUBCATEGORY DISTRIBUTION: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

fig, axes = plt.subplots(1, 2, figsize=(18, 7))

# Category label distribution
if 'category_label' in df_hotel.columns:
    label_counts = df_hotel['category_label'].value_counts()
    label_counts.plot(kind='barh', ax=axes[0], color=sns.color_palette('viridis', len(label_counts)))
    axes[0].set_title('Category Labels - Hotel', fontweight='bold')
    axes[0].set_xlabel('Count')
    for i, v in enumerate(label_counts.values):
        axes[0].text(v + 2, i, f'{v:,}', va='center', fontsize=10)

# Subtype distribution
if 'subtype' in df_hotel.columns:
    subtype_counts = df_hotel['subtype'].dropna().value_counts()
    if len(subtype_counts) > 0:
        top_n = 10
        top_subtypes = subtype_counts.head(top_n)
        other = subtype_counts[top_n:].sum() if len(subtype_counts) > top_n else 0
        pie_data = pd.concat([top_subtypes, pd.Series({'Other': other})]) if other > 0 else top_subtypes
        colors = sns.color_palette('viridis', len(pie_data))
        axes[1].pie(pie_data, labels=pie_data.index, autopct='%1.1f%%',
                    colors=colors, startangle=90, pctdistance=0.85)
        axes[1].set_title('Subtype Proportions - Hotel', fontweight='bold')

plt.suptitle('Categorical Distribution - Hotel', fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('../outputs/figures/hotel_category_distribution.png', bbox_inches='tight')
plt.show()

print('\nCategory Label Counts (hotel):')
if 'category_label' in df_hotel.columns:
    for label, count in df_hotel['category_label'].value_counts().items():
        print(f'  {label:40s} {count:>5,} ({count/len(df_hotel)*100:.1f}%)')

if 'subtype' in df_hotel.columns:
    print('\nSubtype Counts (hotel):')
    for st, count in df_hotel['subtype'].value_counts().head(15).items():
        print(f'  {str(st):40s} {count:>5,} ({count/len(df_hotel)*100:.1f}%)')

# %%
# District distribution
print('=' * 70)
print(f'  DISTRICT DISTRIBUTION: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

dist_counts = df_hotel['district'].value_counts().head(15)

fig, ax = plt.subplots(figsize=(14, 7))
dist_counts.plot(kind='barh', ax=ax, color=sns.color_palette('rocket', len(dist_counts)))
ax.set_title('Top 15 Districts - Hotel', fontweight='bold')
ax.set_xlabel('Count')
for i, v in enumerate(dist_counts.values):
    ax.text(v + 2, i, f'{v:,}', va='center', fontsize=10)
plt.tight_layout()
plt.savefig('../outputs/figures/hotel_district_distribution.png', bbox_inches='tight')
plt.show()

# ---
# ## 7. Geographical Analysis

# %%
cairo_center = [df_hotel['lat'].median(), df_hotel['lon'].median()]

print('=' * 70)
print(f'  GEOGRAPHICAL ANALYSIS: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

# Interactive Folium map
sample_size = min(2000, len(df_hotel))
df_sample = df_hotel.sample(n=sample_size, random_state=42)

m = folium.Map(location=cairo_center, zoom_start=12, tiles='CartoDB positron')
marker_cluster = MarkerCluster().add_to(m)

for _, row in df_sample.iterrows():
    folium.CircleMarker(
        location=[row['lat'], row['lon']],
        radius=4, color='#4C72B0', fill=True, fill_opacity=0.7,
        popup=folium.Popup(
            f"<b>{row['name']}</b><br>"
            f"Category: Hotel<br>"
            f"Rating: {row.get('rating', 'N/A')}<br>"
            f"Reviews: {row.get('review_count', 0):,}",
            max_width=250
        ),
    ).add_to(marker_cluster)

m.save('../outputs/figures/hotel_places_map.html')
print(f'Interactive map saved: outputs/figures/hotel_places_map.html ({sample_size:,} places)')

# Heatmap
m_heat = folium.Map(location=cairo_center, zoom_start=12, tiles='CartoDB positron')
heat_data = df_hotel[['lat', 'lon']].dropna().values.tolist()
HeatMap(heat_data, radius=15, blur=20, max_zoom=13).add_to(m_heat)
m_heat.save('../outputs/figures/hotel_density_heatmap.html')
print('Density heatmap saved: outputs/figures/hotel_density_heatmap.html')

# High-rated places map
high_rated = df_hotel[df_hotel['rating'] >= 4.5]
if len(high_rated) > 0:
    high_rated_sample = high_rated.sample(min(1000, len(high_rated)), random_state=42)
    m_hr = folium.Map(location=cairo_center, zoom_start=12, tiles='CartoDB positron')
    for _, row in high_rated_sample.iterrows():
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=5, color='gold', fill=True, fill_opacity=0.8,
            popup=f"<b>{row['name']}</b><br>Rating: {row['rating']}<br>Reviews: {row.get('review_count', 0):,}",
        ).add_to(m_hr)
    m_hr.save('../outputs/figures/hotel_high_rated_map.html')
    print(f'High-rated places map saved ({len(high_rated_sample):,} places)')

# Static scatter map with Plotly
fig = px.scatter_mapbox(
    df_hotel.sample(min(2000, len(df_hotel)), random_state=42),
    lat='lat', lon='lon',
    size='review_count', size_max=15,
    hover_name='name',
    hover_data={'rating': True, 'review_count': True},
    mapbox_style='carto-positron',
    center={'lat': cairo_center[0], 'lon': cairo_center[1]},
    zoom=11, title='Hotels - Geographic Distribution', height=600,
)
fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
fig.write_html('../outputs/figures/hotel_plotly_map.html')
print('Plotly map saved: outputs/figures/hotel_plotly_map.html')

# ---
# ## 8. Rating & Review Analysis

# %%
print('=' * 70)
print(f'  RATING & REVIEW ANALYSIS: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

# Top reviewed
top_reviewed = df_hotel.nlargest(10, 'review_count')[['name', 'rating', 'review_count', 'address']]
print('\nTop 10 Most Reviewed Hotels:')
print(top_reviewed.to_string(index=False))

# Rating vs Review Count scatter
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

axes[0].scatter(df_hotel['rating'], df_hotel['review_count'], alpha=0.3, s=10, c=df_hotel['rating'], cmap='RdYlGn')
axes[0].set_xlabel('Rating')
axes[0].set_ylabel('Review Count')
axes[0].set_title('Rating vs Review Count - Hotel', fontweight='bold')
axes[0].set_yscale('log')

rating_bucket = pd.cut(df_hotel['rating'], bins=[0, 2, 3, 3.5, 4, 4.5, 5],
                       labels=['<2', '2-3', '3-3.5', '3.5-4', '4-4.5', '4-5'])
valid_mask = rating_bucket.notna()
if valid_mask.sum() > 0:
    sns.violinplot(x=rating_bucket[valid_mask], y=df_hotel.loc[valid_mask, 'review_count'], ax=axes[1],
                   palette='RdYlGn', inner='quartile')
axes[1].set_title('Review Count by Rating Bucket - Hotel', fontweight='bold')
axes[1].set_yscale('log')

plt.tight_layout()
plt.savefig('../outputs/figures/hotel_rating_vs_reviews.png', bbox_inches='tight')
plt.show()

print(f"\nRating Stats: mean={df_hotel['rating'].mean():.2f}, median={df_hotel['rating'].median():.2f}, "
      f"std={df_hotel['rating'].std():.2f}")
print(f"Review Stats: mean={df_hotel['review_count'].mean():.0f}, median={df_hotel['review_count'].median():.0f}, "
      f"max={df_hotel['review_count'].max():,}")

# ---
# ## 9. Popularity Analysis

# %%
print('=' * 70)
print(f'  POPULARITY ANALYSIS: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

df_hotel = compute_popularity(df_hotel)

print(f"Popularity score computed (0-1 scale)")
print(f"   Mean: {df_hotel['popularity_score'].mean():.3f}")
print(f"   Std:  {df_hotel['popularity_score'].std():.3f}")

# Top popular
top_popular = df_hotel.nlargest(10, 'popularity_score')[['name', 'rating', 'review_count', 'popularity_score']]
print('\nTop 10 Most Popular Hotels:')
print(top_popular.to_string(index=False))

# District popularity
dist_pop = df_hotel.groupby('district').agg(
    avg_popularity=('popularity_score', 'mean'),
    count=('name', 'count'),
    avg_rating=('rating', 'mean')
).sort_values('avg_popularity', ascending=False).head(15)

fig, ax = plt.subplots(figsize=(12, 7))
dist_pop['avg_popularity'].plot(kind='barh', ax=ax, color=sns.color_palette('YlOrRd', len(dist_pop)))
ax.set_title('Top 15 Districts by Avg Popularity - Hotel', fontweight='bold')
ax.set_xlabel('Avg Popularity Score')
for i, v in enumerate(dist_pop['avg_popularity'].values):
    ax.text(v + 0.005, i, f'{v:.3f}', va='center', fontsize=10)
plt.tight_layout()
plt.savefig('../outputs/figures/hotel_district_popularity.png', bbox_inches='tight')
plt.show()

# ---
# ## 10. Location Intelligence

# %%
print('=' * 70)
print(f'  LOCATION INTELLIGENCE: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

area_stats = df_hotel.groupby('area').agg(
    num_places=('name', 'count'),
    avg_rating=('rating', 'mean'),
    total_reviews=('review_count', 'sum'),
    avg_popularity=('popularity_score', 'mean')
).sort_values('num_places', ascending=False)

significant_areas = area_stats[area_stats['num_places'] >= 3].head(15)
print(f'\nSignificant Areas for Hotels (>=3 places):')
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

    plt.suptitle('Area Comparison - Hotels', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('../outputs/figures/hotel_area_comparison.png', bbox_inches='tight')
    plt.show()

# ---
# ## 11. Correlation Analysis

# %%
print('=' * 70)
print(f'  CORRELATION ANALYSIS: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

corr_cols = ['rating', 'review_count', 'photo_count', 'review_text_count',
             'avg_review_length', 'popularity_score', 'has_hours']
corr_cols = [c for c in corr_cols if c in df_hotel.columns]

corr_matrix = df_hotel[corr_cols].corr()

fig, ax = plt.subplots(figsize=(12, 10))
mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
sns.heatmap(corr_matrix, mask=mask, annot=True, fmt='.3f', cmap='RdBu_r',
            center=0, vmin=-1, vmax=1, ax=ax, linewidths=0.5,
            square=True, cbar_kws={'shrink': 0.8})
ax.set_title('Correlation Matrix - Hotel', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig('../outputs/figures/hotel_correlation_heatmap.png', bbox_inches='tight')
plt.show()

print('Key Correlations (hotel):')
for pair in [('rating', 'review_count'), ('rating', 'photo_count'), ('review_count', 'photo_count')]:
    if pair[0] in df_hotel.columns and pair[1] in df_hotel.columns:
        corr = df_hotel[pair[0]].corr(df_hotel[pair[1]])
        print(f"  {pair[0]:20s} x {pair[1]:20s}: r = {corr:+.3f}")

# ---
# ## 12. Outlier Detection

# %%
print('=' * 70)
print(f'  OUTLIER DETECTION: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

print('IQR Outlier Detection (hotel):')
detect_outliers_iqr(df_hotel['review_count'], 'review_count')
detect_outliers_iqr(df_hotel['rating'], 'rating')

# Z-score
df_hotel['review_zscore'] = zscore(df_hotel['review_count'].fillna(0))
z_outliers = df_hotel[df_hotel['review_zscore'].abs() > 3]
print(f"Z-Score outliers (|z| > 3) in review_count: {len(z_outliers):,}")
print(f"   Max z-score: {df_hotel['review_zscore'].max():.2f}")
print(f"   Min z-score: {df_hotel['review_zscore'].min():.2f}")

fig, axes = plt.subplots(1, 2, figsize=(16, 6))

Q1, Q3 = df_hotel['review_count'].quantile(0.25), df_hotel['review_count'].quantile(0.75)
IQR = Q3 - Q1
lower, upper = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR

axes[0].boxplot(df_hotel['review_count'].dropna(), vert=True, patch_artist=True,
                boxprops=dict(facecolor='#4C72B0', alpha=0.6))
axes[0].axhline(upper, color='red', linestyle='--', label=f'Upper fence: {upper:,.0f}')
axes[0].axhline(lower, color='red', linestyle='--', label=f'Lower fence: {lower:,.0f}')
axes[0].set_title('Review Count - Outliers - Hotel', fontweight='bold')
axes[0].legend()

axes[1].hist(df_hotel['review_zscore'].dropna(), bins=50, color='#55A868', edgecolor='white', alpha=0.8)
axes[1].axvline(3, color='red', linestyle='--', label='z = 3')
axes[1].axvline(-3, color='red', linestyle='--', label='z = -3')
axes[1].set_title('Review Count - Z-Score Distribution - Hotel', fontweight='bold')
axes[1].set_xlabel('Z-Score')
axes[1].legend()

plt.tight_layout()
plt.savefig('../outputs/figures/hotel_outlier_detection.png', bbox_inches='tight')
plt.show()

df_hotel.drop(columns=['review_zscore'], inplace=True)

# ---
# ## 13. Tourism Insights

# %%
print('=' * 70)
print(f'  TOURISM INSIGHTS: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

print('\nRating Distribution (hotel):')
for rating, count in df_hotel['rating'].value_counts().head(5).items():
    print(f"  Rating {rating}: {count:,} places ({count/len(df_hotel)*100:.1f}%)")

print('\nHighest-Engagement Districts (hotel):')
top_areas = df_hotel.groupby('district')['review_count'].sum().sort_values(ascending=False).head(5)
for area, reviews in top_areas.items():
    print(f"  {area}: {reviews:,.0f} total reviews")

hidden_gems = df_hotel[(df_hotel['rating'] >= 4.5) & (df_hotel['review_count'] < df_hotel['review_count'].quantile(0.25))]
print(f"\nHidden Gems (rating >= 4.5, low reviews): {len(hidden_gems):,} hotels")
if len(hidden_gems) > 0:
    print('Top hidden gems:')
    for _, row in hidden_gems.nlargest(5, 'rating').iterrows():
        print(f"  Rating: {row['rating']:.1f} - {row['name']} ({row['review_count']:,} reviews)")

# Recommendation candidates
print('\nTop Recommendation Candidates (hotel):')
top_recs = df_hotel.nlargest(10, 'rating')[['name', 'rating', 'review_count', 'popularity_score']]
print(top_recs.to_string(index=False))

# ---
# ## 14. Recommendation-Oriented Features

# %%
print('=' * 70)
print(f'  RECOMMENDATION SCORES: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

df_hotel = compute_recommendation_scores(df_hotel)

score_cols = ['family_friendly_score', 'budget_score', 'luxury_score']
print('\nRecommendation Feature Scores (hotel):')
print(df_hotel[score_cols].describe().round(3).to_string())

# Top recommendations by profile
print('\nTop 5 Recommendations by Profile (hotel):')
profiles = {
    'Family Trip': 'family_friendly_score',
    'Budget Traveler': 'budget_score',
    'Luxury Seeker': 'luxury_score',
}
for profile, score_col in profiles.items():
    top = df_hotel.nlargest(5, score_col)[['name', 'rating', 'review_count', score_col]]
    print(f"\n  {profile}:")
    for _, row in top.iterrows():
        print(f"    Rating: {row['rating']:.1f} | {row['name'][:45]:45s} | score={row[score_col]:.3f}")

# ---
# ## 15. Hotel-Specific Deep Dive

# ---
# ### 15a. Star Class Analysis

# %%
print('=' * 70)
print(f'  STAR CLASS ANALYSIS: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

star_data = df_hotel[df_hotel['star_class'].notna()].copy()
print(f'Hotels with star class data: {len(star_data):,} / {len(df_hotel):,} ({len(star_data)/len(df_hotel)*100:.1f}%)')

if len(star_data) > 0:
    star_counts = star_data['star_class'].value_counts().sort_index()
    print(f'\nStar Class Distribution:')
    for stars, count in star_counts.items():
        print(f'  {int(stars)}-star: {count:,} ({count/len(star_data)*100:.1f}%)')

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Distribution
    star_counts.plot(kind='bar', ax=axes[0], color=sns.color_palette('YlOrRd', len(star_counts)))
    axes[0].set_title('Star Class Distribution', fontweight='bold')
    axes[0].set_xlabel('Star Class')
    axes[0].set_ylabel('Count')

    # Rating by star class
    star_rating = star_data.groupby('star_class')['rating'].agg(['mean', 'median', 'std'])
    star_rating['mean'].plot(kind='bar', ax=axes[1], color='#4C72B0', alpha=0.8, yerr=star_rating['std'])
    axes[1].set_title('Average Rating by Star Class', fontweight='bold')
    axes[1].set_xlabel('Star Class')
    axes[1].set_ylabel('Rating')

    # Review count by star class
    star_reviews = star_data.groupby('star_class')['review_count'].agg(['mean', 'median'])
    star_reviews['median'].plot(kind='bar', ax=axes[2], color='#55A868', alpha=0.8)
    axes[2].set_title('Median Review Count by Star Class', fontweight='bold')
    axes[2].set_xlabel('Star Class')
    axes[2].set_ylabel('Median Reviews')

    plt.suptitle('Star Class Analysis - Hotels', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('../outputs/figures/hotel_star_class_analysis.png', bbox_inches='tight')
    plt.show()

    print('\nStar Class Stats:')
    print(star_data.groupby('star_class')[['rating', 'review_count']].agg(['mean', 'median', 'count']).round(2).to_string())

# ---
# ### 15b. Nightly Rate Analysis

# %%
print('=' * 70)
print(f'  NIGHTLY RATE ANALYSIS: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

rate_data = df_hotel[df_hotel['nightly_rate'].notna()].copy()
print(f'Hotels with nightly rate data: {len(rate_data):,} / {len(df_hotel):,} ({len(rate_data)/len(df_hotel)*100:.1f}%)')

if len(rate_data) > 0:
    # Parse nightly rate (remove $ and convert to float)
    rate_data['nightly_rate_numeric'] = rate_data['nightly_rate'].str.replace('$', '', regex=False).str.replace(',', '', regex=False).astype(float)

    print(f'\nNightly Rate Stats (parsed):')
    print(f"  Mean: ${rate_data['nightly_rate_numeric'].mean():.2f}")
    print(f"  Median: ${rate_data['nightly_rate_numeric'].median():.2f}")
    print(f"  Min: ${rate_data['nightly_rate_numeric'].min():.2f}")
    print(f"  Max: ${rate_data['nightly_rate_numeric'].max():.2f}")
    print(f"  Std: ${rate_data['nightly_rate_numeric'].std():.2f}")

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Distribution
    axes[0].hist(rate_data['nightly_rate_numeric'].dropna(), bins=40, color='#E6A817', edgecolor='white', alpha=0.8)
    axes[0].axvline(rate_data['nightly_rate_numeric'].mean(), color='red', linestyle='--', label=f"Mean: ${rate_data['nightly_rate_numeric'].mean():.2f}")
    axes[0].axvline(rate_data['nightly_rate_numeric'].median(), color='green', linestyle='--', label=f"Median: ${rate_data['nightly_rate_numeric'].median():.2f}")
    axes[0].set_title('Nightly Rate Distribution', fontweight='bold')
    axes[0].set_xlabel('Nightly Rate ($)')
    axes[0].set_ylabel('Count')
    axes[0].legend()

    # Rate vs Rating
    axes[1].scatter(rate_data['nightly_rate_numeric'], rate_data['rating'], alpha=0.4, s=15, c='#4C72B0')
    axes[1].set_xlabel('Nightly Rate ($)')
    axes[1].set_ylabel('Rating')
    axes[1].set_title('Nightly Rate vs Rating', fontweight='bold')

    # Rate by neighborhood
    top_neighborhoods = rate_data['neighborhood'].value_counts().head(10).index
    rate_by_neighborhood = rate_data[rate_data['neighborhood'].isin(top_neighborhoods)].groupby('neighborhood')['nightly_rate_numeric'].median().sort_values(ascending=True)
    rate_by_neighborhood.plot(kind='barh', ax=axes[2], color='#E6A817', alpha=0.8)
    axes[2].set_title('Median Nightly Rate by Neighborhood', fontweight='bold')
    axes[2].set_xlabel('Median Rate ($)')

    plt.suptitle('Nightly Rate Analysis - Hotels', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('../outputs/figures/hotel_nightly_rate_analysis.png', bbox_inches='tight')
    plt.show()

    # Price tiers
    rate_data['price_tier'] = pd.cut(rate_data['nightly_rate_numeric'],
                                      bins=[0, 50, 100, 200, 500, float('inf')],
                                      labels=['Budget (<$50)', 'Economy ($50-100)', 'Mid-Range ($100-200)', 'Premium ($200-500)', 'Luxury ($500+)'])
    print('\nPrice Tier Distribution:')
    tier_counts = rate_data['price_tier'].value_counts().sort_index()
    for tier, count in tier_counts.items():
        print(f'  {tier}: {count:,} ({count/len(rate_data)*100:.1f}%)')

    print('\nPrice Tier Stats:')
    print(rate_data.groupby('price_tier')[['rating', 'review_count', 'nightly_rate_numeric']].agg(['mean', 'median', 'count']).round(2).to_string())

# ---
# ### 15c. Amenities Analysis

# %%
print('=' * 70)
print(f'  AMENITIES ANALYSIS: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

amenity_data = df_hotel[df_hotel['amenities'].notna()].copy()
print(f'Hotels with amenities data: {len(amenity_data):,} / {len(df_hotel):,} ({len(amenity_data)/len(df_hotel)*100:.1f}%)')

if len(amenity_data) > 0:
    # Flatten all amenities
    all_amenities = []
    for amenities in amenity_data['amenities']:
        if isinstance(amenities, list):
            all_amenities.extend(amenities)
        elif isinstance(amenities, str):
            all_amenities.append(amenities)

    amenity_counts = Counter(all_amenities)
    top_amenities = pd.Series(amenity_counts).sort_values(ascending=False).head(20)

    print(f'\nTop 20 Most Common Amenities:')
    for amenity, count in top_amenities.items():
        print(f'  {amenity:40s} {count:>5,} ({count/len(amenity_data)*100:.1f}%)')

    fig, axes = plt.subplots(1, 2, figsize=(18, 8))

    top_amenities.plot(kind='barh', ax=axes[0], color=sns.color_palette('viridis', len(top_amenities)))
    axes[0].set_title('Top 20 Hotel Amenities', fontweight='bold')
    axes[0].set_xlabel('Count')
    axes[0].invert_yaxis()

    # Amenities count per hotel
    amenity_data['amenity_count'] = amenity_data['amenities'].apply(lambda x: len(x) if isinstance(x, list) else 0)
    axes[1].hist(amenity_data['amenity_count'], bins=30, color='#8172B2', edgecolor='white', alpha=0.8)
    axes[1].set_title('Amenities Count per Hotel', fontweight='bold')
    axes[1].set_xlabel('Number of Amenities')
    axes[1].set_ylabel('Count')

    plt.suptitle('Amenities Analysis - Hotels', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('../outputs/figures/hotel_amenities_analysis.png', bbox_inches='tight')
    plt.show()

    # Amenity impact on rating
    amenity_data['amenity_count'] = amenity_data['amenities'].apply(lambda x: len(x) if isinstance(x, list) else 0)
    print(f'\nAmenity Count vs Rating:')
    print(amenity_data.groupby('amenity_count')['rating'].agg(['mean', 'median', 'count']).head(15).round(2).to_string())

# ---
# ### 15d. Booking Platforms Analysis

# %%
print('=' * 70)
print(f'  BOOKING PLATFORMS ANALYSIS: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

booking_data = df_hotel[df_hotel['booking_platforms'].notna()].copy()
print(f'Hotels with booking platform data: {len(booking_data):,} / {len(df_hotel):,} ({len(booking_data)/len(df_hotel)*100:.1f}%)')

if len(booking_data) > 0:
    # Flatten all booking platforms
    all_platforms = []
    for platforms in booking_data['booking_platforms']:
        if isinstance(platforms, list):
            all_platforms.extend(platforms)
        elif isinstance(platforms, str):
            all_platforms.append(platforms)

    platform_counts = Counter(all_platforms)
    top_platforms = pd.Series(platform_counts).sort_values(ascending=False)

    print(f'\nBooking Platform Distribution:')
    for platform, count in top_platforms.items():
        print(f'  {platform:40s} {count:>5,} ({count/len(booking_data)*100:.1f}%)')

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    top_platforms.plot(kind='barh', ax=axes[0], color=sns.color_palette('Set2', len(top_platforms)))
    axes[0].set_title('Booking Platform Distribution', fontweight='bold')
    axes[0].set_xlabel('Count')
    axes[0].invert_yaxis()

    # Platform count per hotel
    booking_data['platform_count'] = booking_data['booking_platforms'].apply(lambda x: len(x) if isinstance(x, list) else 0)
    axes[1].hist(booking_data['platform_count'], bins=range(0, booking_data['platform_count'].max() + 2),
                 color='#C44E52', edgecolor='white', alpha=0.8)
    axes[1].set_title('Booking Platforms Count per Hotel', fontweight='bold')
    axes[1].set_xlabel('Number of Platforms')
    axes[1].set_ylabel('Count')

    plt.suptitle('Booking Platforms Analysis - Hotels', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('../outputs/figures/hotel_booking_platforms_analysis.png', bbox_inches='tight')
    plt.show()

# ---
# ### 15e. Neighborhood Analysis

# %%
print('=' * 70)
print(f'  NEIGHBORHOOD ANALYSIS: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

neighborhood_data = df_hotel[df_hotel['neighborhood'].notna()].copy()
print(f'Hotels with neighborhood data: {len(neighborhood_data):,} / {len(df_hotel):,} ({len(neighborhood_data)/len(df_hotel)*100:.1f}%)')

if len(neighborhood_data) > 0:
    neighborhood_stats = neighborhood_data.groupby('neighborhood').agg(
        count=('name', 'count'),
        avg_rating=('rating', 'mean'),
        avg_reviews=('review_count', 'mean'),
        avg_stars=('star_class', 'mean'),
    ).sort_values('count', ascending=False)

    print('\nTop Neighborhoods:')
    print(neighborhood_stats.head(15).round(2).to_string())

    fig, axes = plt.subplots(1, 2, figsize=(18, 8))

    top_neighborhoods = neighborhood_stats.head(10)
    top_neighborhoods['count'].plot(kind='barh', ax=axes[0], color='#4C72B0')
    axes[0].set_title('Hotels per Neighborhood', fontweight='bold')
    axes[0].set_xlabel('Count')

    top_neighborhoods.sort_values('avg_rating').plot(kind='barh', y='avg_rating', ax=axes[1],
                                                      color='#55A868', legend=False)
    axes[1].set_title('Avg Rating by Neighborhood', fontweight='bold')
    axes[1].set_xlabel('Avg Rating')

    plt.suptitle('Neighborhood Analysis - Hotels', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('../outputs/figures/hotel_neighborhood_analysis.png', bbox_inches='tight')
    plt.show()

# ---
# ## 16. Interactive Dashboard Elements

# %%
print('=' * 70)
print(f'  INTERACTIVE DASHBOARD: HOTEL ({len(df_hotel):,} places)')
print('=' * 70)

# Rating distribution box plot
fig = px.box(
    df_hotel, y='rating',
    title='Hotel - Rating Distribution (Interactive)',
    hover_data=['name', 'review_count'], height=500
)
fig.write_html('../outputs/figures/hotel_interactive_rating_boxplot.html')

# Scatter by subtype
if 'subtype' in df_hotel.columns and df_hotel['subtype'].notna().sum() > 0:
    fig = px.scatter(
        df_hotel.sample(min(2000, len(df_hotel)), random_state=42),
        x='subtype', y='rating', color='district',
        size='review_count', size_max=20, hover_name='name',
        hover_data={'subtype': True, 'rating': True, 'review_count': True, 'district': True},
        title='Hotels - Subtype x Rating x District', height=600,
    )
    fig.update_layout(xaxis_tickangle=-45)
    fig.write_html('../outputs/figures/hotel_interactive_subtype_rating.html')
    print('Subtype scatter saved: hotel_interactive_subtype_rating.html')

# Star class interactive chart
if 'star_class' in df_hotel.columns and df_hotel['star_class'].notna().sum() > 0:
    star_chart_data = df_hotel[df_hotel['star_class'].notna()].copy()
    star_chart_data['star_class'] = star_chart_data['star_class'].astype(int).astype(str)
    fig = px.box(
        star_chart_data, x='star_class', y='rating',
        title='Hotels - Rating by Star Class (Interactive)',
        hover_data=['name', 'review_count', 'nightly_rate'], height=500
    )
    fig.write_html('../outputs/figures/hotel_interactive_star_rating.html')
    print('Star class interactive chart saved: hotel_interactive_star_rating.html')

print('Dashboard saved for hotel')

# ---
# ## 17. Automated Report Generation

# %%
report_data = {
    'Total Hotels': f"{len(df_hotel):,}",
    'Avg Rating': f"{df_hotel['rating'].mean():.2f}",
    'Median Review Count': f"{df_hotel['review_count'].median():,.0f}",
    'Total Reviews': f"{df_hotel['review_count'].sum():,.0f}",
    'Unique Districts': f"{df_hotel['district'].nunique():,}",
    'Hidden Gems': len(df_hotel[(df_hotel['rating'] >= 4.5) & (df_hotel['review_count'] < df_hotel['review_count'].quantile(0.25))]),
    'With Star Class': len(df_hotel[df_hotel['star_class'].notna()]),
    'With Nightly Rate': len(df_hotel[df_hotel['nightly_rate'].notna()]),
}

html_report = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Cairo Hotels EDA Report - TourMate AI</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; background: #f8f9fa; color: #333; }}
        .header {{ background: linear-gradient(135deg, #1a237e, #0d47a1); color: white; padding: 40px; border-radius: 12px; margin-bottom: 30px; }}
        .header h1 {{ margin: 0; font-size: 2.2em; }}
        .header p {{ margin: 8px 0 0; opacity: 0.9; font-size: 1.1em; }}
        .section {{ background: white; border-radius: 10px; padding: 25px 30px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .section h2 {{ color: #1a237e; border-bottom: 2px solid #e8eaf6; padding-bottom: 8px; }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .kpi {{ background: #e8eaf6; border-radius: 8px; padding: 20px; text-align: center; }}
        .kpi .value {{ font-size: 2em; font-weight: bold; color: #1a237e; }}
        .kpi .label {{ font-size: 0.9em; color: #555; margin-top: 5px; }}
        .insight {{ background: #e8f5e9; border-left: 4px solid #4caf50; padding: 12px 18px; margin: 10px 0; border-radius: 0 8px 8px 0; }}
        .footer {{ text-align: center; color: #999; padding: 20px; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Cairo Hotels - EDA Report</h1>
        <p>TourMate AI - Data Intelligence - Generated June 2026</p>
    </div>
    <div class="section">
        <h2>Executive Summary</h2>
        <div class="kpi-grid">
            <div class="kpi"><div class="value">{report_data['Total Hotels']}</div><div class="label">Total Hotels</div></div>
            <div class="kpi"><div class="value">{report_data['Avg Rating']}</div><div class="label">Avg Rating</div></div>
            <div class="kpi"><div class="value">{report_data['Total Reviews']}</div><div class="label">Total Reviews</div></div>
            <div class="kpi"><div class="value">{report_data['Unique Districts']}</div><div class="label">Districts</div></div>
            <div class="kpi"><div class="value">{report_data['Hidden Gems']}</div><div class="label">Hidden Gems</div></div>
            <div class="kpi"><div class="value">{report_data['With Star Class']}</div><div class="label">With Star Class</div></div>
            <div class="kpi"><div class="value">{report_data['With Nightly Rate']}</div><div class="label">With Nightly Rate</div></div>
        </div>
    </div>
    <div class="section">
        <h2>Key Findings</h2>
        <div class="insight"><b>Star Class:</b> Detailed analysis of hotel ratings by star classification reveals quality tiers.</div>
        <div class="insight"><b>Nightly Rates:</b> Price analysis across neighborhoods for budget and luxury travelers.</div>
        <div class="insight"><b>Amenities:</b> Most common amenities and their correlation with guest satisfaction.</div>
        <div class="insight"><b>Booking Platforms:</b> Distribution of booking availability across major platforms.</div>
    </div>
    <div class="section">
        <h2>Recommendations for TourMate AI</h2>
        <ul>
            <li>Use star class and nightly rate data for price-tier recommendations.</li>
            <li>Leverage amenity data for preference-based hotel matching.</li>
            <li>Highlight hidden gems with high ratings but low review counts.</li>
            <li>Use neighborhood analysis for location-based recommendations.</li>
        </ul>
    </div>
    <div class="footer">
        <p>Generated by TourMate AI Data Science Team - June 2026</p>
    </div>
</body>
</html>
"""

with open('../outputs/reports/hotels_eda_report.html', 'w', encoding='utf-8') as f:
    f.write(html_report)

print('HTML report saved to outputs/reports/hotels_eda_report.html')

# ---
# ## 18. Notebook Summary

# %%
print('=' * 70)
print('CAIRO HOTELS EDA - COMPLETED SUCCESSFULLY')
print('=' * 70)
print(f'\nTotal Hotels Analyzed: {len(df_hotel):,}')
print(f'Avg Rating: {df_hotel["rating"].mean():.2f} | Avg Reviews: {df_hotel["review_count"].mean():.0f}')
print(f'\nOutput Files:')
print(f'  outputs/figures/ - hotel-specific visualizations saved')
print(f'  outputs/reports/ - HTML report')
print('\nAll analyses complete. Notebook ready for review.')

# ---
# *This notebook was generated by TourMate AI Data Science Team - June 2026*
# *Hotels-focused EDA for Cairo, Egypt*
