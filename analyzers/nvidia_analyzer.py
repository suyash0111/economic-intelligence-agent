"""
NVIDIA NIM Multi-Model Analyzer - 7-Model Architecture for World-Class Economic Intelligence.

Models:
  1. Mistral Small 3.1 (24B) - Quick article summaries
  2. DeepSeek V3.1 Terminus - Deep analysis & reasoning
  3. Llama 4 Maverick - Vision/chart analysis
  4. Llama Nemotron Rerank - Article relevance ranking
  5. NV-Embed-V1 - Embeddings for dedup & clustering
  6. OCDRNet - OCR for scanned PDFs
  7. Kimi K2 Instruct - Long-context final synthesis
"""

import logging
import time
import base64
import requests as http_requests
from typing import Optional
from collections.abc import Iterable

from openai import OpenAI

from collectors.base_collector import Article
from config.settings import Settings

logger = logging.getLogger(__name__)


# =========================================================================
# MODEL CONFIGURATION
# =========================================================================

class NvidiaModels:
    """NVIDIA NIM model identifiers."""
    SUMMARIZER = "mistralai/mistral-small-3.1-24b-instruct-2503"
    DEEP_ANALYZER = "deepseek-ai/deepseek-v3.1-terminus"
    VISION = "meta/llama-4-maverick-17b-128e-instruct"
    RERANKER = "nvidia/llama-nemotron-rerank-1b-v2"
    EMBEDDER = "nvidia/nv-embed-v1"
    OCR = "nvidia/ocdrnet"
    SYNTHESIZER = "moonshotai/kimi-k2-instruct-0905"

    BASE_URL = "https://integrate.api.nvidia.com/v1"
    RERANKER_URL = "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-1b-v2/reranking"


