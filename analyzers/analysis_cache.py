"""
Analysis Cache — Saves and reuses AI analyses to avoid re-processing.

Saves ~40% of API credits on weekly runs, since many articles persist
across weeks (especially from slower-publishing organizations).
"""

import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from config.settings import Settings

logger = logging.getLogger(__name__)

CACHE_FILE = Settings.BASE_DIR / 'output' / '.analysis_cache.json'
CACHE_MAX_AGE_DAYS = 14  # Expire cached analyses after 2 weeks


class AnalysisCache:
    """
    Persistent cache for article analyses.
    Key: URL hash → Value: {summary, analysis, category, score, timestamp}
    """

    def __init__(self):
        self.cache = self._load_cache()
        self.hits = 0
        self.misses = 0

    def _load_cache(self) -> dict:
        """Load cache from disk."""
        try:
            if CACHE_FILE.exists():
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                # Expire old entries
                cutoff = (datetime.now() - timedelta(days=CACHE_MAX_AGE_DAYS)).isoformat()
                cache = {
                    k: v for k, v in cache.items()
                    if v.get('timestamp', '') > cutoff
                }
                logger.info(f"[CACHE] Loaded {len(cache)} entries from disk")
                return cache
        except Exception as e:
            logger.warning(f"[CACHE] Could not load cache: {e}")
        return {}

    def save(self):
        """Persist cache to disk."""
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, default=str)
            logger.info(f"[CACHE] Saved {len(self.cache)} entries "
                       f"(hits: {self.hits}, misses: {self.misses})")
        except Exception as e:
            logger.warning(f"[CACHE] Could not save cache: {e}")

    def _url_key(self, url: str) -> str:
        """Generate a cache key from a URL."""
        return hashlib.md5(url.encode()).hexdigest()

    def get(self, url: str) -> Optional[dict]:
        """Look up cached analysis for a URL."""
        key = self._url_key(url)
        entry = self.cache.get(key)
        if entry:
            self.hits += 1
            return entry
        self.misses += 1
        return None

    def put(self, url: str, summary: str, analysis: str,
            category: str, importance: int, themes: list):
        """Store an analysis in the cache."""
        key = self._url_key(url)
        self.cache[key] = {
            'summary': summary,
            'analysis': analysis,
            'category': category,
            'importance': importance,
            'themes': themes,
            'timestamp': datetime.now().isoformat()
        }

    def apply_cached(self, article) -> bool:
        """
        Try to apply cached analysis to an article.
        Returns True if cache hit, False if miss.
        """
        cached = self.get(article.url)
        if cached and cached.get('summary'):
            article.ai_summary = cached['summary']
            article.ai_analysis = cached.get('analysis', '')
            article.ai_category = cached.get('category', '')
            article.importance_score = cached.get('importance', 5)
            article.importance_level = (
                'Critical' if article.importance_score >= 8
                else 'Important' if article.importance_score >= 5
                else 'Standard'
            )
            article.themes = cached.get('themes', [])
            article.verification_status = 'cached'
            return True
        return False

    def store_article(self, article):
        """Store an article's analysis in the cache."""
        if article.ai_summary and article.verification_status not in ('filtered', 'unverified'):
            self.put(
                url=article.url,
                summary=article.ai_summary,
                analysis=article.ai_analysis or '',
                category=article.ai_category or '',
                importance=article.importance_score,
                themes=article.themes or []
            )
