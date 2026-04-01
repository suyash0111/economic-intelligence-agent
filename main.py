#!/usr/bin/env python3
"""
Economic Intelligence Agent - Main Orchestration Script

Powered by NVIDIA NIM 7-Model Architecture:
  1. Mistral Small 3.1 - Quick article summaries
  2. DeepSeek V3.1 Terminus - Deep analysis & reasoning
  3. Llama 4 Maverick - Vision/chart analysis
  4. Rerank QA Mistral - Article relevance ranking
  5. NV-Embed-V1 - Embeddings for dedup & clustering
  6. OCDRNet - OCR for scanned PDFs
  7. Kimi K2 Instruct - Long-context final synthesis

Usage:
    python main.py                    # Full run with email delivery
    python main.py --dry-run          # Generate reports without email
    python main.py --test-email       # Test email configuration
    python main.py --orgs IMF,RBI     # Only specific organizations
    python main.py --limit 5          # Limit to 5 organizations
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings
from collectors.collector_manager import CollectorManager
from analyzers.nvidia_analyzer import NvidiaAnalyzer
from generators.document_generator import DocumentGenerator
from generators.excel_generator import ExcelGenerator
from delivery.email_sender import EmailSender

# Set up logging with UTF-8 encoding for Windows compatibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(stream=sys.stdout),
        logging.FileHandler(Settings.BASE_DIR / 'agent.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def get_date_range() -> str:
    """Get the date range string for the report."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=Settings.LOOKBACK_DAYS)
    return f"{start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}"


