# Asia Society Speaker Database

An AI-powered tool that scrapes event pages from Asia Society's **global events website**, extracts speaker information using Claude AI, and stores comprehensive data in SQLite with natural language search capabilities.

**✨ Features: Smart Auto-Pagination • Fuzzy Deduplication • Global Coverage • Natural Language Search**

## What This Does

1. **Scrapes Events**: Uses Selenium to open a real Chrome browser and download event pages from all Asia Society locations worldwide
2. **Extracts Speakers**: Uses Claude AI to intelligently extract speaker names, titles, affiliations, roles, and bios
3. **Enriches Data**: Optional AI-powered enrichment adds demographics, locations, expertise tags, and languages
4. **Semantic Search**: Natural language search powered by OpenAI embeddings finds relevant speakers by topic, expertise, or criteria

## Quick Start

```bash
# 1. Install dependencies
pip3 install -r requirements.txt

# 2. Set up API keys
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY and OPENAI_API_KEY

# 3. Scrape events and extract speakers
python3 main_selenium.py -e 10 --stats --export

# 4. Generate embeddings for search (one-time setup)
python3 generate_embeddings.py

# 5. Search naturally!
python3 search_speakers.py "climate policy experts from Asia"
```

## Core Features

### Intelligent Scraping
- ✅ **Selenium-based scraping** - Bypasses anti-bot protection with real browser automation
- ✅ **Smart auto-pagination** - Automatically fetches additional pages to find new events
- ✅ **Global coverage** - Scrapes from all Asia Society locations worldwide
- ✅ **Resume capability** - Won't re-process already scraped events
- ✅ **Location extraction** - Automatically extracts event location from URL

### AI-Powered Extraction
- ✅ **Claude AI extraction** - Understands context, not just pattern matching
- ✅ **Fuzzy deduplication** - Recognizes speakers with similar names/affiliations (e.g., "NYU" = "New York University")
- ✅ **Dynamic token allocation** - Scales API tokens (2k→4k→8k) based on event size for large multi-panel events
- ✅ **Automatic duplicate cleanup** - Runs merge after extraction to catch edge cases
- ✅ **Speaker tagging** - Optional AI-generated expertise tags with confidence scores

### Natural Language Search

Search your speaker database using plain English:

```bash
# Find experts by topic
python3 search_speakers.py "climate policy experts"

# With demographic preferences
python3 search_speakers.py "women in tech policy"

# Geographic filtering
python3 search_speakers.py "5 geopolitics experts from Asia"

# Language requirements
python3 search_speakers.py "mandarin-speaking economists"

# With explanations
python3 search_speakers.py "technology policy specialists" --explain
```

**How It Works:**

1. **Query Parsing (Claude AI)**: Understands natural language and extracts structured criteria
   - Distinguishes hard requirements ("need", "must") vs soft preferences ("ideally", "prefer")
   - Extracts: count, expertise topics, demographics, location, languages

2. **Semantic Search (OpenAI Embeddings)**: Finds semantically similar speakers
   - Converts speaker profiles → 1536-dim vectors
   - Uses cosine similarity to find relevant candidates
   - Understands "chinese economy" matches "China trade policy expert"

3. **Intelligent Ranking**: Scores candidates with bonuses for:
   - High-confidence expertise tags (+20%)
   - Complete biographical information (+10%)
   - Active speaking history (+10%)
   - Matching demographic preferences (up to +30-40%)

### Optional: Speaker Enrichment

Enhance search with demographics, location, and language data:

```bash
# Enrich speakers with demographics/location/languages
python3 enrich_speakers.py --limit 10  # Start with 10 speakers

# Show enrichment statistics
python3 enrich_speakers.py --stats

# Search with enriched data
python3 search_speakers.py "european experts on technology policy"
```

**Enrichment Features:**
- Extracts: gender, nationality, birth year, location (city/country/region), languages
- Confidence scores for all extracted data
- ~$0.01-0.02 per speaker (uses Claude Haiku for cost efficiency)
- Fully optional - search works without enrichment

