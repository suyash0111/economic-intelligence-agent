"""
Document Generator - Creates professionally formatted Word documents.
Complete rewrite for proper typography, layout, and structure.
"""

from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
from pathlib import Path
from datetime import datetime
import logging
import re

from collectors.base_collector import Article
from config.settings import Settings

logger = logging.getLogger(__name__)

# =========================================================================
# DESIGN CONSTANTS
# =========================================================================

# Color Palette
NAVY = RGBColor(0x0D, 0x1B, 0x2A)      # Primary headers
DARK_BLUE = RGBColor(0x1B, 0x3A, 0x4B)  # Secondary headers
ACCENT_BLUE = RGBColor(0x00, 0x66, 0x99) # Subheadings
LINK_BLUE = RGBColor(0x05, 0x63, 0xC1)   # Hyperlinks
GREY_TEXT = RGBColor(0x71, 0x80, 0x96)    # Captions, dates
LIGHT_GREY = RGBColor(0xA0, 0xAE, 0xC0)  # Subtle text
RED = RGBColor(0xB4, 0x00, 0x00)          # Critical items
ORANGE = RGBColor(0xC8, 0x64, 0x00)       # Important items
GREEN = RGBColor(0x00, 0x78, 0x00)        # Positive/notable

# Font
FONT_FAMILY = 'Calibri'
BODY_SIZE = Pt(10.5)
SMALL_SIZE = Pt(9)
CAPTION_SIZE = Pt(8.5)

# Hex color strings for XML shading
SHADE_TITLE_BG = "0D1B2A"
SHADE_SECTION_BG = "E8EDF2"
SHADE_ARTICLE_BG = "F4F6F8"
SHADE_CRITICAL = "FFF0F0"
SHADE_IMPORTANT = "FFF8F0"