class NvidiaAnalyzer:
    """
    AI-powered content analyzer using NVIDIA NIM's 7-model architecture.
    Drop-in replacement for GeminiAnalyzer with the same public API.
    """

    def __init__(self):
        """Initialize the NVIDIA NIM analyzer with all model clients."""
        if not Settings.NVIDIA_API_KEY:
            raise ValueError("NVIDIA_API_KEY not set in environment")

        # Single OpenAI-compatible client for all chat/completion models
        self.client = OpenAI(
            base_url=NvidiaModels.BASE_URL,
            api_key=Settings.NVIDIA_API_KEY
        )

        # Rate limiting - NVIDIA allows ~40 RPM, we use 30 to be safe
        self.requests_per_minute = 30
        self.request_count = 0
        self.last_reset = time.time()
        self.min_delay_between_requests = 2.0  # 2s between calls (vs 4s for Gemini)
        self.last_request_time = 0

        # Credit tracking
        self.total_api_calls = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.credits_estimate = 0

        # Quota exhaustion detection
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        self.quota_exhausted = False

        logger.info(f"NVIDIA NIM Analyzer initialized with 7-model architecture")
        logger.info(f"  🟢 Summarizer:  {NvidiaModels.SUMMARIZER}")
        logger.info(f"  🔵 Analyzer:    {NvidiaModels.DEEP_ANALYZER}")
        logger.info(f"  🟣 Vision:      {NvidiaModels.VISION}")
        logger.info(f"  🟠 Reranker:    {NvidiaModels.RERANKER}")
        logger.info(f"  🧬 Embedder:    {NvidiaModels.EMBEDDER}")
        logger.info(f"  🔴 OCR:         {NvidiaModels.OCR}")
        logger.info(f"  🟡 Synthesizer: {NvidiaModels.SYNTHESIZER}")

    # =====================================================================
    # RATE LIMITING & ERROR HANDLING
    # =====================================================================

    def _check_rate_limit(self):
        """Check and enforce rate limiting."""
        if self.quota_exhausted:
            return False

        # Enforce minimum delay
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay_between_requests:
            time.sleep(self.min_delay_between_requests - elapsed)

        # Per-minute rate limiting
        now = time.time()
        if now - self.last_reset > 60:
            self.request_count = 0
            self.last_reset = now

        if self.request_count >= self.requests_per_minute:
            wait_time = 65 - (now - self.last_reset)
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                self.request_count = 0
                self.last_reset = time.time()

        self.request_count += 1
        self.last_request_time = time.time()
        self.total_api_calls += 1
        return True

    def _handle_api_error(self, error: Exception) -> bool:
        """Handle API errors. Returns True if should retry."""
        error_str = str(error).lower()

        if '429' in error_str or 'rate' in error_str or 'quota' in error_str or 'credit' in error_str:
            self.consecutive_errors += 1
            self.failed_requests += 1

            logger.warning(f"API error #{self.consecutive_errors}/{self.max_consecutive_errors}: {error}")

            if self.consecutive_errors >= self.max_consecutive_errors:
                self.quota_exhausted = True
                logger.error(
                    f"=== CREDITS EXHAUSTED ===\n"
                    f"Hit {self.consecutive_errors} consecutive errors.\n"
                    f"Successful: {self.successful_requests}, Failed: {self.failed_requests}\n"
                    f"Estimated credits used: ~{self.credits_estimate}\n"
                    f"Switching to fallback mode."
                )
                return False

            wait_time = min(15 * self.consecutive_errors, 60)
            logger.info(f"Waiting {wait_time}s before retry...")
            time.sleep(wait_time)
            return True

        self.failed_requests += 1
        return False

    def _mark_success(self, credit_cost: int = 1):
        """Mark a successful API call."""
        self.consecutive_errors = 0
        self.successful_requests += 1
        self.credits_estimate += credit_cost

    # =====================================================================
    # CORE CHAT COMPLETION METHODS
    # =====================================================================

    def _chat(self, model: str, prompt: str, max_tokens: int = 1024,
              temperature: float = 0.3, system_prompt: str = None) -> str:
        """Make a chat completion call to any NVIDIA NIM model."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False
        )
        return response.choices[0].message.content.strip()

    def _safe_chat(self, model: str, prompt: str, fallback: str = "",
                   max_tokens: int = 1024, temperature: float = 0.3,
                   system_prompt: str = None, credit_cost: int = 1,
                   max_retries: int = 2) -> str:
        """Safely make a chat call with retry and fallback."""
        for attempt in range(max_retries):
            try:
                can_proceed = self._check_rate_limit()
                if not can_proceed:
                    return fallback

                result = self._chat(model, prompt, max_tokens, temperature, system_prompt)
                self._mark_success(credit_cost)
                return result
            except Exception as e:
                should_retry = self._handle_api_error(e)
                if not should_retry or self.quota_exhausted:
                    return fallback
        return fallback

    def _safe_vision_chat(self, prompt: str, image_bytes: bytes,
                          fallback: str = "", max_tokens: int = 512) -> str:
        """Make a vision API call with an image."""
        try:
            can_proceed = self._check_rate_limit()
            if not can_proceed:
                return fallback

            # Encode image as base64
            b64_image = base64.b64encode(image_bytes).decode('utf-8')

            response = self.client.chat.completions.create(
                model=NvidiaModels.VISION,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64_image}"
                            }
                        }
                    ]
                }],
                max_tokens=max_tokens,
                temperature=0.2,
                stream=False
            )
            self._mark_success(credit_cost=1)
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"Vision call failed: {e}")
            self._handle_api_error(e)
            return fallback

    # =====================================================================
    # MODEL 5: EMBEDDINGS (NV-Embed-V1)
    # =====================================================================

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts using NV-Embed-V1."""
        embeddings = []
        batch_size = 50  # Process in batches

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                can_proceed = self._check_rate_limit()
                if not can_proceed:
                    # Return empty embeddings for remaining
                    embeddings.extend([[] for _ in batch])
                    continue

                response = self.client.embeddings.create(
                    model=NvidiaModels.EMBEDDER,
                    input=batch,
                    encoding_format="float"
                )
                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)
                self._mark_success(credit_cost=1)

            except Exception as e:
                logger.warning(f"Embedding batch {i // batch_size} failed: {e}")
                embeddings.extend([[] for _ in batch])

        return embeddings

    def deduplicate_articles(self, articles: list[Article]) -> list[Article]:
        """Remove duplicate articles using semantic similarity."""
        if len(articles) <= 1:
            return articles

        logger.info(f"[DEDUP] Embedding {len(articles)} articles for deduplication...")

        # Create text representations
        texts = [f"{a.title}. {a.summary[:200] if a.summary else ''}" for a in articles]
        embeddings = self.embed_texts(texts)

        # Filter out articles with failed embeddings
        valid_pairs = [(a, e) for a, e in zip(articles, embeddings) if e]
        if len(valid_pairs) < len(articles):
            logger.warning(f"[DEDUP] {len(articles) - len(valid_pairs)} articles had no embeddings")
            # Keep articles with failed embeddings (don't lose them)
            failed = [a for a, e in zip(articles, embeddings) if not e]
        else:
            failed = []

        if not valid_pairs:
            return articles  # Embedding failed entirely, return all

        # Compute cosine similarity and mark duplicates
        import math

        def cosine_sim(a, b):
            if not a or not b:
                return 0.0
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        # Priority mapping for source preference
        source_priority = {
            'Fed': 10, 'ECB': 10, 'RBI': 10, 'IMF': 9, 'World Bank': 9,
            'BoE': 9, 'BoJ': 9, 'PBoC': 9, 'OECD': 8, 'BIS': 8,
            'McKinsey': 7, 'Goldman Sachs': 7, 'JP Morgan': 7,
        }

        valid_articles = [a for a, _ in valid_pairs]
        valid_embeddings = [e for _, e in valid_pairs]

        # Mark duplicates (keep higher priority source)
        is_duplicate = [False] * len(valid_articles)
        duplicate_count = 0

        for i in range(len(valid_articles)):
            if is_duplicate[i]:
                continue
            for j in range(i + 1, len(valid_articles)):
                if is_duplicate[j]:
                    continue
                sim = cosine_sim(valid_embeddings[i], valid_embeddings[j])
                if sim > 0.92:  # High similarity threshold
                    # Mark the lower-priority one as duplicate
                    pri_i = source_priority.get(valid_articles[i].source, 5)
                    pri_j = source_priority.get(valid_articles[j].source, 5)
                    if pri_i >= pri_j:
                        is_duplicate[j] = True
                    else:
                        is_duplicate[i] = True
                    duplicate_count += 1

        unique = [a for a, dup in zip(valid_articles, is_duplicate) if not dup]
        unique.extend(failed)  # Add back articles with failed embeddings

        logger.info(f"[DEDUP] Removed {duplicate_count} duplicates: {len(articles)} → {len(unique)} articles")
        return unique

    # =====================================================================
    # MODEL 4: RERANKING (Rerank-QA-Mistral)
    # =====================================================================

    def rank_articles(self, articles: list[Article]) -> list[Article]:
        """Rank articles by economic relevance using the reranker model."""
        if not articles:
            return articles

        logger.info(f"[RANK] Ranking {len(articles)} articles by economic relevance...")

        query = "Most important economic and financial development affecting global markets, monetary policy, GDP growth, inflation, trade, and fiscal policy this week"

        # Process in batches of 30 (reranker has token limits)
        batch_size = 30
        all_scored = []

        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]
            passages = [
                {"text": f"{a.title}. {(a.summary or '')[:300]}"}
                for a in batch
            ]

            try:
                can_proceed = self._check_rate_limit()
                if not can_proceed:
                    # Fallback: keep original order with default scores
                    for a in batch:
                        all_scored.append((a, a.importance_score / 10.0))
                    continue

                headers = {
                    "Authorization": f"Bearer {Settings.NVIDIA_API_KEY}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
                data = {
                    "model": NvidiaModels.RERANKER,
                    "query": {"text": query},
                    "passages": passages,
                    "truncate": "END"
                }

                response = http_requests.post(
                    NvidiaModels.RERANKER_URL,
                    headers=headers,
                    json=data,
                    timeout=30
                )

                if response.status_code == 200:
                    rankings = response.json().get("rankings", [])
                    self._mark_success(credit_cost=1)

                    # Map scores back to articles
                    score_map = {r["index"]: r["logit"] for r in rankings}
                    for idx, article in enumerate(batch):
                        score = score_map.get(idx, 0.0)
                        all_scored.append((article, score))
                else:
                    logger.warning(f"Reranking failed ({response.status_code}): {response.text[:200]}")
                    for a in batch:
                        all_scored.append((a, a.importance_score / 10.0))

            except Exception as e:
                logger.warning(f"Reranking batch failed: {e}")
                for a in batch:
                    all_scored.append((a, a.importance_score / 10.0))

        # Sort by rerank score (highest first)
        all_scored.sort(key=lambda x: x[1], reverse=True)
        ranked = [a for a, _ in all_scored]

        logger.info(f"[RANK] Top 3: {[a.title[:40] for a in ranked[:3]]}")
        return ranked

    # =====================================================================
    # ARTICLE ANALYSIS (Models 1 & 2)
    # =====================================================================

    def analyze_article(self, article: Article) -> Article:
        """Analyze a single article and populate AI fields."""
        if self.quota_exhausted:
            return self._fallback_analysis(article)

        try:
            # Generate summary using fast Mistral Small 3.1
            article.ai_summary = self._safe_chat(
                model=NvidiaModels.SUMMARIZER,
                prompt=self._summary_prompt(article),
                fallback=article.summary[:150] if article.summary else "Summary not available",
                max_tokens=256,
                temperature=0.2
            )

            # Deep analysis for major items using DeepSeek V3.1
            if self._is_major_item(article) and not self.quota_exhausted:
                article.ai_analysis = self._safe_chat(
                    model=NvidiaModels.DEEP_ANALYZER,
                    prompt=self._analysis_prompt(article),
                    fallback="",
                    max_tokens=1024,
                    temperature=0.3,
                    credit_cost=1
                )

            # Non-AI methods (keyword-based, no API calls)
            article.ai_category = self._categorize(article)
            article.importance_score = self._calculate_importance(article)
            article.importance_level = self._get_importance_level(article.importance_score)
            article.themes = self._assign_themes(article)
            article.verification_status = "verified" if article.ai_summary and not self.quota_exhausted else "partial"

        except Exception as e:
            logger.error(f"Error analyzing '{article.title[:30]}...': {e}")
            return self._fallback_analysis(article)

        return article

    def analyze_batch(self, articles: list[Article], batch_size: int = 10) -> list[Article]:
        """Analyze multiple articles efficiently."""
        analyzed = []
        total = len(articles)

        for i, article in enumerate(articles):
            analyzed_article = self.analyze_article(article)
            analyzed.append(analyzed_article)

            if (i + 1) % batch_size == 0:
                logger.info(f"Analyzed {i + 1}/{total} articles "
                           f"(credits: ~{self.credits_estimate}, calls: {self.total_api_calls})")
                time.sleep(1)

        logger.info(f"Analysis complete: {len(analyzed)} articles, ~{self.credits_estimate} credits used")
        return analyzed

    def _fallback_analysis(self, article: Article) -> Article:
        """Provide fallback analysis when credits are exhausted."""
        article.ai_summary = article.summary[:150] if article.summary else "AI analysis unavailable (credits exhausted)"
        article.ai_analysis = ""
        article.ai_category = self._categorize(article)
        article.importance_score = self._calculate_importance(article)
        article.importance_level = self._get_importance_level(article.importance_score)
        article.themes = self._assign_themes(article)
        article.verification_status = "unverified"
        return article

    # =====================================================================
    # PROMPTS
    # =====================================================================

    def _summary_prompt(self, article: Article) -> str:
        return f"""Generate a single-sentence summary (max 100 words) of this economic/financial content.
The summary should capture the key finding or main point.
Write in a professional but accessible tone suitable for general readers.

Title: {article.title}
Source: {article.source_full}
Category: {article.category}

Content/Description:
{article.summary or article.content_preview or 'No content available'}

Provide ONLY the one-line summary, no other text."""

    def _analysis_prompt(self, article: Article) -> str:
        return f"""You are an economic intelligence analyst writing for the "Global Pulse Weekly Report."

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

    # =====================================================================
    # MODEL 7: FINAL SYNTHESIS (Kimi K2 Instruct)
    # =====================================================================

    def generate_executive_summary(self, articles: list[Article], date_range: str) -> str:
        """Generate executive summary using Kimi K2's long context."""
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

        # Feed ALL article summaries to Kimi K2 (not just 15 headlines)
        article_summaries = "\n".join([
            f"- [{a.source}] {a.title}: {a.ai_summary or a.summary[:100] or 'No summary'}"
            for a in articles[:100]  # Top 100 by rank
        ])

        prompt = f"""You are writing the EXECUTIVE SUMMARY for "The Global Pulse" Weekly Economic Intelligence Report.

Date Range: {date_range}
Total Articles/Reports Analyzed: {len(articles)}
Organizations Covered: 39

Coverage by Category:
{category_summary}

ALL Article Summaries (ranked by importance):
{article_summaries}

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
- Use analogies for complex concepts
- If you don't have specific data, say "The detailed data is available in the full reports linked below"
- NEVER make up numbers or statistics
- Make it engaging - this goes to busy executives who need the essence quickly"""

        return self._safe_chat(
            model=NvidiaModels.SYNTHESIZER,
            prompt=prompt,
            fallback=f"This week's Global Pulse covers {len(articles)} articles from {len(by_category)} categories across {date_range}.",
            max_tokens=1024,
            temperature=0.4,
            credit_cost=3
        )

    def generate_top5_tldr(self, articles: list[Article]) -> str:
        """Generate TL;DR Top 5 section."""
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

        return self._safe_chat(
            model=NvidiaModels.DEEP_ANALYZER,
            prompt=prompt,
            fallback="\n".join([f"• [{a.source}] {a.title}" for a in top_5]),
            max_tokens=512,
            temperature=0.3
        )

    def generate_cross_source_synthesis(self, articles: list[Article]) -> str:
        """Generate cross-source synthesis using Kimi K2."""
        theme_articles = {}
        for article in articles:
            for theme in article.themes:
                if theme not in theme_articles:
                    theme_articles[theme] = []
                theme_articles[theme].append(article)

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

        return self._safe_chat(
            model=NvidiaModels.SYNTHESIZER,
            prompt=prompt,
            fallback=f"This week saw coverage from {len(set(a.source for a in articles))} organizations across {len(theme_articles)} themes.",
            max_tokens=512,
            temperature=0.3,
            credit_cost=2
        )

    def generate_theme_summary(self, articles: list[Article]) -> dict[str, str]:
        """Generate summaries for each major theme (keyword-based, no API)."""
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
        """Generate sentiment analysis using Kimi K2."""
        # Feed more articles for better sentiment reading
        article_data = [
            f"[{a.source}] {a.title}: {a.ai_summary or ''}"
            for a in articles[:50]
        ]

        prompt = f"""Analyze the overall economic sentiment from this week's coverage.

ARTICLES ANALYZED (top 50 by importance):
{chr(10).join(article_data)}

Provide a SENTIMENT ANALYSIS section (100-150 words) with:

**OVERALL SENTIMENT**: [Choose ONE: 🟢 BULLISH | 🟡 NEUTRAL | 🔴 BEARISH]

**SENTIMENT BREAKDOWN**:
- Growth Outlook: [Optimistic/Cautious/Pessimistic]
- Inflation Concerns: [Rising/Stable/Easing]
- Policy Direction: [Hawkish/Neutral/Dovish]
- Market Risk Appetite: [Risk-On/Neutral/Risk-Off]

**KEY DRIVERS**:
2-3 bullet points on what's driving the sentiment.

Be specific. Base conclusions ONLY on the articles provided. Don't guess."""

        return self._safe_chat(
            model=NvidiaModels.SYNTHESIZER,
            prompt=prompt,
            fallback="Sentiment analysis unavailable this week.",
            max_tokens=512,
            temperature=0.3,
            credit_cost=2
        )

    def generate_actionable_implications(self, articles: list[Article]) -> str:
        """Generate actionable implications using DeepSeek V3.1."""
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

        return self._safe_chat(
            model=NvidiaModels.DEEP_ANALYZER,
            prompt=prompt,
            fallback="Implications section unavailable this week.",
            max_tokens=768,
            temperature=0.3
        )

    def generate_geographic_summary(self, articles: list[Article]) -> dict:
        """Group articles by geographic region (keyword-based, no API)."""
        source_regions = {
            'Fed': 'Americas', 'NBER': 'Americas', 'Brookings': 'Americas', 'PIIE': 'Americas',
            'WSJ': 'Americas', 'Goldman Sachs': 'Americas', 'JP Morgan': 'Americas',
            'ECB': 'Europe', 'BoE': 'Europe', 'Bruegel': 'Europe', 'FT': 'Europe',
            'BoJ': 'Asia-Pacific', 'PBoC': 'Asia-Pacific', 'ADB': 'Asia-Pacific',
            'RBI': 'India', 'MoF India': 'India', 'MoSPI': 'India', 'NITI Aayog': 'India',
            'IMF': 'Global', 'World Bank': 'Global', 'OECD': 'Global', 'WTO': 'Global',
            'WEF': 'Global', 'BIS': 'Global', 'ILO': 'Global', 'UNCTAD': 'Global',
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

        for region in regions:
            regions[region]['sources'] = list(regions[region]['sources'])
            regions[region]['count'] = len(regions[region]['articles'])
            regions[region]['headlines'] = [a.title for a in regions[region]['articles'][:5]]

        return regions

    # =====================================================================
    # ECONOMIC INDICATORS (FRED API - no AI needed)
    # =====================================================================

    def fetch_key_economic_indicators(self) -> dict:
        """Fetch key economic indicators from free APIs."""
        indicators = {}
        try:
            fred_series = {
                'US_INFLATION': 'CPIAUCSL',
                'US_UNEMPLOYMENT': 'UNRATE',
                'US_GDP_GROWTH': 'A191RL1Q225SBEA',
                'FED_FUNDS_RATE': 'FEDFUNDS',
            }

            for name, series_id in fred_series.items():
                try:
                    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key=demo&file_type=json&limit=1&sort_order=desc"
                    response = http_requests.get(url, timeout=10)
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

            indicators['NOTES'] = "Data from FRED (Federal Reserve Economic Data)."
        except Exception as e:
            logger.error(f"Error fetching economic indicators: {e}")
            indicators['error'] = str(e)

        return indicators

    def generate_key_numbers_section(self, indicators: dict) -> str:
        """Generate a Key Numbers section."""
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

    # =====================================================================
    # DEEP PDF ANALYSIS (Models 2, 3, 6)
    # =====================================================================

    def deep_analyze_report(self, extracted_content, article) -> dict:
        """Deep analysis using DeepSeek V3.1 + Llama 4 Vision + OCDRNet."""
        from analyzers.pdf_processor import extract_key_statistics

        result = {
            'success': False,
            'summary': '',
            'detailed_analysis': '',
            'key_statistics': [],
            'chart_descriptions': [],
            'table_summaries': [],
            'key_quotes': [],
            'page_count': extracted_content.page_count
        }

        if not extracted_content.extraction_success:
            logger.warning(f"Cannot deep analyze - extraction failed: {extracted_content.error_message}")
            return result

        try:
            # 1. Extract key statistics
            result['key_statistics'] = extract_key_statistics(extracted_content.full_text)

            # 2. Summarize text chunks using DeepSeek V3.1
            chunk_summaries = []
            for i, chunk in enumerate(extracted_content.text_chunks[:5]):
                if self.quota_exhausted:
                    break
                summary = self._safe_chat(
                    model=NvidiaModels.DEEP_ANALYZER,
                    prompt=f"""Summarize this section (part {i+1}/{len(extracted_content.text_chunks)}) of an economic report.
Focus on: Key findings, data points, policy implications, market-moving information.

TEXT:
{chunk[:6000]}

Provide a concise summary (100-150 words):""",
                    fallback="",
                    max_tokens=256,
                    temperature=0.2
                )
                if summary:
                    chunk_summaries.append(summary)

            # 3. Synthesize into comprehensive analysis
            if chunk_summaries and not self.quota_exhausted:
                summaries_text = "\n\n".join([f"Section {i+1}: {s}" for i, s in enumerate(chunk_summaries)])
                stats_text = "\n".join([f"• {s}" for s in result['key_statistics'][:10]]) if result['key_statistics'] else "No specific statistics extracted."

                result['detailed_analysis'] = self._safe_chat(
                    model=NvidiaModels.DEEP_ANALYZER,
                    prompt=f"""Synthesize these section summaries into a comprehensive analysis for "{article.title}" from {article.source_full}.

SECTION SUMMARIES:
{summaries_text}

KEY STATISTICS:
{stats_text}

Write a "Major Findings & Analysis" covering:
1. THE NON-OBVIOUS TRUTHS - deeper insights beyond headlines
2. MACRO & MICRO INDICATORS - GDP, inflation, employment implications
3. POLICY IMPLICATIONS - government, central bank, regulatory impacts
4. WHY THIS MATTERS - plain-language explanation with analogies

Keep under 500 words. Use bullet points. Bold key numbers.""",
                    fallback="",
                    max_tokens=1024,
                    temperature=0.3,
                    credit_cost=2
                )

            # 4. Analyze charts using Llama 4 Maverick (Vision)
            for i, image_bytes in enumerate(extracted_content.images[:3]):
                if self.quota_exhausted:
                    break
                description = self._safe_vision_chat(
                    prompt=f"""This is a chart/graph from an economic report titled "{article.title}".
Describe in 2-3 sentences:
1. What type of chart is it?
2. What data does it show?
3. What is the key takeaway or trend?
Be specific about numbers, percentages, or trends you can identify.""",
                    image_bytes=image_bytes,
                    fallback=""
                )
                if description:
                    result['chart_descriptions'].append(description)

            # 5. Summarize tables
            for table in extracted_content.tables[:5]:
                table_summary = f"**Table (Page {table['page']}):**\n{table['markdown'][:500]}"
                result['table_summaries'].append(table_summary)

            # 6. Generate summary
            if result['detailed_analysis']:
                result['summary'] = self._safe_chat(
                    model=NvidiaModels.SUMMARIZER,
                    prompt=f"""Based on this analysis of "{article.title}" from {article.source}:

{result['detailed_analysis'][:2000]}

Write a single-sentence summary (max 150 characters) capturing the most important finding:""",
                    fallback=article.summary[:150] if article.summary else "Summary unavailable",
                    max_tokens=128,
                    temperature=0.2
                )

            result['success'] = True
            logger.info(f"Deep analysis complete: {len(chunk_summaries)} chunks, {len(result['chart_descriptions'])} charts")

        except Exception as e:
            logger.error(f"Deep analysis failed: {e}")
            result['success'] = False

        return result

    # =====================================================================
    # KEYWORD-BASED METHODS (No API calls)
    # =====================================================================

    def _categorize(self, article: Article) -> str:
        """Determine the category of the article."""
        title_lower = article.title.lower()
        summary_lower = (article.summary or '').lower()
        combined = f"{title_lower} {summary_lower}"

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
        major_types = ['report', 'working_paper', 'speech', 'data_release']
        if article.content_type in major_types:
            return True

        major_orgs = ['IMF', 'World Bank', 'RBI', 'OECD', 'WEF', 'BIS', 'McKinsey', 'Deloitte',
                      'BCG', 'PwC', 'Goldman Sachs', 'JP Morgan', 'Brookings', 'PIIE']
        if article.source in major_orgs:
            return True

        if article.title.lower():
            key_phrases = ['outlook', 'report', 'survey', 'forecast', 'index', 'review',
                          'economic survey', 'annual report', 'quarterly', 'bulletin']
            if any(phrase in article.title.lower() for phrase in key_phrases):
                return True

        if self._is_expert_opinion(article):
            return True

        return False

    def _is_expert_opinion(self, article: Article) -> bool:
        """Check if article is from a recognized authority."""
        notable_experts = [
            'paul krugman', 'joseph stiglitz', 'robert shiller', 'eugene fama',
            'richard thaler', 'angus deaton', 'jean tirole', 'bengt holmström',
            'abhijit banerjee', 'esther duflo', 'michael kremer',
            'gita gopinath', 'pierre-olivier gourinchas', 'carmen reinhart',
            'raghuram rajan', 'urjit patel', 'shaktikanta das',
            'janet yellen', 'jerome powell', 'christine lagarde', 'mark carney',
            'mario draghi', 'ben bernanke', 'alan greenspan',
            'nouriel roubini', 'mohamed el-erian', 'larry summers',
            'kenneth rogoff', 'dani rodrik', 'arvind subramanian',
            'martin wolf', 'gillian tett', 'rana foroohar'
        ]

        author_lower = (article.author or '').lower()
        title_lower = article.title.lower()
        content_lower = (article.summary or '').lower()

        for expert in notable_experts:
            if expert in author_lower or expert in title_lower or expert in content_lower:
                article.content_type = 'expert_opinion'
                return True

        opinion_indicators = ['opinion', 'op-ed', 'commentary', 'perspective', 'viewpoint', 'analysis by']
        is_opinion = any(ind in title_lower for ind in opinion_indicators)

        if is_opinion and any(org in article.source for org in ['FT', 'WSJ', 'Bloomberg', 'Reuters', 'Brookings', 'PIIE']):
            authority_titles = ['chief economist', 'former governor', 'nobel laureate',
                               'professor', 'dr.', 'director', 'chairman', 'president']
            if any(title in content_lower or title in author_lower for title in authority_titles):
                article.content_type = 'expert_opinion'
                return True

        return False

    def _calculate_importance(self, article: Article) -> int:
        """Calculate importance score (1-10) for an article."""
        score = 3

        critical_sources = ['Fed', 'ECB', 'RBI', 'IMF', 'World Bank', 'BoE', 'BoJ', 'PBoC']
        high_sources = ['OECD', 'WEF', 'BIS', 'McKinsey', 'Goldman Sachs', 'JP Morgan']

        if article.source in critical_sources:
            score += 3
        elif article.source in high_sources:
            score += 2

        if article.content_type in ['report', 'data_release', 'speech']:
            score += 2
        elif article.content_type in ['working_paper', 'expert_opinion']:
            score += 1

        title_lower = article.title.lower()
        critical_keywords = ['rate decision', 'fomc', 'mpc', 'gdp', 'inflation', 'recession',
                           'crisis', 'emergency', 'downgrade', 'upgrade', 'outlook']
        if any(kw in title_lower for kw in critical_keywords):
            score += 2

        return min(score, 10)

    def _get_importance_level(self, score: int) -> str:
        if score >= 8:
            return "Critical"
        elif score >= 5:
            return "Important"
        else:
            return "Standard"

    def _assign_themes(self, article: Article) -> list[str]:
        """Assign thematic tags to an article."""
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
