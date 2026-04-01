# 📊 Economic Intelligence Agent

> **World-class automated economic intelligence** powered by NVIDIA NIM's 7-Model Architecture. Collects, deduplicates, analyzes, and synthesizes economic reports from 39 global organizations into actionable weekly briefings.

## 🏗️ Architecture: 7-Model NVIDIA NIM Engine

```
📰 277 Articles Collected
        │
        ▼
🧬 Model 5: NV-Embed-V1 ──── Smart Deduplication & Topic Clustering
        │
        ▼ (~200 unique)
🟠 Model 4: Rerank-QA-Mistral ──── AI Relevance Ranking
        │
        ▼ (ranked by importance)
   ┌────┴────┐
   │         │
🟢 Model 1  🔵 Model 2
Mistral      DeepSeek V3.1
Small 3.1    Terminus
(Quick       (Deep analysis
summaries)   128K context)
   │         │
   │    ┌────┴────┐
   │    │         │
   │  🟣 Model 3  🔴 Model 6
   │  Llama 4     OCDRNet
   │  Maverick    (OCR for
   │  (Vision/    scanned
   │  charts)     PDFs)
   │    │         │
   └────┴────┬────┘
             │
             ▼
🟡 Model 7: Kimi K2 Instruct ──── Long-Context Final Synthesis
             │
             ▼
📊 Executive Summary + Cross-Source Intelligence + Sentiment + Implications
```

### The 7 Models

| # | Model | Role | Why |
|---|-------|------|-----|
| 🟢 | **Mistral Small 3.1** (24B) | Quick article summaries | Fast, cheap — handles ~200 articles efficiently |
| 🔵 | **DeepSeek V3.1 Terminus** | Deep analysis & reasoning | 128K context, Think/Non-Think modes, best reasoning |
| 🟣 | **Llama 4 Maverick** | Chart/image analysis | Multimodal vision — reads graphs from PDFs |
| 🟠 | **Rerank QA Mistral** | Article relevance ranking | Purpose-built ranker, not a general LLM |
| 🧬 | **NV-Embed-V1** | Dedup + semantic clustering | Removes duplicate articles, saves credits |
| 🔴 | **OCDRNet** | OCR for scanned PDFs | Extracts text from image-based PDFs |
| 🟡 | **Kimi K2 Instruct** | Final synthesis | Longest context — sees ALL analyses at once |

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- NVIDIA API Key (free from [build.nvidia.com](https://build.nvidia.com))
- Gmail account with App Password

### Setup

```bash
# Clone the repository
git clone https://github.com/suyash0111/economic-intelligence-agent.git
cd economic-intelligence-agent

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your NVIDIA_API_KEY, email credentials
```

### Run

```bash
# Full run with email delivery
python main.py

# Generate reports without email (testing)
python main.py --dry-run

# Test with limited organizations
python main.py --dry-run --limit 3

# Process specific organizations only
python main.py --orgs IMF,RBI,Fed
```

## 🔑 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `NVIDIA_API_KEY` | NVIDIA NIM API key from [build.nvidia.com](https://build.nvidia.com) | ✅ |
| `EMAIL_ADDRESS` | Gmail address for sending reports | ✅ |
| `EMAIL_APP_PASSWORD` | Gmail App Password | ✅ |
| `RECIPIENT_EMAIL` | Report recipient email | ✅ |
| `LOOKBACK_DAYS` | How many days back to collect articles (default: 7) | ❌ |
| `MAX_ARTICLES_PER_ORG` | Max articles per organization (default: 20) | ❌ |

## 📁 Project Structure

```
economic_intelligence_agent/
├── analyzers/
│   ├── nvidia_analyzer.py     # 🆕 7-model NVIDIA NIM engine
│   ├── gemini_analyzer.py     # Legacy Gemini analyzer (backup)
│   └── pdf_processor.py       # PDF download, extraction, chunking
├── collectors/
│   ├── base_collector.py      # Article dataclass & base collector
│   └── collector_manager.py   # Multi-org collection orchestrator
├── config/
│   ├── settings.py            # Environment & configuration
│   └── organizations.yaml     # 39 organization definitions
├── generators/
│   ├── document_generator.py  # Word document report generator
│   └── excel_generator.py     # Excel spreadsheet generator
├── delivery/
│   └── email_sender.py        # Gmail SMTP email delivery
├── .github/
│   └── workflows/
│       └── weekly_report.yml  # Automated Monday morning runs
├── main.py                    # Main orchestration script
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## 📈 Credit Budget

Each full run uses approximately **~320 NVIDIA credits**:

| Step | Model | Credits |
|------|-------|---------|
| Embedding & dedup | NV-Embed-V1 | ~30 |
| Ranking | Rerank-QA-Mistral | ~25 |
| Quick summaries | Mistral Small 3.1 | ~150 |
| Deep analysis | DeepSeek V3.1 | ~60 |
| Chart analysis | Llama 4 Maverick | ~15 |
| OCR | OCDRNet | ~10 |
| Final synthesis | Kimi K2 Instruct | ~30 |
| **Total** | | **~320** |

With **5,000 free credits** → ≈ **15 weekly runs** → ≈ **3.5 months** of reports.

## 🏛️ Organizations Covered (39)

**Central Banks**: Fed, ECB, BoE, BoJ, PBoC, RBI, and more
**International**: IMF, World Bank, OECD, WTO, BIS, WEF
**Government (India)**: MoF, MoSPI, NITI Aayog
**Think Tanks**: Brookings, PIIE, Bruegel, NBER
**Consulting**: McKinsey, Deloitte, BCG, PwC
**Financial**: Goldman Sachs, JP Morgan
**Media**: FT, Bloomberg, Reuters, WSJ

## 🤖 GitHub Actions (Automated)

The agent runs automatically every **Monday at 6:00 AM IST** via GitHub Actions.

To trigger manually: Repository → Actions → "Weekly Economic Intelligence Report" → Run workflow

### Required GitHub Secrets

| Secret | Value |
|--------|-------|
| `NVIDIA_API_KEY` | Your NVIDIA NIM API key |
| `EMAIL_ADDRESS` | Gmail address |
| `EMAIL_APP_PASSWORD` | Gmail App Password |
| `RECIPIENT_EMAIL` | Report recipient |

## 📄 Output

Each run generates:
1. **Word Document** — Full report with executive summary, analysis, and charts
2. **Excel Spreadsheet** — All articles with AI summaries, scores, and categories
3. **Email** — HTML email with TL;DR and sentiment analysis

---

*Built with ❤️ and 7 AI models*