### Data Freshness Management

Track and refresh stale speaker data:

```bash
# Update freshness scores for all speakers
python3 freshness_manager.py --update

# Show report of stale speakers
python3 freshness_manager.py --report

# Refresh high-priority stale speakers
python3 freshness_manager.py --refresh-stale --limit 10
```

## Web Interface

A password-protected Flask web app provides:
- 🔍 **Natural language search** - Search interface with real-time results
- 📊 **Statistics dashboard** - Database stats, API costs, enrichment progress
- 👤 **Speaker profiles** - Detailed pages with bios, tags, events, demographics
- 📅 **Event listings** - Browse events by location
- 🏆 **Leaderboard** - Most active speakers by event count
- 📈 **Search analytics** - Query patterns, popular searches, performance metrics

**Deploy to Railway in 10 minutes** - See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for complete guide.

## Setup Instructions

### 1. Install Chrome Browser

Make sure you have Google Chrome installed. Selenium will control Chrome to scrape the website.

### 2. Install Python Dependencies

```bash
pip3 install -r requirements.txt
```

This will install:
- `selenium` - Browser automation
- `anthropic` - Claude AI SDK
- `openai` - OpenAI embeddings
- `beautifulsoup4` - HTML parsing
- `flask` - Web interface
- And more (see requirements.txt)

### 3. Set Up API Keys

Copy the template and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` and add:
- `ANTHROPIC_API_KEY` - Get from https://console.anthropic.com/settings/keys
- `OPENAI_API_KEY` - Get from https://platform.openai.com/api-keys

### 4. Run the Tool

```bash
# Scrape 10 events with stats and export
python3 main_selenium.py -e 10 --stats --export

# Or extract speakers from already-scraped events
python3 extract_only.py

# Or run the web interface
python3 web_app/app.py
```

## Usage

### Command Reference

```bash
# Scrape events with all features
python3 main_selenium.py -e 10 --stats --export --tag

# Common flags:
#   -e N          Number of new events to scrape (default: 5)
#   --stats       Show detailed timing and API cost statistics
#   --export      Export speakers to timestamped CSV file
#   --tag         Tag speakers with expertise tags after extraction
#   -p N/auto     Max pages to scrape (default: auto)
#   --url URL     Custom base URL (default: global events page)

# Extract speakers only (no scraping)
python3 extract_only.py

# Merge duplicate speakers
python3 merge_duplicates.py          # Dry run (preview)
python3 merge_duplicates.py --execute # Actually merge

# Reset failed events
python3 reset_events.py

# Test API connectivity
python3 test_api.py

# Refresh stale speaker data
python3 refresh_stale_speakers.py --limit 20 --months 6
```

### Search System Commands

```bash
# Generate embeddings (one-time setup)
python3 generate_embeddings.py

# Search with natural language
python3 search_speakers.py "climate experts"
python3 search_speakers.py "3 speakers on chinese economy, ideally women based in Europe"

# Search with options
python3 search_speakers.py "climate experts" \
  --limit 10 \         # Max results
  --explain \          # Show why each matched
  --stats              # Database statistics

# List all speakers
python3 search_speakers.py --list

