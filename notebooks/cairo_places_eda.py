#!/usr/bin/env python
# coding: utf-8

# # Cairo Places - Exploratory Data Analysis (EDA) - Per Category
# ## TourMate AI - Data Intelligence Report
#
# **Date:** June 2026
# **Analyst:** TourMate AI Data Science Team
# **Dataset:** `data/cairo_places_filled (9).json` - 6,600+ places across Cairo, Egypt
#
# This notebook performs **category-separated** EDA for **Hotels**, **Restaurants**, and **Attractions**.
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
print(f'City: {df["city"].unique()}')
print(f'Country: {df["country"].unique()}')

# Identify hashable (non-nested) columns for pandas operations
nested_fields = {'photos', 'reviews', 'hours'}
hashable_cols = [c for c in df.columns if c not in nested_fields]
for c in list(hashable_cols):
    if df[c].dtype == 'object' and df[c].apply(lambda x: isinstance(x, (list, dict))).any():
        hashable_cols.remove(c)

print(f'Hashable columns: {len(hashable_cols)} of {len(df.columns)}')

# %%
df.head()

# %%
df['category'].value_counts()

# %%
df['city'].value_counts()

# %%
df['country'].value_counts()

# %%
df.info()

# %%
df[hashable_cols].describe(include='all')

# ---
# ## 2. Split Data by Category

# %%
df_hotel = df[df['category'] == 'hotel'].copy().reset_index(drop=True)
df_restaurant = df[df['category'] == 'restaurant'].copy().reset_index(drop=True)
df_attractions = df[df['category'] == 'attractions'].copy().reset_index(drop=True)

categories = {
    'hotel': df_hotel,
    'restaurant': df_restaurant,
    'attractions': df_attractions,
}

print('Dataset split by category:')
for cat_name, cat_df in categories.items():
    print(f'  {cat_name:15s}: {len(cat_df):>5,} places')

# ---
# ## 3. Derive Features (on full dataset, then used per-category)

# %%
if 'photos' in df.columns:
    df['photo_count'] = df['photos'].apply(lambda x: len(x) if isinstance(x, list) else 0)

if 'reviews' in df.columns:
    df['review_text_count'] = df['reviews'].apply(lambda x: len(x) if isinstance(x, list) else 0)
    df['avg_review_length'] = df['reviews'].apply(
        lambda x: np.mean([len(r) for r in x]) if isinstance(x, list) and len(x) > 0 else 0
    )

if 'hours' in df.columns:
    df['has_hours'] = df['hours'].apply(lambda x: 1 if isinstance(x, dict) and len(x) > 0 else 0)

# District / area extraction
def extract_location(address, depth=2):
    """Extract a meaningful location part from an address string."""
    if not isinstance(address, str):
        return 'Unknown'
    parts = [p.strip() for p in address.split(',')]
    skip = {'cairo', 'giza', 'egypt', 'governorate', 'cairo governorate', 'giza governorate'}
    for p in reversed(parts[1:depth+2]):
        if p.lower() in skip or any(kw in p.lower() for kw in skip):
            continue
        if len(p) > 3:
            return p
    return parts[1] if len(parts) > 1 else 'Unknown'

df['district'] = df['address'].apply(extract_location)
df['area'] = df['address'].apply(lambda x: extract_location(x, depth=3))

# Re-split after deriving features
df_hotel = df[df['category'] == 'hotel'].copy().reset_index(drop=True)
df_restaurant = df[df['category'] == 'restaurant'].copy().reset_index(drop=True)
df_attractions = df[df['category'] == 'attractions'].copy().reset_index(drop=True)

categories = {
    'hotel': df_hotel,
    'restaurant': df_restaurant,
    'attractions': df_attractions,
}

print('Derived features created: photo_count, review_text_count, avg_review_length, has_hours, district, area')

# ---
# ## 4. Data Quality Assessment (Per Category)

