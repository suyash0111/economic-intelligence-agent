"""
PDF Extractor utility for extracting text from PDF reports.
Uses PyMuPDF (fitz) for PDF parsing.
"""

import logging
from pathlib import Path
import tempfile
from typing import Optional
import requests

logger = logging.getLogger(__name__)


def extract_pdf_text(url: str, max_pages: int = 10) -> Optional[str]:
    """
    Download and extract text from a PDF URL.
    
    Args:
        url: URL to the PDF file
        max_pages: Maximum number of pages to extract
    
    Returns:
        Extracted text or None if extraction failed
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("PyMuPDF not installed. Run: pip install pymupdf")
        return None
    
    try:
        # Download PDF
        logger.info(f"Downloading PDF: {url[:50]}...")
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if response.status_code != 200:
            logger.warning(f"Failed to download PDF: {response.status_code}")
            return None
        
        # Check if it's actually a PDF
        content_type = response.headers.get('content-type', '')
        if 'pdf' not in content_type.lower() and not url.lower().endswith('.pdf'):
            logger.warning(f"URL does not appear to be a PDF: {content_type}")
            return None
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name
        
        # Extract text
        text_parts = []
        with fitz.open(tmp_path) as doc:
            total_pages = min(len(doc), max_pages)
            
            for page_num in range(total_pages):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    text_parts.append(f"--- Page {page_num + 1} ---\n{text}")
        
        # Clean up temp file
        Path(tmp_path).unlink(missing_ok=True)
        
        if text_parts:
            extracted = "\n\n".join(text_parts)
            logger.info(f"Extracted {len(text_parts)} pages, {len(extracted)} characters")
            return extracted
        
        logger.warning("No text extracted from PDF")
        return None
        
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return None


def detect_pdf_links(html_content: str, base_url: str) -> list[str]:
    """
    Detect PDF links in HTML content.
    
    Args:
        html_content: HTML content to search
        base_url: Base URL for relative links
    
    Returns:
        List of PDF URLs found
    """
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    
    pdf_links = []
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Check if it's a PDF
            if '.pdf' in href.lower():
                full_url = urljoin(base_url, href)
                if full_url not in pdf_links:
                    pdf_links.append(full_url)
    
    except Exception as e:
        logger.error(f"Error detecting PDF links: {e}")
    
    return pdf_links


def summarize_pdf_content(text: str, max_length: int = 2000) -> str:
    """
    Create a summary-friendly version of PDF text.
    Removes common boilerplate and truncates intelligently.
    
    Args:
        text: Full PDF text
        max_length: Maximum length to return
    
    Returns:
        Cleaned and truncated text
    """
    # Remove common PDF artifacts
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        
        # Skip page markers
        if line.startswith('--- Page'):
            continue
        
        # Skip very short lines (likely headers/footers)
        if len(line) < 10:
            continue
        
        # Skip lines that are just numbers
        if line.replace('.', '').replace(',', '').isdigit():
            continue
        
        cleaned_lines.append(line)
    
    cleaned_text = '\n'.join(cleaned_lines)
    
    # Truncate to max length at a sentence boundary if possible
    if len(cleaned_text) > max_length:
        truncated = cleaned_text[:max_length]
        
        # Try to end at a sentence
        last_period = truncated.rfind('.')
        if last_period > max_length * 0.7:
            truncated = truncated[:last_period + 1]
        
        truncated += "\n\n[Content truncated. See full report for details.]"
        return truncated
    
    return cleaned_text
