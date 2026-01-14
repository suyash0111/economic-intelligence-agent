"""
Collector Manager - Orchestrates all collectors and aggregates results.
"""

import logging
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from .base_collector import Article
from .rss_collector import RSSCollector
from .web_collector import WebCollector
from config.settings import Settings

logger = logging.getLogger(__name__)


class CollectorManager:
    """
    Manages and coordinates all data collectors.
    Provides a unified interface for collecting from all organizations.
    """
    
    def __init__(self, lookback_days: int = None):
        """
        Initialize the collector manager.
        
        Args:
            lookback_days: Number of days to look back (default from settings)
        """
        self.lookback_days = lookback_days or Settings.LOOKBACK_DAYS
        self.organizations = Settings.load_organizations()
        
    def collect_all(self, max_workers: int = 5, specific_orgs: list[str] = None) -> dict[str, list[Article]]:
        """
        Collect articles from all organizations.
        
        Args:
            max_workers: Number of parallel workers
            specific_orgs: Optional list of specific organization short names to collect from
        
        Returns:
            Dictionary mapping organization short_name to list of articles
        """
        results = {}
        orgs_to_process = self.organizations
        
        # Filter to specific organizations if requested
        if specific_orgs:
            specific_orgs_lower = [o.lower() for o in specific_orgs]
            orgs_to_process = [
                org for org in self.organizations 
                if org.get('short_name', '').lower() in specific_orgs_lower
            ]
        
        logger.info(f"Starting collection for {len(orgs_to_process)} organizations")
        
        # Process organizations with controlled parallelism
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_org = {
                executor.submit(self._collect_from_org, org): org 
                for org in orgs_to_process
            }
            
            for future in as_completed(future_to_org):
                org = future_to_org[future]
                short_name = org.get('short_name', 'Unknown')
                
                try:
                    articles = future.result()
                    results[short_name] = articles
                    logger.info(f"[{short_name}] Completed: {len(articles)} articles")
                except Exception as e:
                    logger.error(f"[{short_name}] Collection failed: {e}")
                    results[short_name] = []
        
        # Summary
        total_articles = sum(len(arts) for arts in results.values())
        logger.info(f"Collection complete: {total_articles} total articles from {len(results)} organizations")
        
        return results
    
    def _collect_from_org(self, org_config: dict) -> list[Article]:
        """
        Collect articles from a single organization using appropriate collectors.
        
        Args:
            org_config: Organization configuration dictionary
        
        Returns:
            List of articles from this organization
        """
        short_name = org_config.get('short_name', 'Unknown')
        articles = []
        
        # Use RSS collector if feeds are available
        if org_config.get('feeds'):
            try:
                rss_collector = RSSCollector(org_config, self.lookback_days)
                rss_articles = rss_collector.collect()
                articles.extend(rss_articles)
            except Exception as e:
                logger.error(f"[{short_name}] RSS collection error: {e}")
        
        # Use web collector if scrape URLs are available
        if org_config.get('scrape_urls'):
            try:
                web_collector = WebCollector(org_config, self.lookback_days)
                web_articles = web_collector.collect()
                articles.extend(web_articles)
            except Exception as e:
                logger.error(f"[{short_name}] Web scraping error: {e}")
        
        # Deduplicate by URL
        seen_urls = set()
        unique_articles = []
        for article in articles:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                unique_articles.append(article)
        
        # Sort by date (newest first)
        unique_articles.sort(
            key=lambda a: a.published_date or datetime.min,
            reverse=True
        )
        
        # Limit to max articles per org
        max_articles = Settings.MAX_ARTICLES_PER_ORG
        if len(unique_articles) > max_articles:
            logger.debug(f"[{short_name}] Limiting from {len(unique_articles)} to {max_articles} articles")
            unique_articles = unique_articles[:max_articles]
        
        return unique_articles
    
    def collect_single(self, org_short_name: str) -> list[Article]:
        """
        Collect articles from a single organization.
        
        Args:
            org_short_name: Short name of the organization
        
        Returns:
            List of articles
        """
        result = self.collect_all(max_workers=1, specific_orgs=[org_short_name])
        return result.get(org_short_name, [])
    
    def get_all_articles_flat(self, results: dict[str, list[Article]] = None) -> list[Article]:
        """
        Get all articles as a flat list, sorted by date.
        
        Args:
            results: Optional pre-collected results, or collect fresh
        
        Returns:
            Flat list of all articles sorted by date
        """
        if results is None:
            results = self.collect_all()
        
        all_articles = []
        for articles in results.values():
            all_articles.extend(articles)
        
        # Sort by date (newest first)
        all_articles.sort(
            key=lambda a: a.published_date or datetime.min,
            reverse=True
        )
        
        return all_articles
    
    def get_articles_by_category(self, results: dict[str, list[Article]] = None) -> dict[str, list[Article]]:
        """
        Organize articles by category (International, Consulting, etc.).
        
        Args:
            results: Optional pre-collected results, or collect fresh
        
        Returns:
            Dictionary mapping category to list of articles
        """
        if results is None:
            results = self.collect_all()
        
        by_category = {}
        for articles in results.values():
            for article in articles:
                category = article.category
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append(article)
        
        # Sort each category by date
        for category in by_category:
            by_category[category].sort(
                key=lambda a: a.published_date or datetime.min,
                reverse=True
            )
        
        return by_category


# Import datetime for sorting
from datetime import datetime