# View detailed speaker profile
python3 search_speakers.py --speaker "Hillary Clinton"
python3 search_speakers.py --id 42
```

## Project Structure

```
speaker_database/
├── main_selenium.py              # Main scraping + extraction pipeline
├── selenium_scraper.py           # Selenium-based web scraper
├── speaker_extractor.py          # AI speaker extraction
├── database.py                   # SQLite database manager
├── speaker_search.py             # Search engine with semantic matching
├── query_parser.py               # Natural language query parser
├── embedding_engine.py           # OpenAI embeddings
├── generate_embeddings.py        # Generate embeddings for speakers
├── enrich_speakers.py            # Speaker enrichment CLI
├── speaker_enricher.py           # AI-powered enrichment
├── refresh_stale_speakers.py     # Automated data refresh
├── web_app/                      # Flask web interface
│   ├── app.py                   # Flask routes and API
│   ├── templates/               # HTML templates
│   └── static/                  # CSS, JS, images
├── docs/                         # Documentation
│   ├── DEPLOYMENT.md            # Railway deployment guide
│   ├── PIPELINE.md              # Pipeline architecture
│   └── SEARCH_SYSTEM.md         # Search system docs
├── requirements.txt              # Python dependencies
├── .env                          # API keys (create from .env.example)
└── speakers.db                   # SQLite database (auto-created)
```

## Database Schema

### Core Tables
- **events** - Event metadata, URLs, body text, processing status
- **speakers** - Speaker profiles with fuzzy deduplication
- **event_speakers** - Junction table with role information
- **speaker_tags** - Expertise tags with confidence scores

### Search & Enrichment Tables
- **speaker_embeddings** - Semantic vectors for search (1536-dim)
- **speaker_demographics** - Gender, nationality, birth year
- **speaker_locations** - City, country, region with confidence scores
- **speaker_languages** - Languages spoken with proficiency levels
- **speaker_corrections** - User-submitted corrections with AI verification

## Cost Estimation

### One-Time Setup
- **Event scraping & extraction**: ~$0.20-0.50 per event (Claude Sonnet 4)
- **Generate embeddings**: ~$0.02 for 1000 speakers (OpenAI)
- **Initial enrichment**: ~$0.01 per speaker (Claude Haiku) - **OPTIONAL**

### Ongoing Costs
- **Query parsing**: ~$0.0006 per search (Claude Haiku - 80% cheaper than Sonnet)
- **Query embedding**: ~$0.0000004 per search (OpenAI - negligible)
- **Data refresh**: ~$0.01 per speaker (Claude Haiku)
- **Embedding new speakers**: ~$0.00002 per speaker (OpenAI)

### Production Deployment (Railway)
- **Hosting**: $5/month (Railway)
- **Automated pipeline**: Scrapes 20 events twice daily + enriches 20 speakers
- **Total**: ~$9-10/month (includes API calls)

## Why Selenium?

The Asia Society website blocks simple scrapers (403 Forbidden error). Selenium solves this by:
- Opening a real Chrome browser
- Navigating like a human would
- Executing JavaScript on the page
- Looking completely legitimate to the website

It's slower than simple HTTP requests, but it actually works!

## Tips

1. **Start small**: Test with 3-5 events first
2. **Watch it work**: Chrome will run headless by default, but you can watch on first run
3. **Review results**: Check if speaker extraction is working well
4. **Adjust as needed**: The AI extraction is robust but can be tuned if needed
5. **Resume anytime**: Script tracks what's been processed
6. **View database**: Use [DB Browser for SQLite](https://sqlitebrowser.org/) to explore your data

## Troubleshooting

**"ANTHROPIC_API_KEY not found"**
- Make sure you created `.env` file with your API key

**"Error initializing Chrome WebDriver"**
- Make sure Chrome browser is installed
- Try: `pip3 install --upgrade selenium`
- The script will auto-download the ChromeDriver

**"Failed to fetch events page"**
- Check your internet connection
- The website might be temporarily down

**"No speakers detected"**
- Some events might not have speaker info in the description
- The AI extraction might need tuning for specific formats

**Browser opens but nothing happens**
- Increase wait times in `selenium_scraper.py` (change `time.sleep(2)` to `time.sleep(5)`)

## Documentation

- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Complete Railway deployment guide
- **[PIPELINE.md](docs/PIPELINE.md)** - Speaker identification & enrichment pipeline
- **[SEARCH_SYSTEM.md](docs/SEARCH_SYSTEM.md)** - Search system architecture
- **[CLAUDE.md](CLAUDE.md)** - Instructions for AI assistants working on this project

## License

See [LICENSE](LICENSE) file for details.

---

**Built with:** Claude Code + Sonnet 4.5
**Deployment:** Railway (automated)
**Technologies:** Python, Selenium, Claude AI, OpenAI, SQLite, Flask
