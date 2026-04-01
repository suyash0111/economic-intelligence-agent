"""
Article Enricher - Fetches full article text from URLs before AI analysis.

The key bottleneck in analysis quality is INPUT quality.
Collectors only capture titles and short summary/meta tags.
This module fetches and parses the actual article body text,
giving the AI models 10-50x more content to analyze.
"""

import logging
import time
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from collectors.base_collector import Article
from config.settings import Settings

logger = logging.getLogger(__name__)


class ArticleEnricher:
    """
    Enriches articles by fetching and parsing full article text from URLs.
    Runs between collection and AI analysis to maximize input quality.
    """

    # Domains where we should NOT try to fetch full text
    # (they block bots, require auth, or are PDF-only)
    SKIP_DOMAINS = [
        'doi.org', 'ssrn.com', 'sciencedirect.com', 'springer.com',
        'jstor.org', 'wiley.com', 'nber.org/papers',
    ]

    # Max chars of article body to store (avoid memory issues)
    MAX_BODY_LENGTH = 4000

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': Settings.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        self.stats = {'enriched': 0, 'skipped': 0, 'failed': 0}

    def enrich_articles(self, articles: list[Article], max_workers: int = 5) -> list[Article]:
        """
        Fetch full text for all articles in parallel.

        Args:
            articles: List of articles to enrich
            max_workers: Number of parallel fetchers

        Returns:
            Same list of articles with content_preview populated
        """
        # Only enrich articles that don't already have substantial content
        to_enrich = [
            a for a in articles
            if len(a.content_preview or '') < 200 and len(a.summary or '') < 300
            and not a.url.lower().endswith('.pdf')
            and not any(domain in a.url.lower() for domain in self.SKIP_DOMAINS)
        ]

        already_rich = len(articles) - len(to_enrich)
        logger.info(f"[ENRICH] {len(to_enrich)} articles need full-text extraction "
                    f"({already_rich} already have content)")

        if not to_enrich:
            return articles

        # Fetch in parallel with rate limiting
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_article = {
                executor.submit(self._fetch_article_text, article): article
                for article in to_enrich
            }

            for future in as_completed(future_to_article):
                article = future_to_article[future]
                try:
                    body_text = future.result()
                    if body_text and len(body_text) > 100:
                        article.content_preview = body_text[:self.MAX_BODY_LENGTH]
                        self.stats['enriched'] += 1
                    else:
                        self.stats['skipped'] += 1
                except Exception as e:
                    logger.debug(f"[ENRICH] Failed for {article.title[:40]}: {e}")
                    self.stats['failed'] += 1

        logger.info(f"[ENRICH] Complete: {self.stats['enriched']} enriched, "
                    f"{self.stats['skipped']} skipped, {self.stats['failed']} failed")
        return articles

    def _fetch_article_text(self, article: Article) -> Optional[str]:
        """Fetch and parse the full text of a single article."""
        try:
            response = self.session.get(
                article.url,
                timeout=15,
                allow_redirects=True
            )
            response.raise_for_status()

            # Check content type — only parse HTML
            content_type = response.headers.get('content-type', '').lower()
            if 'html' not in content_type and 'text' not in content_type:
                return None

            soup = BeautifulSoup(response.content, 'lxml')

            # Remove non-content elements
            for tag in soup.select('nav, header, footer, script, style, aside, '
                                   '.sidebar, .menu, .navigation, .cookie, '
                                   '.social-share, .comments, .related-posts, '
                                   '.breadcrumb, .pagination, #cookie-banner'):
                tag.decompose()

            # Try to find the main article content
            body_text = self._extract_main_content(soup)

            if body_text and len(body_text) > 100:
                # Also try to update summary if it was empty
                if not article.summary or len(article.summary) < 50:
                    # Use first 500 chars as summary
                    article.summary = body_text[:500]

                return body_text

        except requests.exceptions.Timeout:
            logger.debug(f"[ENRICH] Timeout: {article.url[:50]}")
        except requests.exceptions.RequestException as e:
            logger.debug(f"[ENRICH] Request error: {e}")
        except Exception as e:
            logger.debug(f"[ENRICH] Parse error: {e}")

        return None

    def _extract_main_content(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract the main article content from parsed HTML.
        Uses multiple strategies to find the article body.
        """
        # Strategy 1: Look for semantic article containers
        article_selectors = [
            'article .content', 'article .body', 'article',
            '.article-content', '.article-body', '.post-content',
            '.entry-content', '.page-content', '.main-content',
            '[role="main"]', '#main-content', '#content',
            '.ecb-pressRelease', '.ecb-contentPage',  # ECB-specific
            '.publication-text', '.research-text',
            '.speech-text', '.press-release-text',
        ]

        for selector in article_selectors:
            container = soup.select_one(selector)
            if container:
                text = self._clean_text(container)
                if len(text) > 200:
                    return text

        # Strategy 2: Find the largest text block
        paragraphs = soup.find_all('p')
        if paragraphs:
            # Group consecutive paragraphs
            texts = [p.get_text(strip=True) for p in paragraphs]
            # Filter out very short paragraphs (likely navigation/UI)
            substantial = [t for t in texts if len(t) > 40]
            if substantial:
                return '\n\n'.join(substantial[:20])  # First 20 substantial paragraphs

        # Strategy 3: Fall back to body text
        body = soup.find('body')
        if body:
            text = self._clean_text(body)
            if len(text) > 200:
                return text[:self.MAX_BODY_LENGTH]

        return None

    def _clean_text(self, element) -> str:
        """Clean extracted text: normalize whitespace, remove noise."""
        text = element.get_text(separator='\n')

        # Clean up
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            # Skip very short lines (likely UI elements)
            if len(line) < 15:
                continue
            # Skip common noise patterns
            if any(noise in line.lower() for noise in [
                'cookie', 'subscribe', 'sign up', 'follow us',
                'share this', 'print this', 'email this',
                'copyright', 'all rights reserved',
                'terms of use', 'privacy policy',
            ]):
                continue
            lines.append(line)

        return '\n'.join(lines)