def run_agent(
    dry_run: bool = False,
    specific_orgs: list[str] = None,
    limit_orgs: int = None
) -> bool:
    """
    Run the economic intelligence agent.

    Args:
        dry_run: If True, generate reports but don't send email
        specific_orgs: List of specific organization short names to process
        limit_orgs: Limit to N organizations (for testing)

    Returns:
        True if successful, False otherwise
    """
    logger.info("=" * 60)
    logger.info("Economic Intelligence Agent Starting")
    logger.info("Powered by NVIDIA NIM 7-Model Architecture")
    logger.info("=" * 60)

    date_range = get_date_range()
    logger.info(f"Report period: {date_range}")

    # Validate settings
    missing = Settings.validate()
    if missing and not dry_run:
        logger.error(f"Missing required settings: {', '.join(missing)}")
        logger.error("Please configure these in your .env file")
        return False

    try:
        # Step 1: Collect articles
        logger.info("\n[STEP 1] Collecting articles from organizations...")
        collector = CollectorManager(lookback_days=Settings.LOOKBACK_DAYS)

        # Apply limits if specified
        orgs_to_use = specific_orgs
        if limit_orgs and not specific_orgs:
            all_orgs = Settings.load_organizations()
            orgs_to_use = [org['short_name'] for org in all_orgs[:limit_orgs]]

        articles_by_org = collector.collect_all(max_workers=5, specific_orgs=orgs_to_use)

        # Get flat list of all articles
        all_articles = collector.get_all_articles_flat(articles_by_org)

        if not all_articles:
            logger.warning("No articles collected. Check your internet connection and organization configurations.")
            return False

        logger.info(f"[OK] Collected {len(all_articles)} articles from {len(articles_by_org)} organizations")

        # Step 2: AI Analysis with NVIDIA NIM
        logger.info("\n[STEP 2] AI Analysis with NVIDIA NIM 7-Model Engine...")

        tldr_top5 = ""
        cross_source = ""
        theme_summary = {}
        sentiment = ""
        implications = ""
        geographic = {}
        key_numbers = ""
        executive_summary = ""
        analyzed_articles = all_articles

        # Check for NVIDIA API key
        if not Settings.NVIDIA_API_KEY:
            logger.warning("[WARNING] NVIDIA_API_KEY not set - skipping AI analysis")
            executive_summary = f"Weekly economic intelligence covering {len(all_articles)} articles from {len(articles_by_org)} organizations."
        else:
            logger.info("[NVIDIA] Initializing 7-model architecture...")
            try:
                analyzer = NvidiaAnalyzer()

                # ============================================================
                # STEP 2a: FETCH ECONOMIC INDICATORS (FRED API - no AI)
                # ============================================================
                logger.info("[NVIDIA] Fetching key economic indicators...")
                indicators = analyzer.fetch_key_economic_indicators()
                key_numbers = analyzer.generate_key_numbers_section(indicators)
                logger.info("[OK] Fetched economic indicators")

                # ============================================================
                # STEP 2b: SMART DEDUPLICATION (Model 5: NV-Embed-V1)
                # ============================================================
                logger.info(f"[NVIDIA] 🧬 Deduplicating {len(all_articles)} articles with NV-Embed-V1...")
                deduplicated_articles = analyzer.deduplicate_articles(all_articles)
                logger.info(f"[OK] Deduplicated: {len(all_articles)} → {len(deduplicated_articles)} unique articles")

                # ============================================================
                # STEP 2c: AI RELEVANCE RANKING (Model 4: Rerank-QA-Mistral)
                # ============================================================
                logger.info(f"[NVIDIA] 🟠 Ranking {len(deduplicated_articles)} articles by economic relevance...")
                ranked_articles = analyzer.rank_articles(deduplicated_articles)
                logger.info("[OK] Articles ranked by economic relevance")

                # ============================================================
                # STEP 2d: ARTICLE ANALYSIS (Models 1 & 2: Mistral Small + DeepSeek)
                # ============================================================
                logger.info(f"[NVIDIA] 🟢🔵 Analyzing {len(ranked_articles)} articles...")
                logger.info("[NVIDIA]   🟢 Mistral Small 3.1 → quick summaries")
                logger.info("[NVIDIA]   🔵 DeepSeek V3.1 → deep analysis (major reports)")
                analyzed_articles = analyzer.analyze_batch(ranked_articles)

                if analyzer.quota_exhausted:
                    logger.warning("[NVIDIA] Credits exhausted during article analysis")
                    logger.info(f"[NVIDIA] Success: {analyzer.successful_requests}, Failed: {analyzer.failed_requests}")
                else:
                    logger.info(f"[NVIDIA] Article analysis complete: {analyzer.successful_requests} successful")

                # ============================================================
                # STEP 2e: DEEP PDF ANALYSIS (Models 2, 3, 6)
                # ============================================================
                if not analyzer.quota_exhausted:
                    from analyzers.pdf_processor import PDFProcessor

                    pdf_processor = PDFProcessor()
                    deep_analyzed_count = 0

                    major_articles = [a for a in analyzed_articles if pdf_processor.should_deep_analyze(a)]
                    logger.info(f"[DEEP ANALYSIS] Found {len(major_articles)} major reports for deep PDF analysis")
                    logger.info("[NVIDIA]   🔵 DeepSeek V3.1 → PDF text analysis")
                    logger.info("[NVIDIA]   🟣 Llama 4 Maverick → chart/image vision")
                    logger.info("[NVIDIA]   🔴 OCDRNet → OCR for scanned PDFs")

                    for i, article in enumerate(major_articles):
                        if analyzer.quota_exhausted:
                            logger.warning(f"[DEEP ANALYSIS] Stopping - credits exhausted after {deep_analyzed_count} reports")
                            break

                        pdf_path = pdf_processor.download_pdf(article.url)

                        if pdf_path:
                            logger.info(f"[DEEP ANALYSIS] Processing {i+1}/{len(major_articles)}: {article.title[:50]}...")

                            extracted = pdf_processor.extract_content(pdf_path)

                            if extracted.extraction_success:
                                deep_result = analyzer.deep_analyze_report(extracted, article)

                                if deep_result['success']:
                                    article.ai_summary = deep_result['summary'] or article.ai_summary
                                    article.ai_analysis = deep_result['detailed_analysis'] or article.ai_analysis
                                    article.deep_analysis = deep_result
                                    article.verification_status = "deep_verified"
                                    deep_analyzed_count += 1

                                    logger.info(f"[DEEP ANALYSIS] Complete: {extracted.page_count} pages, "
                                              f"{len(deep_result['chart_descriptions'])} charts, "
                                              f"{len(deep_result['table_summaries'])} tables")

                        if (i + 1) % 10 == 0:
                            logger.info(f"[DEEP ANALYSIS] Progress: {i+1}/{len(major_articles)}")

                    pdf_processor.cleanup()
                    stats = pdf_processor.get_stats()
                    logger.info(f"[DEEP ANALYSIS] Complete: {deep_analyzed_count} reports deep-analyzed, "
                              f"{stats['downloaded']} downloaded, {stats['skipped']} skipped")

                # ============================================================
                # STEP 2f: FINAL SYNTHESIS (Model 7: Kimi K2 Instruct)
                # ============================================================
                logger.info("[NVIDIA] 🟡 Generating final synthesis with Kimi K2 Instruct (long-context)...")

                executive_summary = analyzer.generate_executive_summary(analyzed_articles, date_range)
                logger.info("[OK] Generated executive summary")

                tldr_top5 = analyzer.generate_top5_tldr(analyzed_articles)
                logger.info("[OK] Generated TL;DR Top 5")

                cross_source = analyzer.generate_cross_source_synthesis(analyzed_articles)
                logger.info("[OK] Generated cross-source synthesis")

                theme_summary = analyzer.generate_theme_summary(analyzed_articles)
                logger.info("[OK] Generated theme summary")

                sentiment = analyzer.generate_sentiment_analysis(analyzed_articles)
                logger.info("[OK] Generated sentiment analysis")

                implications = analyzer.generate_actionable_implications(analyzed_articles)
                logger.info("[OK] Generated actionable implications")

                geographic = analyzer.generate_geographic_summary(analyzed_articles)
                logger.info("[OK] Generated geographic breakdown")

                # Final status
                logger.info(f"[NVIDIA] ═══ FINAL STATUS ═══")
                logger.info(f"[NVIDIA] Total API calls: {analyzer.total_api_calls}")
                logger.info(f"[NVIDIA] Successful: {analyzer.successful_requests}")
                logger.info(f"[NVIDIA] Failed: {analyzer.failed_requests}")
                logger.info(f"[NVIDIA] Estimated credits used: ~{analyzer.credits_estimate}")

                if analyzer.quota_exhausted:
                    logger.warning("[NVIDIA] Some analysis may be partial due to credit limits")

            except Exception as e:
                logger.error(f"[NVIDIA] Error during analysis: {e}")
                import traceback
                traceback.print_exc()
                executive_summary = f"Weekly economic intelligence covering {len(all_articles)} articles from {len(articles_by_org)} organizations."

        # Update articles_by_org with analyzed versions
        for org_name in articles_by_org:
            articles_by_org[org_name] = [
                a for a in analyzed_articles if a.source == org_name
            ]

        # Step 3: Generate reports
        logger.info("\n[STEP 3] Generating reports...")

        Settings.ensure_output_dir()

        doc_generator = DocumentGenerator()
        doc_path = doc_generator.generate(
            articles_by_org=articles_by_org,
            executive_summary=executive_summary,
            date_range=date_range,
            tldr_top5=tldr_top5,
            cross_source_synthesis=cross_source,
            theme_summary=theme_summary,
            sentiment_analysis=sentiment,
            actionable_implications=implications,
            geographic_summary=geographic,
            key_numbers=key_numbers
        )
        logger.info(f"[OK] Word document: {doc_path}")

        excel_generator = ExcelGenerator()
        excel_path = excel_generator.generate(
            articles=analyzed_articles,
            date_range=date_range
        )
        logger.info(f"[OK] Excel spreadsheet: {excel_path}")

        # Step 4: Send email
        if not dry_run:
            logger.info("\n[STEP 4] Sending email...")

            email_sender = EmailSender()
            success = email_sender.send_weekly_report(
                date_range=date_range,
                total_articles=len(analyzed_articles),
                executive_summary=executive_summary,
                doc_path=doc_path,
                excel_path=excel_path,
                tldr_top5=tldr_top5,
                sentiment=sentiment
            )

            if success:
                logger.info("[OK] Email sent successfully!")
            else:
                logger.error("[ERROR] Failed to send email")
                return False
        else:
            logger.info("\n[STEP 4] Skipped (dry run mode)")
            logger.info(f"Reports saved to: {Settings.OUTPUT_DIR}")

        logger.info("\n" + "=" * 60)
        logger.info("[SUCCESS] Economic Intelligence Agent completed successfully!")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.exception(f"Agent failed with error: {e}")
        return False


