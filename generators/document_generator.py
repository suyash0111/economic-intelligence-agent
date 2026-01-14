"""
Document Generator - Creates Word documents for comprehensive reports.
"""

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from pathlib import Path
from datetime import datetime
import logging

from collectors.base_collector import Article
from config.settings import Settings

logger = logging.getLogger(__name__)


class DocumentGenerator:
    """
    Generates Word documents with comprehensive economic intelligence reports.
    Reports are organized by organization/category with detailed analysis.
    """
    
    def __init__(self):
        """Initialize the document generator."""
        self.doc = None
    
    def generate(
        self, 
        articles_by_org: dict[str, list[Article]],
        executive_summary: str,
        date_range: str,
        output_path: Path = None,
        tldr_top5: str = "",
        cross_source_synthesis: str = "",
        theme_summary: dict = None,
        sentiment_analysis: str = "",
        actionable_implications: str = "",
        geographic_summary: dict = None,
        key_numbers: str = ""
    ) -> Path:
        """
        Generate a comprehensive Word document report.
        
        Args:
            articles_by_org: Dictionary mapping organization short_name to articles
            executive_summary: AI-generated executive summary
            date_range: String describing the date range
            output_path: Optional output path
            tldr_top5: TL;DR Top 5 section content
            cross_source_synthesis: Cross-source analysis content
            theme_summary: Dictionary of themes and their articles
            sentiment_analysis: Sentiment analysis content
            actionable_implications: Implications for stakeholders
            geographic_summary: Regional breakdown
            key_numbers: Key economic indicators
        
        Returns:
            Path to the generated document
        """
        self.doc = Document()
        self._setup_styles()
        
        # Title Page
        self._add_title_page(date_range)
        
        # TL;DR Top 5 Section (first for quick readers)
        if tldr_top5:
            self._add_tldr_section(tldr_top5)
        
        # Key Numbers Dashboard
        if key_numbers:
            self._add_key_numbers_section(key_numbers)
        
        # Sentiment Analysis
        if sentiment_analysis:
            self._add_sentiment_section(sentiment_analysis)
        
        # Executive Summary
        self._add_executive_summary(executive_summary)
        
        # Cross-Source Intelligence Section
        if cross_source_synthesis:
            self._add_cross_source_section(cross_source_synthesis)
        
        # Actionable Implications
        if actionable_implications:
            self._add_implications_section(actionable_implications)
        
        # Geographic Breakdown
        if geographic_summary:
            self._add_geographic_section(geographic_summary)
        
        # Theme-Based Summary Section
        if theme_summary:
            self._add_theme_section(theme_summary)
        
        # Table of Contents placeholder
        self._add_toc_placeholder()
        
        # Group organizations by category
        orgs_by_category = self._group_by_category(articles_by_org)
        
        # Generate sections for each category
        for category in self._get_category_order():
            if category in orgs_by_category:
                self._add_category_section(category, orgs_by_category[category])
        
        # Save document
        if output_path is None:
            Settings.ensure_output_dir()
            output_path = Settings.OUTPUT_DIR / f"Global_Pulse_Weekly_Report_{datetime.now().strftime('%Y%m%d')}.docx"
        
        self.doc.save(output_path)
        logger.info(f"Document saved: {output_path}")
        
        return output_path
    
    def _setup_styles(self):
        """Set up document styles."""
        styles = self.doc.styles
        
        # Title style
        if 'Report Title' not in [s.name for s in styles]:
            title_style = styles.add_style('Report Title', WD_STYLE_TYPE.PARAGRAPH)
            title_style.font.size = Pt(28)
            title_style.font.bold = True
            title_style.font.color.rgb = RGBColor(0, 51, 102)
            title_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            title_style.paragraph_format.space_after = Pt(12)
        
        # Subtitle style
        if 'Report Subtitle' not in [s.name for s in styles]:
            subtitle_style = styles.add_style('Report Subtitle', WD_STYLE_TYPE.PARAGRAPH)
            subtitle_style.font.size = Pt(14)
            subtitle_style.font.italic = True
            subtitle_style.font.color.rgb = RGBColor(102, 102, 102)
            subtitle_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    def _add_title_page(self, date_range: str):
        """Add the title page."""
        # Add some spacing at top
        for _ in range(3):
            self.doc.add_paragraph()
        
        # Title
        title = self.doc.add_paragraph()
        title.add_run("THE GLOBAL PULSE").bold = True
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title.runs[0].font.size = Pt(32)
        title.runs[0].font.color.rgb = RGBColor(0, 51, 102)
        
        # Subtitle
        subtitle = self.doc.add_paragraph()
        subtitle.add_run("Weekly Economic Intelligence Report")
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        subtitle.runs[0].font.size = Pt(16)
        subtitle.runs[0].font.color.rgb = RGBColor(0, 51, 102)
        
        # Date range
        date_p = self.doc.add_paragraph()
        date_p.add_run(date_range)
        date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        date_p.runs[0].font.size = Pt(14)
        date_p.runs[0].font.italic = True
        date_p.runs[0].font.color.rgb = RGBColor(102, 102, 102)
        
        # Spacer
        self.doc.add_paragraph()
        self.doc.add_paragraph()
        
        # Description
        desc = self.doc.add_paragraph()
        desc.add_run(
            "360-Degree Analysis of Global Economic Developments\n"
            "Covering 39 Leading Organizations Worldwide\n\n"
            "Macro & Micro Indicators | Policy Implications | Industry Insights"
        )
        desc.alignment = WD_ALIGN_PARAGRAPH.CENTER
        desc.runs[0].font.size = Pt(11)
        
        # Page break
        self.doc.add_page_break()
    
    def _add_executive_summary(self, summary: str):
        """Add executive summary section."""
        self.doc.add_heading("Executive Summary", level=1)
        
        # Add summary paragraphs
        for para in summary.split('\n\n'):
            if para.strip():
                p = self.doc.add_paragraph(para.strip())
                p.paragraph_format.space_after = Pt(12)
        
        self.doc.add_page_break()
    
    def _add_toc_placeholder(self):
        """Add table of contents placeholder."""
        self.doc.add_heading("Table of Contents", level=1)
        
        p = self.doc.add_paragraph()
        p.add_run("1. Executive Summary").bold = True
        self.doc.add_paragraph()
        
        p = self.doc.add_paragraph()
        p.add_run("2. International Organizations").bold = True
        self.doc.add_paragraph()
        
        p = self.doc.add_paragraph()
        p.add_run("3. Consulting Firms & Research").bold = True
        self.doc.add_paragraph()
        
        p = self.doc.add_paragraph()
        p.add_run("4. Think Tanks & Institutes").bold = True
        self.doc.add_paragraph()
        
        p = self.doc.add_paragraph()
        p.add_run("5. News & Data Providers").bold = True
        self.doc.add_paragraph()
        
        p = self.doc.add_paragraph()
        p.add_run("6. India-Specific Sources").bold = True
        
        self.doc.add_page_break()
    
    def _group_by_category(self, articles_by_org: dict) -> dict[str, dict[str, list[Article]]]:
        """Group organizations by their category."""
        orgs_by_category = {}
        
        for org_name, articles in articles_by_org.items():
            if not articles:
                continue
            
            category = articles[0].category
            if category not in orgs_by_category:
                orgs_by_category[category] = {}
            orgs_by_category[category][org_name] = articles
        
        return orgs_by_category
    
    def _get_category_order(self) -> list[str]:
        """Get the order of categories for the report."""
        return [
            'Central Bank',  # Major central banks first
            'International',
            'Consulting',
            'Think Tank',
            'Investment Bank',
            'News',
            'Data Provider',
            'Rating Agency',
            'India',
        ]
    
    def _add_category_section(self, category: str, orgs: dict[str, list[Article]]):
        """Add a section for a category of organizations."""
        # Category header
        category_titles = {
            'International': 'International & Multilateral Organizations',
            'Consulting': 'Consulting Firms & Professional Services',
            'Think Tank': 'Think Tanks & Research Institutes',
            'Investment Bank': 'Investment Banks Research',
            'News': 'News & Data Providers',
            'Data Provider': 'Data & Analytics Providers',
            'Rating Agency': 'Credit Rating Agencies',
            'India': 'India-Specific Sources',
        }
        
        self.doc.add_heading(category_titles.get(category, category), level=1)
        
        # Add each organization
        for org_name, articles in sorted(orgs.items()):
            self._add_organization_section(org_name, articles)
        
        self.doc.add_page_break()
    
    def _add_organization_section(self, org_name: str, articles: list[Article]):
        """Add a section for a single organization."""
        if not articles:
            return
        
        # Organization name as heading
        full_name = articles[0].source_full
        self.doc.add_heading(full_name, level=2)
        
        # Summary count
        p = self.doc.add_paragraph()
        p.add_run(f"{len(articles)} items this week").italic = True
        p.runs[0].font.size = Pt(10)
        p.runs[0].font.color.rgb = RGBColor(102, 102, 102)
        
        # Add "Major Findings & Analysis" header if there are major items
        has_major = any(a.ai_analysis for a in articles)
        if has_major:
            findings_header = self.doc.add_paragraph()
            findings_header.add_run("MAJOR FINDINGS & ANALYSIS").bold = True
            findings_header.runs[0].font.size = Pt(11)
            findings_header.runs[0].font.color.rgb = RGBColor(0, 102, 153)
        
        # Add each article
        for article in articles:
            self._add_article(article)
    
    def _add_article(self, article: Article):
        """Add a single article to the document."""
        # Article title
        p = self.doc.add_paragraph()
        run = p.add_run(f"• {article.title}")
        run.bold = True
        run.font.size = Pt(11)
        
        # Date if available
        if article.published_date:
            date_run = p.add_run(f"  ({article.published_date.strftime('%b %d, %Y')})")
            date_run.font.size = Pt(9)
            date_run.font.color.rgb = RGBColor(102, 102, 102)
        
        # AI Summary (one-liner)
        if article.ai_summary:
            summary_p = self.doc.add_paragraph()
            summary_p.add_run(article.ai_summary)
            summary_p.runs[0].font.size = Pt(10)
            summary_p.paragraph_format.left_indent = Inches(0.25)
        
        # AI Analysis (detailed - only for major items)
        if article.ai_analysis:
            analysis_p = self.doc.add_paragraph()
            
            # Parse and add formatted analysis
            for line in article.ai_analysis.split('\n'):
                if line.strip():
                    # Handle bold headers
                    if line.startswith('**') and line.endswith('**'):
                        run = analysis_p.add_run(line.strip('*') + '\n')
                        run.bold = True
                    elif '**' in line:
                        # Handle inline bold
                        parts = line.split('**')
                        for i, part in enumerate(parts):
                            run = analysis_p.add_run(part)
                            if i % 2 == 1:  # Odd indices are bold
                                run.bold = True
                        analysis_p.add_run('\n')
                    else:
                        analysis_p.add_run(line + '\n')
            
            analysis_p.paragraph_format.left_indent = Inches(0.25)
            analysis_p.runs[0].font.size = Pt(10) if analysis_p.runs else None
        
        # Link
        link_p = self.doc.add_paragraph()
        link_p.add_run("Read more: ")
        link_run = link_p.add_run(article.url)
        link_run.font.size = Pt(9)
        link_run.font.color.rgb = RGBColor(0, 102, 204)
        link_run.underline = True
        link_p.paragraph_format.left_indent = Inches(0.25)
        link_p.paragraph_format.space_after = Pt(12)
    
    def _add_tldr_section(self, tldr_content: str):
        """Add TL;DR Top 5 section at the beginning for quick readers."""
        self.doc.add_heading("TOP 5 THINGS TO KNOW THIS WEEK", level=1)
        
        # Add introductory text
        intro = self.doc.add_paragraph()
        intro.add_run("The most important developments ranked by impact score. ").italic = True
        intro.runs[0].font.color.rgb = RGBColor(102, 102, 102)
        
        # Add the TL;DR content
        for line in tldr_content.split('\n'):
            if line.strip():
                p = self.doc.add_paragraph()
                # Handle emoji indicators
                if line.startswith('1.') or '🔴' in line:
                    run = p.add_run(line.replace('🔴', '[CRITICAL] '))
                    run.bold = True
                    run.font.color.rgb = RGBColor(180, 0, 0)
                elif '🟠' in line:
                    run = p.add_run(line.replace('🟠', '[IMPORTANT] '))
                    run.bold = True
                    run.font.color.rgb = RGBColor(200, 100, 0)
                elif '🟢' in line:
                    run = p.add_run(line.replace('🟢', '[NOTABLE] '))
                    run.font.color.rgb = RGBColor(0, 120, 0)
                else:
                    p.add_run(line)
        
        self.doc.add_page_break()
    
    def _add_cross_source_section(self, cross_source_content: str):
        """Add cross-source intelligence synthesis section."""
        self.doc.add_heading("CROSS-SOURCE INTELLIGENCE", level=1)
        
        intro = self.doc.add_paragraph()
        intro.add_run("Analysis of consensus and divergent views across organizations.").italic = True
        intro.runs[0].font.color.rgb = RGBColor(102, 102, 102)
        
        # Add the content with markdown parsing
        for para in cross_source_content.split('\n\n'):
            if para.strip():
                p = self.doc.add_paragraph()
                for line in para.split('\n'):
                    if line.strip():
                        if line.startswith('**') and line.endswith('**'):
                            run = p.add_run(line.strip('*') + '\n')
                            run.bold = True
                            run.font.color.rgb = RGBColor(0, 51, 102)
                        elif '**' in line:
                            parts = line.split('**')
                            for i, part in enumerate(parts):
                                run = p.add_run(part)
                                if i % 2 == 1:
                                    run.bold = True
                            p.add_run('\n')
                        else:
                            p.add_run(line + '\n')
        
        self.doc.add_paragraph()
    
    def _add_theme_section(self, theme_summary: dict):
        """Add theme-based summary section."""
        if not theme_summary:
            return
            
        self.doc.add_heading("THEMATIC OVERVIEW", level=1)
        
        intro = self.doc.add_paragraph()
        intro.add_run("Articles grouped by economic theme for quick navigation.").italic = True
        intro.runs[0].font.color.rgb = RGBColor(102, 102, 102)
        
        for theme, data in theme_summary.items():
            # Theme sub-heading
            theme_p = self.doc.add_paragraph()
            theme_run = theme_p.add_run(f"➤ {theme}")
            theme_run.bold = True
            theme_run.font.size = Pt(12)
            theme_run.font.color.rgb = RGBColor(0, 51, 102)
            
            # Stats
            stats_p = self.doc.add_paragraph()
            stats_p.add_run(
                f"   {data['count']} items from {len(data['sources'])} sources: " + 
                ", ".join(data['sources'][:5])
            )
            stats_p.runs[0].font.size = Pt(10)
            stats_p.runs[0].font.color.rgb = RGBColor(102, 102, 102)
            
            # Top headlines
            for headline in data['headlines'][:3]:
                hl_p = self.doc.add_paragraph()
                hl_p.add_run(f"   • {headline[:80]}...")
                hl_p.runs[0].font.size = Pt(9)
        
        self.doc.add_page_break()
    
    def _add_key_numbers_section(self, key_numbers: str):
        """Add key economic numbers dashboard section."""
        self.doc.add_heading("KEY ECONOMIC NUMBERS", level=1)
        
        intro = self.doc.add_paragraph()
        intro.add_run("Latest available economic indicators from major economies.").italic = True
        intro.runs[0].font.color.rgb = RGBColor(102, 102, 102)
        
        # Parse and add the content
        for line in key_numbers.split('\n'):
            if line.strip():
                p = self.doc.add_paragraph()
                if line.startswith('**'):
                    run = p.add_run(line.strip('*'))
                    run.bold = True
                    run.font.size = Pt(12)
                elif line.startswith('•'):
                    run = p.add_run(line)
                    run.font.size = Pt(11)
                else:
                    run = p.add_run(line)
                    run.font.size = Pt(10)
                    run.font.color.rgb = RGBColor(102, 102, 102)
    
    def _add_sentiment_section(self, sentiment: str):
        """Add sentiment analysis section."""
        self.doc.add_heading("MARKET SENTIMENT", level=1)
        
        intro = self.doc.add_paragraph()
        intro.add_run("Overall economic sentiment based on this week's coverage.").italic = True
        intro.runs[0].font.color.rgb = RGBColor(102, 102, 102)
        
        # Parse and add with color coding
        for line in sentiment.split('\n'):
            if line.strip():
                p = self.doc.add_paragraph()
                # Color code sentiment indicators
                if 'BULLISH' in line or '🟢' in line:
                    run = p.add_run(line.replace('🟢', '[BULLISH] '))
                    run.bold = True
                    run.font.color.rgb = RGBColor(0, 128, 0)
                elif 'BEARISH' in line or '🔴' in line:
                    run = p.add_run(line.replace('🔴', '[BEARISH] '))
                    run.bold = True
                    run.font.color.rgb = RGBColor(180, 0, 0)
                elif 'NEUTRAL' in line or '🟡' in line:
                    run = p.add_run(line.replace('🟡', '[NEUTRAL] '))
                    run.bold = True
                    run.font.color.rgb = RGBColor(180, 150, 0)
                elif line.startswith('**'):
                    run = p.add_run(line.strip('*'))
                    run.bold = True
                else:
                    p.add_run(line)
        
        self.doc.add_paragraph()
    
    def _add_implications_section(self, implications: str):
        """Add actionable implications section."""
        self.doc.add_heading("ACTIONABLE IMPLICATIONS", level=1)
        
        intro = self.doc.add_paragraph()
        intro.add_run("Practical considerations for key stakeholders based on this week's intelligence.").italic = True
        intro.runs[0].font.color.rgb = RGBColor(102, 102, 102)
        
        # Parse with markdown handling
        for para in implications.split('\n\n'):
            if para.strip():
                p = self.doc.add_paragraph()
                for line in para.split('\n'):
                    if line.strip():
                        if line.startswith('**FOR'):
                            run = p.add_run(line.strip('*') + '\n')
                            run.bold = True
                            run.font.size = Pt(11)
                            run.font.color.rgb = RGBColor(0, 51, 102)
                        elif line.startswith('**'):
                            run = p.add_run(line.strip('*') + '\n')
                            run.bold = True
                        elif line.startswith('-'):
                            p.add_run(line + '\n')
                        else:
                            p.add_run(line + '\n')
        
        self.doc.add_page_break()
    
    def _add_geographic_section(self, geographic: dict):
        """Add geographic/regional breakdown section."""
        if not geographic:
            return
            
        self.doc.add_heading("REGIONAL BREAKDOWN", level=1)
        
        intro = self.doc.add_paragraph()
        intro.add_run("Coverage by geographic region.").italic = True
        intro.runs[0].font.color.rgb = RGBColor(102, 102, 102)
        
        region_icons = {
            'Global': '🌍',
            'Americas': '🇺🇸',
            'Europe': '🇪🇺',
            'Asia-Pacific': '🌏',
            'India': '🇮🇳',
        }
        
        for region, data in geographic.items():
            if data.get('count', 0) == 0:
                continue
                
            # Region header
            region_p = self.doc.add_paragraph()
            icon = region_icons.get(region, '📍')
            region_run = region_p.add_run(f"{icon} {region}")
            region_run.bold = True
            region_run.font.size = Pt(12)
            region_run.font.color.rgb = RGBColor(0, 51, 102)
            
            # Stats
            stats_p = self.doc.add_paragraph()
            stats_p.add_run(
                f"   {data['count']} articles from: " + 
                ", ".join(data.get('sources', [])[:4])
            )
            stats_p.runs[0].font.size = Pt(10)
            stats_p.runs[0].font.color.rgb = RGBColor(102, 102, 102)
            
            # Top headlines
            for headline in data.get('headlines', [])[:2]:
                hl_p = self.doc.add_paragraph()
                hl_p.add_run(f"   • {headline[:70]}...")
                hl_p.runs[0].font.size = Pt(9)
        
        self.doc.add_paragraph()
