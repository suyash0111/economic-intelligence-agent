"""
Web Collector - Scrapes web pages for articles and publications.
Used for organizations without RSS feeds or to supplement RSS data.
"""

import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime
from typing import Optional
from dateutil import parser as date_parser
import time
import re

from .base_collector import BaseCollector, Article
from config.settings import Settings

logger = logging.getLogger(__name__)


class WebCollector(BaseCollector):
    """
    Collector that scrapes web pages for articles.
    Uses BeautifulSoup for HTML parsing.
    """
    
    def __init__(self, org_config: dict, lookback_days: int = 7):
        super().__init__(org_config, lookback_days)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': Settings.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
    
    def collect(self) -> list[Article]:
        """Collect articles by scraping configured URLs."""
        articles = []
        
        for scrape_config in self.scrape_urls:
            url = scrape_config.get('url', '') if isinstance(scrape_config, dict) else scrape_config
            content_type = scrape_config.get('type', 'general') if isinstance(scrape_config, dict) else 'general'
            
            try:
                page_articles = self._scrape_page(url, content_type)
                articles.extend(page_articles)
            except Exception as e:
                logger.error(f"[{self.short_name}] Error scraping {url}: {e}")
            
            # Be polite - delay between requests
            time.sleep(Settings.REQUEST_DELAY)
        
        # Remove duplicates
        seen_urls = set()
        unique_articles = []
        for article in articles:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                unique_articles.append(article)
        
        # Filter by date
        filtered = [a for a in unique_articles if self.is_within_lookback(a.published_date)]
        
        self.log_collection_result(filtered)
        return filtered
    
    def _scrape_page(self, url: str, content_type: str) -> list[Article]:
        """Scrape a single page for articles."""
        logger.debug(f"[{self.short_name}] Scraping: {url}")
        
        try:
            response = self.session.get(url, timeout=Settings.REQUEST_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"[{self.short_name}] Request failed for {url}: {e}")
            return []
        
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Try different extraction strategies
        articles = []
        
        # Strategy 1: Look for article/news containers
        articles.extend(self._extract_from_articles(soup, url, content_type))
        
        # Strategy 2: Look for listing patterns
        if not articles:
            articles.extend(self._extract_from_listings(soup, url, content_type))
        
        # Strategy 3: Generic link extraction
        if not articles:
            articles.extend(self._extract_from_links(soup, url, content_type))
        
        return articles
    
    def _extract_from_articles(self, soup: BeautifulSoup, base_url: str, content_type: str) -> list[Article]:
        """Extract from article/card containers."""
        articles = []
        
        # Common article container selectors
        selectors = [
            'article',
            '.article',
            '.news-item',
            '.publication-item',
            '.card',
            '.list-item',
            '.entry',
            '.post',
            '[class*="article"]',
            '[class*="news"]',
            '[class*="publication"]',
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            for item in items[:20]:  # Limit to 20 items per selector
                article = self._parse_article_container(item, base_url, content_type)
                if article:
                    articles.append(article)
        
        return articles
    
    def _extract_from_listings(self, soup: BeautifulSoup, base_url: str, content_type: str) -> list[Article]:
        """Extract from list-based layouts."""
        articles = []
        
        # Look for lists
        for ul in soup.select('ul.publications, ul.news-list, ul.articles, ol.publications'):
            for li in ul.select('li')[:20]:
                article = self._parse_list_item(li, base_url, content_type)
                if article:
                    articles.append(article)
        
        return articles
    
    def _extract_from_links(self, soup: BeautifulSoup, base_url: str, content_type: str) -> list[Article]:
        """Generic extraction based on links with dates nearby."""
        articles = []
        
        # Look for links that might be articles
        for a in soup.select('a[href]')[:50]:
            href = a.get('href', '')
            title = a.get_text(strip=True)
            
            # Skip navigation links, social links, etc.
            if not title or len(title) < 20:
                continue
            if any(skip in href.lower() for skip in ['twitter', 'facebook', 'linkedin', 'mailto:', 'tel:', '#']):
                continue
            if any(skip in title.lower() for skip in ['read more', 'click here', 'learn more']):
                continue
            
            # Build full URL
            full_url = self._resolve_url(href, base_url)
            
            # Try to find a date nearby
            published_date = self._find_nearby_date(a)
            
            # Get nearby text as summary
            summary = self._get_nearby_text(a)
            
            article = self.create_article(
                title=title,
                url=full_url,
                published_date=published_date,
                summary=summary,
                content_type=content_type
            )
            articles.append(article)
        
        return articles
    
    def _parse_article_container(self, container, base_url: str, content_type: str) -> Optional[Article]:
        """Parse an article container element."""
        # Find title/link
        title_elem = container.select_one('h1, h2, h3, h4, a.title, .title a, a[class*="title"]')
        if not title_elem:
            title_elem = container.select_one('a')
        
        if not title_elem:
            return None
        
        # Get title text
        title = title_elem.get_text(strip=True)
        if not title or len(title) < 10:
            return None
        
        # Get URL
        link = title_elem if title_elem.name == 'a' else title_elem.find('a')
        if link:
            url = self._resolve_url(link.get('href', ''), base_url)
        else:
            return None
        
        # Get date
        date_elem = container.select_one('.date, .published, time, [class*="date"], [datetime]')
        published_date = None
        if date_elem:
            date_str = date_elem.get('datetime') or date_elem.get_text(strip=True)
            published_date = self._parse_date(date_str)
        
        # Get summary
        summary_elem = container.select_one('.summary, .excerpt, .description, p')
        summary = summary_elem.get_text(strip=True) if summary_elem else ''
        
        # Get author
        author_elem = container.select_one('.author, .byline, [class*="author"]')
        author = author_elem.get_text(strip=True) if author_elem else ''
        
        return self.create_article(
            title=title,
            url=url,
            published_date=published_date,
            summary=summary[:500],
            content_type=content_type,
            author=author
        )
    
    def _parse_list_item(self, li, base_url: str, content_type: str) -> Optional[Article]:
        """Parse a list item element."""
        link = li.select_one('a')
        if not link:
            return None
        
        title = link.get_text(strip=True)
        url = self._resolve_url(link.get('href', ''), base_url)
        
        if not title or len(title) < 10:
            return None
        
        # Look for date in list item
        date_text = li.get_text()
        published_date = self._extract_date_from_text(date_text)
        
        return self.create_article(
            title=title,
            url=url,
            published_date=published_date,
            content_type=content_type
        )
    
    def _resolve_url(self, href: str, base_url: str) -> str:
        """Resolve relative URLs to absolute URLs."""
        if not href:
            return base_url
        if href.startswith(('http://', 'https://')):
            return href
        if href.startswith('//'):
            return 'https:' + href
        if href.startswith('/'):
            # Extract domain from base_url
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            return f"{parsed.scheme}://{parsed.netloc}{href}"
        # Relative path
        return base_url.rstrip('/') + '/' + href.lstrip('/')
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse a date string into datetime."""
        if not date_str:
            return None
        try:
            return date_parser.parse(date_str, fuzzy=True)
        except Exception:
            return None
    
    def _extract_date_from_text(self, text: str) -> Optional[datetime]:
        """Try to extract a date from mixed text."""
        # Common date patterns
        patterns = [
            r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}',
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}',
            r'\d{4}-\d{2}-\d{2}',
            r'\d{1,2}/\d{1,2}/\d{4}',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._parse_date(match.group())
        
        return None
    
    def _find_nearby_date(self, element) -> Optional[datetime]:
        """Find a date in elements near the given element."""
        # Check parent
        parent = element.parent
        if parent:
            date_elem = parent.select_one('.date, time, [datetime]')
            if date_elem:
                date_str = date_elem.get('datetime') or date_elem.get_text(strip=True)
                return self._parse_date(date_str)
        
        # Check siblings
        for sibling in element.find_next_siblings()[:3]:
            if 'date' in str(sibling.get('class', '')):
                return self._parse_date(sibling.get_text(strip=True))
        
        return None
    
    def _get_nearby_text(self, element) -> str:
        """Get descriptive text near the element."""
        parent = element.parent
        if parent:
            # Look for paragraph or description
            desc = parent.select_one('p, .description, .summary')
            if desc:
                return desc.get_text(strip=True)[:300]
        return ''
