"""
Excel Generator - Creates Excel spreadsheets for article tracking.
"""

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from pathlib import Path
from datetime import datetime
import logging

from collectors.base_collector import Article
from config.settings import Settings

logger = logging.getLogger(__name__)


class ExcelGenerator:
    """
    Generates the Master Intelligence Index - Excel spreadsheet with all articles.
    Provides easy-to-scan format with all 39 organizations represented.
    """
    
    # Category colors for conditional formatting
    CATEGORY_COLORS = {
        'Central Bank': 'FFEBEE',     # Light red - highest priority
        'International': 'E3F2FD',    # Light blue
        'Consulting': 'E8F5E9',       # Light green
        'Think Tank': 'FFF3E0',       # Light orange
        'Investment Bank': 'F3E5F5',  # Light purple
        'News': 'FFFDE7',             # Light yellow
        'Data Provider': 'E0F7FA',    # Light cyan
        'Rating Agency': 'FCE4EC',    # Light pink
        'India': 'FFF8E1',            # Light amber
    }
    
    def __init__(self):
        """Initialize the Excel generator."""
        self.wb = None
        self.ws = None
    
    def generate(
        self,
        articles: list[Article],
        date_range: str,
        output_path: Path = None
    ) -> Path:
        """
        Generate an Excel spreadsheet with all articles.
        
        Args:
            articles: List of all articles (flat list)
            date_range: String describing the date range
            output_path: Optional output path
        
        Returns:
            Path to the generated Excel file
        """
        self.wb = Workbook()
        self.ws = self.wb.active
        self.ws.title = "Master Intelligence Index"
        
        # Set up headers
        self._setup_headers()
        
        # Add data rows
        self._add_data_rows(articles)
        
        # Apply formatting
        self._apply_formatting(len(articles))
        
        # Add summary sheet
        self._add_summary_sheet(articles, date_range)
        
        # Save
        if output_path is None:
            Settings.ensure_output_dir()
            output_path = Settings.OUTPUT_DIR / f"Master_Intelligence_Index_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        self.wb.save(output_path)
        logger.info(f"Excel saved: {output_path}")
        
        return output_path
    
    def _setup_headers(self):
        """Set up column headers."""
        headers = [
            ('Organization', 25),
            ('Title', 50),
            ('Published Date', 15),
            ('Category', 20),
            ('Type', 15),
            ('Summary', 80),
            ('Link', 60),
        ]
        
        # Header style
        header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
        header_font = Font(color='FFFFFF', bold=True, size=11)
        header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        
        for col, (header, width) in enumerate(headers, 1):
            cell = self.ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
            self.ws.column_dimensions[get_column_letter(col)].width = width
        
        # Freeze header row
        self.ws.freeze_panes = 'A2'
    
    def _add_data_rows(self, articles: list[Article]):
        """Add data rows for all articles."""
        for row, article in enumerate(articles, 2):
            # Organization
            self.ws.cell(row=row, column=1, value=article.source)
            
            # Title
            self.ws.cell(row=row, column=2, value=article.title)
            
            # Published Date
            if article.published_date:
                self.ws.cell(row=row, column=3, value=article.published_date.strftime('%Y-%m-%d'))
            else:
                self.ws.cell(row=row, column=3, value='N/A')
            
            # Category
            self.ws.cell(row=row, column=4, value=article.ai_category or article.category)
            
            # Content Type
            self.ws.cell(row=row, column=5, value=article.content_type.replace('_', ' ').title())
            
            # Summary (AI-generated one-liner)
            self.ws.cell(row=row, column=6, value=article.ai_summary or article.summary[:200])
            
            # Link (as hyperlink)
            link_cell = self.ws.cell(row=row, column=7, value=article.url)
            link_cell.hyperlink = article.url
            link_cell.font = Font(color='0563C1', underline='single')
    
    def _apply_formatting(self, num_articles: int):
        """Apply formatting to data rows."""
        thin_border = Border(
            left=Side(style='thin', color='CCCCCC'),
            right=Side(style='thin', color='CCCCCC'),
            top=Side(style='thin', color='CCCCCC'),
            bottom=Side(style='thin', color='CCCCCC')
        )
        
        for row in range(2, num_articles + 2):
            # Get category for this row
            category_cell = self.ws.cell(row=row, column=4)
            org_cell = self.ws.cell(row=row, column=1)
            
            # Determine the color based on organization category
            org_name = org_cell.value or ''
            color = self._get_org_color(org_name)
            
            if color:
                fill = PatternFill(start_color=color, end_color=color, fill_type='solid')
            else:
                fill = PatternFill(start_color='FFFFFF', end_color='FFFFFF', fill_type='solid')
            
            for col in range(1, 8):
                cell = self.ws.cell(row=row, column=col)
                cell.border = thin_border
                cell.fill = fill
                
                # Alignment
                if col == 6:  # Summary column
                    cell.alignment = Alignment(wrap_text=True, vertical='top')
                elif col == 7:  # Link column
                    cell.alignment = Alignment(wrap_text=True)
                else:
                    cell.alignment = Alignment(vertical='center')
            
            # Set row height for readability
            self.ws.row_dimensions[row].height = 45
    
    def _get_org_color(self, org_name: str) -> str:
        """Get the color for an organization based on its category."""
        org_categories = {
            # Central Banks (NEW)
            'Fed': 'Central Bank', 'ECB': 'Central Bank', 'BoE': 'Central Bank',
            'BoJ': 'Central Bank', 'PBoC': 'Central Bank',
            # International
            'IMF': 'International', 'World Bank': 'International', 'WTO': 'International',
            'OECD': 'International', 'WEF': 'International', 'BIS': 'International',
            'UNCTAD': 'International', 'ILO': 'International', 'UNDP': 'International',
            'NBER': 'International', 'ADB': 'International',
            # Consulting
            'McKinsey': 'Consulting', 'Deloitte': 'Consulting', 'BCG': 'Consulting',
            'PwC': 'Consulting', 'EY': 'Consulting', 'KPMG': 'Consulting',
            'Accenture': 'Consulting', 'Bain': 'Consulting',
            # Think Tanks
            'Brookings': 'Think Tank', 'PIIE': 'Think Tank', 'Bruegel': 'Think Tank',
            'Oxford Economics': 'Think Tank', 'Capital Economics': 'Think Tank',
            # Investment Banks
            'Goldman Sachs': 'Investment Bank', 'JP Morgan': 'Investment Bank',
            # News
            'Bloomberg': 'News', 'Reuters': 'News', 'WSJ': 'News', 'FT': 'News',
            # Data Providers
            'S&P Global': 'Data Provider', 'EIU': 'Data Provider',
            # Rating Agencies
            "Moody's": 'Rating Agency', 'Fitch': 'Rating Agency', 'S&P Ratings': 'Rating Agency',
            # India
            'RBI': 'India', 'MoSPI': 'India', 'MoF India': 'India', 'NITI Aayog': 'India',
        }
        
        category = org_categories.get(org_name, '')
        return self.CATEGORY_COLORS.get(category, 'FFFFFF')
    
    def _add_summary_sheet(self, articles: list[Article], date_range: str):
        """Add a summary sheet with statistics."""
        summary_ws = self.wb.create_sheet(title="Summary")
        
        # Title
        summary_ws['A1'] = "Master Intelligence Index - Summary"
        summary_ws['A1'].font = Font(bold=True, size=16)
        summary_ws.merge_cells('A1:D1')
        
        # Date range
        summary_ws['A2'] = f"Period: {date_range}"
        summary_ws['A2'].font = Font(italic=True, size=12)
        summary_ws.merge_cells('A2:D2')
        
        # Statistics
        summary_ws['A4'] = "Statistics"
        summary_ws['A4'].font = Font(bold=True, size=14)
        
        summary_ws['A5'] = "Total Articles/Reports"
        summary_ws['B5'] = len(articles)
        
        # Count by organization
        org_counts = {}
        for article in articles:
            org = article.source
            org_counts[org] = org_counts.get(org, 0) + 1
        
        summary_ws['A6'] = "Organizations Covered"
        summary_ws['B6'] = len(org_counts)
        
        # Count by category
        cat_counts = {}
        for article in articles:
            cat = article.ai_category or article.category
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        
        # Category breakdown
        summary_ws['A8'] = "By Category"
        summary_ws['A8'].font = Font(bold=True, size=12)
        
        row = 9
        for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
            summary_ws.cell(row=row, column=1, value=cat)
            summary_ws.cell(row=row, column=2, value=count)
            row += 1
        
        # Organization breakdown
        row += 1
        summary_ws.cell(row=row, column=1, value="By Organization")
        summary_ws.cell(row=row, column=1).font = Font(bold=True, size=12)
        
        row += 1
        for org, count in sorted(org_counts.items(), key=lambda x: -x[1]):
            summary_ws.cell(row=row, column=1, value=org)
            summary_ws.cell(row=row, column=2, value=count)
            row += 1
        
        # Auto-fit columns
        summary_ws.column_dimensions['A'].width = 30
        summary_ws.column_dimensions['B'].width = 15
