"""
RSS Feed Collector - Parses RSS/Atom feeds for articles.
Many organizations provide RSS feeds for their news and publications.
"""

import feedparser
import logging
from datetime import datetime
from typing import Optional
from dateutil import parser as date_parser
import time

from .base_collector import BaseCollector, Article
from config.settings import Settings

logger = logging.getLogger(__name__)


class RSSCollector(BaseCollector):
    """
    Collector that parses RSS/Atom feeds.
    Used for organizations that provide RSS feeds.
    """
    
    def collect(self) -> list[Article]:
        """Collect articles from all RSS feeds for this organization."""
        articles = []
        
        for feed_url in self.feeds:
            try:
                feed_articles = self._parse_feed(feed_url)
                articles.extend(feed_articles)
            except Exception as e:
                logger.error(f"[{self.short_name}] Error parsing feed {feed_url}: {e}")
            
            # Be polite - small delay between requests
            time.sleep(0.5)
        
        # Remove duplicates based on URL
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
    
    def _parse_feed(self, feed_url: str) -> list[Article]:
        """Parse a single RSS/Atom feed."""
        logger.debug(f"[{self.short_name}] Parsing feed: {feed_url}")
        
        # Parse the feed
        feed = feedparser.parse(feed_url)
        
        if feed.bozo and feed.bozo_exception:
            logger.warning(f"[{self.short_name}] Feed parsing warning: {feed.bozo_exception}")
        
        articles = []
        for entry in feed.entries:
            try:
                article = self._entry_to_article(entry)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"[{self.short_name}] Error parsing entry: {e}")
        
        return articles
    
    def _entry_to_article(self, entry) -> Optional[Article]:
        """Convert a feed entry to an Article object."""
        # Get title
        title = entry.get('title', '').strip()
        if not title:
            return None
        
        # Get URL
        url = entry.get('link', '')
        if not url:
            url = entry.get('id', '')
        if not url:
            return None
        
        # Get published date
        published_date = None
        for date_field in ['published_parsed', 'updated_parsed', 'created_parsed']:
            if hasattr(entry, date_field) and getattr(entry, date_field):
                try:
                    time_struct = getattr(entry, date_field)
                    published_date = datetime(*time_struct[:6])
                    break
                except Exception:
                    pass
        
        # Try parsing from string if struct failed
        if not published_date:
            for date_field in ['published', 'updated', 'created']:
                if hasattr(entry, date_field) and getattr(entry, date_field):
                    try:
                        published_date = date_parser.parse(getattr(entry, date_field))
                        break
                    except Exception:
                        pass
        
        # Get summary/description
        summary = ''
        if hasattr(entry, 'summary'):
            summary = self._clean_html(entry.summary)
        elif hasattr(entry, 'description'):
            summary = self._clean_html(entry.description)
        
        # Get content preview if available
        content_preview = ''
        if hasattr(entry, 'content') and entry.content:
            content_preview = self._clean_html(entry.content[0].get('value', ''))
        
        # Get author
        author = ''
        if hasattr(entry, 'author'):
            author = entry.author
        elif hasattr(entry, 'authors') and entry.authors:
            author = entry.authors[0].get('name', '')
        
        # Get tags/categories
        tags = []
        if hasattr(entry, 'tags'):
            tags = [tag.get('term', '') for tag in entry.tags if tag.get('term')]
        
        # Determine content type from tags or title
        content_type = self._determine_content_type(title, tags)
        
        return self.create_article(
            title=title,
            url=url,
            published_date=published_date,
            summary=summary[:500] if summary else '',  # Limit summary length
            content_preview=content_preview[:1000] if content_preview else '',
            content_type=content_type,
            author=author,
            tags=tags
        )
    
    def _clean_html(self, html_text: str) -> str:
        """Remove HTML tags and clean up text."""
        from bs4 import BeautifulSoup
        if not html_text:
            return ''
        soup = BeautifulSoup(html_text, 'html.parser')
        text = soup.get_text(separator=' ')
        # Clean up whitespace
        text = ' '.join(text.split())
        return text
    
    def _determine_content_type(self, title: str, tags: list[str]) -> str:
        """Determine the type of content based on title and tags."""
        title_lower = title.lower()
        tags_lower = [t.lower() for t in tags]
        
        if any(kw in title_lower for kw in ['report', 'outlook', 'survey']):
            return 'report'
        if any(kw in title_lower for kw in ['press release', 'announcement']):
            return 'press_release'
        if any(kw in title_lower for kw in ['working paper', 'research paper', 'paper']):
            return 'working_paper'
        if any(kw in title_lower for kw in ['speech', 'remarks', 'address']):
            return 'speech'
        if any(kw in title_lower for kw in ['blog', 'insight', 'analysis']):
            return 'insight'
        if 'data' in title_lower or 'statistics' in title_lower:
            return 'data_release'
        
        return 'article'