def test_email():
    """Test email configuration."""
    logger.info("Testing email configuration...")

    missing = Settings.validate()
    if missing:
        logger.error(f"Missing settings: {', '.join(missing)}")
        return False

    sender = EmailSender()
    if sender.test_connection():
        logger.info("[OK] Email configuration is correct!")

        success = sender.send_report(
            subject="🧪 Economic Intelligence Agent - Test Email",
            body_html="""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2>✅ Test Successful!</h2>
                <p>Your Economic Intelligence Agent email configuration is working correctly.</p>
                <p>Now powered by <b>NVIDIA NIM 7-Model Architecture</b>.</p>
                <p>You will receive weekly reports at this address every Monday.</p>
            </body>
            </html>
            """,
            attachments=[]
        )

        return success
    else:
        logger.error("[ERROR] Email configuration failed")
        return False


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description='Economic Intelligence Agent - Weekly Report Generator (NVIDIA NIM Powered)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    Run full agent with email delivery
  python main.py --dry-run          Generate reports without sending email
  python main.py --test-email       Test email configuration
  python main.py --orgs IMF,RBI     Only process specific organizations
  python main.py --limit 5          Process only first 5 organizations
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Generate reports without sending email'
    )

    parser.add_argument(
        '--test-email',
        action='store_true',
        help='Test email configuration'
    )

    parser.add_argument(
        '--orgs',
        type=str,
        help='Comma-separated list of organization short names to process'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Limit to N organizations (for testing)'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.test_email:
        success = test_email()
        sys.exit(0 if success else 1)

    specific_orgs = None
    if args.orgs:
        specific_orgs = [o.strip() for o in args.orgs.split(',')]

    success = run_agent(
        dry_run=args.dry_run,
        specific_orgs=specific_orgs,
        limit_orgs=args.limit
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