class DocumentGenerator:
    """
    Generates professionally formatted Word documents for the
    Global Pulse Weekly Economic Intelligence Report.
    """

    def __init__(self):
        self.doc = None

    # =====================================================================
    # PUBLIC API
    # =====================================================================

    def generate(
        self,
        articles_by_org: dict[str, list[Article]],
        executive_summary: str,
        date_range: str,
        output_path: Path = None,
        all_articles: list = None,
        tldr_top5: str = "",
        cross_source_synthesis: str = "",
        theme_summary: dict = None,
        sentiment_analysis: str = "",
        risk_assessment: str = "",
        actionable_implications: str = "",
        geographic_summary: dict = None,
        key_numbers: str = "",
        forward_watchlist: str = "",
        charts: list = None
    ) -> Path:
        """Generate institutional-grade Word document report (WEF/BIS structure)."""
        self.doc = Document()
        self._setup_document()

        # Separate charts by type for inline placement
        chart_map = {}
        remaining_charts = []
        if charts:
            for title, image_bytes in charts:
                title_lower = title.lower()
                if 'economic indicator' in title_lower or 'fred' in title_lower:
                    chart_map['macro'] = (title, image_bytes)
                elif 'importance' in title_lower:
                    chart_map['importance'] = (title, image_bytes)
                elif 'source coverage' in title_lower or 'articles per' in title_lower:
                    chart_map['sources'] = (title, image_bytes)
                elif 'topic' in title_lower or 'distribution' in title_lower:
                    chart_map['topics'] = (title, image_bytes)
                elif 'cross-source' in title_lower or 'stacked' in title_lower:
                    chart_map['cross_source'] = (title, image_bytes)
                else:
                    remaining_charts.append((title, image_bytes))

        # === PAGE 1: Cover ===
        self._add_cover_page(date_range)

        # === PAGE 2: Table of Contents ===
        self._add_table_of_contents()

        # === SECTION 1: THIS WEEK AT A GLANCE ===
        if tldr_top5:
            self._add_section_header("THIS WEEK AT A GLANCE", "1")
            self._add_intro_text(
                "The most consequential economic developments this week, "
                "ranked by significance across 39 monitored organizations."
            )
            self._add_bluf_content(tldr_top5)
            self.doc.add_page_break()

        # === SECTION 2: EXECUTIVE NARRATIVE (moved up from old section 4) ===
        self._add_section_header("EXECUTIVE NARRATIVE", "2")
        self._add_intro_text(
            "A connected narrative of this week's economic landscape \u2014 "
            "what happened, why it matters, and what to watch."
        )
        self._add_formatted_text(executive_summary)
        self.doc.add_page_break()

        # === SECTION 3: MACROECONOMIC DASHBOARD (numbers + inline charts) ===
        if key_numbers:
            self._add_section_header("MACROECONOMIC DASHBOARD", "3")
            self._add_intro_text(
                "Key economic indicators from the Federal Reserve Economic Data (FRED) "
                "and AI-extracted statistics from this week's reports."
            )
            self._add_formatted_text(key_numbers)
            if 'macro' in chart_map:
                self._add_inline_chart(*chart_map['macro'], "Key US/Global Economic Indicators")
            if 'importance' in chart_map:
                self._add_inline_chart(*chart_map['importance'], "Intelligence Importance Distribution")

        # === SECTION 4: RISK & SENTIMENT ASSESSMENT ===
        if risk_assessment or sentiment_analysis:
            self._add_section_header("RISK & SENTIMENT ASSESSMENT", "4")
            self._add_intro_text(
                "Multi-horizon risk radar and market sentiment analysis "
                "based on cross-source signal aggregation."
            )
            if risk_assessment:
                self._add_formatted_text(risk_assessment)
            if sentiment_analysis:
                self._add_sentiment_content(sentiment_analysis)
            self.doc.add_page_break()

        # === SECTION 5: CROSS-SOURCE INTELLIGENCE ===
        if cross_source_synthesis:
            self._add_section_header("CROSS-SOURCE INTELLIGENCE", "5")
            self._add_intro_text(
                "Consensus, divergence, and blind spots across 39 organizations. "
                "This section identifies what sources agree on, where they disagree, "
                "and what nobody is covering."
            )
            self._add_formatted_text(cross_source_synthesis)
            if 'sources' in chart_map:
                self._add_inline_chart(*chart_map['sources'], "Intelligence Source Coverage")
            if 'cross_source' in chart_map:
                self._add_inline_chart(*chart_map['cross_source'], "Cross-Source Topic Coverage")

        # === SECTION 6: THEMATIC DEEP-DIVES ===
        if theme_summary:
            self._add_section_header("THEMATIC DEEP-DIVES", "6")
            self._add_intro_text(
                "In-depth analysis of the week's dominant economic themes, "
                "modeled on BIS Quarterly Review analytical approach."
            )
            self._add_theme_content(theme_summary)
            if 'topics' in chart_map:
                self._add_inline_chart(*chart_map['topics'], "Topic Distribution Across Sources")
            self.doc.add_page_break()

        # === SECTION 7: REGIONAL OUTLOOK ===
        if geographic_summary:
            self._add_section_header("REGIONAL OUTLOOK", "7")
            self._add_intro_text(
                "Geographic breakdown of economic developments, "
                "organized by major economic region."
            )
            self._add_geographic_content(geographic_summary)

        # === SECTION 8: STRATEGIC IMPLICATIONS ===
        if actionable_implications:
            self._add_section_header("STRATEGIC IMPLICATIONS", "8")
            self._add_intro_text(
                "Practical considerations for policymakers, investors, and businesses. "
                "The 'So What?' of this week's intelligence."
            )
            self._add_formatted_text(actionable_implications)
            self.doc.add_page_break()

        # === SECTION 9: FORWARD WATCHLIST (NEW) ===
        if forward_watchlist:
            self._add_section_header("FORWARD WATCHLIST", "9")
            self._add_intro_text(
                "Key events, data releases, and conditional scenarios to monitor "
                "in the coming week."
            )
            self._add_formatted_text(forward_watchlist)
            self.doc.add_page_break()

        # === SECTION 10: DETAILED INTELLIGENCE BY SECTOR ===
        self._add_section_header("DETAILED INTELLIGENCE BY SECTOR", "10")
        self._add_intro_text(
            "Comprehensive coverage organized by economic sector. "
            "Articles with multi-pass deep verification are marked."
        )
        self._add_sector_intelligence(articles_by_org, all_articles or [])

        # === APPENDIX A: METHODOLOGY & DATA SOURCES ===
        self.doc.add_page_break()
        self._add_section_header("APPENDIX A: METHODOLOGY & DATA SOURCES", "A")
        self._add_methodology_appendix(articles_by_org, all_articles or [])

        # === APPENDIX B: COMPLETE CHARTS ===
        if remaining_charts:
            self.doc.add_page_break()
            self._add_section_header("APPENDIX B: ECONOMIC DASHBOARD", "B")
            self._add_intro_text("Complete set of auto-generated analytical charts.")
            self._add_charts_section(remaining_charts)

        # Save
        if output_path is None:
            Settings.ensure_output_dir()
            output_path = Settings.OUTPUT_DIR / f"Global_Pulse_Weekly_Report_{datetime.now().strftime('%Y%m%d')}.docx"

        self.doc.save(output_path)
        logger.info(f"Document saved: {output_path}")
        return output_path

    # =====================================================================
    # DOCUMENT SETUP
    # =====================================================================

    def _setup_document(self):
        """Set up document defaults: font, margins, styles."""
        # Set default font for entire document
        style = self.doc.styles['Normal']
        font = style.font
        font.name = FONT_FAMILY
        font.size = BODY_SIZE
        font.color.rgb = RGBColor(0x33, 0x33, 0x33)

        # Set paragraph defaults
        pf = style.paragraph_format
        pf.space_after = Pt(6)
        pf.space_before = Pt(2)
        pf.line_spacing = 1.15

        # Configure heading styles
        for level in range(1, 4):
            heading_style = self.doc.styles[f'Heading {level}']
            heading_style.font.name = FONT_FAMILY
            heading_style.font.color.rgb = NAVY

            if level == 1:
                heading_style.font.size = Pt(18)
                heading_style.paragraph_format.space_before = Pt(24)
                heading_style.paragraph_format.space_after = Pt(10)
            elif level == 2:
                heading_style.font.size = Pt(14)
                heading_style.paragraph_format.space_before = Pt(18)
                heading_style.paragraph_format.space_after = Pt(8)
            elif level == 3:
                heading_style.font.size = Pt(12)
                heading_style.font.color.rgb = ACCENT_BLUE
                heading_style.paragraph_format.space_before = Pt(12)
                heading_style.paragraph_format.space_after = Pt(6)

        # Set page margins
        for section in self.doc.sections:
            section.top_margin = Cm(2.0)
            section.bottom_margin = Cm(2.0)
            section.left_margin = Cm(2.5)
            section.right_margin = Cm(2.5)

        # Add page numbers in footer
        self._add_page_numbers()

    def _add_page_numbers(self):
        """Add page numbers to footer."""
        section = self.doc.sections[0]
        footer = section.footer
        footer.is_linked_to_previous = False

        p = footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # "The Global Pulse" text
        run = p.add_run("The Global Pulse  |  ")
        run.font.size = Pt(8)
        run.font.color.rgb = LIGHT_GREY
        run.font.name = FONT_FAMILY

        # Page number field
        run2 = p.add_run("Page ")
        run2.font.size = Pt(8)
        run2.font.color.rgb = LIGHT_GREY
        run2.font.name = FONT_FAMILY

        # Insert PAGE field
        fld_xml = (
            '<w:fldSimple {} w:instr=" PAGE "><w:r><w:t>0</w:t></w:r></w:fldSimple>'
        ).format(nsdecls('w'))
        fld_elem = parse_xml(fld_xml)
        p._p.append(fld_elem)

    # =====================================================================
    # COVER PAGE
    # =====================================================================

    def _add_cover_page(self, date_range: str):
        """Add a professional cover page."""
        # Top spacer
        for _ in range(4):
            p = self.doc.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.space_before = Pt(0)

        # Title
        title = self.doc.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title.add_run("THE GLOBAL PULSE")
        run.font.size = Pt(36)
        run.font.bold = True
        run.font.color.rgb = NAVY
        run.font.name = FONT_FAMILY
        title.paragraph_format.space_after = Pt(4)

        # Decorative line
        line = self.doc.add_paragraph()
        line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = line.add_run("_" * 40)
        run.font.color.rgb = ACCENT_BLUE
        run.font.size = Pt(12)
        line.paragraph_format.space_after = Pt(8)

        # Subtitle
        sub = self.doc.add_paragraph()
        sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = sub.add_run("Weekly Economic Intelligence Report")
        run.font.size = Pt(16)
        run.font.color.rgb = DARK_BLUE
        run.font.name = FONT_FAMILY
        sub.paragraph_format.space_after = Pt(20)

        # Date range
        date_p = self.doc.add_paragraph()
        date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = date_p.add_run(date_range)
        run.font.size = Pt(14)
        run.font.italic = True
        run.font.color.rgb = GREY_TEXT
        run.font.name = FONT_FAMILY
        date_p.paragraph_format.space_after = Pt(40)

        # Description
        desc = self.doc.add_paragraph()
        desc.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for text in [
            "360-Degree Analysis of Global Economic Developments",
            "Covering 39 Leading Organizations Worldwide",
            "",
            "Macro & Micro Indicators  |  Policy Implications  |  Industry Insights",
        ]:
            run = desc.add_run(text + "\n")
            run.font.size = Pt(11)
            run.font.color.rgb = GREY_TEXT
            run.font.name = FONT_FAMILY

        # Powered by
        powered = self.doc.add_paragraph()
        powered.alignment = WD_ALIGN_PARAGRAPH.CENTER
        powered.paragraph_format.space_before = Pt(60)
        run = powered.add_run("Powered by NVIDIA NIM 5-Model Architecture + Multi-Provider Fallback")
        run.font.size = Pt(9)
        run.font.italic = True
        run.font.color.rgb = LIGHT_GREY
        run.font.name = FONT_FAMILY

        # Tagline
        tagline = self.doc.add_paragraph()
        tagline.alignment = WD_ALIGN_PARAGRAPH.CENTER
        tagline.paragraph_format.space_before = Pt(8)
        run2 = tagline.add_run("360-Degree Analysis of Global Economic Developments")
        run2.font.size = Pt(9)
        run2.font.color.rgb = GREY_TEXT
        run2.font.name = FONT_FAMILY

        self.doc.add_page_break()

    # =====================================================================
    # TABLE OF CONTENTS
    # =====================================================================

    def _add_table_of_contents(self):
        """Add a Table of Contents page."""
        h = self.doc.add_heading("TABLE OF CONTENTS", level=1)

        toc_items = [
            ("1.", "This Week at a Glance"),
            ("2.", "Executive Narrative"),
            ("3.", "Macroeconomic Dashboard"),
            ("4.", "Risk & Sentiment Assessment"),
            ("5.", "Cross-Source Intelligence"),
            ("6.", "Thematic Deep-Dives"),
            ("7.", "Regional Outlook"),
            ("8.", "Strategic Implications"),
            ("9.", "Forward Watchlist"),
            ("10.", "Detailed Intelligence by Sector"),
            ("A.", "Methodology & Data Sources"),
            ("B.", "Economic Dashboard (Charts)"),
        ]

        for num, title in toc_items:
            p = self.doc.add_paragraph()
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.left_indent = Inches(0.3)

            num_run = p.add_run(f"{num}  ")
            num_run.font.bold = True
            num_run.font.size = Pt(11)
            num_run.font.color.rgb = ACCENT_BLUE

            title_run = p.add_run(title)
            title_run.font.size = Pt(11)

        self.doc.add_page_break()

    # =====================================================================
    # SECTION HEADERS
    # =====================================================================

    def _add_section_header(self, title: str, number: str = ""):
        """Add a visually distinct section header with background shading."""
        # Add a heading
        display_title = f"{number}. {title}" if number else title
        h = self.doc.add_heading(display_title, level=1)

        # Add shading to the heading paragraph
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{SHADE_SECTION_BG}"/>')
        h.paragraph_format.element.get_or_add_pPr().append(shading)

        # Add thin accent line below
        line = self.doc.add_paragraph()
        line.paragraph_format.space_after = Pt(8)
        line.paragraph_format.space_before = Pt(0)

    def _add_intro_text(self, text: str):
        """Add italic intro/description text below a section header."""
        p = self.doc.add_paragraph()
        run = p.add_run(text)
        run.font.italic = True
        run.font.color.rgb = GREY_TEXT
        run.font.size = SMALL_SIZE
        p.paragraph_format.space_after = Pt(10)

    # =====================================================================
    # MARKDOWN-TO-WORD PARSER
    # =====================================================================

    def _add_formatted_text(self, text: str):
        """
        Parse markdown-like text and render it properly in Word.
        Handles: **bold**, *italic*, - bullets, ## headers, numbered lists.
        """
        if not text:
            return

        paragraphs = text.split('\n')
        current_paragraph = None

        for line in paragraphs:
            stripped = line.strip()
            if not stripped:
                current_paragraph = None  # Reset on blank line
                continue

            # Heading lines: **SOME HEADER** or ## Header or ### Header or #### Header
            if (stripped.startswith('**') and stripped.endswith('**') and
                    stripped.count('**') == 2):
                inner = stripped[2:-2].strip()
                p = self.doc.add_paragraph()
                p.paragraph_format.space_before = Pt(12)
                p.paragraph_format.space_after = Pt(4)
                run = p.add_run(inner)
                run.font.bold = True
                run.font.size = Pt(11)
                run.font.color.rgb = DARK_BLUE
                current_paragraph = None
                continue

            # Handle all markdown heading levels: ####, ###, ##
            heading_match = re.match(r'^(#{2,4})\s+(.+)', stripped)
            if heading_match:
                heading_text = heading_match.group(2).strip().rstrip('*')  # Remove trailing **
                p = self.doc.add_paragraph()
                p.paragraph_format.space_before = Pt(12)
                p.paragraph_format.space_after = Pt(4)
                run = p.add_run(heading_text)
                run.font.bold = True
                run.font.size = Pt(11)
                run.font.color.rgb = DARK_BLUE
                current_paragraph = None
                continue

            # Section-numbered headers: "1. THE NON-OBVIOUS TRUTHS" (all caps with number)
            section_match = re.match(r'^(\d+)\.\s+([A-Z][A-Z\s&]+)$', stripped)
            if section_match:
                p = self.doc.add_paragraph()
                p.paragraph_format.space_before = Pt(12)
                p.paragraph_format.space_after = Pt(4)
                run = p.add_run(f"{section_match.group(1)}. {section_match.group(2)}")
                run.font.bold = True
                run.font.size = Pt(11)
                run.font.color.rgb = ACCENT_BLUE
                current_paragraph = None
                continue

            # Bullet points: - text or * text
            if stripped.startswith('- ') or stripped.startswith('* '):
                p = self.doc.add_paragraph()
                p.paragraph_format.left_indent = Inches(0.3)
                p.paragraph_format.space_after = Pt(3)
                p.paragraph_format.space_before = Pt(1)
                bullet_text = stripped[2:]
                self._add_inline_formatted_run(p, "  " + bullet_text)
                current_paragraph = None
                continue

            # Numbered items: 1. text, 2. text
            num_match = re.match(r'^(\d+)\.\s+(.+)', stripped)
            if num_match:
                p = self.doc.add_paragraph()
                p.paragraph_format.left_indent = Inches(0.3)
                p.paragraph_format.space_after = Pt(3)
                num_run = p.add_run(f"{num_match.group(1)}. ")
                num_run.font.bold = True
                self._add_inline_formatted_run(p, num_match.group(2))
                current_paragraph = None
                continue

            # Regular paragraph with inline formatting
            p = self.doc.add_paragraph()
            p.paragraph_format.space_after = Pt(6)
            self._add_inline_formatted_run(p, stripped)
            current_paragraph = p

    def _add_inline_formatted_run(self, paragraph, text: str):
        """
        Parse inline **bold** and *italic* markers within a line
        and add properly formatted runs to the paragraph.
        """
        # Split on **bold** markers
        parts = re.split(r'(\*\*.*?\*\*)', text)

        for part in parts:
            if not part:
                continue

            if part.startswith('**') and part.endswith('**'):
                # Bold text
                inner = part[2:-2]
                # Check for nested *italic* inside bold
                italic_parts = re.split(r'(\*.*?\*)', inner)
                for ip in italic_parts:
                    if ip.startswith('*') and ip.endswith('*'):
                        run = paragraph.add_run(ip[1:-1])
                        run.font.bold = True
                        run.font.italic = True
                    else:
                        run = paragraph.add_run(ip)
                        run.font.bold = True
            else:
                # Check for *italic* in non-bold text
                italic_parts = re.split(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', part)
                for i, ip in enumerate(italic_parts):
                    run = paragraph.add_run(ip)
                    if i % 2 == 1:
                        run.font.italic = True

    # =====================================================================
    # TL;DR TOP 5
    # =====================================================================

    def _add_tldr_content(self, content: str):
        """Add TL;DR Top 5 with color-coded priority indicators."""
        self._add_intro_text("The most important developments ranked by impact score.")

        for line in content.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue

            p = self.doc.add_paragraph()
            p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.left_indent = Inches(0.2)

            # Determine priority level and apply formatting
            if any(marker in stripped for marker in ['[CRITICAL]', chr(0x1F534)]):
                clean = stripped.replace(chr(0x1F534), '').strip()
                tag = p.add_run("[CRITICAL] ")
                tag.font.bold = True
                tag.font.color.rgb = RED
                tag.font.size = BODY_SIZE
                self._add_inline_formatted_run(p, clean)
                # Add background shading
                shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{SHADE_CRITICAL}"/>')
                p.paragraph_format.element.get_or_add_pPr().append(shading)

            elif any(marker in stripped for marker in ['[IMPORTANT]', chr(0x1F7E0)]):
                clean = stripped.replace(chr(0x1F7E0), '').strip()
                tag = p.add_run("[IMPORTANT] ")
                tag.font.bold = True
                tag.font.color.rgb = ORANGE
                tag.font.size = BODY_SIZE
                self._add_inline_formatted_run(p, clean)
                shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{SHADE_IMPORTANT}"/>')
                p.paragraph_format.element.get_or_add_pPr().append(shading)

            elif any(marker in stripped for marker in ['[NOTABLE]', chr(0x1F7E2)]):
                clean = stripped.replace(chr(0x1F7E2), '').strip()
                tag = p.add_run("[NOTABLE] ")
                tag.font.bold = True
                tag.font.color.rgb = GREEN
                tag.font.size = BODY_SIZE
                self._add_inline_formatted_run(p, clean)
            else:
                self._add_inline_formatted_run(p, stripped)

    # =====================================================================
    # SENTIMENT
    # =====================================================================

    def _add_sentiment_content(self, content: str):
        """Add sentiment analysis with color-coded indicators."""
        self._add_intro_text("Overall economic sentiment based on this week's coverage.")

        for line in content.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue

            p = self.doc.add_paragraph()
            p.paragraph_format.space_after = Pt(4)

            # Detect sentiment markers
            if 'BULLISH' in stripped.upper():
                clean = stripped.replace(chr(0x1F7E2), '[BULLISH]')
                run = p.add_run(clean)
                run.font.bold = True
                run.font.color.rgb = GREEN
            elif 'BEARISH' in stripped.upper():
                clean = stripped.replace(chr(0x1F534), '[BEARISH]')
                run = p.add_run(clean)
                run.font.bold = True
                run.font.color.rgb = RED
            elif 'NEUTRAL' in stripped.upper():
                clean = stripped.replace(chr(0x1F7E1), '[NEUTRAL]')
                run = p.add_run(clean)
                run.font.bold = True
                run.font.color.rgb = ORANGE
            elif stripped.startswith('**'):
                self._add_inline_formatted_run(p, stripped)
            elif stripped.startswith('- ') or stripped.startswith('* '):
                p.paragraph_format.left_indent = Inches(0.3)
                self._add_inline_formatted_run(p, "  " + stripped[2:])
            else:
                self._add_inline_formatted_run(p, stripped)

    # =====================================================================
    # GEOGRAPHIC BREAKDOWN
    # =====================================================================

    def _add_geographic_content(self, geographic: dict):
        """Add geographic summary as a proper Word table."""
        if not geographic:
            return

        self._add_intro_text("Coverage by geographic region.")

        # Create a table
        regions_with_data = {k: v for k, v in geographic.items() if v.get('count', 0) > 0}
        if not regions_with_data:
            return

        table = self.doc.add_table(rows=1, cols=4)
        table.style = 'Table Grid'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        # Header row
        headers = ['Region', 'Articles', 'Sources', 'Top Headlines']
        for i, header in enumerate(headers):
            cell = table.rows[0].cells[i]
            cell.text = header
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.bold = True
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                    run.font.size = Pt(10)
                    run.font.name = FONT_FAMILY
            # Dark background
            shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{SHADE_TITLE_BG}"/>')
            cell._tc.get_or_add_tcPr().append(shading)

        region_labels = {
            'Global': 'Global',
            'Americas': 'Americas',
            'Europe': 'Europe',
            'Asia-Pacific': 'Asia-Pacific',
            'India': 'India',
        }

        for region, data in regions_with_data.items():
            row = table.add_row()
            row.cells[0].text = region_labels.get(region, region)
            row.cells[1].text = str(data.get('count', 0))
            row.cells[2].text = ", ".join(data.get('sources', [])[:4])
            headlines = data.get('headlines', [])[:2]
            row.cells[3].text = "\n".join([f"- {h[:60]}..." for h in headlines]) if headlines else "—"

            # Format cells
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.size = Pt(9)
                        run.font.name = FONT_FAMILY

        # Set column widths
        widths = [Inches(1.2), Inches(0.8), Inches(2.0), Inches(3.0)]
        for i, width in enumerate(widths):
            for row in table.rows:
                row.cells[i].width = width

        self.doc.add_paragraph()  # Spacer after table

    # =====================================================================
    # THEMATIC OVERVIEW
    # =====================================================================

    def _add_theme_content(self, theme_summary: dict):
        """Add theme-based summary with clean formatting."""
        if not theme_summary:
            return

        self._add_intro_text("Articles grouped by economic theme.")

        for theme, data in theme_summary.items():
            # Theme heading
            p = self.doc.add_paragraph()
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(2)
            run = p.add_run(f">> {theme}")
            run.font.bold = True
            run.font.size = Pt(11)
            run.font.color.rgb = DARK_BLUE

            # Stats line
            stats = self.doc.add_paragraph()
            stats.paragraph_format.left_indent = Inches(0.3)
            stats.paragraph_format.space_after = Pt(2)
            run = stats.add_run(
                f"{data['count']} items from {len(data['sources'])} sources: "
                + ", ".join(data['sources'][:5])
            )
            run.font.size = SMALL_SIZE
            run.font.color.rgb = GREY_TEXT

            # Headlines
            for headline in data.get('headlines', [])[:3]:
                hl = self.doc.add_paragraph()
                hl.paragraph_format.left_indent = Inches(0.5)
                hl.paragraph_format.space_after = Pt(1)
                run = hl.add_run(f"- {headline[:80]}")
                run.font.size = SMALL_SIZE

    # =====================================================================
    # ORGANIZATION & ARTICLE SECTIONS
    # =====================================================================

    def _group_by_category(self, articles_by_org: dict) -> dict:
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
        return [
            'Central Bank', 'International', 'Consulting', 'Think Tank',
            'Investment Bank', 'News', 'Data Provider', 'Rating Agency', 'India',
        ]

    def _add_category_section(self, category: str, orgs: dict, section_num: str = ""):
        """Add a category section with all its organizations."""
        category_titles = {
            'Central Bank': 'Central Banks',
            'International': 'International & Multilateral Organizations',
            'Consulting': 'Consulting Firms & Professional Services',
            'Think Tank': 'Think Tanks & Research Institutes',
            'Investment Bank': 'Investment Banks Research',
            'News': 'News & Data Providers',
            'Data Provider': 'Data & Analytics Providers',
            'Rating Agency': 'Credit Rating Agencies',
            'India': 'India-Specific Sources',
        }

        title = category_titles.get(category, category)
        self._add_section_header(title, section_num)

        total_articles = sum(len(arts) for arts in orgs.values())
        self._add_intro_text(
            f"{len(orgs)} organizations  |  {total_articles} articles this week"
        )

        for org_name, articles in sorted(orgs.items()):
            self._add_organization_section(org_name, articles)

        self.doc.add_page_break()

    def _add_organization_section(self, org_name: str, articles: list[Article]):
        """Add a section for a single organization."""
        if not articles:
            return

        # Organization heading
        full_name = articles[0].source_full
        self.doc.add_heading(full_name, level=2)

        # Item count
        p = self.doc.add_paragraph()
        run = p.add_run(f"{len(articles)} items this week")
        run.font.italic = True
        run.font.size = SMALL_SIZE
        run.font.color.rgb = GREY_TEXT
        p.paragraph_format.space_after = Pt(8)

        # Articles — skip filtered (non-economic) content
        for article in articles:
            if getattr(article, 'verification_status', '') == 'filtered':
                continue
            self._add_article(article)

    def _add_article(self, article: Article):
        """Add a single article with proper formatting and visual separation."""

        # --- Article Title ---
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(3)

        # Importance indicator
        if article.importance_score >= 8:
            tag = p.add_run("[CRITICAL] ")
            tag.font.bold = True
            tag.font.color.rgb = RED
            tag.font.size = CAPTION_SIZE
        elif article.importance_score >= 5:
            tag = p.add_run("[IMPORTANT] ")
            tag.font.bold = True
            tag.font.color.rgb = ORANGE
            tag.font.size = CAPTION_SIZE

        # Title
        title_run = p.add_run(article.title)
        title_run.bold = True
        title_run.font.size = Pt(11)

        # Date
        if article.published_date:
            date_run = p.add_run(f"  ({article.published_date.strftime('%b %d, %Y')})")
            date_run.font.size = CAPTION_SIZE
            date_run.font.color.rgb = GREY_TEXT

        # Deep analysis badge
        if article.verification_status == "deep_verified" and article.deep_analysis:
            badge = p.add_run("  [Full Report Analyzed]")
            badge.font.size = CAPTION_SIZE
            badge.font.color.rgb = GREEN
            badge.font.italic = True

        # --- AI Summary ---
        if article.ai_summary:
            summary_p = self.doc.add_paragraph()
            summary_p.paragraph_format.left_indent = Inches(0.25)
            summary_p.paragraph_format.space_after = Pt(4)
            run = summary_p.add_run(article.ai_summary)
            run.font.size = Pt(10)

        # --- Deep Analysis Content ---
        if article.deep_analysis and article.deep_analysis.get('success'):
            self._add_deep_analysis_content(article.deep_analysis)

        # --- AI Analysis (detailed) ---
        if article.ai_analysis:
            # Render as properly formatted paragraphs
            analysis_lines = article.ai_analysis.split('\n')
            for line in analysis_lines:
                stripped = line.strip()
                if not stripped:
                    continue

                ap = self.doc.add_paragraph()
                ap.paragraph_format.left_indent = Inches(0.25)
                ap.paragraph_format.space_after = Pt(3)

                # Handle section-numbered headers like "1. THE NON-OBVIOUS TRUTHS"
                section_match = re.match(r'^(\d+)\.\s+([A-Z][A-Z\s&]+)$', stripped)
                if section_match:
                    run = ap.add_run(f"{section_match.group(1)}. {section_match.group(2)}")
                    run.font.bold = True
                    run.font.size = Pt(10)
                    run.font.color.rgb = ACCENT_BLUE
                elif stripped.startswith('**') and stripped.endswith('**'):
                    run = ap.add_run(stripped.strip('*'))
                    run.font.bold = True
                    run.font.size = Pt(10)
                    run.font.color.rgb = ACCENT_BLUE
                elif re.match(r'^#{2,4}\s+', stripped):
                    # Handle markdown headings in analysis
                    clean = re.sub(r'^#{2,4}\s+', '', stripped).rstrip('*')
                    run = ap.add_run(clean)
                    run.font.bold = True
                    run.font.size = Pt(10)
                    run.font.color.rgb = ACCENT_BLUE
                elif stripped.startswith('- ') or stripped.startswith('* '):
                    ap.paragraph_format.left_indent = Inches(0.5)
                    self._add_inline_formatted_run(ap, stripped[2:])
                    for run in ap.runs:
                        run.font.size = Pt(10)
                else:
                    self._add_inline_formatted_run(ap, stripped)
                    for run in ap.runs:
                        run.font.size = Pt(10)

        # --- Link ---
        link_p = self.doc.add_paragraph()
        link_p.paragraph_format.left_indent = Inches(0.25)
        link_p.paragraph_format.space_after = Pt(6)

        label = link_p.add_run("Source: ")
        label.font.size = CAPTION_SIZE
        label.font.color.rgb = GREY_TEXT

        # Add clickable hyperlink
        self._add_hyperlink(link_p, article.url, article.url[:80] + ("..." if len(article.url) > 80 else ""))

        # --- Visual separator between articles ---
        sep = self.doc.add_paragraph()
        sep.paragraph_format.space_before = Pt(2)
        sep.paragraph_format.space_after = Pt(2)
        run = sep.add_run("_" * 60)
        run.font.color.rgb = RGBColor(0xE2, 0xE8, 0xF0)
        run.font.size = Pt(6)

    def _add_deep_analysis_content(self, deep: dict):
        """Add deep analysis sections using proper Word formatting."""
        from io import BytesIO

        # Key Statistics (AI-extracted, clean sentences)
        if deep.get('key_statistics'):
            header = self.doc.add_paragraph()
            header.paragraph_format.left_indent = Inches(0.25)
            header.paragraph_format.space_before = Pt(6)
            run = header.add_run("KEY STATISTICS")
            run.font.bold = True
            run.font.size = Pt(10)
            run.font.color.rgb = ACCENT_BLUE

            for stat in deep['key_statistics'][:8]:
                sp = self.doc.add_paragraph()
                sp.paragraph_format.left_indent = Inches(0.5)
                sp.paragraph_format.space_after = Pt(2)
                run = sp.add_run(f"- {stat}")
                run.font.size = SMALL_SIZE

        # Charts — embed actual images from PDF + descriptions
        chart_images = deep.get('chart_images', [])
        chart_descriptions = deep.get('chart_descriptions', [])

        if chart_descriptions:
            header = self.doc.add_paragraph()
            header.paragraph_format.left_indent = Inches(0.25)
            header.paragraph_format.space_before = Pt(6)
            run = header.add_run("CHARTS FROM REPORT")
            run.font.bold = True
            run.font.size = Pt(10)
            run.font.color.rgb = ACCENT_BLUE

            for i, desc in enumerate(chart_descriptions[:3]):
                # Embed the actual chart image if available
                if i < len(chart_images):
                    try:
                        image_stream = BytesIO(chart_images[i])
                        self.doc.add_picture(image_stream, width=Inches(4.5))
                        # Caption below image
                        caption = self.doc.add_paragraph()
                        caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        caption.paragraph_format.space_after = Pt(2)
                        run = caption.add_run(f"Chart {i+1}")
                        run.font.italic = True
                        run.font.size = CAPTION_SIZE
                        run.font.color.rgb = GREY_TEXT
                    except Exception as e:
                        logger.warning(f"Could not embed chart image {i+1}: {e}")

                # Chart analysis description
                cp = self.doc.add_paragraph()
                cp.paragraph_format.left_indent = Inches(0.3)
                cp.paragraph_format.space_after = Pt(8)
                label = cp.add_run(f"Chart {i+1} Analysis: ")
                label.font.bold = True
                label.font.size = SMALL_SIZE
                text = cp.add_run(desc)
                text.font.size = SMALL_SIZE

        # Tables — render structured data as proper Word tables
        table_data = deep.get('table_data', [])
        if table_data:
            header = self.doc.add_paragraph()
            header.paragraph_format.left_indent = Inches(0.25)
            header.paragraph_format.space_before = Pt(6)
            run = header.add_run("KEY TABLES FROM REPORT")
            run.font.bold = True
            run.font.size = Pt(10)
            run.font.color.rgb = ACCENT_BLUE

            for td in table_data[:3]:
                self._render_structured_table(td)
        # Fallback to markdown tables if no structured data
        elif deep.get('table_summaries'):
            header = self.doc.add_paragraph()
            header.paragraph_format.left_indent = Inches(0.25)
            header.paragraph_format.space_before = Pt(6)
            run = header.add_run("KEY TABLES")
            run.font.bold = True
            run.font.size = Pt(10)
            run.font.color.rgb = ACCENT_BLUE

            for summary in deep['table_summaries'][:3]:
                p = self.doc.add_paragraph()
                p.paragraph_format.left_indent = Inches(0.5)
                run = p.add_run(summary)
                run.font.size = SMALL_SIZE

    def _render_structured_table(self, table_info: dict):
        """Render a structured table (headers + rows) as a proper Word table."""
        headers = table_info.get('headers', [])
        rows = table_info.get('rows', [])
        page = table_info.get('page', '?')

        if not headers or not rows:
            return

        # Clean headers
        clean_headers = [str(h).strip() if h else f"Col{i}" for i, h in enumerate(headers)]
        # Limit columns to 6 for readability
        num_cols = min(len(clean_headers), 6)
        clean_headers = clean_headers[:num_cols]

        # Table label
        label = self.doc.add_paragraph()
        label.paragraph_format.left_indent = Inches(0.3)
        label.paragraph_format.space_before = Pt(6)
        run = label.add_run(f"Table from page {page}:")
        run.font.italic = True
        run.font.size = SMALL_SIZE
        run.font.color.rgb = GREY_TEXT

        # Create Word table
        table = self.doc.add_table(rows=1, cols=num_cols)
        table.style = 'Table Grid'

        # Header row
        for i, h in enumerate(clean_headers):
            cell = table.rows[0].cells[i]
            cell.text = h
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.bold = True
                    run.font.size = Pt(8)
                    run.font.name = FONT_FAMILY
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{SHADE_TITLE_BG}"/>')
            cell._tc.get_or_add_tcPr().append(shading)

        # Data rows (limit to 10)
        for row_data in rows[:10]:
            row = table.add_row()
            for i in range(num_cols):
                cell_text = str(row_data[i]).strip() if i < len(row_data) and row_data[i] else ""
                row.cells[i].text = cell_text
                for paragraph in row.cells[i].paragraphs:
                    for run in paragraph.runs:
                        run.font.size = Pt(8)
                        run.font.name = FONT_FAMILY

        self.doc.add_paragraph()  # Spacer

    def _render_markdown_table(self, markdown_text: str):
        """Convert a markdown table to a Word table, or render as text if not parseable."""
        lines = [l.strip() for l in markdown_text.split('\n') if l.strip()]

        # Filter out separator lines (e.g., |---|---|)
        data_lines = []
        for line in lines:
            if line.startswith('|') and not re.match(r'^\|[\s\-:]+\|', line):
                cells = [c.strip() for c in line.strip('|').split('|')]
                data_lines.append(cells)
            elif not line.startswith('|'):
                # Not a table line — render as text
                if line.startswith('**'):
                    p = self.doc.add_paragraph()
                    p.paragraph_format.left_indent = Inches(0.5)
                    self._add_inline_formatted_run(p, line)
                    for r in p.runs:
                        r.font.size = SMALL_SIZE
                    return  # It's a header, not a table

        if len(data_lines) < 2:
            # Not enough data for a table, render as text
            p = self.doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.5)
            run = p.add_run(markdown_text[:300])
            run.font.size = SMALL_SIZE
            return

        # Create Word table
        num_cols = len(data_lines[0])
        table = self.doc.add_table(rows=1, cols=num_cols)
        table.style = 'Table Grid'

        # Header row
        for i, cell_text in enumerate(data_lines[0]):
            cell = table.rows[0].cells[i]
            cell.text = cell_text
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.bold = True
                    run.font.size = Pt(8)
                    run.font.name = FONT_FAMILY

        # Data rows
        for row_data in data_lines[1:]:
            row = table.add_row()
            for i, cell_text in enumerate(row_data):
                if i < num_cols:
                    row.cells[i].text = cell_text
                    for paragraph in row.cells[i].paragraphs:
                        for run in paragraph.runs:
                            run.font.size = Pt(8)
                            run.font.name = FONT_FAMILY

        self.doc.add_paragraph()  # Spacer

    # =====================================================================
    # HYPERLINKS
    # =====================================================================

    def _add_hyperlink(self, paragraph, url: str, text: str = None):
        """Add a real clickable hyperlink to a paragraph."""
        if text is None:
            text = url

        # Create the relationship
        part = paragraph.part
        r_id = part.relate_to(url, 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink', is_external=True)

        # Build the hyperlink XML
        hyperlink = parse_xml(
            f'<w:hyperlink {nsdecls("w")} r:id="{r_id}" '
            f'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<w:r>'
            f'<w:rPr>'
            f'<w:rStyle w:val="Hyperlink"/>'
            f'<w:color w:val="0563C1"/>'
            f'<w:u w:val="single"/>'
            f'<w:sz w:val="{int(CAPTION_SIZE.pt * 2)}"/>'
            f'<w:rFonts w:ascii="{FONT_FAMILY}" w:hAnsi="{FONT_FAMILY}"/>'
            f'</w:rPr>'
            f'<w:t>{self._escape_xml(text)}</w:t>'
            f'</w:r>'
            f'</w:hyperlink>'
        )

        paragraph._p.append(hyperlink)

    @staticmethod
    def _escape_xml(text: str) -> str:
        """Escape special characters for XML."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))

    # =====================================================================
    # ECONOMIC DASHBOARD (Auto-Generated Charts)
    # =====================================================================

    def _add_charts_section(self, charts: list):
        """
        Embed auto-generated charts into the document.
        charts: list of (title, image_bytes) tuples
        """
        import io

        for i, (title, image_bytes) in enumerate(charts):
            try:
                # Chart title
                h = self.doc.add_heading(f"Figure {i+1}: {title}", level=2)
                for run in h.runs:
                    run.font.color.rgb = DARK_BLUE
                    run.font.name = FONT_FAMILY

                # Embed the chart image
                image_stream = io.BytesIO(image_bytes)
                self.doc.add_picture(image_stream, width=Inches(6.0))

                # Center the image
                last_paragraph = self.doc.paragraphs[-1]
                last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

                # Caption
                caption = self.doc.add_paragraph()
                caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = caption.add_run(f"Figure {i+1}: {title}")
                run.font.size = CAPTION_SIZE
                run.font.color.rgb = GREY_TEXT
                run.font.italic = True
                run.font.name = FONT_FAMILY
                caption.paragraph_format.space_after = Pt(20)

            except Exception as e:
                logger.warning(f"Could not embed chart '{title}': {e}")
                p = self.doc.add_paragraph()
                run = p.add_run(f"[Chart: {title} - could not be embedded]")
                run.font.color.rgb = GREY_TEXT

    # =====================================================================
    # WEF BLUF CONTENT (Bold-Lead Bullet Format)
    # =====================================================================

    def _add_bluf_content(self, text: str):
        """
        Render BLUF content with bold lead phrases.
        Detects patterns like "Bold headline. Explanation text" and
        makes the headline bold.
        """
        lines = [l.strip() for l in text.strip().split('\n') if l.strip()]

        for line in lines:
            # Strip numbering (1. 2. 3. or - or *)
            clean = line.lstrip('0123456789.-*) ').strip()
            if not clean:
                continue

            p = self.doc.add_paragraph()
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.left_indent = Inches(0.2)

            # Try to split on first period to make bold lead
            period_idx = clean.find('. ')
            if period_idx > 0 and period_idx < 80:
                headline = clean[:period_idx + 1]
                explanation = clean[period_idx + 2:]

                run_bold = p.add_run(headline + " ")
                run_bold.font.bold = True
                run_bold.font.size = BODY_SIZE
                run_bold.font.name = FONT_FAMILY
                run_bold.font.color.rgb = NAVY

                if explanation:
                    run_text = p.add_run(explanation)
                    run_text.font.size = BODY_SIZE
                    run_text.font.name = FONT_FAMILY
                    run_text.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
            else:
                run = p.add_run(clean)
                run.font.size = BODY_SIZE
                run.font.name = FONT_FAMILY

    # =====================================================================
    # INLINE CHART EMBEDDING
    # =====================================================================

    def _add_inline_chart(self, title: str, image_bytes: bytes, caption_text: str):
        """Embed a single chart inline within a section."""
        import io
        try:
            # Small spacing before chart
            spacer = self.doc.add_paragraph()
            spacer.paragraph_format.space_before = Pt(12)
            spacer.paragraph_format.space_after = Pt(4)

            # Embed image
            image_stream = io.BytesIO(image_bytes)
            self.doc.add_picture(image_stream, width=Inches(5.8))

            # Center
            last_paragraph = self.doc.paragraphs[-1]
            last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

            # Caption
            caption = self.doc.add_paragraph()
            caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = caption.add_run(caption_text)
            run.font.size = CAPTION_SIZE
            run.font.color.rgb = GREY_TEXT
            run.font.italic = True
            run.font.name = FONT_FAMILY
            caption.paragraph_format.space_after = Pt(16)

        except Exception as e:
            logger.warning(f"Could not embed inline chart '{title}': {e}")

    # =====================================================================
    # SECTOR-BASED INTELLIGENCE (replaces org-based)
    # =====================================================================

    SECTOR_MAPPING = {
        'Central Banking & Monetary Policy': [
            'monetary policy', 'interest rate', 'central bank', 'repo rate',
            'fed', 'ecb', 'fomc', 'mpc', 'quantitative', 'rate decision'
        ],
        'Fiscal Policy & Government Finance': [
            'budget', 'fiscal', 'government spending', 'taxation', 'deficit', 'debt'
        ],
        'Trade & Commerce': [
            'trade', 'tariff', 'export', 'import', 'wto', 'trade war',
            'protectionism', 'commerce', 'supply chain'
        ],
        'Labor Markets & Employment': [
            'employment', 'unemployment', 'jobs', 'labor', 'wage', 'workforce',
            'skills', 'hiring'
        ],
        'Energy & Commodities': [
            'energy', 'oil', 'gas', 'commodity', 'opec', 'renewable', 'fossil'
        ],
        'Technology & Digital Economy': [
            'technology', 'digital', 'ai', 'fintech', 'cryptocurrency',
            'blockchain', 'innovation', 'data'
        ],
        'Financial Markets & Banking': [
            'financial stability', 'banking', 'stock', 'equity', 'bond',
            'yield', 'credit', 'market', 'investment'
        ],
        'Climate & Sustainability': [
            'climate', 'esg', 'sustainable', 'green', 'carbon', 'net zero',
            'environment', 'transition'
        ],
    }

    def _add_sector_intelligence(self, articles_by_org: dict, all_articles: list):
        """Group articles by economic sector instead of by organization."""
        # Build sector buckets
        sector_articles = {sector: [] for sector in self.SECTOR_MAPPING}
        sector_articles['General Economic'] = []

        for article in all_articles:
            combined = f"{article.title} {article.summary or ''}".lower()
            placed = False
            for sector, keywords in self.SECTOR_MAPPING.items():
                if any(kw in combined for kw in keywords):
                    sector_articles[sector].append(article)
                    placed = True
                    break
            if not placed:
                sector_articles['General Economic'].append(article)

        # Render each sector with articles
        sub_num = 1
        for sector, articles in sector_articles.items():
            if not articles:
                continue

            # Sector sub-heading
            h = self.doc.add_heading(f"10.{sub_num} {sector}", level=2)
            for run in h.runs:
                run.font.color.rgb = ACCENT_BLUE
                run.font.name = FONT_FAMILY

            count_text = self.doc.add_paragraph()
            run = count_text.add_run(f"{len(articles)} articles in this sector")
            run.font.size = SMALL_SIZE
            run.font.color.rgb = GREY_TEXT
            run.font.italic = True
            run.font.name = FONT_FAMILY

            # Sort by importance
            sorted_arts = sorted(articles, key=lambda x: x.importance_score, reverse=True)

            for article in sorted_arts[:12]:  # Cap at 12 per sector
                # Article entry
                p = self.doc.add_paragraph()
                p.paragraph_format.space_before = Pt(8)

                # Source badge
                src_run = p.add_run(f"[{article.source}] ")
                src_run.font.bold = True
                src_run.font.size = SMALL_SIZE
                src_run.font.color.rgb = ACCENT_BLUE
                src_run.font.name = FONT_FAMILY

                # Title
                title_run = p.add_run(article.title)
                title_run.font.bold = True
                title_run.font.size = BODY_SIZE
                title_run.font.name = FONT_FAMILY

                # Importance badge
                level = "CRITICAL" if article.importance_score >= 8 else "IMPORTANT" if article.importance_score >= 5 else ""
                if level:
                    badge_run = p.add_run(f"  [{level}]")
                    badge_run.font.size = CAPTION_SIZE
                    badge_run.font.color.rgb = RED if level == "CRITICAL" else ORANGE
                    badge_run.font.name = FONT_FAMILY

                # Summary
                if article.ai_summary:
                    sum_p = self.doc.add_paragraph()
                    sum_p.paragraph_format.left_indent = Inches(0.3)
                    sum_run = sum_p.add_run(article.ai_summary[:500])
                    sum_run.font.size = SMALL_SIZE
                    sum_run.font.name = FONT_FAMILY
                    sum_run.font.color.rgb = RGBColor(0x44, 0x44, 0x44)

                # Deep analysis (if multi-pass verified)
                if hasattr(article, 'deep_analysis') and article.deep_analysis:
                    deep_p = self.doc.add_paragraph()
                    deep_p.paragraph_format.left_indent = Inches(0.3)
                    badge = deep_p.add_run("\u2b50 Deep Verified: ")
                    badge.font.bold = True
                    badge.font.size = SMALL_SIZE
                    badge.font.color.rgb = GREEN
                    badge.font.name = FONT_FAMILY
                    analysis_run = deep_p.add_run(article.deep_analysis[:400])
                    analysis_run.font.size = SMALL_SIZE
                    analysis_run.font.name = FONT_FAMILY

            sub_num += 1

    # =====================================================================
    # APPENDIX A: METHODOLOGY
    # =====================================================================

    def _add_methodology_appendix(self, articles_by_org: dict, all_articles: list):
        """Add transparency appendix with methodology and data sources."""
        total_articles = len(all_articles)
        total_orgs = len(articles_by_org)

        # Methodology paragraph
        self._add_formatted_text(
            f"This report was generated by the Global Pulse Economic Intelligence Agent, "
            f"an automated system that monitors {total_orgs} leading economic organizations worldwide. "
            f"A total of {total_articles} articles were collected, deduplicated, and analyzed "
            f"using a multi-model AI architecture."
        )

        # AI Architecture
        h = self.doc.add_heading("AI Architecture", level=2)
        for run in h.runs:
            run.font.color.rgb = DARK_BLUE
            run.font.name = FONT_FAMILY

        arch_items = [
            "Primary Analysis: NVIDIA NIM (Qwen 2.5 72B, DeepSeek V3.1, Kimi K2)",
            "Deduplication: NV-Embed-V1 semantic embeddings",
            "Ranking: NV-RerankQA-Mistral-4B",
            "Fallback Chain: Groq \u2192 Cerebras \u2192 OpenRouter (auto-triggered on credit exhaustion)",
        ]
        for item in arch_items:
            p = self.doc.add_paragraph(item, style='List Bullet')
            for run in p.runs:
                run.font.size = SMALL_SIZE
                run.font.name = FONT_FAMILY

        # Organizations Monitored
        h2 = self.doc.add_heading("Organizations Monitored", level=2)
        for run in h2.runs:
            run.font.color.rgb = DARK_BLUE
            run.font.name = FONT_FAMILY

        org_list = sorted(articles_by_org.keys())
        # Create 3-column layout text
        for i in range(0, len(org_list), 3):
            row = org_list[i:i+3]
            p = self.doc.add_paragraph()
            run = p.add_run("  |  ".join(row))
            run.font.size = CAPTION_SIZE
            run.font.name = FONT_FAMILY
            run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
