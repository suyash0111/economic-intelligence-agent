"""
NVIDIA NIM Multi-Model Analyzer - 6-Model Architecture for World-Class Economic Intelligence.

Models:
  1. Qwen 2.5 72B Instruct - Executive summaries & short analysis
  2. DeepSeek V3.1 Terminus - Deep analysis & reasoning
  3. Rerank QA Mistral - Article relevance ranking
  4. NV-Embed-V1 - Embeddings for dedup & clustering
  5. Kimi K2 Instruct - Long-context final synthesis

Fallback: Groq API (Llama 3.3 70B) when NVIDIA credits exhaust
Chart Analysis: Text-based interpretation (no vision model needed)
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
    SUMMARIZER = "qwen/qwen2.5-72b-instruct"
    DEEP_ANALYZER = "qwen/qwen2.5-72b-instruct"  # DeepSeek V3.x returns 404 on free tier
    RERANKER = "nvidia/nv-rerankqa-mistral-4b-v3"
    EMBEDDER = "nvidia/nv-embed-v1"
    SYNTHESIZER = "moonshotai/kimi-k2-instruct-0905"

    BASE_URL = "https://integrate.api.nvidia.com/v1"


class GroqModels:
    """Groq API — Fallback 1."""
    MODEL = "llama-3.3-70b-versatile"
    BASE_URL = "https://api.groq.com/openai/v1"


class CerebrasModels:
    """Cerebras API — Fallback 2 (fastest inference)."""
    MODEL = "llama-3.3-70b"
    BASE_URL = "https://api.cerebras.ai/v1"


class OpenRouterModels:
    """OpenRouter API — Fallback 3 (widest model selection)."""
    SUMMARIZER = "meta-llama/llama-3.3-70b-instruct:free"
    ANALYZER = "nousresearch/hermes-3-llama-3.1-405b:free"
    BASE_URL = "https://openrouter.ai/api/v1"


class NvidiaAnalyzer:
    """
    AI-powered content analyzer using NVIDIA NIM + 3-provider fallback chain.
    NVIDIA NIM → Groq → Cerebras → OpenRouter
    """

    def __init__(self):
        """Initialize the NVIDIA NIM analyzer with 3-provider fallback chain."""
        if not Settings.NVIDIA_API_KEY:
            raise ValueError("NVIDIA_API_KEY not set in environment")

        # Primary: NVIDIA NIM client
        self.client = OpenAI(
            base_url=NvidiaModels.BASE_URL,
            api_key=Settings.NVIDIA_API_KEY
        )

        # Build fallback chain: Groq → Cerebras → OpenRouter
        self.fallback_providers = []
        self.using_fallback = False
        self.active_fallback_name = None

        if Settings.GROQ_API_KEY:
            self.fallback_providers.append({
                'name': 'Groq',
                'client': OpenAI(base_url=GroqModels.BASE_URL, api_key=Settings.GROQ_API_KEY),
                'model': GroqModels.MODEL,
                'delay': 2.0,
                'calls': 0,
                'failed': False,
            })
            logger.info("  ✅ Fallback 1: Groq (Llama 3.3 70B)")

        if Settings.CEREBRAS_API_KEY:
            self.fallback_providers.append({
                'name': 'Cerebras',
                'client': OpenAI(base_url=CerebrasModels.BASE_URL, api_key=Settings.CEREBRAS_API_KEY),
                'model': CerebrasModels.MODEL,
                'delay': 1.0,  # Cerebras is very fast
                'calls': 0,
                'failed': False,
            })
            logger.info("  ✅ Fallback 2: Cerebras (Llama 3.3 70B)")

        if Settings.OPENROUTER_API_KEY:
            self.fallback_providers.append({
                'name': 'OpenRouter',
                'client': OpenAI(
                    base_url=OpenRouterModels.BASE_URL,
                    api_key=Settings.OPENROUTER_API_KEY,
                    default_headers={'HTTP-Referer': 'https://github.com/suyash0111/economic-intelligence-agent'}
                ),
                'model': OpenRouterModels.SUMMARIZER,
                'delay': 3.0,  # OpenRouter free has lower rate limits
                'calls': 0,
                'failed': False,
            })
            logger.info("  ✅ Fallback 3: OpenRouter (Hermes 405B / Llama 70B)")

        if not self.fallback_providers:
            logger.warning("  ⚠️ No fallback providers configured!")

        # Rate limiting
        self.requests_per_minute = 30
        self.request_count = 0
        self.last_reset = time.time()
        self.min_delay_between_requests = 2.0
        self.last_request_time = 0

        # Credit tracking
        self.total_api_calls = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.credits_estimate = 0
        self.fallback_calls = 0

        # Quota exhaustion detection
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        self.quota_exhausted = False

        fb_count = len(self.fallback_providers)
        logger.info(f"NVIDIA NIM Analyzer initialized (5 models + {fb_count} fallback providers)")
        logger.info(f"  🟢 Summarizer:  {NvidiaModels.SUMMARIZER}")
        logger.info(f"  🔵 Analyzer:    {NvidiaModels.DEEP_ANALYZER}")
        logger.info(f"  🟠 Reranker:    {NvidiaModels.RERANKER}")
        logger.info(f"  🧬 Embedder:    {NvidiaModels.EMBEDDER}")
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
        """
        Safely make a chat call with retry + 4-provider fallback chain.
        NVIDIA NIM → Groq → Cerebras → OpenRouter → fallback text
        """
        # Try NVIDIA NIM first
        if not self.quota_exhausted:
            for attempt in range(max_retries):
                try:
                    can_proceed = self._check_rate_limit()
                    if not can_proceed:
                        break  # Fall through to fallback chain

                    result = self._chat(model, prompt, max_tokens, temperature, system_prompt)
                    self._mark_success(credit_cost)
                    return result
                except Exception as e:
                    should_retry = self._handle_api_error(e)
                    if not should_retry or self.quota_exhausted:
                        break  # Fall through to fallback chain

        # Cascade through fallback providers
        if self.quota_exhausted or self.using_fallback:
            self.using_fallback = True
            result = self._fallback_chat(prompt, max_tokens, temperature)
            if result:
                return result

        return fallback

    def _fallback_chat(self, prompt: str, max_tokens: int = 1024,
                       temperature: float = 0.3) -> str:
        """
        Try each fallback provider in sequence until one succeeds.
        Groq → Cerebras → OpenRouter
        """
        for provider in self.fallback_providers:
            if provider['failed']:
                continue  # Skip providers that have permanently failed

            try:
                time.sleep(provider['delay'])

                response = provider['client'].chat.completions.create(
                    model=provider['model'],
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False
                )

                provider['calls'] += 1
                self.fallback_calls += 1
                self.active_fallback_name = provider['name']
                result = response.choices[0].message.content.strip()

                if self.fallback_calls % 10 == 0:
                    summary = ', '.join(f"{p['name']}:{p['calls']}" for p in self.fallback_providers if p['calls'] > 0)
                    logger.info(f"[FALLBACK] Active: {summary}")

                return result

            except Exception as e:
                error_str = str(e).lower()
                # Mark as permanently failed if auth error, otherwise just skip this call
                if '401' in error_str or '403' in error_str or 'auth' in error_str:
                    provider['failed'] = True
                    logger.warning(f"[FALLBACK] {provider['name']} permanently failed (auth): {e}")
                elif '429' in error_str or 'rate' in error_str:
                    logger.info(f"[FALLBACK] {provider['name']} rate limited, trying next...")
                else:
                    logger.warning(f"[FALLBACK] {provider['name']} failed: {e}")
                continue  # Try next provider

        logger.warning("[FALLBACK] All providers exhausted")
        return ""

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
                    "Content-Type": "application/json",
                }
                data = {
                    "model": NvidiaModels.RERANKER,
                    "query": {"text": query},
                    "passages": passages
                }

                response = http_requests.post(
                    f"{NvidiaModels.BASE_URL}/ranking",
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

    # Patterns that indicate non-economic content (navigation pages, HR, etc.)
    NON_ECONOMIC_PATTERNS = [
        'career', 'join us', 'join our team', 'returner programme', 'diversity and inclusion',
        'why you should join', 'speaker for your school', 'request a speaker',
        'using images of banknotes', 'damaged and contaminated', 'exchanging old banknotes',
        'counterfeit banknotes', 'note circulation scheme', 'advice for retailers',
        'scottish and northern ireland banknotes', 'wholesale cash supervision',
        'what is monetary policy?', 'benefits of price stability', 'scope of monetary policy',
        'transmission mechanism', 'medium-term orientation', 'two per cent inflation target',
        'economic, monetary and financial analysis', 'decisions, statements',
        'monetary policy strategy', 'asset purchase programmes',
        'research support programme', 'we value diversity',
        'cookie policy', 'privacy policy', 'terms of use', 'contact us',
        'subscribe', 'newsletter', 'about us', 'sitemap',
    ]

    def _is_economic_content(self, article: Article) -> bool:
        """Filter out non-economic content like HR pages, navigation links, etc."""
        title_lower = article.title.lower().strip()

        # Check against non-economic patterns
        for pattern in self.NON_ECONOMIC_PATTERNS:
            if pattern in title_lower:
                return False

        # Very short titles with no economic keywords are suspicious
        if len(title_lower) < 15:
            economic_words = ['rate', 'gdp', 'inflation', 'policy', 'growth', 'trade',
                            'bank', 'economic', 'financial', 'market', 'data', 'report']
            if not any(w in title_lower for w in economic_words):
                return False

        return True

    def analyze_article(self, article: Article) -> Article:
        """Analyze a single article and populate AI fields."""
        if self.quota_exhausted:
            return self._fallback_analysis(article)

        # Filter out non-economic content (no API calls wasted)
        if not self._is_economic_content(article):
            article.ai_summary = ""
            article.ai_analysis = ""
            article.ai_category = "Non-Economic"
            article.importance_score = 0
            article.importance_level = "Filtered"
            article.themes = []
            article.verification_status = "filtered"
            logger.debug(f"[FILTER] Skipped non-economic: {article.title[:60]}")
            return article

        try:
            # Generate 3-5 sentence summary using Mistral Small 3.1
            article.ai_summary = self._safe_chat(
                model=NvidiaModels.SUMMARIZER,
                prompt=self._summary_prompt(article),
                fallback=article.summary[:200] if article.summary else "Summary not available",
                max_tokens=512,
                temperature=0.2
            )

            # Full 4-section analysis for major items using DeepSeek V3.1
            if self._is_major_item(article) and not self.quota_exhausted:
                article.ai_analysis = self._safe_chat(
                    model=NvidiaModels.DEEP_ANALYZER,
                    prompt=self._analysis_prompt(article),
                    fallback="",
                    max_tokens=1024,
                    temperature=0.3,
                    credit_cost=1
                )
            # Short 2-paragraph analysis for all other economic articles
            elif not self.quota_exhausted:
                article.ai_analysis = self._safe_chat(
                    model=NvidiaModels.SUMMARIZER,
                    prompt=self._short_analysis_prompt(article),
                    fallback="",
                    max_tokens=512,
                    temperature=0.3
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
        """Analyze multiple articles efficiently, then apply multi-pass to top articles."""
        analyzed = []
        filtered_count = 0
        total = len(articles)

        for i, article in enumerate(articles):
            analyzed_article = self.analyze_article(article)
            if analyzed_article.verification_status == "filtered":
                filtered_count += 1
            analyzed.append(analyzed_article)

            if (i + 1) % batch_size == 0:
                logger.info(f"Analyzed {i + 1}/{total} articles "
                           f"(filtered: {filtered_count}, credits: ~{self.credits_estimate}, calls: {self.total_api_calls})")
                time.sleep(1)

        logger.info(f"Single-pass complete: {len(analyzed)} articles ({filtered_count} filtered), ~{self.credits_estimate} credits")

        # Multi-pass analysis for top 5 most important articles
        if not self.quota_exhausted or self.fallback_providers:
            analyzed = self._apply_multi_pass(analyzed)

        logger.info(f"Analysis complete: {len(analyzed)} articles, ~{self.credits_estimate} credits, {self.fallback_calls} fallback calls")
        return analyzed

    def _apply_multi_pass(self, articles: list[Article], top_n: int = 5) -> list[Article]:
        """
        Apply 3-pass analysis to the top N articles by importance score.
        Pass 1: Extract key facts & numbers (Qwen 72B)
        Pass 2: Cross-reference with other articles (DeepSeek V3.1)
        Pass 3: Generate strategic assessment (Kimi K2)
        """
        # Sort by importance and select top N that have analysis content
        candidates = [
            a for a in articles
            if a.ai_analysis and a.verification_status not in ('filtered', 'unverified')
            and a.importance_score >= 6
        ]
        candidates.sort(key=lambda a: a.importance_score, reverse=True)
        top_articles = candidates[:top_n]

        if not top_articles:
            return articles

        logger.info(f"[MULTI-PASS] Enhancing top {len(top_articles)} articles with 3-pass analysis...")

        # Collect all summaries for cross-referencing context
        all_summaries = "\n".join([
            f"- {a.source}: {a.title} — {(a.ai_summary or '')[:150]}"
            for a in articles
            if a.ai_summary and a.verification_status != 'filtered'
        ][:20])  # Top 20 summaries as context

        for idx, article in enumerate(top_articles):
            logger.info(f"[MULTI-PASS] ({idx+1}/{len(top_articles)}) {article.title[:50]}...")

            # Get article's full text for deeper analysis
            full_text = article.content_preview or article.summary or ''

            # === PASS 1: FACT EXTRACTION (Qwen 72B) ===
            facts = self._safe_chat(
                model=NvidiaModels.SUMMARIZER,
                prompt=f"""Extract every concrete fact, number, date, and data point from this article.

