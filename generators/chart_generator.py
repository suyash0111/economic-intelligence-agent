"""
Chart Generator — Creates publication-quality charts for the Global Pulse Report.

ALL data comes exclusively from the analyzed articles/reports.
No external data sources are used for chart generation.

Visual style inspired by WEF Future of Jobs Report 2025.
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path
from datetime import datetime
import logging
import json
import os
import re

logger = logging.getLogger(__name__)

# =========================================================================
# WEF-INSPIRED COLOR PALETTE
# =========================================================================

COLORS = {
    'primary_blue': '#1B3A4B',
    'accent_blue': '#0066CC',
    'light_blue': '#4DA6FF',
    'dark_navy': '#0D1B2A',
    'teal': '#0097A7',
    'green': '#2E7D32',
    'orange': '#E65100',
    'red': '#B71C1C',
    'grey': '#757575',
    'light_grey': '#E0E0E0',
    'bg_grey': '#F5F5F5',
    'white': '#FFFFFF',
}

# Palette for bar charts (up to 10 categories)
BAR_PALETTE = [
    '#0066CC', '#0097A7', '#2E7D32', '#F57F17',
    '#E65100', '#8E24AA', '#1565C0', '#00838F',
    '#558B2F', '#BF360C'
]

# For positive/negative charts
POS_COLOR = '#2E7D32'
NEG_COLOR = '#B71C1C'
NEUTRAL_COLOR = '#757575'


class ChartGenerator:
    """
    Generates matplotlib charts from data extracted from analyzed articles.

    STRICT RULE: All data visualized must come from the articles/reports
    the agent analyzed. No independently-fetched external data.
    """

    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path('output/charts')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.figure_counter = 0
        self._setup_style()

    def _setup_style(self):
        """Configure matplotlib to match WEF visual language."""
        plt.rcParams.update({
            'font.family': 'sans-serif',
            'font.sans-serif': ['Calibri', 'Arial', 'Helvetica', 'DejaVu Sans'],
            'font.size': 10,
            'axes.titlesize': 12,
            'axes.titleweight': 'bold',
            'axes.labelsize': 10,
            'axes.spines.top': False,
            'axes.spines.right': False,
            'axes.edgecolor': '#CCCCCC',
            'axes.facecolor': COLORS['white'],
            'figure.facecolor': COLORS['white'],
            'figure.dpi': 200,
            'savefig.dpi': 200,
            'savefig.bbox': 'tight',
            'savefig.pad_inches': 0.3,
        })

    def _next_figure_number(self) -> str:
        """Get next figure number for WEF-style labeling."""
        self.figure_counter += 1
        return f"FIGURE {self.figure_counter}"

    # =====================================================================
    # CHART 1: KEY DATA POINTS — Horizontal Bar Chart
    # =====================================================================

    def generate_key_data_chart(self, data_points: list[dict]) -> Path | None:
        """
        Generate a horizontal bar chart of key numerical data points
        extracted from the analyzed reports.

        data_points: list of {"metric": str, "value": float, "unit": str, "source": str}
        """
        if not data_points or len(data_points) < 2:
            logger.info("[CHART] Not enough data points for key data chart")
            return None

        # Filter to numeric-only, take top 12
        valid = [d for d in data_points if d.get('value') is not None]
        valid = sorted(valid, key=lambda x: abs(x['value']), reverse=True)[:12]

        if len(valid) < 2:
            return None

        fig, ax = plt.subplots(figsize=(8, max(3, len(valid) * 0.5)))

        labels = [d['metric'][:45] for d in valid]
        values = [d['value'] for d in valid]
        colors = [POS_COLOR if v >= 0 else NEG_COLOR for v in values]

        bars = ax.barh(range(len(valid)), values, color=colors, height=0.6, edgecolor='none')

        ax.set_yticks(range(len(valid)))
        ax.set_yticklabels(labels, fontsize=9)
        ax.invert_yaxis()
        ax.axvline(x=0, color='#333333', linewidth=0.8)

        # Data labels
        for bar, val, dp in zip(bars, values, valid):
            unit = dp.get('unit', '')
            label = f"{val:+.1f}{unit}" if val != int(val) else f"{val:+.0f}{unit}"
            x_pos = bar.get_width()
            align = 'left' if x_pos >= 0 else 'right'
            offset = 0.3 if x_pos >= 0 else -0.3
            ax.text(x_pos + offset, bar.get_y() + bar.get_height() / 2,
                    label, va='center', ha=align, fontsize=8, fontweight='bold')

        ax.set_xlabel('')
        ax.spines['bottom'].set_visible(False)
        ax.tick_params(axis='x', which='both', bottom=False, labelbottom=False)

        # Source attribution
        sources = list(set(d.get('source', '') for d in valid if d.get('source')))
        source_text = f"Source: {'; '.join(sources[:3])}" if sources else "Source: Analyzed reports and publications"
        fig.text(0.02, -0.02, source_text, fontsize=7, color=COLORS['grey'], style='italic')

        path = self.output_dir / 'key_data_points.png'
        fig.savefig(path)
        plt.close(fig)
        logger.info(f"[CHART] Generated key data chart: {path}")
        return path

    # =====================================================================
    # CHART 2: RATE COMPARISON — Central Bank Rates from Articles
    # =====================================================================

    def generate_rate_comparison(self, rate_data: list[dict]) -> Path | None:
        """
        Generate horizontal bar chart comparing central bank rates
        as mentioned in the analyzed articles.

        rate_data: list of {"bank": str, "rate": float, "action": str, "source": str}
        """
        if not rate_data or len(rate_data) < 2:
            logger.info("[CHART] Not enough rate data for comparison chart")
            return None

        fig, ax = plt.subplots(figsize=(8, max(2.5, len(rate_data) * 0.55)))

        banks = [d['bank'] for d in rate_data]
        rates = [d['rate'] for d in rate_data]

        # Color by action
        def action_color(action):
            action = (action or '').lower()
            if 'hike' in action or 'raise' in action or 'increase' in action:
                return COLORS['red']
            elif 'cut' in action or 'lower' in action or 'decrease' in action:
                return COLORS['green']
            else:
                return COLORS['accent_blue']

        colors = [action_color(d.get('action', '')) for d in rate_data]

        bars = ax.barh(range(len(rate_data)), rates, color=colors, height=0.55, edgecolor='none')

        ax.set_yticks(range(len(rate_data)))
        ax.set_yticklabels(banks, fontsize=9)
        ax.invert_yaxis()
        ax.set_xlabel('Policy Rate (%)', fontsize=9)

        # Data labels
        for bar, rate, dp in zip(bars, rates, rate_data):
            action = dp.get('action', '')
            label = f"{rate:.2f}%"
            if action:
                label += f" ({action})"
            ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                    label, va='center', fontsize=8, fontweight='bold')

        # Legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor=COLORS['red'], label='Tightening'),
            Patch(facecolor=COLORS['accent_blue'], label='Holding'),
            Patch(facecolor=COLORS['green'], label='Easing'),
        ]
        ax.legend(handles=legend_elements, loc='lower right', fontsize=7, framealpha=0.8)

        sources = list(set(d.get('source', '') for d in rate_data if d.get('source')))
        source_text = f"Source: {'; '.join(sources[:3])}" if sources else "Source: Central bank reports analyzed this week"
        fig.text(0.02, -0.02, source_text, fontsize=7, color=COLORS['grey'], style='italic')

        path = self.output_dir / 'rate_comparison.png'
        fig.savefig(path)
        plt.close(fig)
        logger.info(f"[CHART] Generated rate comparison: {path}")
        return path

    # =====================================================================
    # CHART 3: TOPIC DISTRIBUTION — What the Reports Are About
    # =====================================================================

    def generate_topic_chart(self, topic_counts: dict[str, int]) -> Path | None:
        """
        Horizontal bar chart showing the distribution of topics
        covered in the analyzed reports.

        topic_counts: {"Trade & Tariffs": 5, "Inflation & Prices": 3, ...}
        """
        if not topic_counts or len(topic_counts) < 2:
            return None

        # Sort and take top 10
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        labels = [t[0] for t in sorted_topics]
        counts = [t[1] for t in sorted_topics]

        fig, ax = plt.subplots(figsize=(7, max(2.5, len(sorted_topics) * 0.45)))

        bars = ax.barh(range(len(sorted_topics)), counts,
                       color=[BAR_PALETTE[i % len(BAR_PALETTE)] for i in range(len(sorted_topics))],
                       height=0.55, edgecolor='none')

        ax.set_yticks(range(len(sorted_topics)))
        ax.set_yticklabels(labels, fontsize=9)
        ax.invert_yaxis()
        ax.set_xlabel('Number of reports/articles', fontsize=9)

        for bar, count in zip(bars, counts):
            ax.text(bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2,
                    str(count), va='center', fontsize=9, fontweight='bold')

        fig.text(0.02, -0.02, "Source: Analysis of reports published this week",
                 fontsize=7, color=COLORS['grey'], style='italic')

        path = self.output_dir / 'topic_distribution.png'
        fig.savefig(path)
        plt.close(fig)
        logger.info(f"[CHART] Generated topic distribution: {path}")
        return path

    # =====================================================================
    # CHART 4: SENTIMENT GAUGE — Overall Market Outlook from Reports
    # =====================================================================

    def generate_sentiment_gauge(self, sentiment_data: dict) -> Path | None:
        """
        Semicircular gauge showing overall sentiment from analyzed reports.

        sentiment_data: {
            "score": float (-1.0 to 1.0),
            "label": str ("Bearish", "Cautious", "Neutral", "Cautiously Optimistic", "Bullish"),
            "source_count": int
        }
        """
        if not sentiment_data or 'score' not in sentiment_data:
            return None

        import numpy as np

        score = max(-1.0, min(1.0, sentiment_data.get('score', 0.0)))
        label = sentiment_data.get('label', 'Neutral')
        source_count = sentiment_data.get('source_count', 0)

        fig, ax = plt.subplots(figsize=(5, 3), subplot_kw={'projection': 'polar'})

        # Semicircle gauge
        theta_bg = np.linspace(np.pi, 0, 100)
        ax.fill_between(theta_bg, 0.6, 1.0, color=COLORS['light_grey'], alpha=0.3)

        # Color zones
        zone_colors = [COLORS['red'], COLORS['orange'], '#FDD835', '#66BB6A', COLORS['green']]
        zone_labels = ['Bearish', 'Cautious', 'Neutral', 'Optimistic', 'Bullish']
        n_zones = len(zone_colors)
        for i in range(n_zones):
            start = np.pi - (i * np.pi / n_zones)
            end = np.pi - ((i + 1) * np.pi / n_zones)
            theta_zone = np.linspace(start, end, 20)
            ax.fill_between(theta_zone, 0.6, 1.0, color=zone_colors[i], alpha=0.4)

        # Needle
        needle_angle = np.pi * (1 - (score + 1) / 2)
        ax.annotate('', xy=(needle_angle, 0.95), xytext=(needle_angle, 0.0),
                    arrowprops=dict(arrowstyle='->', color=COLORS['dark_navy'], lw=2.5))

        ax.set_ylim(0, 1.1)
        ax.set_thetamin(0)
        ax.set_thetamax(180)
        ax.set_rticks([])
        ax.set_thetagrids([])
        ax.spines['polar'].set_visible(False)
        ax.grid(False)

        # Label
        fig.text(0.5, 0.18, label, ha='center', fontsize=14, fontweight='bold',
                 color=COLORS['dark_navy'])
        fig.text(0.5, 0.08, f"Based on analysis of {source_count} reports",
                 ha='center', fontsize=8, color=COLORS['grey'], style='italic')

        path = self.output_dir / 'sentiment_gauge.png'
        fig.savefig(path)
        plt.close(fig)
        logger.info(f"[CHART] Generated sentiment gauge: {path}")
        return path

    # =====================================================================
    # CHART 5: KEY FINDINGS DASHBOARD — Big Number Callouts
    # =====================================================================

    def generate_key_findings_dashboard(self, findings: list[dict]) -> Path | None:
        """
        Grid of big number callouts with supporting context.
        Visual equivalent of WEF's highlighted statistics.

        findings: list of {
            "number": str (e.g., "3.2%", "$1.4T", "78M"),
            "label": str (e.g., "Global GDP Growth"),
            "detail": str (e.g., "Q3 2026, IMF estimate"),
            "source": str
        }
        """
        if not findings:
            return None

        # Take first 6 findings max
        findings = findings[:6]
        n = len(findings)
        cols = min(3, n)
        rows = (n + cols - 1) // cols

        fig, axes = plt.subplots(rows, cols, figsize=(9, rows * 2.2))

        if rows == 1 and cols == 1:
            axes = [[axes]]
        elif rows == 1:
            axes = [axes]
        elif cols == 1:
            axes = [[a] for a in axes]

        for i, finding in enumerate(findings):
            r, c = divmod(i, cols)
            ax = axes[r][c]

            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')

            # Background box
            from matplotlib.patches import FancyBboxPatch
            bg = FancyBboxPatch((0.02, 0.05), 0.96, 0.9,
                                boxstyle="round,pad=0.05",
                                facecolor=COLORS['bg_grey'], edgecolor=COLORS['light_grey'],
                                linewidth=1)
            ax.add_patch(bg)

            # Big number
            ax.text(0.5, 0.65, finding.get('number', '—'),
                    ha='center', va='center', fontsize=22, fontweight='bold',
                    color=COLORS['primary_blue'])

            # Label
            ax.text(0.5, 0.35, finding.get('label', '')[:30],
                    ha='center', va='center', fontsize=9, fontweight='bold',
                    color=COLORS['dark_navy'])

            # Detail
            detail = finding.get('detail', '')[:40]
            if detail:
                ax.text(0.5, 0.18, detail,
                        ha='center', va='center', fontsize=7,
                        color=COLORS['grey'], style='italic')

        # Hide unused axes
        for i in range(n, rows * cols):
            r, c = divmod(i, cols)
            axes[r][c].axis('off')

        plt.tight_layout()
        path = self.output_dir / 'key_findings.png'
        fig.savefig(path)
        plt.close(fig)
        logger.info(f"[CHART] Generated key findings dashboard: {path}")
        return path

    # =====================================================================
    # CHART 6: COMPARISON TABLE IMAGE — For Tables That Need Visual Polish
    # =====================================================================

    def generate_comparison_table(self, table_data: dict) -> Path | None:
        """
        Render a data comparison table as an image for maximum visual control.

        table_data: {
            "title": str,
            "headers": list[str],
            "rows": list[list[str]],
            "source": str
        }
        """
        if not table_data or not table_data.get('rows'):
            return None

        headers = table_data.get('headers', [])
        rows = table_data.get('rows', [])
        title = table_data.get('title', '')
        source = table_data.get('source', '')

        n_cols = len(headers)
        n_rows = len(rows)

        fig_width = max(7, n_cols * 2)
        fig_height = max(2, (n_rows + 1) * 0.4 + 1)

        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        ax.axis('off')

        # Build table
        table = ax.table(
            cellText=rows,
            colLabels=headers,
            loc='center',
            cellLoc='center',
        )

        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 1.5)

        # Style header
        for j in range(n_cols):
            cell = table[0, j]
            cell.set_facecolor(COLORS['primary_blue'])
            cell.set_text_props(color='white', fontweight='bold', fontsize=9)
            cell.set_edgecolor(COLORS['white'])

        # Style rows (alternating)
        for i in range(n_rows):
            for j in range(n_cols):
                cell = table[i + 1, j]
                bg = COLORS['bg_grey'] if i % 2 == 0 else COLORS['white']
                cell.set_facecolor(bg)
                cell.set_edgecolor('#E0E0E0')

        if title:
            fig.text(0.5, 0.98, title, ha='center', fontsize=11, fontweight='bold',
                     color=COLORS['dark_navy'])

        if source:
            fig.text(0.02, 0.02, f"Source: {source}",
                     fontsize=7, color=COLORS['grey'], style='italic')

        path = self.output_dir / 'comparison_table.png'
        fig.savefig(path)
        plt.close(fig)
        logger.info(f"[CHART] Generated comparison table: {path}")
        return path

    # =====================================================================
    # MASTER METHOD: Generate All Charts
    # =====================================================================

    def generate_all_charts(self, extracted_data: dict) -> dict[str, Path]:
        """
        Generate all available charts from the extracted data.

        extracted_data: {
            "data_points": list[dict],      → key_data_chart
            "rate_data": list[dict],         → rate_comparison
            "topic_counts": dict,            → topic_chart
            "sentiment": dict,               → sentiment_gauge
            "key_findings": list[dict],      → key_findings_dashboard
            "comparison_table": dict,        → comparison_table
        }

        Returns dict of chart_name → file_path for successfully generated charts.
        """
        charts = {}

        try:
            path = self.generate_key_data_chart(extracted_data.get('data_points', []))
            if path:
                charts['key_data'] = path
        except Exception as e:
            logger.warning(f"[CHART] Failed to generate key data chart: {e}")

        try:
            path = self.generate_rate_comparison(extracted_data.get('rate_data', []))
            if path:
                charts['rate_comparison'] = path
        except Exception as e:
            logger.warning(f"[CHART] Failed to generate rate comparison: {e}")

        try:
            path = self.generate_topic_chart(extracted_data.get('topic_counts', {}))
            if path:
                charts['topic_distribution'] = path
        except Exception as e:
            logger.warning(f"[CHART] Failed to generate topic chart: {e}")

        try:
            path = self.generate_sentiment_gauge(extracted_data.get('sentiment', {}))
            if path:
                charts['sentiment'] = path
        except Exception as e:
            logger.warning(f"[CHART] Failed to generate sentiment gauge: {e}")

        try:
            path = self.generate_key_findings_dashboard(extracted_data.get('key_findings', []))
            if path:
                charts['key_findings'] = path
        except Exception as e:
            logger.warning(f"[CHART] Failed to generate key findings: {e}")

        try:
            path = self.generate_comparison_table(extracted_data.get('comparison_table', {}))
            if path:
                charts['comparison_table'] = path
        except Exception as e:
            logger.warning(f"[CHART] Failed to generate comparison table: {e}")

        logger.info(f"[CHART] Generated {len(charts)} charts: {list(charts.keys())}")
        return charts
