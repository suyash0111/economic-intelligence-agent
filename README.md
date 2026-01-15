# The Global Pulse 📊
## Weekly Economic Intelligence Agent

An automated agent that monitors **44 leading economic and financial organizations** weekly, performs **deep PDF analysis** using AI, and delivers comprehensive intelligence reports via email.

---

## 🌟 Features

### Core Capabilities
- **Comprehensive Coverage**: Monitors 44 organizations including Fed, ECB, IMF, World Bank, RBI, McKinsey, and more
- **AI-Powered Analysis**: Uses Google's Gemini 2.0 Flash AI for 360-degree analysis
- **Multiple Output Formats**:
  - 📄 **Word Document**: "The Global Pulse" - comprehensive agency-wise report (40-60 pages)
  - 📊 **Excel Spreadsheet**: "Master Intelligence Index" - quick reference with all articles

### 🆕 Deep PDF Analysis (New!)
- **Full Report Processing**: Downloads and analyzes major PDF reports (50+ pages)
- **Text Extraction**: Full text extraction using PyMuPDF
- **Table Extraction**: Converts PDF tables to structured data with pdfplumber
- **Chart Analysis**: AI Vision describes charts and graphs
- **Statistics Extraction**: Automatically extracts key numbers and percentages
- **Smart Selection**: Only major reports from priority sources get deep analysis

### Advanced Features
- 🎯 **TL;DR Top 5**: Critical developments ranked by importance
- 📈 **Market Sentiment**: Bullish/Neutral/Bearish indicator
- 💼 **Actionable Implications**: For investors, businesses, policymakers
- 🌍 **Regional Breakdown**: Global, Americas, Europe, Asia-Pacific, India
- 📊 **Key Economic Numbers**: Live data from FRED API
- 🔄 **Cross-Source Synthesis**: Consensus vs divergent views
- 📧 **Automated Delivery**: Weekly email with mobile-friendly HTML digest

---

## 🏛️ Organizations Covered (44)

| Category | Organizations |
|----------|---------------|
| **Central Banks** | Fed, ECB, Bank of England, Bank of Japan, PBoC |
| **International** | IMF, World Bank, WTO, OECD, WEF, BIS, UNCTAD, ILO, UNDP, NBER, ADB |
| **Consulting** | McKinsey, Deloitte, BCG, PwC, EY, KPMG, Accenture, Bain |
| **Think Tanks** | Brookings, PIIE, Bruegel, Oxford Economics, Capital Economics |
| **Investment Banks** | Goldman Sachs, JP Morgan |
| **News** | Bloomberg, Reuters, WSJ, Financial Times, S&P Global, EIU |
| **Rating Agencies** | Moody's, Fitch, S&P Ratings |
| **India** | RBI, MoSPI, Ministry of Finance, NITI Aayog |

---

## 🚀 Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/suyash0111/economic-intelligence-agent.git
cd economic-intelligence-agent
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Get from https://aistudio.google.com/apikey
GEMINI_API_KEY=your_gemini_api_key

# Gmail with App Password
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_APP_PASSWORD=your_app_password
RECIPIENT_EMAIL=recipient@example.com
```

> **Note**: For Gmail App Password:
> 1. Enable 2-Factor Authentication
> 2. Go to Google Account → Security → App Passwords
> 3. Generate a password for "Mail"

### 3. Run Locally

```bash
# Full run with email delivery
python main.py

# Generate reports without email (dry run)
python main.py --dry-run

# Test email configuration
python main.py --test-email

# Process specific organizations only
python main.py --orgs "Fed,IMF,RBI,McKinsey"