TITLE: {article.title}
SOURCE: {article.source_full}
TEXT: {full_text[:3000]}
EXISTING ANALYSIS: {(article.ai_analysis or '')[:1000]}

List every factual claim as a bullet point. Include:
- Specific numbers (percentages, dollar amounts, growth rates)
- Named entities (people, organizations, countries)
- Dates and timelines
- Policy decisions or announcements
- Comparisons with previous periods

Do NOT editorialize. Only state facts found in the text.
Write in plain text without markdown formatting.""",
                fallback="",
                max_tokens=512,
                temperature=0.1
            )

            if not facts:
                continue

            # === PASS 2: CROSS-REFERENCE (DeepSeek V3.1) ===
            cross_ref = self._safe_chat(
                model=NvidiaModels.DEEP_ANALYZER,
                prompt=f"""You are a senior economic analyst cross-referencing intelligence reports.

ARTICLE BEING ANALYZED:
Title: {article.title}
Source: {article.source_full}
Facts extracted: {facts[:1500]}

OTHER REPORTS THIS WEEK:
{all_summaries}

Cross-reference this article with the other reports above and answer:
1. CORROBORATION: Which other reports support or confirm the findings in this article?
2. CONTRADICTIONS: Do any other reports present conflicting data?
3. BLIND SPOTS: What important context or data is missing from this article that other reports cover?
4. INTERCONNECTIONS: How does this article connect to broader economic trends visible across multiple reports?

