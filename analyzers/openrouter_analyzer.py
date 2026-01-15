"""
OpenRouter Analyzer - Multi-model AI analysis using OpenRouter API.
Provides access to Llama, Mistral, Gemma and other free models.
"""

import logging
import time
from typing import Optional
import requests
from config import Settings
from collectors.base_collector import Article

logger = logging.getLogger(__name__)


class OpenRouterAnalyzer:
    """AI analyzer using OpenRouter API with multiple free models."""
    
    # Free models in order of preference
    FREE_MODELS = [
        {
            "id": "meta-llama/llama-3.3-70b-instruct:free",
            "name": "Llama 3.3 70B",
            "context": 131072,
            "best_for": "Complex analysis, reasoning"
        },
        {
            "id": "mistralai/mistral-small-3.1-24b-instruct:free",
            "name": "Mistral Small 24B",
            "context": 96000,
            "best_for": "Fast processing"
        },
        {
            "id": "google/gemma-3-27b-it:free",
            "name": "Gemma 3 27B",
            "context": 128000,
            "best_for": "Multilingual, reasoning"
        },
        {
            "id": "meta-llama/llama-3.1-8b-instruct:free",
            "name": "Llama 3.1 8B",
            "context": 131072,
            "best_for": "Simple summaries"
        }
    ]
    
    def __init__(self, api_key: str = None):
        """Initialize OpenRouter analyzer."""
        self.api_key = api_key or Settings.OPENROUTER_API_KEY
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set")
        
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.current_model_index = 0
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/economic-intelligence-agent",
            "X-Title": "Economic Intelligence Agent"
        }
        
        # Rate limiting
        self.requests_per_minute = 15
        self.request_count = 0
        self.last_reset = time.time()
        self.min_delay = 3
        self.last_request = 0
        
        # Quota tracking
        self.consecutive_errors = 0
        self.max_consecutive_errors = 3
        self.quota_exhausted = False
        self.successful_requests = 0
        self.failed_requests = 0
    
    @property
    def current_model(self):
        """Get the current model being used."""
        return self.FREE_MODELS[self.current_model_index]
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        if self.quota_exhausted:
            return False
        
        # Minimum delay between requests
        elapsed = time.time() - self.last_request
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        
        # Per-minute rate limit
        if time.time() - self.last_reset > 60:
            self.request_count = 0
            self.last_reset = time.time()
        
        if self.request_count >= self.requests_per_minute:
            wait = 65 - (time.time() - self.last_reset)
            if wait > 0:
                logger.info(f"Rate limit reached, waiting {wait:.1f}s")
                time.sleep(wait)
            self.request_count = 0
            self.last_reset = time.time()
        
        self.request_count += 1
        self.last_request = time.time()
        return True
    
    def _switch_model(self):
        """Switch to the next available model."""
        if self.current_model_index < len(self.FREE_MODELS) - 1:
            self.current_model_index += 1
            self.consecutive_errors = 0
            logger.warning(
                f"Switching to model: {self.current_model['name']} "
                f"({self.current_model['id']})"
            )
            return True
        return False
    
    def _call_api(self, messages: list, max_tokens: int = 1000) -> Optional[str]:
        """Make API call to OpenRouter."""
        if not self._rate_limit():
            return None
        
        payload = {
            "model": self.current_model["id"],
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                self.consecutive_errors = 0
                self.successful_requests += 1
                return data["choices"][0]["message"]["content"]
            
            elif response.status_code == 429:
                self.consecutive_errors += 1
                self.failed_requests += 1
                logger.warning(
                    f"Rate limit on {self.current_model['name']}: "
                    f"error {self.consecutive_errors}/{self.max_consecutive_errors}"
                )
                
                if self.consecutive_errors >= self.max_consecutive_errors:
                    if not self._switch_model():
                        self.quota_exhausted = True
                        logger.error("=== ALL MODELS EXHAUSTED ===")
                        return None
                
                time.sleep(30 * self.consecutive_errors)
                return self._call_api(messages, max_tokens)
            
            else:
                logger.error(f"API error {response.status_code}: {response.text}")
                self.failed_requests += 1
                return None
                
        except Exception as e:
            logger.error(f"Request error: {e}")
            self.failed_requests += 1
            return None
    
    def generate_summary(self, article: Article) -> str:
        """Generate a one-liner summary for an article."""
        if self.quota_exhausted:
            return article.summary[:150] if article.summary else "Summary unavailable"
        
        prompt = f"""Summarize this economic article in exactly one sentence (max 150 characters):

Title: {article.title}
Source: {article.source}
Content: {article.summary or article.content[:500]}

One-sentence summary:"""
        
        messages = [{"role": "user", "content": prompt}]
        result = self._call_api(messages, max_tokens=100)
        
        if result:
            return result.strip()[:200]
        return article.summary[:150] if article.summary else "Summary unavailable"
    
    def generate_analysis(self, article: Article) -> str:
        """Generate detailed analysis for important articles."""
        if self.quota_exhausted:
            return ""
        
        prompt = f"""Analyze this economic article as an expert economist. Provide:
1. KEY INSIGHT (most important takeaway)
2. MARKET IMPLICATIONS (how this affects markets/economy)
3. WHAT TO WATCH (future developments to monitor)

Title: {article.title}
Source: {article.source}
Content: {article.summary or article.content[:1000]}

Analysis:"""
        
        messages = [{"role": "user", "content": prompt}]
        result = self._call_api(messages, max_tokens=500)
        
        return result or ""
    
    def generate_executive_summary(self, articles: list[Article], date_range: str) -> str:
        """Generate executive summary of all articles."""
        if self.quota_exhausted or not articles:
            return f"Weekly economic intelligence covering {len(articles)} articles."
        
        # Prepare article digest
        digest = []
        for i, article in enumerate(articles[:30]):  # Top 30 articles
            digest.append(f"{i+1}. [{article.source}] {article.title}")
        
        prompt = f"""You are an expert economist writing a weekly intelligence brief.

Based on these {len(articles)} articles from {date_range}, write an executive summary:

{chr(10).join(digest)}

Write a 200-word executive summary covering:
- Major economic developments
- Key policy changes
- Market trends
- Risks and opportunities

Executive Summary:"""
        
        messages = [{"role": "user", "content": prompt}]
        result = self._call_api(messages, max_tokens=400)
        
        return result or f"Weekly economic intelligence covering {len(articles)} articles."
    
    def generate_tldr_top5(self, articles: list[Article]) -> str:
        """Generate TL;DR Top 5 developments."""
        if self.quota_exhausted or not articles:
            return ""
        
        digest = []
        for i, a in enumerate(articles[:20]):
            digest.append(f"{i+1}. [{a.source}] {a.title}")
        
        prompt = f"""From these articles, identify the TOP 5 most important developments.
For each, provide:
- Priority indicator (CRITICAL/IMPORTANT/NOTABLE)
- One-sentence explanation

Articles:
{chr(10).join(digest)}

Format:
1. [CRITICAL] Development - Brief explanation
2. [IMPORTANT] Development - Brief explanation
... etc

TOP 5:"""
        
        messages = [{"role": "user", "content": prompt}]
        result = self._call_api(messages, max_tokens=400)
        
        return result or ""
    
    def generate_sentiment(self, articles: list[Article]) -> str:
        """Generate market sentiment analysis."""
        if self.quota_exhausted or not articles:
            return ""
        
        digest = [f"- [{a.source}] {a.title}" for a in articles[:25]]
        
        prompt = f"""Analyze the overall market sentiment from these economic articles:

{chr(10).join(digest)}

Provide:
1. OVERALL SENTIMENT: BULLISH / NEUTRAL / BEARISH
2. Confidence level (High/Medium/Low)
3. Key factors driving sentiment
4. Sector breakdown (which sectors bullish/bearish)

Sentiment Analysis:"""
        
        messages = [{"role": "user", "content": prompt}]
        result = self._call_api(messages, max_tokens=400)
        
        return result or ""
    
    def generate_cross_source_synthesis(self, articles: list[Article]) -> str:
        """Generate cross-source synthesis finding common themes."""
        if self.quota_exhausted or not articles:
            return ""
        
        # Group by source
        by_source = {}
        for a in articles[:30]:
            if a.source not in by_source:
                by_source[a.source] = []
            by_source[a.source].append(a.title)
        
        source_summary = []
        for source, titles in list(by_source.items())[:10]:
            source_summary.append(f"{source}: {', '.join(titles[:3])}")
        
        prompt = f"""Analyze these articles from multiple sources and find:
1. COMMON THEMES across different organizations
2. CONTRASTING VIEWS where sources disagree
3. EMERGING CONSENSUS on key issues

Sources and their articles:
{chr(10).join(source_summary)}

Cross-Source Synthesis:"""
        
        messages = [{"role": "user", "content": prompt}]
        result = self._call_api(messages, max_tokens=500)
        
        return result or ""
    
    def generate_theme_summary(self, articles: list[Article]) -> dict:
        """Generate theme-based summary of articles."""
        if self.quota_exhausted or not articles:
            return {}
        
        # Define themes
        themes = {
            "Monetary Policy": [],
            "Trade & Tariffs": [],
            "Inflation": [],
            "Employment": [],
            "Growth & GDP": [],
            "Financial Markets": [],
            "Technology & AI": [],
            "Energy & Climate": []
        }
        
        # Categorize articles by keyword matching
        for article in articles:
            text = f"{article.title} {article.summary or ''}".lower()
            if any(w in text for w in ['rate', 'fed', 'central bank', 'monetary', 'interest']):
                themes["Monetary Policy"].append(article.title)
            if any(w in text for w in ['trade', 'tariff', 'export', 'import', 'wto']):
                themes["Trade & Tariffs"].append(article.title)
            if any(w in text for w in ['inflation', 'cpi', 'price', 'deflation']):
                themes["Inflation"].append(article.title)
            if any(w in text for w in ['job', 'employment', 'unemployment', 'labor', 'wage']):
                themes["Employment"].append(article.title)
            if any(w in text for w in ['gdp', 'growth', 'recession', 'expansion']):
                themes["Growth & GDP"].append(article.title)
            if any(w in text for w in ['stock', 'bond', 'equity', 'market', 'investor']):
                themes["Financial Markets"].append(article.title)
            if any(w in text for w in ['ai', 'tech', 'digital', 'artificial', 'automation']):
                themes["Technology & AI"].append(article.title)
            if any(w in text for w in ['energy', 'oil', 'climate', 'carbon', 'renewable']):
                themes["Energy & Climate"].append(article.title)
        
        # Remove empty themes and limit articles
        return {k: v[:5] for k, v in themes.items() if v}
    
    def generate_actionable_implications(self, articles: list[Article]) -> str:
        """Generate actionable implications from the articles."""
        if self.quota_exhausted or not articles:
            return ""
        
        digest = [f"- [{a.source}] {a.title}" for a in articles[:20]]
        
        prompt = f"""Based on these economic articles, provide ACTIONABLE IMPLICATIONS for:

Articles:
{chr(10).join(digest)}

Provide specific, actionable insights for:
1. INVESTORS: What should they watch/consider?
2. BUSINESSES: What strategic adjustments to consider?
3. POLICYMAKERS: What policy responses might be needed?
4. CONSUMERS: How might this affect household decisions?

Actionable Implications:"""
        
        messages = [{"role": "user", "content": prompt}]
        result = self._call_api(messages, max_tokens=500)
        
        return result or ""
    
    def generate_geographic_summary(self, articles: list[Article]) -> dict:
        """Generate geographic breakdown of articles."""
        if not articles:
            return {}
        
        # Define regions
        regions = {
            "United States": ["us", "usa", "america", "fed", "treasury", "washington"],
            "Europe": ["europe", "eu", "ecb", "eurozone", "uk", "britain", "germany", "france"],
            "Asia Pacific": ["china", "japan", "india", "asia", "pacific", "asean", "korea"],
            "Emerging Markets": ["emerging", "brazil", "mexico", "africa", "middle east", "latam"],
            "Global": ["global", "world", "imf", "worldbank", "wto", "g20", "g7", "oecd"]
        }
        
        result = {}
        for article in articles:
            text = f"{article.title} {article.source} {article.summary or ''}".lower()
            for region, keywords in regions.items():
                if any(kw in text for kw in keywords):
                    if region not in result:
                        result[region] = []
                    if len(result[region]) < 5:  # Limit per region
                        result[region].append(article.title)
        
        return result
    
    def generate_key_numbers_section(self, indicators: dict = None) -> str:
        """Generate key numbers section (placeholder for FRED data)."""
        if not indicators:
            return "Key economic indicators will be updated when data is available."
        
        # Format any indicators that were passed
        lines = ["Key Economic Indicators:"]
        for name, value in indicators.items():
            lines.append(f"- {name}: {value}")
        return "\n".join(lines)
    
    def fetch_key_economic_indicators(self) -> dict:
        """Placeholder for FRED API integration."""
        # This would normally call FRED API
        # For now, return empty dict - actual data comes from GeminiAnalyzer
        return {}
    
    def get_status(self) -> dict:
        """Get current analyzer status."""
        return {
            "current_model": self.current_model["name"],
            "model_id": self.current_model["id"],
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "quota_exhausted": self.quota_exhausted,
            "models_tried": self.current_model_index + 1,
            "models_available": len(self.FREE_MODELS)
        }

