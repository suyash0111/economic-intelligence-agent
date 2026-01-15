"""
PDF Processor - Downloads and extracts content from PDF reports.

Handles:
- PDF downloading with caching
- Full text extraction using PyMuPDF
- Table extraction using pdfplumber
- Image/chart extraction for vision analysis
- Document chunking for efficient LLM processing
"""

import os
import re
import logging
import tempfile
import hashlib
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from io import BytesIO

import requests
import fitz  # PyMuPDF
import pdfplumber
from PIL import Image

from config.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class ExtractedContent:
    """Container for extracted PDF content."""
    full_text: str = ""
    text_chunks: list[str] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    images: list[bytes] = field(default_factory=list)
    page_count: int = 0
    title: str = ""
    metadata: dict = field(default_factory=dict)
    extraction_success: bool = False
    error_message: str = ""


class PDFProcessor:
    """
    Processes PDF documents for deep analysis.
    Downloads, extracts text/tables/images, and chunks for LLM processing.
    """
    
    # Organizations whose PDFs should be deep-analyzed
    DEEP_ANALYSIS_SOURCES = [
        # Central Banks
        'Fed', 'ECB', 'BoE', 'BoJ', 'PBoC', 'RBI',
        # International Organizations
        'IMF', 'World Bank', 'OECD', 'WTO', 'BIS', 'ADB', 'ILO',
        # Consulting & Research
        'McKinsey', 'BCG', 'Deloitte', 'PwC', 'KPMG', 'EY', 'Bain',
        # Think Tanks
        'Brookings', 'PIIE', 'NBER', 'Oxford Economics', 'Capital Economics',
        # Investment Banks
        'Goldman Sachs', 'JP Morgan',
        # India
        'MoF India', 'NITI Aayog', 'MoSPI',
        # Rating Agencies
        "Moody's", 'Fitch', 'S&P Ratings',
    ]
    
    # Content types that warrant deep analysis
    DEEP_ANALYSIS_TYPES = ['report', 'working_paper', 'data_release', 'speech']
    
    # Keywords in titles that indicate important reports
    IMPORTANT_KEYWORDS = [
        'outlook', 'report', 'survey', 'forecast', 'index', 'review',
        'annual', 'quarterly', 'bulletin', 'assessment', 'analysis',
        'monitor', 'update', 'economic', 'financial stability'
    ]
    
    def __init__(self, cache_dir: Path = None):
        """Initialize PDF processor with cache directory."""
        self.cache_dir = cache_dir or (Settings.BASE_DIR / 'cache' / 'pdfs')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Track processed PDFs to avoid duplicates
        self.processed_urls = set()
        
        # Statistics
        self.stats = {
            'downloaded': 0,
            'extracted': 0,
            'failed': 0,
            'skipped': 0
        }
    
    def should_deep_analyze(self, article) -> bool:
        """
        Determine if an article should receive deep PDF analysis.
        
        Args:
            article: Article object to evaluate
            
        Returns:
            True if article warrants deep analysis
        """
        # Check if source is in our priority list
        is_priority_source = article.source in self.DEEP_ANALYSIS_SOURCES
        
        # Check content type
        is_report_type = article.content_type in self.DEEP_ANALYSIS_TYPES
        
        # Check for important keywords in title
        title_lower = article.title.lower()
        has_important_keywords = any(kw in title_lower for kw in self.IMPORTANT_KEYWORDS)
        
        # Check if URL might be a PDF
        url_lower = article.url.lower()
        likely_pdf = (
            url_lower.endswith('.pdf') or 
            '/pdf/' in url_lower or
            'download' in url_lower or
            'publication' in url_lower
        )
        
        # Decision logic: must be priority source AND (report type OR important keywords)
        return is_priority_source and (is_report_type or has_important_keywords or likely_pdf)
    
    def download_pdf(self, url: str, timeout: int = 30) -> Optional[Path]:
        """
        Download PDF from URL to cache directory.
        
        Args:
            url: URL of the PDF
            timeout: Request timeout in seconds
            
        Returns:
            Path to downloaded file or None if failed
        """
        if url in self.processed_urls:
            logger.debug(f"Already processed: {url}")
            return None
        
        try:
            # Generate cache filename from URL hash
            url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
            cache_path = self.cache_dir / f"{url_hash}.pdf"
            
            # Check if already cached
            if cache_path.exists():
                logger.debug(f"Using cached PDF: {cache_path}")
                self.processed_urls.add(url)
                return cache_path
            
            # Download the PDF
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=timeout, stream=True)
            response.raise_for_status()
            
            # Check if it's actually a PDF
            content_type = response.headers.get('content-type', '').lower()
            if 'pdf' not in content_type and not url.lower().endswith('.pdf'):
                # Try to detect PDF magic bytes
                content_start = response.content[:10]
                if not content_start.startswith(b'%PDF'):
                    logger.warning(f"URL does not point to PDF: {url}")
                    self.stats['skipped'] += 1
                    return None
            
            # Save to cache
            with open(cache_path, 'wb') as f:
                f.write(response.content)
            
            self.processed_urls.add(url)
            self.stats['downloaded'] += 1
            logger.info(f"Downloaded PDF: {url[:50]}... ({len(response.content) / 1024:.1f} KB)")
            
            return cache_path
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to download PDF from {url[:50]}...: {e}")
            self.stats['failed'] += 1
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading PDF: {e}")
            self.stats['failed'] += 1
            return None
    
    def extract_content(self, pdf_path: Path, max_pages: int = 50) -> ExtractedContent:
        """
        Extract all content from a PDF file.
        
        Args:
            pdf_path: Path to PDF file
            max_pages: Maximum pages to process (for very long documents)
            
        Returns:
            ExtractedContent with text, tables, and images
        """
        result = ExtractedContent()
        
        try:
            # Extract text and images with PyMuPDF
            doc = fitz.open(pdf_path)
            result.page_count = min(len(doc), max_pages)
            result.metadata = doc.metadata or {}
            result.title = result.metadata.get('title', '')
            
            all_text = []
            
            for page_num in range(result.page_count):
                page = doc[page_num]
                
                # Extract text
                text = page.get_text()
                if text.strip():
                    all_text.append(f"--- Page {page_num + 1} ---\n{text}")
                
                # Extract images (limit to first 10 significant images)
                if len(result.images) < 10:
                    for img_index, img in enumerate(page.get_images(full=True)):
                        try:
                            xref = img[0]
                            base_image = doc.extract_image(xref)
                            image_bytes = base_image["image"]
                            
                            # Only keep images larger than 10KB (likely charts/graphs)
                            if len(image_bytes) > 10240:
                                result.images.append(image_bytes)
                        except Exception:
                            continue
            
            doc.close()
            
            result.full_text = "\n\n".join(all_text)
            
            # Extract tables with pdfplumber
            result.tables = self._extract_tables(pdf_path, max_pages)
            
            # Chunk the text for LLM processing
            result.text_chunks = self._chunk_text(result.full_text)
            
            result.extraction_success = True
            self.stats['extracted'] += 1
            
            logger.info(f"Extracted: {result.page_count} pages, {len(result.tables)} tables, {len(result.images)} images")
            
        except Exception as e:
            result.error_message = str(e)
            logger.error(f"Failed to extract PDF content: {e}")
            self.stats['failed'] += 1
        
        return result
    
    def _extract_tables(self, pdf_path: Path, max_pages: int = 50) -> list[dict]:
        """Extract tables from PDF using pdfplumber."""
        tables = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages[:max_pages]):
                    page_tables = page.extract_tables()
                    
                    for table_idx, table in enumerate(page_tables):
                        if table and len(table) > 1:  # Must have at least header + 1 row
                            # Convert to dict format
                            headers = table[0] if table[0] else [f"Col{i}" for i in range(len(table[1]))]
                            
                            table_data = {
                                'page': page_num + 1,
                                'table_index': table_idx + 1,
                                'headers': headers,
                                'rows': table[1:],
                                'markdown': self._table_to_markdown(headers, table[1:])
                            }
                            tables.append(table_data)
                            
                            # Limit to 20 tables total
                            if len(tables) >= 20:
                                return tables
                                
        except Exception as e:
            logger.warning(f"Table extraction failed: {e}")
        
        return tables
    
    def _table_to_markdown(self, headers: list, rows: list) -> str:
        """Convert table to markdown format."""
        if not headers or not rows:
            return ""
        
        # Clean headers
        clean_headers = [str(h).strip() if h else f"Col{i}" for i, h in enumerate(headers)]
        
        # Build markdown table
        md = "| " + " | ".join(clean_headers) + " |\n"
        md += "| " + " | ".join(["---"] * len(clean_headers)) + " |\n"
        
        for row in rows[:20]:  # Limit rows
            clean_row = [str(cell).strip() if cell else "" for cell in row]
            # Pad row if needed
            while len(clean_row) < len(clean_headers):
                clean_row.append("")
            md += "| " + " | ".join(clean_row[:len(clean_headers)]) + " |\n"
        
        return md
    
    def _chunk_text(self, text: str, chunk_size: int = 8000, overlap: int = 500) -> list[str]:
        """
        Split text into chunks for LLM processing.
        
        Args:
            text: Full text to chunk
            chunk_size: Target size per chunk (chars)
            overlap: Overlap between chunks for context
            
        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text] if text.strip() else []
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at paragraph or sentence boundary
            if end < len(text):
                # Look for paragraph break
                para_break = text.rfind('\n\n', start + chunk_size // 2, end)
                if para_break > start:
                    end = para_break
                else:
                    # Look for sentence break
                    sentence_break = text.rfind('. ', start + chunk_size // 2, end)
                    if sentence_break > start:
                        end = sentence_break + 1
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap if end < len(text) else len(text)
        
        return chunks
    
    def cleanup(self):
        """Remove all cached PDFs to free space."""
        count = 0
        for pdf_file in self.cache_dir.glob("*.pdf"):
            try:
                pdf_file.unlink()
                count += 1
            except Exception as e:
                logger.warning(f"Failed to delete {pdf_file}: {e}")
        
        logger.info(f"Cleaned up {count} cached PDFs")
        
        # Reset tracking
        self.processed_urls.clear()
    
    def get_stats(self) -> dict:
        """Get processing statistics."""
        return self.stats.copy()


def extract_key_statistics(text: str) -> list[str]:
    """
    Extract key statistics and numbers from text.
    
    Args:
        text: Text to analyze
        
    Returns:
        List of extracted statistics
    """
    stats = []
    
    # Patterns for common statistics
    patterns = [
        # Percentages
        r'(\d+(?:\.\d+)?)\s*(?:percent|%)',
        # Dollar amounts
        r'\$\s*(\d+(?:\.\d+)?)\s*(?:billion|million|trillion|B|M|T)',
        # Growth rates
        r'(?:grew|growth|increase|decline|fell|rose)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%',
        # Year-over-year
        r'(\d+(?:\.\d+)?)\s*%\s*(?:YoY|year-over-year|y/y)',
        # Basis points
        r'(\d+)\s*(?:basis points|bps)',
        # GDP figures
        r'GDP.{1,30}?(\d+(?:\.\d+)?)\s*%',
        # Unemployment
        r'unemployment.{1,20}?(\d+(?:\.\d+)?)\s*%',
        # Inflation
        r'inflation.{1,20}?(\d+(?:\.\d+)?)\s*%',
    ]
    
    text_lower = text.lower()
    
    for pattern in patterns:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        # Get context around each match
        for match in re.finditer(pattern, text, re.IGNORECASE):
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end].strip()
            # Clean up and add if not duplicate
            context = re.sub(r'\s+', ' ', context)
            if context and context not in stats:
                stats.append(context)
                if len(stats) >= 15:  # Limit to 15 stats
                    return stats
    
    return stats