Write 3-4 paragraphs. Be specific — name the sources and data points.
Do NOT use markdown formatting. Write in plain professional English.""",
                fallback="",
                max_tokens=768,
                temperature=0.3,
                credit_cost=2
            )

            # === PASS 3: STRATEGIC ASSESSMENT (Kimi K2 or DeepSeek) ===
            assessment = self._safe_chat(
                model=NvidiaModels.SYNTHESIZER if not self.quota_exhausted else NvidiaModels.DEEP_ANALYZER,
                prompt=f"""You are the Chief Economist writing a strategic assessment for institutional investors.

ARTICLE: {article.title} ({article.source_full})

VERIFIED FACTS:
{facts[:1000]}

CROSS-REFERENCE ANALYSIS:
{(cross_ref or 'No cross-reference available')[:1000]}

Write a strategic assessment covering:
1. INVESTMENT IMPLICATIONS: What does this mean for asset allocation, sectors, and risk?
2. POLICY TRAJECTORY: Where is this heading in the next 3-6 months?
3. SECOND-ORDER EFFECTS: What indirect consequences will ripple through the economy?
4. ACTIONABLE INTELLIGENCE: What should decision-makers do differently based on this?

Write 3-4 concise paragraphs. This is for sophisticated readers — be specific and opinionated.
Do NOT use markdown formatting. Write in plain professional English.""",
                fallback="",
                max_tokens=768,
                temperature=0.4,
                credit_cost=2
            )

            # Combine all passes into enhanced analysis
            if cross_ref or assessment:
                enhanced = article.ai_analysis or ""
                if cross_ref:
                    enhanced += "\n\nCROSS-SOURCE INTELLIGENCE\n" + cross_ref
                if assessment:
                    enhanced += "\n\nSTRATEGIC ASSESSMENT\n" + assessment

                article.ai_analysis = enhanced
                article.verification_status = "deep_verified"
                logger.info(f"[MULTI-PASS] Enhanced: {article.title[:40]}... (+{len(cross_ref or '')+len(assessment or '')} chars)")

        return articles

    def _fallback_analysis(self, article: Article) -> Article:
        """Provide fallback analysis when credits are exhausted."""
        article.ai_summary = article.summary[:200] if article.summary else "AI analysis unavailable (credits exhausted)"
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
        return f"""Write an executive summary (3-5 sentences, 150-200 words) of this economic/financial content.

