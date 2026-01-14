"""
Gemini AI Analyzer - Uses Google's Gemini API for content analysis.
Provides summarization, key findings extraction, and categorization.
"""

import google.generativeai as genai
import logging
import time
from typing import Optional
from collections.abc import Iterable

from collectors.base_collector import Article
from config.settings import Settings

logger = logging.getLogger(__name__)


class GeminiAnalyzer:
    """
    AI-powered content analyzer using Google's Gemini API.
    Provides summarization and analysis for economic reports and articles.
    """
    
    def __init__(self):
        """Initialize the Gemini analyzer."""
        if not Settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set in environment")
        
        genai.configure(api_key=Settings.GEMINI_API_KEY)
        
        # Use Gemini 2.0 Flash for fast, cost-effective processing
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Rate limiting - conservative for free tier
        # Free tier: 15 requests/minute, 1500/day
        # We use 10/minute to be safe and avoid hitting limits
        self.requests_per_minute = 10
        self.request_count = 0
        self.last_reset = time.time()
        self.min_delay_between_requests = 4  # 4 seconds between API calls
        self.last_request_time = 0
    
    def _check_rate_limit(self):
        """Check and enforce rate limiting with conservative delays."""
        # Ensure minimum delay between requests
        time_since_last = time.time() - self.last_request_time
        if time_since_last < self.min_delay_between_requests:
            sleep_time = self.min_delay_between_requests - time_since_last
            time.sleep(sleep_time)
        
        current_time = time.time()
        if current_time - self.last_reset > 60:
            self.request_count = 0
            self.last_reset = current_time
        
        if self.request_count >= self.requests_per_minute:
            wait_time = 65 - (current_time - self.last_reset)  # Wait a bit extra
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                self.request_count = 0
                self.last_reset = time.time()
        
        self.request_count += 1
        self.last_request_time = time.time()
    
    def analyze_article(self, article: Article) -> Article:
        """
        Analyze a single article and populate AI fields.
        
        Args:
            article: Article to analyze
        
        Returns:
            Article with ai_summary and ai_analysis populated
        """
        try:
            self._check_rate_limit()
            
            # Generate one-liner summary for Excel
            article.ai_summary = self._generate_summary(article)
            
            # Generate detailed analysis for document (only for major items)
            if self._is_major_item(article):
                self._check_rate_limit()
                article.ai_analysis = self._generate_analysis(article)
            
            # Categorize the article
            article.ai_category = self._categorize(article)
            
            # Calculate importance score
            article.importance_score = self._calculate_importance(article)
            article.importance_level = self._get_importance_level(article.importance_score)
            
            # Assign themes for grouping
            article.themes = self._assign_themes(article)
            
            # Set verification status
            article.verification_status = "verified" if article.ai_summary else "unverified"
            
            logger.debug(f"Analyzed: {article.title[:50]}...")
            
        except Exception as e:
            logger.error(f"Error analyzing article '{article.title[:30]}...': {e}")
            article.ai_summary = article.summary[:150] if article.summary else "Summary not available"
            article.ai_analysis = ""
            article.ai_category = "General"
            article.importance_score = 3
            article.importance_level = "Standard"
        
        return article
    
    def analyze_batch(self, articles: list[Article], batch_size: int = 10) -> list[Article]:
        """
        Analyze multiple articles efficiently.
        
        Args:
            articles: List of articles to analyze
            batch_size: Number of articles to process before a longer pause
        
        Returns:
            List of analyzed articles
        """
        analyzed = []
        total = len(articles)
        
        for i, article in enumerate(articles):
            analyzed_article = self.analyze_article(article)
            analyzed.append(analyzed_article)
            
            if (i + 1) % batch_size == 0:
                logger.info(f"Analyzed {i + 1}/{total} articles")
                time.sleep(2)  # Pause between batches
        
        logger.info(f"Analysis complete: {len(analyzed)} articles processed")
        return analyzed
    
    def _generate_summary(self, article: Article) -> str:
        """Generate a one-liner summary for Excel."""
        prompt = f"""Generate a single-sentence summary (max 100 words) of this economic/financial content.
The summary should capture the key finding or main point.
Write in a professional but accessible tone suitable for general readers.

Title: {article.title}
Source: {article.source_full}
Category: {article.category}

Content/Description:
{article.summary or article.content_preview or 'No content available'}

Provide ONLY the one-line summary, no other text."""

        try:
            response = self.model.generate_content(prompt)
            summary = response.text.strip()
            # Clean up any quotes or extra formatting
            summary = summary.strip('"\'')
            return summary[:300]  # Limit length
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return article.summary[:150] if article.summary else "Summary not available"
    
    def _generate_analysis(self, article: Article) -> str:
        """Generate detailed 360-degree analysis for the document."""
        prompt = f"""You are an economic intelligence analyst writing for the "Global Pulse Weekly Report."

ARTICLE TO ANALYZE:
Title: {article.title}
Source: {article.source_full}
Organization Category: {article.category}
Published: {article.published_date.strftime('%B %d, %Y') if article.published_date else 'Date not specified'}
Content Type: {article.content_type}

Available Content:
{article.summary}

{article.content_preview if article.content_preview else ''}

YOUR TASK: Provide a comprehensive "Major Findings & Analysis" block following this structure:

**1. THE NON-OBVIOUS TRUTHS**
Don't just report headlines. Extract the underlying shifts, hidden patterns, or counterintuitive findings that a casual reader would miss. What does the data REALLY tell us beyond the press release?

**2. MACRO & MICRO INDICATORS**
- Macroeconomic: GDP growth, inflation, employment, trade balance implications
- Microeconomic: Industry-specific impacts, consumer behavior, business implications

**3. POLICY IMPLICATIONS**
What does this mean for:
- Government policy (fiscal, monetary, regulatory)
- Central bank actions
- Industry regulations

**4. WHY THIS MATTERS TO YOU**
Explain the real-world impact in plain terms. Use clear analogies for complex concepts:
- Example: "Fiscal deficit is like the nation's credit card balance"
- Example: "Quantitative easing is like the central bank 'printing money' to stimulate the economy"

CRITICAL RULES:
- Use "Professional-Layman Mix" tone: Be precise with data but explain jargon simply
- If specific data points are NOT in the content, say "The full report contains detailed data at [source URL]" - NEVER guess or make up numbers
- Keep total response under 500 words but be substantive, not generic
- Use bullet points for readability
- Bold key numbers and findings"""

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Analysis generation failed: {e}")
            return ""
    
    def _categorize(self, article: Article) -> str:
        """Determine the category of the article."""
        title_lower = article.title.lower()
        summary_lower = (article.summary or '').lower()
        combined = f"{title_lower} {summary_lower}"
        
        # Simple rule-based categorization
        categories = {
            'Monetary Policy': ['interest rate', 'monetary policy', 'central bank', 'inflation target', 'policy rate'],
            'Fiscal Policy': ['budget', 'fiscal', 'government spending', 'taxation', 'deficit'],
            'Trade & Tariffs': ['trade', 'tariff', 'export', 'import', 'wto', 'trade war'],
            'Employment': ['employment', 'unemployment', 'jobs', 'labor', 'workforce', 'wage'],
            'GDP & Growth': ['gdp', 'growth', 'recession', 'economic outlook', 'expansion'],
            'Inflation': ['inflation', 'cpi', 'price', 'deflation', 'consumer price'],
            'Financial Markets': ['market', 'stock', 'bond', 'equity', 'forex', 'currency'],
            'Banking & Finance': ['bank', 'lending', 'credit', 'financial stability', 'liquidity'],
            'Development': ['development', 'poverty', 'inequality', 'sdg', 'sustainable'],
            'Industry & Sector': ['industry', 'sector', 'manufacturing', 'services', 'technology'],
            'Rating Actions': ['rating', 'downgrade', 'upgrade', 'credit rating', 'outlook'],
            'Data Release': ['data', 'statistics', 'indicator', 'release', 'figures'],
        }
        
        for category, keywords in categories.items():
            if any(kw in combined for kw in keywords):
                return category
        
        return 'General Economic'
    
    def _is_major_item(self, article: Article) -> bool:
        """Determine if an article is major enough for detailed analysis."""
        # Reports, working papers, and speeches get full analysis
        major_types = ['report', 'working_paper', 'speech', 'data_release']
        if article.content_type in major_types:
            return True
        
        # Items from key organizations get analysis
        major_orgs = ['IMF', 'World Bank', 'RBI', 'OECD', 'WEF', 'BIS', 'McKinsey', 'Deloitte',
                      'BCG', 'PwC', 'Goldman Sachs', 'JP Morgan', 'Brookings', 'PIIE']
        if article.source in major_orgs:
            return True
        
        # Items with key report names
        if article.title.lower():
            key_phrases = ['outlook', 'report', 'survey', 'forecast', 'index', 'review', 
                          'economic survey', 'annual report', 'quarterly', 'bulletin']
            if any(phrase in article.title.lower() for phrase in key_phrases):
                return True
        
        # Check if it's an expert opinion piece
        if self._is_expert_opinion(article):
            return True
        
        return False
    
    def _is_expert_opinion(self, article: Article) -> bool:
        """
        Check if article is an opinion piece from a recognized authority.
        Includes Nobel laureates, Chief Economists, former central bankers, etc.
        """
        # List of recognized global authorities
        notable_experts = [
            # Nobel laureates in Economics
            'paul krugman', 'joseph stiglitz', 'robert shiller', 'eugene fama',
            'richard thaler', 'angus deaton', 'jean tirole', 'bengt holmström',
            'abhijit banerjee', 'esther duflo', 'michael kremer',
            # Chief Economists and Central Bankers
            'gita gopinath', 'pierre-olivier gourinchas', 'carmen reinhart',
            'raghuram rajan', 'urjit patel', 'shaktikanta das',
            'janet yellen', 'jerome powell', 'christine lagarde', 'mark carney',
            'mario draghi', 'ben bernanke', 'alan greenspan',
            # Other prominent economists
            'nouriel roubini', 'mohamed el-erian', 'larry summers',
            'kenneth rogoff', 'dani rodrik', 'arvind subramanian',
            'martin wolf', 'gillian tett', 'rana foroohar'
        ]
        
        # Check author field
        author_lower = (article.author or '').lower()
        title_lower = article.title.lower()
        content_lower = (article.summary or '').lower()
        
        for expert in notable_experts:
            if expert in author_lower or expert in title_lower or expert in content_lower:
                article.content_type = 'expert_opinion'  # Tag it
                return True
        
        # Check for opinion indicators from these sources
        opinion_indicators = ['opinion', 'op-ed', 'commentary', 'perspective', 'viewpoint', 'analysis by']
        is_opinion = any(ind in title_lower for ind in opinion_indicators)
        
        # Only include opinions if they seem to be from authorities
        if is_opinion and any(org in article.source for org in ['FT', 'WSJ', 'Bloomberg', 'Reuters', 'Brookings', 'PIIE']):
            # Check for title indicators of authority
            authority_titles = ['chief economist', 'former governor', 'nobel laureate', 
                               'professor', 'dr.', 'director', 'chairman', 'president']
            if any(title in content_lower or title in author_lower for title in authority_titles):
                article.content_type = 'expert_opinion'
                return True
        
        return False
    
    def generate_executive_summary(self, articles: list[Article], date_range: str) -> str:
        """
        Generate an executive summary for The Global Pulse Weekly Report.
        
        Args:
            articles: All articles collected this week
            date_range: String describing the date range (e.g., "January 7-14, 2025")
        
        Returns:
            Executive summary text
        """
        # Group by category for summary
        by_category = {}
        for article in articles:
            cat = article.ai_category or article.category
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(article.title)
        
        category_summary = "\n".join([
            f"- {cat}: {len(titles)} items"
            for cat, titles in sorted(by_category.items(), key=lambda x: -len(x[1]))
        ])
        
        # Get top headlines
        top_headlines = "\n".join([
            f"- [{a.source}] {a.title}"
            for a in articles[:15]
        ])
        
        prompt = f"""You are writing the EXECUTIVE SUMMARY for "The Global Pulse" Weekly Economic Intelligence Report.

Date Range: {date_range}
Total Articles/Reports Analyzed: {len(articles)}
Organizations Covered: 39

Coverage by Category:
{category_summary}

Top Headlines This Week:
{top_headlines}

Write a 250-350 word executive summary following this structure:

**THIS WEEK'S PULSE**
Start with the single most important economic development this week - the one thing every reader MUST know.

**KEY MACRO MOVEMENTS**
2-3 sentences covering major shifts in:
- GDP/Growth outlooks
- Inflation trends
- Employment data
- Trade dynamics

**POLICY SIGNALS**
What central banks, governments, or international bodies are signaling:
- Rate decisions or guidance
- Fiscal policy shifts
- Regulatory changes

**SECTOR SPOTLIGHT**
One industry or sector that saw significant developments this week.

**LOOKING AHEAD**
What to watch for in the coming week.

WRITING STYLE:
- Use "Professional-Layman Mix" tone: Precise data + simple explanations
- Use analogies for complex concepts (e.g., "Think of quantitative tightening as the Fed putting the economy on a diet after years of feast")
- If you don't have specific data, say "The detailed data is available in the full reports linked below"
- NEVER make up numbers or statistics
- Make it engaging - this goes to busy executives who need the essence quickly"""

        try:
            self._check_rate_limit()
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Executive summary generation failed: {e}")
            return f"This week's Global Pulse covers {len(articles)} articles and reports from {len(by_category)} categories across {date_range}."

    def _calculate_importance(self, article: Article) -> int:
        """Calculate importance score (1-10) for an article."""
        score = 3  # Base score
        
        # Source importance boost
        critical_sources = ['Fed', 'ECB', 'RBI', 'IMF', 'World Bank', 'BoE', 'BoJ', 'PBoC']
        high_sources = ['OECD', 'WEF', 'BIS', 'McKinsey', 'Goldman Sachs', 'JP Morgan']
        
        if article.source in critical_sources:
            score += 3
        elif article.source in high_sources:
            score += 2
        
        # Content type boost
        if article.content_type in ['report', 'data_release', 'speech']:
            score += 2
        elif article.content_type in ['working_paper', 'expert_opinion']:
            score += 1
        
        # Keyword boost - market-moving content
        title_lower = article.title.lower()
        critical_keywords = ['rate decision', 'fomc', 'mpc', 'gdp', 'inflation', 'recession', 
                           'crisis', 'emergency', 'downgrade', 'upgrade', 'outlook']
        if any(kw in title_lower for kw in critical_keywords):
            score += 2
        
        # Cap at 10
        return min(score, 10)
    
    def _get_importance_level(self, score: int) -> str:
        """Convert numeric score to importance level."""
        if score >= 8:
            return "Critical"
        elif score >= 5:
            return "Important"
        else:
            return "Standard"
    
    def _assign_themes(self, article: Article) -> list[str]:
        """Assign thematic tags to an article for grouping."""
        themes = []
        combined = f"{article.title} {article.summary}".lower()
        
        theme_keywords = {
            'Monetary Policy': ['interest rate', 'central bank', 'monetary policy', 'repo rate', 
                               'fed', 'ecb', 'fomc', 'mpc', 'quantitative'],
            'Inflation': ['inflation', 'cpi', 'price index', 'deflation', 'stagflation'],
            'Growth & GDP': ['gdp', 'growth', 'recession', 'expansion', 'economic outlook'],
            'Employment': ['employment', 'unemployment', 'jobs', 'labor', 'wage', 'workforce'],
            'Trade': ['trade', 'tariff', 'export', 'import', 'wto', 'trade war', 'protectionism'],
            'Fiscal Policy': ['budget', 'fiscal', 'government spending', 'taxation', 'deficit'],
            'Financial Stability': ['financial stability', 'systemic risk', 'banking crisis', 'stress test'],
            'Currency & Forex': ['currency', 'forex', 'exchange rate', 'dollar', 'yuan', 'rupee'],
            'Debt & Credit': ['debt', 'credit', 'bond', 'yield', 'sovereign debt', 'credit rating'],
            'Technology & AI': ['technology', 'digital', 'ai', 'fintech', 'cryptocurrency'],
            'Climate & ESG': ['climate', 'esg', 'sustainable', 'green', 'carbon', 'net zero'],
            'Emerging Markets': ['emerging market', 'developing', 'brics', 'frontier market'],
        }
        
        for theme, keywords in theme_keywords.items():
            if any(kw in combined for kw in keywords):
                themes.append(theme)
        
        return themes if themes else ['General Economic']
    
    def generate_top5_tldr(self, articles: list[Article]) -> str:
        """Generate TL;DR Top 5 section with the most critical developments."""
        # Sort by importance score
        sorted_articles = sorted(articles, key=lambda x: x.importance_score, reverse=True)
        top_5 = sorted_articles[:5]
        
        if not top_5:
            return "No critical developments this week."
        
        headlines = "\n".join([
            f"{i+1}. [{a.source}] {a.title} (Score: {a.importance_score}/10)"
            for i, a in enumerate(top_5)
        ])
        
        prompt = f"""Create a "TOP 5 THINGS TO KNOW THIS WEEK" section for busy executives.

The 5 most important developments (ranked by importance score):
{headlines}

For each item, write ONE sentence that answers: "What happened and why should I care?"

Format:
1. 🔴 [HEADLINE IN BOLD] - One sentence explanation
2. 🟠 [HEADLINE IN BOLD] - One sentence explanation
...

Use 🔴 for critical (score 8+), 🟠 for important (5-7), 🟢 for notable (below 5).
Be specific. No jargon. Maximum 20 words per explanation.
If you don't have the specific data, keep it general but accurate."""

        try:
            self._check_rate_limit()
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"TL;DR generation failed: {e}")
            # Fallback
            return "\n".join([f"• [{a.source}] {a.title}" for a in top_5])
    
    def generate_cross_source_synthesis(self, articles: list[Article]) -> str:
        """Generate cross-source synthesis identifying trends across organizations."""
        # Group by theme
        theme_articles = {}
        for article in articles:
            for theme in article.themes:
                if theme not in theme_articles:
                    theme_articles[theme] = []
                theme_articles[theme].append(article)
        
        # Find themes with multiple sources
        multi_source_themes = {
            theme: arts for theme, arts in theme_articles.items() 
            if len(set(a.source for a in arts)) >= 2
        }
        
        if not multi_source_themes:
            return "Limited cross-source patterns identified this week."
        
        theme_summary = "\n".join([
            f"- {theme}: {len(arts)} items from {len(set(a.source for a in arts))} sources"
            for theme, arts in sorted(multi_source_themes.items(), key=lambda x: -len(x[1]))[:5]
        ])
        
        # Identify consensus/divergence
        sources_summary = []
        for theme, arts in list(multi_source_themes.items())[:3]:
            sources = list(set(a.source for a in arts))[:4]
            titles = [a.title[:50] for a in arts[:3]]
            sources_summary.append(f"{theme}:\n  Sources: {', '.join(sources)}\n  Headlines: {'; '.join(titles)}")
        
        prompt = f"""Analyze cross-source patterns in this week's economic intelligence.

THEMES WITH MULTIPLE SOURCES:
{theme_summary}

DETAILS:
{chr(10).join(sources_summary)}

Write a "CROSS-SOURCE INTELLIGENCE" section (150-200 words) that:

1. **CONSENSUS VIEWS**: Where are multiple organizations saying the same thing?
2. **DIVERGENT VIEWS**: Where do organizations disagree?
3. **EMERGING PATTERNS**: What trends are appearing across sources?

Format with bold headers. Be specific about which organizations agree/disagree.
If you don't have enough detail, say "Based on available headlines..." and keep it accurate."""

        try:
            self._check_rate_limit()
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Cross-source synthesis failed: {e}")
            return f"This week saw coverage from {len(set(a.source for a in articles))} organizations across {len(theme_articles)} themes."
    
    def generate_theme_summary(self, articles: list[Article]) -> dict[str, str]:
        """Generate summaries for each major theme."""
        theme_articles = {}
        for article in articles:
            for theme in article.themes:
                if theme not in theme_articles:
                    theme_articles[theme] = []
                theme_articles[theme].append(article)
        
        summaries = {}
        for theme, arts in sorted(theme_articles.items(), key=lambda x: -len(x[1])):
            if len(arts) < 2:
                continue
            
            sources = list(set(a.source for a in arts))
            headlines = [a.title for a in arts[:5]]
            
            summaries[theme] = {
                'count': len(arts),
                'sources': sources,
                'headlines': headlines
            }
        
        return summaries
    
    def generate_sentiment_analysis(self, articles: list[Article]) -> str:
        """Generate overall market/economic sentiment analysis."""
        # Collect key headlines
        headlines = [f"[{a.source}] {a.title}" for a in articles[:20]]
        
        prompt = f"""Analyze the overall economic sentiment from this week's headlines.

HEADLINES:
{chr(10).join(headlines)}

Provide a SENTIMENT ANALYSIS section (100-150 words) with:

**OVERALL SENTIMENT**: [Choose ONE: 🟢 BULLISH | 🟡 NEUTRAL | 🔴 BEARISH]

**SENTIMENT BREAKDOWN**:
- Growth Outlook: [Optimistic/Cautious/Pessimistic]
- Inflation Concerns: [Rising/Stable/Easing]
- Policy Direction: [Hawkish/Neutral/Dovish]
- Market Risk Appetite: [Risk-On/Neutral/Risk-Off]

**KEY DRIVERS**:
2-3 bullet points on what's driving the sentiment.

Be specific. Base conclusions ONLY on the headlines provided. Don't guess."""

        try:
            self._check_rate_limit()
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return "Sentiment analysis unavailable this week."
    
    def generate_actionable_implications(self, articles: list[Article]) -> str:
        """Generate actionable implications for different stakeholders."""
        # Get top articles by importance
        top_articles = sorted(articles, key=lambda x: x.importance_score, reverse=True)[:10]
        summaries = [f"[{a.source}] {a.title}: {a.ai_summary or a.summary[:100]}" for a in top_articles]
        
        prompt = f"""Based on this week's key economic developments, provide ACTIONABLE IMPLICATIONS.

KEY DEVELOPMENTS:
{chr(10).join(summaries)}

Write an "ACTIONABLE IMPLICATIONS" section (200-250 words) with:

**FOR INVESTORS**:
- 2-3 specific, actionable insights (e.g., "Consider reducing emerging market exposure given...")
- Include asset classes if relevant (bonds, equities, commodities, currencies)

**FOR BUSINESSES**:
- 2-3 implications for corporate strategy, hiring, pricing, supply chains

**FOR POLICYMAKERS**:
- 2-3 points relevant to government/central bank decision-makers

**WATCH LIST**:
3-4 upcoming events/data releases that could change the picture.

CRITICAL RULES:
- Be specific, not generic
- Use "Consider..." or "Monitor..." language, not "You must..."
- If data is insufficient, say "Based on available headlines..."
- Do NOT give financial advice, frame as considerations"""

        try:
            self._check_rate_limit()
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Implications generation failed: {e}")
            return "Implications section unavailable this week."
    
    def generate_geographic_summary(self, articles: list[Article]) -> dict:
        """Group articles by geographic region."""
        # Define region mappings
        source_regions = {
            # Americas
            'Fed': 'Americas', 'NBER': 'Americas', 'Brookings': 'Americas', 'PIIE': 'Americas',
            'WSJ': 'Americas', 'Goldman Sachs': 'Americas', 'JP Morgan': 'Americas',
            # Europe
            'ECB': 'Europe', 'BoE': 'Europe', 'Bruegel': 'Europe', 'FT': 'Europe',
            # Asia-Pacific
            'BoJ': 'Asia-Pacific', 'PBoC': 'Asia-Pacific', 'ADB': 'Asia-Pacific',
            # India-specific
            'RBI': 'India', 'MoF India': 'India', 'MoSPI': 'India', 'NITI Aayog': 'India',
            # Global/International
            'IMF': 'Global', 'World Bank': 'Global', 'OECD': 'Global', 'WTO': 'Global',
            'WEF': 'Global', 'BIS': 'Global', 'ILO': 'Global', 'UNCTAD': 'Global',
            # Consulting (Global)
            'McKinsey': 'Global', 'Deloitte': 'Global', 'BCG': 'Global', 'PwC': 'Global',
        }
        
        regions = {
            'Global': {'articles': [], 'sources': set()},
            'Americas': {'articles': [], 'sources': set()},
            'Europe': {'articles': [], 'sources': set()},
            'Asia-Pacific': {'articles': [], 'sources': set()},
            'India': {'articles': [], 'sources': set()},
        }
        
        for article in articles:
            region = source_regions.get(article.source, 'Global')
            if region in regions:
                regions[region]['articles'].append(article)
                regions[region]['sources'].add(article.source)
        
        # Convert sets to lists and add counts
        for region in regions:
            regions[region]['sources'] = list(regions[region]['sources'])
            regions[region]['count'] = len(regions[region]['articles'])
            regions[region]['headlines'] = [a.title for a in regions[region]['articles'][:5]]
        
        return regions
    
    def fetch_key_economic_indicators(self) -> dict:
        """Fetch key economic indicators from free APIs."""
        indicators = {}
        
        try:
            import requests
            
            # FRED API (Federal Reserve Economic Data) - Free, no key required for basic
            fred_series = {
                'US_INFLATION': 'CPIAUCSL',      # US CPI
                'US_UNEMPLOYMENT': 'UNRATE',     # US Unemployment Rate
                'US_GDP_GROWTH': 'A191RL1Q225SBEA',  # US Real GDP Growth
                'FED_FUNDS_RATE': 'FEDFUNDS',    # Federal Funds Rate
            }
            
            for name, series_id in fred_series.items():
                try:
                    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key=demo&file_type=json&limit=1&sort_order=desc"
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('observations'):
                            obs = data['observations'][0]
                            indicators[name] = {
                                'value': obs.get('value', 'N/A'),
                                'date': obs.get('date', 'N/A')
                            }
                except Exception as e:
                    logger.debug(f"Could not fetch {name}: {e}")
            
            # Add placeholder for other indicators
            indicators['NOTES'] = "Data from FRED (Federal Reserve Economic Data). For more indicators, add API keys."
            
        except Exception as e:
            logger.error(f"Error fetching economic indicators: {e}")
            indicators['error'] = str(e)
        
        return indicators
    
    def generate_key_numbers_section(self, indicators: dict) -> str:
        """Generate a Key Numbers This Week section."""
        if not indicators or 'error' in indicators:
            return "Key economic indicators unavailable. Check API connectivity."
        
        lines = ["**KEY ECONOMIC NUMBERS**\n"]
        
        indicator_names = {
            'US_INFLATION': 'US Inflation (CPI)',
            'US_UNEMPLOYMENT': 'US Unemployment Rate',
            'US_GDP_GROWTH': 'US GDP Growth (Q/Q)',
            'FED_FUNDS_RATE': 'Fed Funds Rate',
        }
        
        for key, name in indicator_names.items():
            if key in indicators:
                val = indicators[key]
                lines.append(f"• {name}: {val['value']}% (as of {val['date']})")
        
        if indicators.get('NOTES'):
            lines.append(f"\n_{indicators['NOTES']}_")
        
        return "\n".join(lines)

