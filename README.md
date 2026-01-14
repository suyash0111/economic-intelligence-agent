# The Global Pulse 📊
## Weekly Economic Intelligence Agent

An automated agent that monitors **44 leading economic and financial organizations** weekly, analyzes their publications using AI, and delivers comprehensive intelligence reports via email.

## 🌟 Features

- **Comprehensive Coverage**: Monitors 44 organizations including Fed, ECB, IMF, World Bank, RBI, McKinsey, and more
- **AI-Powered Analysis**: Uses Google's Gemini AI for 360-degree analysis with Professional-Layman tone
- **Multiple Output Formats**:
  - 📄 **Word Document**: "The Global Pulse" - comprehensive agency-wise report
  - 📊 **Excel Spreadsheet**: "Master Intelligence Index" - quick reference
- **Advanced Features**:
  - 🎯 **TL;DR Top 5**: Critical developments ranked by importance
  - 📈 **Market Sentiment**: Bullish/Neutral/Bearish indicator
  - 💼 **Actionable Implications**: For investors, businesses, policymakers
  - 🌍 **Regional Breakdown**: Global, Americas, Europe, Asia-Pacific, India
  - 📊 **Key Economic Numbers**: Live data from FRED API
  - 🔄 **Cross-Source Synthesis**: Consensus vs divergent views
  - 📑 **PDF Extraction**: Extract content from PDF reports
- **Automated Delivery**: Weekly email with mobile-friendly HTML digest

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

## 🚀 Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/economic_intelligence_agent.git
cd economic_intelligence_agent
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

## ⚙️ GitHub Actions (Automated)

### Setup Secrets

In your GitHub repository, go to Settings → Secrets and Variables → Actions, add:

| Secret | Description |
|--------|-------------|
| `GEMINI_API_KEY` | Your Gemini API key |
| `EMAIL_ADDRESS` | Gmail address for sending |
| `EMAIL_APP_PASSWORD` | Gmail App Password |
| `RECIPIENT_EMAIL` | Email to receive reports |

### Schedule

The agent runs automatically every **Monday at 6:00 AM IST** (00:30 UTC).

You can also trigger manually from the Actions tab.

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
│   └── gemini_analyzer.py    # Gemini AI + FRED API integration
├── generators/
│   ├── document_generator.py # Word document output
│   └── excel_generator.py    # Excel spreadsheet output
├── delivery/
│   └── email_sender.py       # Email with mobile-friendly HTML
├── main.py                   # Main entry point
├── requirements.txt          # Python dependencies
└── .github/workflows/        # GitHub Actions
```

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

### Excel Spreadsheet (Master_Intelligence_Index.xlsx)

Columns:
- Organization
- Title
- Published Date
- Category (e.g., Monetary Policy, Trade, Employment)
- Content Type (Report, Press Release, etc.)
- Importance Score (1-10)
- One-liner Summary
- Link

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

### Adjust Lookback Period

In `.env`:

```env
LOOKBACK_DAYS=7     # Default: 7 days
MAX_ARTICLES_PER_ORG=20
```

## 📝 License

MIT License - feel free to use and modify.

## 🤝 Contributing

Contributions welcome! Please open an issue or PR.