Cover these points in your summary:
1. WHAT: The main announcement, finding, or development
2. WHY IT MATTERS: The significance for markets, policy, or the broader economy
3. KEY NUMBERS: Any specific data points, percentages, or figures mentioned
4. IMPLICATIONS: What this means going forward

Title: {article.title}
Source: {article.source_full}
Category: {article.category}

Content/Description:
{article.summary or article.content_preview or 'No content available'}

Write a professional but accessible summary. Do NOT use markdown formatting (no **, no ##, no bullet points).
Do NOT make up numbers — only include data explicitly stated in the content.
Provide ONLY the summary paragraph, no headers or labels."""

    def _short_analysis_prompt(self, article: Article) -> str:
        """Shorter analysis for non-major articles (2 paragraphs instead of 4 sections)."""
        return f"""You are an economic intelligence analyst. Write a brief analysis (2 paragraphs, 100-150 words total) of this article.

Title: {article.title}
Source: {article.source_full}
Category: {article.category}
Content: {article.summary or article.content_preview or 'No content available'}

Paragraph 1: What is the key development and what does it signal for the economy?
Paragraph 2: What should investors, businesses, or policymakers watch for as a result?

CRITICAL: Do NOT use markdown formatting (no **, ##, ####, or bullet dashes).
Do NOT invent numbers. Write in plain professional English."""

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

YOUR TASK: Provide a comprehensive "Major Findings & Analysis" block following this EXACT structure.
IMPORTANT: Do NOT use markdown hash symbols (##, ###, ####). Use plain text headers like "1. THE NON-OBVIOUS TRUTHS" without any # or ** markers.

1. THE NON-OBVIOUS TRUTHS
Don't just report headlines. Extract the underlying shifts, hidden patterns, or counterintuitive findings that a casual reader would miss. What does the data REALLY tell us beyond the press release?

2. MACRO AND MICRO INDICATORS
Macroeconomic: GDP growth, inflation, employment, trade balance implications.
Microeconomic: Industry-specific impacts, consumer behavior, business implications.

3. POLICY IMPLICATIONS
What does this mean for:
- Government policy (fiscal, monetary, regulatory)
- Central bank actions
- Industry regulations

4. WHY THIS MATTERS
Explain the real-world impact in plain terms. Use clear analogies for complex concepts.
Example: "Fiscal deficit is like the nation's credit card balance."

CRITICAL RULES:
- Do NOT use markdown formatting: no ** for bold, no ## for headers, no #### anywhere
- Use plain text with numbered sections (1. 2. 3. 4.) and dashes for sub-points
- Use "Professional-Layman Mix" tone: Be precise with data but explain jargon simply
- If specific data points are NOT in the content, say "The full report contains detailed data" - NEVER guess or make up numbers
- Keep total response under 500 words but be substantive, not generic"""

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
        """Generate 'This Week at a Glance' section using WEF BLUF format."""
        sorted_articles = sorted(articles, key=lambda x: x.importance_score, reverse=True)
        top_7 = sorted_articles[:7]

        if not top_7:
            return "No critical developments this week."

        headlines = "\n".join([
            f"{i+1}. [{a.source}] {a.title} — {(a.ai_summary or '')[:150]}"
            for i, a in enumerate(top_7)
        ])

        prompt = f"""Create a "THIS WEEK AT A GLANCE" briefing for senior executives.

The 7 most important developments (ranked by importance):
{headlines}

Write 5-7 bullet points. Each bullet MUST follow this EXACT format:
[BOLD ACTION HEADLINE]. [1-2 sentences of context with specific data if available].

Example format:
Fed holds rates despite inflation surprise. The March CPI print of 3.2% exceeded the expected 2.9%, but Powell's post-meeting statement signals patience through Q2.

Rules:
- The headline should be a SHORT declarative statement (5-8 words)
- Follow it with 1-2 sentences providing context, numbers, and implications
- Be specific — include percentages, names, organizations, dates
- Do NOT use markdown formatting, emojis, asterisks, or hashtags
- Do NOT use bullet symbols — just number them 1, 2, 3...
- Write in plain professional English"""

        return self._safe_chat(
            model=NvidiaModels.DEEP_ANALYZER,
            prompt=prompt,
            fallback="\n".join([f"- [{a.source}] {a.title}" for a in top_7]),
            max_tokens=768,
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

        result = {
            'success': False,
            'summary': '',
            'detailed_analysis': '',
            'key_statistics': [],
            'chart_descriptions': [],
            'chart_images': [],          # Store actual image bytes for Word embedding
            'table_summaries': [],
            'table_data': [],            # Store structured table data for Word tables
            'key_quotes': [],
            'page_count': extracted_content.page_count
        }

        if not extracted_content.extraction_success:
            logger.warning(f"Cannot deep analyze - extraction failed: {extracted_content.error_message}")
            return result

        try:
            # 1. AI-powered statistics extraction (replaces broken regex)
            if not self.quota_exhausted:
                stats_text = self._safe_chat(
                    model=NvidiaModels.SUMMARIZER,
                    prompt=f"""Extract the 5-8 most important statistics and data points from this economic report text.
For each statistic, provide: the metric name, the value, and one sentence of context.

Format each as a complete sentence like:
- GDP growth is projected at 2.1% for 2026, down from 2.8% in 2025.
- Inflation expectations rose to 3.2%, above the ECB's 2% target.

TEXT (first 4000 chars):
{extracted_content.full_text[:4000]}

IMPORTANT: Only extract statistics that are EXPLICITLY stated in the text.
Do NOT include chart axis labels, page numbers, or OCR artifacts.
If no clear statistics are found, write "No specific statistics available in the extracted text.""""",
                    fallback="",
                    max_tokens=512,
                    temperature=0.1
                )
                if stats_text:
                    # Parse the AI response into clean stat lines
                    for line in stats_text.split('\n'):
                        line = line.strip().lstrip('- ')
                        if line and len(line) > 20 and not line.startswith('No specific'):
                            result['key_statistics'].append(line)

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

Provide a concise summary (150-200 words). Do NOT use markdown formatting (no **, ##, or ####).
Write in plain professional English with clear sentences:""",
                    fallback="",
                    max_tokens=384,
                    temperature=0.2
                )
                if summary:
                    chunk_summaries.append(summary)

            # 3. Synthesize into comprehensive analysis
            if chunk_summaries and not self.quota_exhausted:
                summaries_text = "\n\n".join([f"Section {i+1}: {s}" for i, s in enumerate(chunk_summaries)])
                stats_bullets = "\n".join([f"- {s}" for s in result['key_statistics'][:8]]) if result['key_statistics'] else "No specific statistics extracted."

                result['detailed_analysis'] = self._safe_chat(
                    model=NvidiaModels.DEEP_ANALYZER,
                    prompt=f"""Synthesize these section summaries into a comprehensive analysis for "{article.title}" from {article.source_full}.

SECTION SUMMARIES:
{summaries_text}

KEY STATISTICS:
{stats_bullets}

Write a "Major Findings and Analysis" covering:
1. THE NON-OBVIOUS TRUTHS - deeper insights beyond headlines
2. MACRO AND MICRO INDICATORS - GDP, inflation, employment implications
3. POLICY IMPLICATIONS - government, central bank, regulatory impacts
4. WHY THIS MATTERS - plain-language explanation with analogies

CRITICAL FORMATTING RULES:
- Do NOT use markdown: no ** for bold, no ## or ### or #### for headers
- Use plain numbered headers like "1. THE NON-OBVIOUS TRUTHS" on their own line
- Use dashes (-) for sub-points
- Keep under 500 words but be substantive
- Write in plain professional English""",
                    fallback="",
                    max_tokens=1024,
                    temperature=0.3,
                    credit_cost=2
                )

            # 4. Text-based chart analysis (replaces broken vision model)
            #    Uses surrounding text + table data to describe charts
            #    Still store images for Word embedding
            if extracted_content.images and not self.quota_exhausted:
                # Store images for Word doc (up to 3)
                for img in extracted_content.images[:3]:
                    result['chart_images'].append(img)

                # Generate text-based chart descriptions from the report data
                tables_context = ""
                for td in result['table_data'][:3]:
                    headers = ', '.join(str(h) for h in td.get('headers', [])[:6] if h)
                    sample_row = ', '.join(str(c) for c in td.get('rows', [[]])[0][:6] if c) if td.get('rows') else ''
                    tables_context += f"\nTable (page {td['page']}): Columns: {headers}. Sample row: {sample_row}"

                stats_list = '\n'.join('- ' + s for s in result['key_statistics'][:6]) if result['key_statistics'] else 'No statistics extracted'
                insufficient_msg = 'Insufficient data to describe report visualizations.'

                chart_analysis = self._safe_chat(
                    model=NvidiaModels.DEEP_ANALYZER,
                    prompt=f"""This economic report "{article.title}" from {article.source_full} contains {len(extracted_content.images)} images/charts and {len(extracted_content.tables)} data tables.

Based on the report text and table data below, describe what charts and visualizations are likely included in this report.
For each chart (up to 3), describe:
1. What type of chart it likely is (bar, line, trend, comparison)
2. What data it shows based on the statistics and tables
3. The key trend or takeaway

KEY STATISTICS FROM REPORT:
{stats_list}

TABLE DATA:{tables_context if tables_context else ' No tables extracted'}

REPORT TEXT (first 2000 chars):
{extracted_content.full_text[:2000]}

Write 1-3 chart descriptions as separate paragraphs. Each should be 2-3 sentences.
Do NOT use markdown formatting. Write in plain professional English.
If there is not enough data to describe charts, write: {insufficient_msg}""",
                    fallback="",
                    max_tokens=512,
                    temperature=0.2
                )
                if chart_analysis and 'insufficient' not in chart_analysis.lower():
                    # Split into separate descriptions
                    for para in chart_analysis.split('\n\n'):
                        para = para.strip()
                        if len(para) > 30:
                            result['chart_descriptions'].append(para)

            # 5. Store structured table data (headers + rows) for proper Word rendering
            for table in extracted_content.tables[:5]:
                result['table_data'].append({
                    'page': table['page'],
                    'headers': table['headers'],
                    'rows': table['rows'][:15],  # Limit rows
                })
                # Also store a text summary for reference
                result['table_summaries'].append(
                    f"Table from page {table['page']}: {len(table['rows'])} rows, columns: {', '.join(str(h) for h in table['headers'][:6] if h)}"
                )

            # 6. Generate 3-5 sentence summary of the full report
            if result['detailed_analysis']:
                result['summary'] = self._safe_chat(
                    model=NvidiaModels.SUMMARIZER,
                    prompt=f"""Based on this analysis of "{article.title}" from {article.source}:

{result['detailed_analysis'][:2000]}

Write a 3-5 sentence executive summary (150-200 words) covering:
1. The main finding
2. Why it matters
3. Key data points
4. What to watch for

Do NOT use markdown formatting. Write in plain professional English.""",
                    fallback=article.summary[:200] if article.summary else "Summary unavailable",
                    max_tokens=384,
                    temperature=0.2
                )

            result['success'] = True
            logger.info(f"Deep analysis complete: {len(chunk_summaries)} chunks, "
                       f"{len(result['chart_descriptions'])} charts, {len(result['table_data'])} tables, "
                       f"{len(result['key_statistics'])} stats")

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
        """Determine if an article is major enough for detailed 4-section analysis."""
        major_types = ['report', 'working_paper', 'speech', 'data_release']
        if article.content_type in major_types:
            return True

        # Include ALL central banks + major organizations
        major_orgs = ['Fed', 'ECB', 'BoE', 'BoJ', 'PBoC', 'RBI',
                      'IMF', 'World Bank', 'OECD', 'WEF', 'BIS', 'ADB',
                      'McKinsey', 'Deloitte', 'BCG', 'PwC', 'Goldman Sachs', 'JP Morgan',
                      'Brookings', 'PIIE', 'NBER', 'Oxford Economics', 'Capital Economics',
                      "Moody's", 'Fitch', 'S&P Ratings', 'S&P Global',
                      'MoF India', 'NITI Aayog', 'MoSPI']
        if article.source in major_orgs:
            return True

        title_lower = article.title.lower()
        key_phrases = ['outlook', 'report', 'survey', 'forecast', 'index', 'review',
                      'economic survey', 'annual report', 'quarterly', 'bulletin',
                      'press conference', 'statement', 'assessment', 'monitor']
        if any(phrase in title_lower for phrase in key_phrases):
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

    # =====================================================================
    # NEW SYNTHESIS: FORWARD WATCHLIST (Goldman Sachs-inspired)
    # =====================================================================

    def generate_forward_watchlist(self, articles: list, date_range: str) -> str:
        """Generate a Forward Watchlist section — what to monitor next week."""
        article_context = "\n".join([
            f"- [{a.source}] {a.title}: {(a.ai_summary or '')[:100]}"
            for a in sorted(articles, key=lambda x: x.importance_score, reverse=True)[:15]
        ])

        prompt = f"""Based on this week's economic intelligence ({date_range}), create a FORWARD WATCHLIST for the coming week.

This week's top intelligence:
{article_context}

Write three sub-sections:

KEY EVENTS NEXT WEEK
List 5-7 specific events to watch (central bank meetings, data releases, political events, earnings). Include dates if known.

TRIPWIRES
Write 3 conditional scenarios in this format: "If [specific event/data point], then [likely consequence]."

DATA TO WATCH
List 4-5 specific economic indicators that would confirm or invalidate this week's analysis.

Rules:
- Be specific — name dates, organizations, data series
- Do NOT use markdown formatting (no asterisks, hashtags, etc.)
- Write in plain professional English
- Keep it concise — maximum 400 words total"""

        return self._safe_chat(
            model=NvidiaModels.SYNTHESIZER,
            prompt=prompt,
            fallback="Forward watchlist unavailable.",
            max_tokens=768,
            temperature=0.3,
            credit_cost=2
        )

    # =====================================================================
    # NEW SYNTHESIS: RISK ASSESSMENT (WEF Global Risks-inspired)
    # =====================================================================

    def generate_risk_assessment(self, articles: list) -> str:
        """Generate a risk assessment with radar table and narrative."""
        article_context = "\n".join([
            f"- [{a.source}] {a.title}: {(a.ai_summary or '')[:120]}"
            for a in sorted(articles, key=lambda x: x.importance_score, reverse=True)[:20]
        ])

        prompt = f"""You are a Chief Risk Officer writing a weekly risk assessment for institutional investors.

Based on this week's intelligence:
{article_context}

Write a risk assessment with these parts:

OVERALL ASSESSMENT
One sentence: the overall risk posture this week (e.g., "Cautiously optimistic with elevated tail risks from trade policy uncertainty").

RISK RADAR
List the top 6-8 risks in this format:
[Risk name] | [Severity: Low/Moderate/Elevated/High/Critical] | [Trend: Rising/Stable/Declining] | [Timeframe: Immediate/Short-term/Medium-term/Structural]

NARRATIVE
2-3 paragraphs explaining why the risk landscape shifted this week compared to recent trends. Name specific events and data points.

Rules:
- Be specific and opinionated — this is for sophisticated investors
- Do NOT use markdown formatting (no asterisks, hashtags, etc.)
- Use pipe separators (|) for the risk radar table
- Write in plain professional English"""

        return self._safe_chat(
            model=NvidiaModels.SYNTHESIZER,
            prompt=prompt,
            fallback="Risk assessment unavailable.",
            max_tokens=1024,
            temperature=0.3,
            credit_cost=2
        )