# %%
for cat_name, cat_df in categories.items():
    print(f'\n{"="*70}')
    print(f'  DATA QUALITY: {cat_name.upper()} ({len(cat_df):,} places)')
    print(f'{"="*70}')

    cat_hashable = [c for c in hashable_cols if c in cat_df.columns]

    # Missing values
    missing = pd.DataFrame({
        'column': cat_df[cat_hashable].columns,
        'missing_count': cat_df[cat_hashable].isnull().sum().values,
        'missing_pct': (cat_df[cat_hashable].isnull().sum().values / len(cat_df) * 100).round(2)
    }).sort_values('missing_pct', ascending=False).reset_index(drop=True)

    missing = missing[missing['missing_count'] > 0]

    if len(missing) > 0:
        print(f'\nColumns with Missing Values ({cat_name}):')
        print(missing.to_string(index=False))
        fig, ax = plt.subplots(figsize=(14, 6))
        sns.heatmap(cat_df[cat_hashable].isnull(), cbar=True, yticklabels=False, cmap='YlOrRd', ax=ax)
        ax.set_title(f'Missing Values Heatmap - {cat_name.title()}', fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig(f'../outputs/figures/{cat_name}_missing_values_heatmap.png', bbox_inches='tight')
        plt.show()
    else:
        print(f'No missing values found for {cat_name}!')

    # Duplicates
    exact_dups = cat_df[cat_hashable].duplicated().sum()
    print(f'\nExact duplicate rows: {exact_dups}')
    if 'id' in cat_df.columns:
        id_dups = cat_df['id'].duplicated().sum()
        print(f'Duplicate id values: {id_dups}')

    # Consistency checks
    issues = []
    if 'lat' in cat_df.columns and 'lon' in cat_df.columns:
        bad_coords = cat_df[(cat_df['lat'] < 28) | (cat_df['lat'] > 32) | (cat_df['lon'] < 29) | (cat_df['lon'] > 33)]
        if len(bad_coords) > 0:
            issues.append(f'[WARN] {len(bad_coords)} rows with coordinates outside Cairo area')
    if 'rating' in cat_df.columns:
        bad_ratings = cat_df[(cat_df['rating'] < 0) | (cat_df['rating'] > 5)]
        if len(bad_ratings) > 0:
            issues.append(f'[WARN] {len(bad_ratings)} rows with rating outside [0, 5]')
    if 'review_count' in cat_df.columns:
        neg_reviews = cat_df[cat_df['review_count'] < 0]
        if len(neg_reviews) > 0:
            issues.append(f'[WARN] {len(neg_reviews)} rows with negative review_count')

    if issues:
        print('\n'.join(issues))
    else:
        print('No data consistency issues found!')

    # Quality report
    quality_report = {
        'Total Records': len(cat_df),
        'Total Columns': len(cat_df.columns),
        'Exact Duplicates': int(exact_dups),
        'Columns with Missing Data': int((cat_df[cat_hashable].isnull().sum() > 0).sum()),
        'Total Missing Cells': int(cat_df[cat_hashable].isnull().sum().sum()),
        'Memory Usage (MB)': round(cat_df.memory_usage(deep=True).sum() / 1024**2, 1),
    }
    report_df = pd.DataFrame.from_dict(quality_report, orient='index', columns=['Value'])
    print(f'\nDATA QUALITY REPORT - {cat_name.upper()}')
    print('=' * 45)
    print(report_df.to_string())

# ---
# ## 5. Univariate Analysis - Numerical Variables (Per Category)

# %%
for cat_name, cat_df in categories.items():
    print(f'\n{"="*70}')
    print(f'  UNIVARIATE NUMERICAL: {cat_name.upper()} ({len(cat_df):,} places)')
    print(f'{"="*70}')

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Histogram
    axes[0].hist(cat_df['rating'].dropna(), bins=30, color='#4C72B0', edgecolor='white', alpha=0.8)
    axes[0].axvline(cat_df['rating'].mean(), color='red', linestyle='--', label=f"Mean: {cat_df['rating'].mean():.2f}")
    axes[0].axvline(cat_df['rating'].median(), color='green', linestyle='--', label=f"Median: {cat_df['rating'].median():.2f}")
    axes[0].set_title('Rating Distribution', fontweight='bold')
    axes[0].set_xlabel('Rating')
    axes[0].set_ylabel('Count')
    axes[0].legend()

    # KDE
    cat_df['rating'].dropna().plot(kind='kde', ax=axes[1], color='#4C72B0', linewidth=2)
    axes[1].set_title('Rating KDE', fontweight='bold')
    axes[1].set_xlabel('Rating')

    # Boxplot
    axes[2].boxplot(cat_df['rating'].dropna(), vert=True, patch_artist=True,
                    boxprops=dict(facecolor='#4C72B0', alpha=0.6))
    axes[2].set_title('Rating Boxplot', fontweight='bold')
    axes[2].set_ylabel('Rating')

    plt.suptitle(f'Rating Distribution - {cat_name.title()}', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(f'../outputs/figures/{cat_name}_rating_distribution.png', bbox_inches='tight')
    plt.show()

    print(f"Rating Stats: mean={cat_df['rating'].mean():.2f}, median={cat_df['rating'].median():.2f}, "
          f"std={cat_df['rating'].std():.2f}, skew={cat_df['rating'].skew():.2f}")

# %%
for cat_name, cat_df in categories.items():
    print(f'\n{"="*70}')
    print(f'  REVIEW COUNT ANALYSIS: {cat_name.upper()} ({len(cat_df):,} places)')
    print(f'{"="*70}')

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    reviews = cat_df['review_count'].dropna()
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

    plt.suptitle(f'Review Count Distribution - {cat_name.title()}', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(f'../outputs/figures/{cat_name}_review_count_distribution.png', bbox_inches='tight')
    plt.show()

    print(f"Review Stats: mean={reviews.mean():.0f}, median={reviews.median():.0f}, "
          f"max={reviews.max():,}, places with 0 reviews: {(reviews == 0).sum()}")

# ---
# ## 6. Univariate Analysis - Categorical / Subcategory Variables (Per Category)

# %%
for cat_name, cat_df in categories.items():
    print(f'\n{"="*70}')
    print(f'  SUBCATEGORY DISTRIBUTION: {cat_name.upper()} ({len(cat_df):,} places)')
    print(f'{"="*70}')

    fig, axes = plt.subplots(1, 2, figsize=(18, 7))

    # Category label distribution
    if 'category_label' in cat_df.columns:
        label_counts = cat_df['category_label'].value_counts()
        label_counts.plot(kind='barh', ax=axes[0], color=sns.color_palette('viridis', len(label_counts)))
        axes[0].set_title(f'Category Labels - {cat_name.title()}', fontweight='bold')
        axes[0].set_xlabel('Count')
        for i, v in enumerate(label_counts.values):
            axes[0].text(v + 2, i, f'{v:,}', va='center', fontsize=10)

    # Subtype distribution
    if 'subtype' in cat_df.columns:
        subtype_counts = cat_df['subtype'].dropna().value_counts()
        if len(subtype_counts) > 0:
            top_n = 10
            top_subtypes = subtype_counts.head(top_n)
            other = subtype_counts[top_n:].sum() if len(subtype_counts) > top_n else 0
            pie_data = pd.concat([top_subtypes, pd.Series({'Other': other})]) if other > 0 else top_subtypes
            colors = sns.color_palette('viridis', len(pie_data))
            axes[1].pie(pie_data, labels=pie_data.index, autopct='%1.1f%%',
                        colors=colors, startangle=90, pctdistance=0.85)
            axes[1].set_title(f'Subtype Proportions - {cat_name.title()}', fontweight='bold')
        else:
            axes[1].text(0.5, 0.5, 'No subtype data', ha='center', va='center', fontsize=14)
            axes[1].set_title(f'Subtype Proportions - {cat_name.title()}', fontweight='bold')
    else:
        axes[1].text(0.5, 0.5, 'No subtype column', ha='center', va='center', fontsize=14)
        axes[1].set_title(f'Subtype Proportions - {cat_name.title()}', fontweight='bold')

    plt.suptitle(f'Categorical Distribution - {cat_name.title()}', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(f'../outputs/figures/{cat_name}_category_distribution.png', bbox_inches='tight')
    plt.show()

    print(f'\nCategory Label Counts ({cat_name}):')
    if 'category_label' in cat_df.columns:
        for label, count in cat_df['category_label'].value_counts().items():
            print(f'  {label:40s} {count:>5,} ({count/len(cat_df)*100:.1f}%)')

    if 'subtype' in cat_df.columns:
        print(f'\nSubtype Counts ({cat_name}):')
        for st, count in cat_df['subtype'].value_counts().head(15).items():
            print(f'  {str(st):40s} {count:>5,} ({count/len(cat_df)*100:.1f}%)')

# %%
# District distribution per category
for cat_name, cat_df in categories.items():
    print(f'\n{"="*70}')
    print(f'  DISTRICT DISTRIBUTION: {cat_name.upper()} ({len(cat_df):,} places)')
    print(f'{"="*70}')

    dist_counts = cat_df['district'].value_counts().head(15)

    fig, ax = plt.subplots(figsize=(14, 7))
    dist_counts.plot(kind='barh', ax=ax, color=sns.color_palette('rocket', len(dist_counts)))
    ax.set_title(f'Top 15 Districts - {cat_name.title()}', fontweight='bold')
    ax.set_xlabel('Count')
    for i, v in enumerate(dist_counts.values):
        ax.text(v + 2, i, f'{v:,}', va='center', fontsize=10)
    plt.tight_layout()
    plt.savefig(f'../outputs/figures/{cat_name}_district_distribution.png', bbox_inches='tight')
    plt.show()

# ---
# ## 7. Geographical Analysis (Per Category)

# %%
cairo_center = [df['lat'].median(), df['lon'].median()]

for cat_name, cat_df in categories.items():
    print(f'\n{"="*70}')
    print(f'  GEOGRAPHICAL ANALYSIS: {cat_name.upper()} ({len(cat_df):,} places)')
    print(f'{"="*70}')

    # Interactive Folium map
    sample_size = min(2000, len(cat_df))
    df_sample = cat_df.sample(n=sample_size, random_state=42)

    m = folium.Map(location=cairo_center, zoom_start=12, tiles='CartoDB positron')
    marker_cluster = MarkerCluster().add_to(m)

    for _, row in df_sample.iterrows():
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=4, color='#4C72B0', fill=True, fill_opacity=0.7,
            popup=folium.Popup(
                f"<b>{row['name']}</b><br>"
                f"Category: {row['category']}<br>"
                f"Rating: {row.get('rating', 'N/A')}<br>"
                f"Reviews: {row.get('review_count', 0):,}",
                max_width=250
            ),
        ).add_to(marker_cluster)

    m.save(f'../outputs/figures/{cat_name}_places_map.html')
    print(f'Interactive map saved: outputs/figures/{cat_name}_places_map.html ({sample_size:,} places)')

    # Heatmap
    m_heat = folium.Map(location=cairo_center, zoom_start=12, tiles='CartoDB positron')
    heat_data = cat_df[['lat', 'lon']].dropna().values.tolist()
    HeatMap(heat_data, radius=15, blur=20, max_zoom=13).add_to(m_heat)
    m_heat.save(f'../outputs/figures/{cat_name}_density_heatmap.html')
    print(f'Density heatmap saved: outputs/figures/{cat_name}_density_heatmap.html')

    # High-rated places map
    high_rated = cat_df[cat_df['rating'] >= 4.5]
    if len(high_rated) > 0:
        high_rated_sample = high_rated.sample(min(1000, len(high_rated)), random_state=42)
        m_hr = folium.Map(location=cairo_center, zoom_start=12, tiles='CartoDB positron')
        for _, row in high_rated_sample.iterrows():
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=5, color='gold', fill=True, fill_opacity=0.8,
                popup=f"<b>{row['name']}</b><br>Rating: {row['rating']}<br>Reviews: {row.get('review_count', 0):,}",
            ).add_to(m_hr)
        m_hr.save(f'../outputs/figures/{cat_name}_high_rated_map.html')
        print(f'High-rated places map saved ({len(high_rated_sample):,} places)')

    # Static scatter map with Plotly
    fig = px.scatter_mapbox(
        cat_df.sample(min(2000, len(cat_df)), random_state=42),
        lat='lat', lon='lon',
        size='review_count', size_max=15,
        hover_name='name',
        hover_data={'rating': True, 'review_count': True},
        mapbox_style='carto-positron',
        center={'lat': cairo_center[0], 'lon': cairo_center[1]},
        zoom=11, title=f'{cat_name.title()} - Geographic Distribution', height=600,
    )
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
    fig.write_html(f'../outputs/figures/{cat_name}_plotly_map.html')
    print(f'Plotly map saved: outputs/figures/{cat_name}_plotly_map.html')

# ---
# ## 8. Rating & Review Analysis (Per Category)

# %%
for cat_name, cat_df in categories.items():
    print(f'\n{"="*70}')
    print(f'  RATING & REVIEW ANALYSIS: {cat_name.upper()} ({len(cat_df):,} places)')
    print(f'{"="*70}')

    # Top reviewed
    top_reviewed = cat_df.nlargest(10, 'review_count')[['name', 'rating', 'review_count', 'address']]
    print(f'\nTop 10 Most Reviewed {cat_name.title()}s:')
    print(top_reviewed.to_string(index=False))

    # Rating vs Review Count scatter
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    axes[0].scatter(cat_df['rating'], cat_df['review_count'], alpha=0.3, s=10, c=cat_df['rating'], cmap='RdYlGn')
    axes[0].set_xlabel('Rating')
    axes[0].set_ylabel('Review Count')
    axes[0].set_title(f'Rating vs Review Count - {cat_name.title()}', fontweight='bold')
    axes[0].set_yscale('log')

    rating_bucket = pd.cut(cat_df['rating'], bins=[0, 2, 3, 3.5, 4, 4.5, 5],
                           labels=['<2', '2-3', '3-3.5', '3.5-4', '4-4.5', '4-5'])
    valid_mask = rating_bucket.notna()
    if valid_mask.sum() > 0:
        sns.violinplot(x=rating_bucket[valid_mask], y=cat_df.loc[valid_mask, 'review_count'], ax=axes[1],
                       palette='RdYlGn', inner='quartile')
    axes[1].set_title(f'Review Count by Rating Bucket - {cat_name.title()}', fontweight='bold')
    axes[1].set_yscale('log')

    plt.tight_layout()
    plt.savefig(f'../outputs/figures/{cat_name}_rating_vs_reviews.png', bbox_inches='tight')
    plt.show()

    print(f"\nRating Stats: mean={cat_df['rating'].mean():.2f}, median={cat_df['rating'].median():.2f}, "
          f"std={cat_df['rating'].std():.2f}")
    print(f"Review Stats: mean={cat_df['review_count'].mean():.0f}, median={cat_df['review_count'].median():.0f}, "
          f"max={cat_df['review_count'].max():,}")

# ---
# ## 9. Popularity Analysis (Per Category)

# %%
for cat_name, cat_df in categories.items():
    print(f'\n{"="*70}')
    print(f'  POPULARITY ANALYSIS: {cat_name.upper()} ({len(cat_df):,} places)')
    print(f'{"="*70}')

    scaler = MinMaxScaler()

    cat_df['rating_norm'] = scaler.fit_transform(cat_df[['rating']].fillna(cat_df['rating'].median()))
    cat_df['review_norm'] = scaler.fit_transform(
        cat_df[['review_count']].fillna(cat_df['review_count'].median()).apply(np.log1p)
    )
    cat_df['popularity_score'] = (0.6 * cat_df['rating_norm'] + 0.4 * cat_df['review_norm']).round(4)

    print(f"Popularity score computed (0-1 scale)")
    print(f"   Mean: {cat_df['popularity_score'].mean():.3f}")
    print(f"   Std:  {cat_df['popularity_score'].std():.3f}")

    # Top popular
    top_popular = cat_df.nlargest(10, 'popularity_score')[['name', 'rating', 'review_count', 'popularity_score']]
    print(f'\nTop 10 Most Popular {cat_name.title()}s:')
    print(top_popular.to_string(index=False))

    # District popularity
    dist_pop = cat_df.groupby('district').agg(
        avg_popularity=('popularity_score', 'mean'),
        count=('name', 'count'),
        avg_rating=('rating', 'mean')
    ).sort_values('avg_popularity', ascending=False).head(15)

    fig, ax = plt.subplots(figsize=(12, 7))
    dist_pop['avg_popularity'].plot(kind='barh', ax=ax, color=sns.color_palette('YlOrRd', len(dist_pop)))
    ax.set_title(f'Top 15 Districts by Avg Popularity - {cat_name.title()}', fontweight='bold')
    ax.set_xlabel('Avg Popularity Score')
    for i, v in enumerate(dist_pop['avg_popularity'].values):
        ax.text(v + 0.005, i, f'{v:.3f}', va='center', fontsize=10)
    plt.tight_layout()
    plt.savefig(f'../outputs/figures/{cat_name}_district_popularity.png', bbox_inches='tight')
    plt.show()

# ---
# ## 10. Location Intelligence (Per Category)

# %%
for cat_name, cat_df in categories.items():
    print(f'\n{"="*70}')
    print(f'  LOCATION INTELLIGENCE: {cat_name.upper()} ({len(cat_df):,} places)')
    print(f'{"="*70}')

    scaler = MinMaxScaler()

    area_stats = cat_df.groupby('area').agg(
        num_places=('name', 'count'),
        avg_rating=('rating', 'mean'),
        total_reviews=('review_count', 'sum'),
        avg_popularity=('popularity_score', 'mean')
    ).sort_values('num_places', ascending=False)

    significant_areas = area_stats[area_stats['num_places'] >= 5].head(15)
    print(f'\nSignificant Areas for {cat_name.title()}s (>=5 places):')
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

        plt.suptitle(f'Area Comparison - {cat_name.title()}s', fontsize=15, fontweight='bold', y=1.02)
        plt.tight_layout()
        plt.savefig(f'../outputs/figures/{cat_name}_area_comparison.png', bbox_inches='tight')
        plt.show()

# ---
# ## 11. Correlation Analysis (Per Category)

# %%
for cat_name, cat_df in categories.items():
    print(f'\n{"="*70}')
    print(f'  CORRELATION ANALYSIS: {cat_name.upper()} ({len(cat_df):,} places)')
    print(f'{"="*70}')

    corr_cols = ['rating', 'review_count', 'photo_count', 'review_text_count',
                 'avg_review_length', 'popularity_score', 'has_hours']
    corr_cols = [c for c in corr_cols if c in cat_df.columns]

    corr_matrix = cat_df[corr_cols].corr()

    fig, ax = plt.subplots(figsize=(12, 10))
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
    sns.heatmap(corr_matrix, mask=mask, annot=True, fmt='.3f', cmap='RdBu_r',
                center=0, vmin=-1, vmax=1, ax=ax, linewidths=0.5,
                square=True, cbar_kws={'shrink': 0.8})
    ax.set_title(f'Correlation Matrix - {cat_name.title()}', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(f'../outputs/figures/{cat_name}_correlation_heatmap.png', bbox_inches='tight')
    plt.show()

    print(f'Key Correlations ({cat_name}):')
    for pair in [('rating', 'review_count'), ('rating', 'photo_count'), ('review_count', 'photo_count')]:
        if pair[0] in cat_df.columns and pair[1] in cat_df.columns:
            corr = cat_df[pair[0]].corr(cat_df[pair[1]])
            print(f"  {pair[0]:20s} x {pair[1]:20s}: r = {corr:+.3f}")

# ---
# ## 12. Outlier Detection (Per Category)

# %%
for cat_name, cat_df in categories.items():
    print(f'\n{"="*70}')
    print(f'  OUTLIER DETECTION: {cat_name.upper()} ({len(cat_df):,} places)')
    print(f'{"="*70}')

    def detect_outliers_iqr(series, name):
        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1
        lower = Q1 - 1.5 * IQR
        upper = Q3 + 1.5 * IQR
        outliers = series[(series < lower) | (series > upper)]
        print(f"  {name}: Q1={Q1:.1f}, Q3={Q3:.1f}, IQR={IQR:.1f}, "
              f"bounds=[{lower:.1f}, {upper:.1f}], outliers={len(outliers):,}")
        return outliers

    print(f'IQR Outlier Detection ({cat_name}):')
    detect_outliers_iqr(cat_df['review_count'], 'review_count')
    detect_outliers_iqr(cat_df['rating'], 'rating')

    # Z-score
    cat_df['review_zscore'] = zscore(cat_df['review_count'].fillna(0))
    z_outliers = cat_df[cat_df['review_zscore'].abs() > 3]
    print(f"Z-Score outliers (|z| > 3) in review_count: {len(z_outliers):,}")
    print(f"   Max z-score: {cat_df['review_zscore'].max():.2f}")
    print(f"   Min z-score: {cat_df['review_zscore'].min():.2f}")

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    Q1, Q3 = cat_df['review_count'].quantile(0.25), cat_df['review_count'].quantile(0.75)
    IQR = Q3 - Q1
    lower, upper = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR

    axes[0].boxplot(cat_df['review_count'].dropna(), vert=True, patch_artist=True,
                    boxprops=dict(facecolor='#4C72B0', alpha=0.6))
    axes[0].axhline(upper, color='red', linestyle='--', label=f'Upper fence: {upper:,.0f}')
    axes[0].axhline(lower, color='red', linestyle='--', label=f'Lower fence: {lower:,.0f}')
    axes[0].set_title(f'Review Count - Outliers - {cat_name.title()}', fontweight='bold')
    axes[0].legend()

    axes[1].hist(cat_df['review_zscore'].dropna(), bins=50, color='#55A868', edgecolor='white', alpha=0.8)
    axes[1].axvline(3, color='red', linestyle='--', label='z = 3')
    axes[1].axvline(-3, color='red', linestyle='--', label='z = -3')
    axes[1].set_title(f'Review Count - Z-Score Distribution - {cat_name.title()}', fontweight='bold')
    axes[1].set_xlabel('Z-Score')
    axes[1].legend()

    plt.tight_layout()
    plt.savefig(f'../outputs/figures/{cat_name}_outlier_detection.png', bbox_inches='tight')
    plt.show()

    cat_df.drop(columns=['review_zscore'], inplace=True)

# ---
# ## 13. Tourism Insights (Per Category)

# %%
for cat_name, cat_df in categories.items():
    print(f'\n{"="*70}')
    print(f'  TOURISM INSIGHTS: {cat_name.upper()} ({len(cat_df):,} places)')
    print(f'{"="*70}')

    print(f'\nRating Distribution ({cat_name}):')
    for rating, count in cat_df['rating'].value_counts().head(5).items():
        print(f"  Rating {rating}: {count:,} places ({count/len(cat_df)*100:.1f}%)")

    print(f'\nHighest-Engagement Districts ({cat_name}):')
    top_areas = cat_df.groupby('district')['review_count'].sum().sort_values(ascending=False).head(5)
    for area, reviews in top_areas.items():
        print(f"  {area}: {reviews:,.0f} total reviews")

    hidden_gems = cat_df[(cat_df['rating'] >= 4.5) & (cat_df['review_count'] < cat_df['review_count'].quantile(0.25))]
    print(f"\nHidden Gems (rating >= 4.5, low reviews): {len(hidden_gems):,} {cat_name}s")
    if len(hidden_gems) > 0:
        print('Top hidden gems:')
        for _, row in hidden_gems.nlargest(5, 'rating').iterrows():
            print(f"  Rating: {row['rating']:.1f} - {row['name']} ({row['review_count']:,} reviews)")

    # Recommendation candidates
    print(f'\nTop Recommendation Candidates ({cat_name}):')
    top_recs = cat_df.nlargest(10, 'rating')[['name', 'rating', 'review_count', 'popularity_score']]
    print(top_recs.to_string(index=False))

# ---
# ## 14. Recommendation-Oriented Features (Per Category)

# %%
for cat_name, cat_df in categories.items():
    print(f'\n{"="*70}')
    print(f'  RECOMMENDATION SCORES: {cat_name.upper()} ({len(cat_df):,} places)')
    print(f'{"="*70}')

    if 'rating_norm' not in cat_df.columns:
        scaler = MinMaxScaler()
        cat_df['rating_norm'] = scaler.fit_transform(cat_df[['rating']].fillna(cat_df['rating'].median()))
        cat_df['review_norm'] = scaler.fit_transform(
            cat_df[['review_count']].fillna(cat_df['review_count'].median()).apply(np.log1p)
        )

    # Family-friendly
    cat_df['family_friendly_score'] = (
        0.5 * cat_df['rating_norm'] + 0.5 * cat_df['review_norm']
    ).round(4)

    # Budget-friendly
    cat_df['budget_score'] = (1.0 - cat_df['rating_norm'] * 0.3 + cat_df['review_norm'] * 0.2).clip(0, 1).round(4)

    # Luxury
    cat_df['luxury_score'] = (
        0.7 * cat_df['rating_norm'] + 0.3 * (1 - cat_df['review_norm'])
    ).clip(0, 1).round(4)

    score_cols = ['family_friendly_score', 'budget_score', 'luxury_score']
    print(f'\nRecommendation Feature Scores ({cat_name}):')
    print(cat_df[score_cols].describe().round(3).to_string())

    # Top recommendations by profile
    print(f'\nTop 5 Recommendations by Profile ({cat_name}):')
    profiles = {
        'Family Trip': 'family_friendly_score',
        'Budget Traveler': 'budget_score',
        'Luxury Seeker': 'luxury_score',
    }
    for profile, score_col in profiles.items():
        top = cat_df.nlargest(5, score_col)[['name', 'rating', 'review_count', score_col]]
        print(f"\n  {profile}:")
        for _, row in top.iterrows():
            print(f"    Rating: {row['rating']:.1f} | {row['name'][:45]:45s} | score={row[score_col]:.3f}")

# ---
# ## 15. Interactive Dashboard Elements (Per Category)
#
# > **Note:** Interactive charts are saved as `.html` files in `outputs/figures/`. Open them in a browser for full interactivity.

# %%
for cat_name, cat_df in categories.items():
    print(f'\n{"="*70}')
    print(f'  INTERACTIVE DASHBOARD: {cat_name.upper()} ({len(cat_df):,} places)')
    print(f'{"="*70}')

    # Rating distribution box plot
    fig = px.box(
        cat_df, y='rating',
        title=f'{cat_name.title()} - Rating Distribution (Interactive)',
        hover_data=['name', 'review_count'], height=500
    )
    fig.write_html(f'../outputs/figures/{cat_name}_interactive_rating_boxplot.html')

    # Scatter by subtype
    if 'subtype' in cat_df.columns and cat_df['subtype'].notna().sum() > 0:
        fig = px.scatter(
            cat_df.sample(min(2000, len(cat_df)), random_state=42),
            x='subtype', y='rating', color='district',
            size='review_count', size_max=20, hover_name='name',
            hover_data={'subtype': True, 'rating': True, 'review_count': True, 'district': True},
            title=f'{cat_name.title()} - Subtype x Rating x District', height=600,
        )
        fig.update_layout(xaxis_tickangle=-45)
        fig.write_html(f'../outputs/figures/{cat_name}_interactive_subtype_rating.html')
        print(f'Subtype scatter saved: {cat_name}_interactive_subtype_rating.html')

    print(f'Dashboard saved for {cat_name}')

# ---
# ## 16. Cross-Category Comparison (Summary)

# %%
print('\n' + '=' * 70)
print('  CROSS-CATEGORY COMPARISON')
print('=' * 70)

cat_comparison = pd.DataFrame()
for cat_name, cat_df in categories.items():
    row = pd.DataFrame({
        'category': [cat_name],
        'count': [len(cat_df)],
        'avg_rating': [cat_df['rating'].mean()],
        'median_rating': [cat_df['rating'].median()],
        'std_rating': [cat_df['rating'].std()],
        'avg_reviews': [cat_df['review_count'].mean()],
        'total_reviews': [cat_df['review_count'].sum()],
        'unique_districts': [cat_df['district'].nunique()],
    })
    cat_comparison = pd.concat([cat_comparison, row], ignore_index=True)

cat_comparison = cat_comparison.round(2)
print('\nCategory Comparison Summary:')
print(cat_comparison.to_string(index=False))

# Comparison charts
fig, axes = plt.subplots(1, 3, figsize=(20, 7))

cat_comparison.set_index('category')['count'].plot(kind='barh', ax=axes[0], color=sns.color_palette('viridis', len(cat_comparison)))
axes[0].set_title('Number of Places', fontweight='bold')
axes[0].set_xlabel('Count')

cat_comparison.set_index('category')['avg_rating'].plot(kind='barh', ax=axes[1], color=sns.color_palette('RdYlGn', len(cat_comparison)))
axes[1].set_title('Average Rating', fontweight='bold')
axes[1].set_xlabel('Rating')

cat_comparison.set_index('category')['avg_reviews'].plot(kind='barh', ax=axes[2], color=sns.color_palette('magma', len(cat_comparison)))
axes[2].set_title('Average Review Count', fontweight='bold')
axes[2].set_xlabel('Avg Reviews')

plt.suptitle('Cross-Category Comparison', fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('../outputs/figures/cross_category_comparison.png', bbox_inches='tight')
plt.show()

# Category x Rating heatmap (cross-category)
cat_rating_ct = pd.crosstab(
    df['category'],
    pd.cut(df['rating'], bins=[0, 1, 2, 3, 4, 5], labels=['0-1', '1-2', '2-3', '3-4', '4-5'])
)
cat_rating_pct = cat_rating_ct.div(cat_rating_ct.sum(axis=1), axis=0) * 100

fig, ax = plt.subplots(figsize=(12, 7))
sns.heatmap(cat_rating_pct, annot=True, fmt='.1f', cmap='YlGnBu', ax=ax, linewidths=0.5)
ax.set_title('Rating Distribution by Category (%)', fontsize=14, fontweight='bold')
ax.set_xlabel('Rating Range')
ax.set_ylabel('Category')
plt.tight_layout()
plt.savefig('../outputs/figures/category_rating_heatmap.png', bbox_inches='tight')
plt.show()

# ---
# ## 17. Automated Report Generation

# %%
report_data = {
    'Total Places': f"{len(df):,}",
    'Hotel Count': f"{len(df_hotel):,}",
    'Restaurant Count': f"{len(df_restaurant):,}",
    'Attractions Count': f"{len(df_attractions):,}",
    'Average Rating': f"{df['rating'].mean():.2f}",
    'Median Review Count': f"{df['review_count'].median():,.0f}",
    'Total Reviews': f"{df['review_count'].sum():,.0f}",
    'Hidden Gems': len(df[(df['rating'] >= 4.5) & (df['review_count'] < df['review_count'].quantile(0.25))]),
}

html_report = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Cairo Places EDA Report - Per Category - TourMate AI</title>
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
        .warning {{ background: #fff3e0; border-left: 4px solid #ff9800; padding: 12px 18px; margin: 10px 0; border-radius: 0 8px 8px 0; }}
        .footer {{ text-align: center; color: #999; padding: 20px; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Cairo Places - EDA Report (Per Category)</h1>
        <p>TourMate AI - Data Intelligence - Generated June 2026</p>
    </div>
    <div class="section">
        <h2>Executive Summary</h2>
        <div class="kpi-grid">
            <div class="kpi"><div class="value">{report_data['Total Places']}</div><div class="label">Total Places</div></div>
            <div class="kpi"><div class="value">{report_data['Hotel Count']}</div><div class="label">Hotels</div></div>
            <div class="kpi"><div class="value">{report_data['Restaurant Count']}</div><div class="label">Restaurants</div></div>
            <div class="kpi"><div class="value">{report_data['Attractions Count']}</div><div class="label">Attractions</div></div>
            <div class="kpi"><div class="value">{report_data['Average Rating']}</div><div class="label">Avg Rating</div></div>
            <div class="kpi"><div class="value">{report_data['Total Reviews']}</div><div class="label">Total Reviews</div></div>
            <div class="kpi"><div class="value">{report_data['Hidden Gems']}</div><div class="label">Hidden Gems</div></div>
        </div>
    </div>
    <div class="section">
        <h2>Key Findings</h2>
        <div class="insight"><b>Hotels:</b> {report_data['Hotel Count']} hotel listings analyzed separately with category-specific insights.</div>
        <div class="insight"><b>Restaurants:</b> {report_data['Restaurant Count']} restaurant listings with food-specific analysis.</div>
        <div class="insight"><b>Attractions:</b> {report_data['Attractions Count']} attraction listings with tourism-focused insights.</div>
        <div class="warning"><b>Data Quality:</b> All analyses performed per-category for more accurate and relevant insights.</div>
    </div>
    <div class="section">
        <h2>Recommendations for TourMate AI</h2>
        <ul>
            <li>Use per-category popularity scores for more accurate recommendations.</li>
            <li>Build category-specific user profiles (foodie, hotel-seeker, explorer).</li>
            <li>Prioritize hidden gems within each category for personalized discovery.</li>
            <li>Leverage district-level insights for location-based recommendations.</li>
        </ul>
    </div>
    <div class="footer">
        <p>Generated by TourMate AI Data Science Team - June 2026</p>
    </div>
</body>
</html>
"""

with open('../outputs/reports/cairo_places_eda_report.html', 'w', encoding='utf-8') as f:
    f.write(html_report)

print('HTML report saved to outputs/reports/cairo_places_eda_report.html')

# ---
# ## 18. Notebook Summary

# %%
print('=' * 70)
print('CAIRO PLACES EDA - PER CATEGORY - COMPLETED SUCCESSFULLY')
print('=' * 70)
print(f'\nTotal Dataset: {len(df):,} places across {df["category"].nunique()} categories')
print(f'\nPer-Category Breakdown:')
for cat_name, cat_df in categories.items():
    print(f'  {cat_name:15s}: {len(cat_df):>5,} places | avg rating: {cat_df["rating"].mean():.2f} | avg reviews: {cat_df["review_count"].mean():.0f}')
print(f'\nOutput Files:')
print(f'  outputs/figures/ - per-category visualizations saved')
print(f'  outputs/reports/ - HTML report')
print('\nAll analyses complete. Notebook ready for review.')

# ---
# *This notebook was generated by TourMate AI Data Science Team - June 2026*
# *Per-category EDA for Hotels, Restaurants, and Attractions*
