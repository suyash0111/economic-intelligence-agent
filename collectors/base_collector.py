"""
Base collector class and Article data model.
All collectors inherit from BaseCollector.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class Article:
    """Represents a single article/report/news item from any source."""
    
    title: str
    url: str
    source: str  # Organization short name
    source_full: str  # Organization full name
    category: str  # Organization category (International, Consulting, etc.)
    published_date: Optional[datetime] = None
    summary: str = ""  # Brief summary or description
    content_preview: str = ""  # First few paragraphs if available
    content_type: str = "article"  # article, report, press_release, working_paper, etc.
    author: str = ""
    tags: list[str] = field(default_factory=list)
    
    # AI-generated fields (populated by analyzer)
    ai_summary: str = ""  # One-liner for Excel
    ai_analysis: str = ""  # Detailed analysis for document
    ai_category: str = ""  # AI-determined category
    
    # Advanced features
    importance_score: int = 0  # 1-10 importance rating
    importance_level: str = ""  # "Critical", "Important", "Standard"
    themes: list[str] = field(default_factory=list)  # Theme tags for grouping
    verification_status: str = "unverified"  # "verified", "unverified", "needs_review"
    has_pdf: bool = False  # Whether source has a PDF to extract
    pdf_url: str = ""  # URL to the PDF if available
    
    def __post_init__(self):
        """Validate and normalize data."""
        # Ensure title and URL are not empty
        if not self.title:
            self.title = "Untitled"
        if not self.url:
            self.url = "#"
        
        # Normalize source names
        self.source = self.source.strip()
        self.source_full = self.source_full.strip()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'title': self.title,
            'url': self.url,
            'source': self.source,
            'source_full': self.source_full,
            'category': self.category,
            'published_date': self.published_date.isoformat() if self.published_date else None,
            'summary': self.summary,
            'content_preview': self.content_preview,
            'content_type': self.content_type,
            'author': self.author,
            'tags': self.tags,
            'ai_summary': self.ai_summary,
            'ai_analysis': self.ai_analysis,
            'ai_category': self.ai_category,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Article':
        """Create Article from dictionary."""
        if data.get('published_date'):
            data['published_date'] = datetime.fromisoformat(data['published_date'])
        return cls(**data)


class BaseCollector(ABC):
    """
    Abstract base class for all data collectors.
    Each organization can have its own collector implementation.
    """
    
    def __init__(self, org_config: dict, lookback_days: int = 7):
        """
        Initialize collector with organization configuration.
        
        Args:
            org_config: Dictionary from organizations.yaml
            lookback_days: Number of days to look back for articles
        """
        self.org_config = org_config
        self.name = org_config.get('name', 'Unknown')
        self.short_name = org_config.get('short_name', self.name)
        self.category = org_config.get('category', 'Other')
        self.lookback_days = lookback_days
        self.cutoff_date = datetime.now() - timedelta(days=lookback_days)
        
        self.feeds = org_config.get('feeds', [])
        self.scrape_urls = org_config.get('scrape_urls', [])
        self.key_reports = org_config.get('key_reports', [])
    
    @abstractmethod
    def collect(self) -> list[Article]:
        """
        Collect articles from this organization.
        
        Returns:
            List of Article objects from the last N days
        """
        pass
    
    def is_within_lookback(self, date: Optional[datetime]) -> bool:
        """Check if a date is within the lookback period."""
        if date is None:
            return True  # Include items without dates
        return date >= self.cutoff_date
    
    def create_article(
        self,
        title: str,
        url: str,
        published_date: Optional[datetime] = None,
        summary: str = "",
        content_preview: str = "",
        content_type: str = "article",
        author: str = "",
        tags: list[str] = None
    ) -> Article:
        """Helper to create an Article with organization info pre-filled."""
        return Article(
            title=title,
            url=url,
            source=self.short_name,
            source_full=self.name,
            category=self.category,
            published_date=published_date,
            summary=summary,
            content_preview=content_preview,
            content_type=content_type,
            author=author,
            tags=tags or []
        )
    
    def log_collection_result(self, articles: list[Article]):
        """Log the collection results."""
        logger.info(f"[{self.short_name}] Collected {len(articles)} articles")
        for article in articles[:3]:  # Log first 3
            logger.debug(f"  - {article.title[:60]}...")