# Limit to N organizations (for testing)
python main.py --limit 5
```

---

## ⚙️ GitHub Actions (Automated)

### Setup Secrets

In your GitHub repository, go to **Settings → Secrets and Variables → Actions**, add:

| Secret | Description |
|--------|-------------|
| `GEMINI_API_KEY` | Your Gemini API key |
| `EMAIL_ADDRESS` | Gmail address for sending |
| `EMAIL_APP_PASSWORD` | Gmail App Password |
| `RECIPIENT_EMAIL` | Email to receive reports |

### Schedule

The agent runs automatically every **Monday at 6:00 AM IST** (00:30 UTC).

You can also trigger manually from the Actions tab.

### Expected Runtime

| Mode | Time | API Calls |
|------|------|-----------|
| Surface Analysis Only | ~25 mins | ~330 |
| **With Deep PDF Analysis** | ~60-70 mins | ~750 |

All within Gemini free tier (1,500 calls/day).

---

## 📁 Project Structure

```
economic_intelligence_agent/
├── config/
│   ├── settings.py           # Configuration management
│   └── organizations.yaml    # All 44 organizations
├── collectors/
│   ├── base_collector.py     # Base class and Article model
│   ├── rss_collector.py      # RSS/Atom feed collector
│   ├── web_collector.py      # Web scraping collector
│   ├── pdf_extractor.py      # PDF content extraction
│   └── collector_manager.py  # Orchestrates all collectors
├── analyzers/
│   ├── gemini_analyzer.py    # Gemini AI + FRED API + Deep Analysis
│   └── pdf_processor.py      # PDF download, text/table/chart extraction
├── generators/
│   ├── document_generator.py # Word document output (with rich charts/tables)
│   └── excel_generator.py    # Excel spreadsheet output
├── delivery/
│   └── email_sender.py       # Email with mobile-friendly HTML
├── cache/
│   └── pdfs/                 # Temporary PDF storage (auto-cleaned)
├── output/                   # Generated reports
├── main.py                   # Main entry point
├── requirements.txt          # Python dependencies
└── .github/workflows/        # GitHub Actions
```

---

## 📊 Report Contents

### Word Document (Global_Pulse_Weekly_Report.docx)

1. **TOP 5 THIS WEEK** - Critical developments ranked by importance
2. **KEY ECONOMIC NUMBERS** - Live FRED data (US inflation, unemployment, etc.)
3. **MARKET SENTIMENT** - Bullish/Neutral/Bearish assessment
4. **EXECUTIVE SUMMARY** - Week's highlights
5. **CROSS-SOURCE INTELLIGENCE** - Consensus and divergent views
6. **ACTIONABLE IMPLICATIONS** - For investors, businesses, policymakers
7. **REGIONAL BREAKDOWN** - Geographic grouping
8. **THEMATIC OVERVIEW** - Articles by theme (Monetary Policy, Inflation, etc.)
9. **ORGANIZATION DETAILS** - Full analysis for all 44 organizations

### Deep-Analyzed Reports Include:

```
• Report Title  📄 Full Report Analyzed

📊 KEY STATISTICS EXTRACTED:
• 70% of companies now deploy generative AI
• 30% of work hours potentially automatable by 2030
• $15-25 trillion added to global GDP by 2030

📈 CHARTS ANALYZED:
[Chart 1] Bar chart showing financial services (78%) leading adoption...
[Chart 2] Line graph projecting job displacement trends...

📋 KEY TABLES:
| Occupation | % Automatable | Workers (M) |
|------------|---------------|-------------|
| Data Entry | 85% | 45M |
| Customer Service | 65% | 78M |

**1. THE NON-OBVIOUS TRUTHS**
[Deep analysis of what headlines miss...]

**2. MACRO & MICRO INDICATORS**
[Economic implications...]
```

### Excel Spreadsheet (Master_Intelligence_Index.xlsx)

| Column | Description |
|--------|-------------|
| Organization | Source organization |
| Title | Article/report title |
| Published Date | Publication date |
| Category | e.g., Monetary Policy, Trade |
| Content Type | Report, Press Release, etc. |
| Summary | AI-generated one-liner |
| Link | Clickable URL |

---

## 🛠️ Customization

### Add an Organization

Edit `config/organizations.yaml`:

```yaml
- name: "Your Organization"
  short_name: "ORG"
  category: "Category"
  description: "Description"
  feeds:
    - "https://example.com/rss"
  scrape_urls:
    - url: "https://example.com/news"
      type: "news"
```

### Adjust Settings

In `.env`:

```env
LOOKBACK_DAYS=7          # Default: 7 days
MAX_ARTICLES_PER_ORG=20  # Articles per organization
```

### Configure Deep Analysis Sources

Edit `analyzers/pdf_processor.py`:

```python
DEEP_ANALYSIS_SOURCES = [
    'Fed', 'ECB', 'IMF', 'McKinsey', ...
]
```

---

## 📋 Requirements

- Python 3.11+
- Gemini API Key (free tier works!)
- Gmail account with App Password (for email delivery)

### Key Dependencies

```
google-generativeai    # Gemini AI
pymupdf               # PDF text extraction
pdfplumber            # PDF table extraction
Pillow                # Image processing for charts
python-docx           # Word document generation
openpyxl              # Excel generation
```

---

## 📝 License

MIT License - feel free to use and modify.

---

## 🤝 Contributing

Contributions welcome! Please open an issue or PR.

---

## 📧 Contact

Created by Suyash - Economic Intelligence for the modern world.
