"""
Economic Chart Generator — Creates professional charts from ALL extracted data.

Sources:
  1. Statistics extracted by AI from reports and PDFs
  2. Table data parsed from PDFs
  3. FRED API baseline economic indicators
  4. Cross-source comparison data

Generates matplotlib charts and embeds them into Word documents.
"""

import logging
import io
from datetime import datetime
from typing import Optional
from collections import defaultdict

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for GitHub Actions
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

import requests as http_requests

logger = logging.getLogger(__name__)

# Professional color palette
COLORS = {
    'primary': '#1a5276',
    'secondary': '#2980b9',
    'accent': '#e74c3c',
    'success': '#27ae60',
    'warning': '#f39c12',
    'dark': '#2c3e50',
    'light': '#ecf0f1',
    'palette': ['#1a5276', '#2980b9', '#27ae60', '#e74c3c', '#f39c12',
                '#8e44ad', '#16a085', '#d35400', '#2c3e50', '#7f8c8d']
}


class ChartGenerator:
    """
    Generates professional economic charts from extracted data.
    All charts are returned as PNG image bytes for Word embedding.
    """

    def __init__(self):
        self.charts = []  # List of (title, image_bytes) tuples
        plt.style.use('seaborn-v0_8-whitegrid')
        plt.rcParams.update({
            'font.family': 'sans-serif',
            'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
            'font.size': 10,
            'axes.titlesize': 13,
            'axes.titleweight': 'bold',
            'axes.labelsize': 10,
            'figure.dpi': 150,
            'figure.facecolor': 'white',
        })

    def generate_all_charts(self, articles: list, analyzed_articles: list,
                            indicators: dict = None) -> list:
        """
        Generate all charts from the collected and analyzed data.

        Args:
            articles: All collected articles
            analyzed_articles: Articles after AI analysis
            indicators: FRED economic indicators dict

        Returns:
            List of (title, image_bytes) tuples
        """
        self.charts = []

        # 1. FRED Economic Dashboard (baseline indicators)
        if indicators:
            chart = self._generate_indicators_dashboard(indicators)
            if chart:
                self.charts.append(chart)

        # 2. Report statistics chart (from AI-extracted stats)
        stats_chart = self._generate_statistics_chart(analyzed_articles)
        if stats_chart:
            self.charts.append(stats_chart)

        # 3. Source coverage chart (articles per organization)
        coverage_chart = self._generate_source_coverage(articles)
        if coverage_chart:
            self.charts.append(coverage_chart)

        # 4. Topic distribution chart
        topic_chart = self._generate_topic_distribution(analyzed_articles)
        if topic_chart:
            self.charts.append(topic_chart)

        # 5. Importance heatmap
        importance_chart = self._generate_importance_chart(analyzed_articles)
        if importance_chart:
            self.charts.append(importance_chart)

        # 6. Cross-source comparison (if enough data)
        comparison_chart = self._generate_cross_source_chart(analyzed_articles)
        if comparison_chart:
            self.charts.append(comparison_chart)

        logger.info(f"[CHARTS] Generated {len(self.charts)} professional charts")
        return self.charts

    # =====================================================================
    # CHART 1: FRED ECONOMIC DASHBOARD
    # =====================================================================

    def _generate_indicators_dashboard(self, indicators: dict) -> Optional[tuple]:
        """Generate a dashboard chart from FRED economic indicators."""
        try:
            # Filter to actual data points (exclude 'NOTES' and 'error')
            data_points = {
                k: v for k, v in indicators.items()
                if isinstance(v, dict) and 'value' in v and v['value'] != 'N/A'
            }

            if not data_points:
                return None

            names_map = {
                'US_INFLATION': 'CPI\nInflation',
                'US_UNEMPLOYMENT': 'Unemployment\nRate',
                'US_GDP_GROWTH': 'GDP\nGrowth',
                'FED_FUNDS_RATE': 'Fed Funds\nRate',
            }

            labels = []
            values = []
            bar_colors = []
            color_map = {
                'US_INFLATION': COLORS['accent'],
                'US_UNEMPLOYMENT': COLORS['warning'],
                'US_GDP_GROWTH': COLORS['success'],
                'FED_FUNDS_RATE': COLORS['primary'],
            }

            for key, data in data_points.items():
                try:
                    val = float(data['value'])
                    labels.append(names_map.get(key, key))
                    values.append(val)
                    bar_colors.append(color_map.get(key, COLORS['secondary']))
                except (ValueError, TypeError):
                    continue

            if not values:
                return None

            fig, ax = plt.subplots(figsize=(8, 4))
            bars = ax.bar(labels, values, color=bar_colors, width=0.6,
                         edgecolor='white', linewidth=1.5)

            # Add value labels on bars
            for bar, val in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 0.1,
                       f'{val:.1f}%', ha='center', va='bottom', fontweight='bold',
                       fontsize=12, color=COLORS['dark'])

            ax.set_title('Key US Economic Indicators', pad=15)
            ax.set_ylabel('Rate (%)')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.set_ylim(0, max(values) * 1.3)

            fig.tight_layout()
            return ('Key US Economic Indicators', self._fig_to_bytes(fig))

        except Exception as e:
            logger.warning(f"[CHARTS] Indicators dashboard failed: {e}")
            return None

    # =====================================================================
    # CHART 2: EXTRACTED STATISTICS
    # =====================================================================

    def _generate_statistics_chart(self, articles: list) -> Optional[tuple]:
        """Generate chart from AI-extracted statistics across all reports."""
        try:
            # Collect all numeric statistics from deep-analyzed articles
            stat_categories = defaultdict(list)

            for article in articles:
                deep = getattr(article, 'deep_analysis', {}) or {}
                stats = deep.get('key_statistics', [])

                for stat in stats:
                    stat_lower = stat.lower()
                    # Categorize by topic
                    if any(w in stat_lower for w in ['gdp', 'growth', 'output']):
                        stat_categories['GDP & Growth'].append(stat)
                    elif any(w in stat_lower for w in ['inflation', 'cpi', 'price']):
                        stat_categories['Inflation'].append(stat)
                    elif any(w in stat_lower for w in ['employ', 'job', 'labor', 'wage']):
                        stat_categories['Employment'].append(stat)
                    elif any(w in stat_lower for w in ['trade', 'export', 'import', 'tariff']):
                        stat_categories['Trade'].append(stat)
                    elif any(w in stat_lower for w in ['rate', 'bond', 'yield', 'monetary']):
                        stat_categories['Monetary Policy'].append(stat)
                    elif any(w in stat_lower for w in ['fiscal', 'budget', 'debt', 'deficit']):
                        stat_categories['Fiscal Policy'].append(stat)
                    else:
                        stat_categories['Other'].append(stat)

            if not stat_categories:
                return None

            # Create horizontal bar chart of data point counts by category
            categories = sorted(stat_categories.keys(), key=lambda k: len(stat_categories[k]), reverse=True)
            counts = [len(stat_categories[c]) for c in categories]

            fig, ax = plt.subplots(figsize=(8, 4))
            y_pos = range(len(categories))
            bars = ax.barh(y_pos, counts, color=COLORS['palette'][:len(categories)],
                          edgecolor='white', linewidth=1)

            ax.set_yticks(y_pos)
            ax.set_yticklabels(categories)
            ax.set_xlabel('Number of Data Points Extracted')
            ax.set_title('Statistics Extracted from Reports by Category', pad=15)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

            # Add count labels
            for bar, count in zip(bars, counts):
                ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2.,
                       str(count), ha='left', va='center', fontweight='bold')

            fig.tight_layout()
            return ('Statistics Extracted by Category', self._fig_to_bytes(fig))

        except Exception as e:
            logger.warning(f"[CHARTS] Statistics chart failed: {e}")
            return None

    # =====================================================================
    # CHART 3: SOURCE COVERAGE
    # =====================================================================

    def _generate_source_coverage(self, articles: list) -> Optional[tuple]:
        """Generate chart showing article count by organization."""
        try:
            source_counts = defaultdict(int)
            for article in articles:
                if getattr(article, 'verification_status', '') != 'filtered':
                    source_counts[article.source] += 1

            if not source_counts:
                return None

            # Sort by count, take top 15
            sorted_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:15]
            names = [s[0] for s in sorted_sources]
            counts = [s[1] for s in sorted_sources]

            fig, ax = plt.subplots(figsize=(8, 5))
            y_pos = range(len(names))
            bars = ax.barh(y_pos, counts, color=COLORS['secondary'],
                          edgecolor='white', linewidth=0.5)

            ax.set_yticks(y_pos)
            ax.set_yticklabels(names, fontsize=9)
            ax.set_xlabel('Number of Articles')
            ax.set_title('Intelligence Coverage by Organization', pad=15)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.invert_yaxis()

            for bar, count in zip(bars, counts):
                ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2.,
                       str(count), ha='left', va='center', fontsize=9)

            fig.tight_layout()
            return ('Intelligence Coverage by Organization', self._fig_to_bytes(fig))

        except Exception as e:
            logger.warning(f"[CHARTS] Source coverage chart failed: {e}")
            return None

    # =====================================================================
    # CHART 4: TOPIC DISTRIBUTION
    # =====================================================================

    def _generate_topic_distribution(self, articles: list) -> Optional[tuple]:
        """Generate pie chart of topic/theme distribution."""
        try:
            theme_counts = defaultdict(int)
            for article in articles:
                if getattr(article, 'verification_status', '') == 'filtered':
                    continue
                category = getattr(article, 'ai_category', '') or 'Uncategorized'
                theme_counts[category] += 1

            if len(theme_counts) < 2:
                return None

            # Sort and take top categories
            sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)

            # Group small categories into "Other"
            if len(sorted_themes) > 8:
                main = sorted_themes[:7]
                other_count = sum(c for _, c in sorted_themes[7:])
                main.append(('Other', other_count))
                sorted_themes = main

            labels = [t[0] for t in sorted_themes]
            sizes = [t[1] for t in sorted_themes]

            fig, ax = plt.subplots(figsize=(8, 5))
            wedges, texts, autotexts = ax.pie(
                sizes, labels=labels, autopct='%1.0f%%',
                colors=COLORS['palette'][:len(labels)],
                startangle=90, pctdistance=0.85,
                wedgeprops=dict(width=0.5, edgecolor='white', linewidth=2)
            )

            for text in texts:
                text.set_fontsize(9)
            for autotext in autotexts:
                autotext.set_fontsize(8)
                autotext.set_fontweight('bold')

            ax.set_title('Topic Distribution Across Reports', pad=20)
            fig.tight_layout()
            return ('Topic Distribution', self._fig_to_bytes(fig))

        except Exception as e:
            logger.warning(f"[CHARTS] Topic distribution chart failed: {e}")
            return None

    # =====================================================================
    # CHART 5: IMPORTANCE DISTRIBUTION
    # =====================================================================

    def _generate_importance_chart(self, articles: list) -> Optional[tuple]:
        """Generate chart showing importance score distribution."""
        try:
            scores = [
                a.importance_score for a in articles
                if getattr(a, 'importance_score', 0) > 0
                and getattr(a, 'verification_status', '') != 'filtered'
            ]

            if not scores:
                return None

            fig, ax = plt.subplots(figsize=(8, 4))

            # Histogram of importance scores
            bins = range(1, 12)
            n, bins_out, patches = ax.hist(scores, bins=bins, color=COLORS['secondary'],
                                           edgecolor='white', linewidth=1.5, align='left')

            # Color code by importance level
            for patch, left_edge in zip(patches, bins_out[:-1]):
                if left_edge >= 8:
                    patch.set_facecolor(COLORS['accent'])
                elif left_edge >= 5:
                    patch.set_facecolor(COLORS['warning'])
                else:
                    patch.set_facecolor(COLORS['secondary'])

            ax.set_xlabel('Importance Score')
            ax.set_ylabel('Number of Articles')
            ax.set_title('Article Importance Distribution', pad=15)
            ax.set_xticks(range(1, 11))
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

            # Add legend
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor=COLORS['accent'], label='Critical (8-10)'),
                Patch(facecolor=COLORS['warning'], label='Important (5-7)'),
                Patch(facecolor=COLORS['secondary'], label='Standard (1-4)')
            ]
            ax.legend(handles=legend_elements, loc='upper right', fontsize=9)

            fig.tight_layout()
            return ('Importance Score Distribution', self._fig_to_bytes(fig))

        except Exception as e:
            logger.warning(f"[CHARTS] Importance chart failed: {e}")
            return None

    # =====================================================================
    # CHART 6: CROSS-SOURCE COMPARISON
    # =====================================================================

    def _generate_cross_source_chart(self, articles: list) -> Optional[tuple]:
        """Generate chart comparing how different sources cover key topics."""
        try:
            # Build source x category matrix
            source_category = defaultdict(lambda: defaultdict(int))
            for article in articles:
                if getattr(article, 'verification_status', '') == 'filtered':
                    continue
                cat = getattr(article, 'ai_category', '') or 'Other'
                source_category[article.source][cat] += 1

            if len(source_category) < 3:
                return None

            # Select top sources and categories
            top_sources = sorted(source_category.keys(),
                                key=lambda s: sum(source_category[s].values()),
                                reverse=True)[:8]

            all_categories = set()
            for source in top_sources:
                all_categories.update(source_category[source].keys())
            top_categories = sorted(all_categories,
                                   key=lambda c: sum(source_category[s].get(c, 0) for s in top_sources),
                                   reverse=True)[:5]

            # Create stacked bar chart
            fig, ax = plt.subplots(figsize=(10, 5))
            x = np.arange(len(top_sources))
            width = 0.7
            bottom = np.zeros(len(top_sources))

            for i, category in enumerate(top_categories):
                values = [source_category[s].get(category, 0) for s in top_sources]
                ax.bar(x, values, width, label=category, bottom=bottom,
                      color=COLORS['palette'][i % len(COLORS['palette'])],
                      edgecolor='white', linewidth=0.5)
                bottom += np.array(values)

            ax.set_xlabel('Organization')
            ax.set_ylabel('Number of Articles')
            ax.set_title('Topic Coverage by Organization', pad=15)
            ax.set_xticks(x)
            ax.set_xticklabels(top_sources, rotation=30, ha='right', fontsize=8)
            ax.legend(loc='upper right', fontsize=8)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

            fig.tight_layout()
            return ('Cross-Source Topic Coverage', self._fig_to_bytes(fig))

        except Exception as e:
            logger.warning(f"[CHARTS] Cross-source chart failed: {e}")
            return None

    # =====================================================================
    # UTILITIES
    # =====================================================================

    def _fig_to_bytes(self, fig) -> bytes:
        """Convert a matplotlib figure to PNG bytes."""
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf.read()
