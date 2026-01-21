# Asia Society Speaker Database Builder

An AI-powered tool that scrapes event pages from Asia Society's **global events website**, extracts speaker information using Claude AI, and stores comprehensive data in SQLite.

**✨ Features: Smart Auto-Pagination • Fuzzy Deduplication • Global Coverage • 200 Events Built!**

## 📊 Current Database Stats

- **200 events** from all Asia Society locations worldwide
- **428 unique speakers**
- **502 speaker-event connections**
- **100% extraction success rate** (0 failed events)
- **15+ locations**: Texas, New York, Hong Kong, Switzerland, India, Japan, Australia, Philippines, France, Seattle, Northern California, Southern California, Asian Women Empowered, and more

### Notable Speakers

Hillary Clinton, Nadia Murad (Nobel Prize), Elaine Chao, Lucy Liu, Shashi Tharoor, Padma Lakshmi, Ustad Amjad Ali Khan, Raj Subramaniam (FedEx CEO), Andy Summers (The Police), and 419 more...

## What This Does

1. **Scrapes Events**: Uses Selenium to open a real Chrome browser and download event pages
2. **Stores Content**: Saves all event data in a SQLite database
3. **Extracts Speakers**: Uses Claude AI to intelligently extract speaker names, titles, affiliations, and roles
4. **Builds Database**: Creates a searchable database of speakers and their event history

## Features

### Core Capabilities
- ✅ **Selenium-based scraping** - Bypasses anti-bot protection with real browser
- ✅ **AI-powered extraction** - Claude AI understands context, not just pattern matching
- ✅ **SQLite database** - Easy to query, no server needed
- ✅ **Global coverage** - Scrapes from all Asia Society locations worldwide
- ✅ **Export to CSV** - Timestamped exports for analysis
- ✅ **Resume capability** - Won't re-process already scraped events

### Advanced Features (Added Today!)
- 🆕 **Smart Auto-Pagination** - Automatically fetches more pages when current page has all scraped events
- 🆕 **Fuzzy Deduplication** - Recognizes speakers with similar names/affiliations (e.g., "NYU" = "New York University")
- 🆕 **Dynamic Token Allocation** - Scales API tokens (2k→4k→8k) based on event size for large multi-panel events
- 🆕 **Automatic Duplicate Cleanup** - Runs merge after extraction to catch any edge cases
- 🆕 **Speaker Tagging** - Optional AI-generated expertise tags with confidence scores
- 🆕 **Location Extraction** - Automatically extracts event location from URL

## Setup Instructions

### 1. Install Chrome Browser

Make sure you have Google Chrome installed on your computer. Selenium will control Chrome to scrape the website.

### 2. Install Python Dependencies

```bash
pip3 install -r requirements.txt
```

This will install:
- `selenium` - Browser automation
- `anthropic` - Claude AI SDK
- `beautifulsoup4` - HTML parsing
- `requests` - HTTP library

### 3. Set Up API Key

Copy the template and add your Anthropic API key:

```bash
cp .env.template .env
```

Then edit `.env` and replace `your_api_key_here` with your actual API key from https://console.anthropic.com/settings/keys

### 4. Run the Tool

```bash
# Scrape 10 events with stats and export
python3 main_selenium.py -e 10 --stats --export

# Or extract speakers from already-scraped events
python3 extract_only.py
```

## Usage

### Quick Command Reference

```bash
# Scrape events with all features
python3 main_selenium.py -e 10 --stats --export --tag

# Common flags:
#   -e N          Number of new events to scrape (default: 5)
#   --stats       Show detailed timing and API cost statistics
#   --export      Export speakers to timestamped CSV file
#   --tag         Tag speakers with expertise tags after extraction
#   --tag-limit N Limit number of speakers to tag (for testing)
#   -p N/auto     Max pages to scrape (default: auto - fetches as many as needed)
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
```

### What Happens When You Run It

1. **Smart Scraping**
   - Opens Chrome browser (headless by default)
   - Checks database for already-scraped events
   - Automatically moves to next pages if needed
   - Downloads and saves new events only
   - Shows progress for each event

2. **AI Extraction**
   - Uses Claude AI to analyze event text
   - Extracts speaker names, titles, affiliations, roles, bios
   - Fuzzy deduplication prevents duplicates
   - Cost: ~$0.01-0.05 per event

3. **Automatic Cleanup**
   - Runs duplicate merge after extraction
   - Shows statistics (events, speakers, connections)
   - Exports to CSV if --export flag used

## Files Overview

### Core Scripts
- `main_selenium.py` - **Main script** - Orchestrates scraping + extraction pipeline
- `selenium_scraper.py` - Selenium-based web scraper with smart pagination
- `speaker_extractor.py` - AI speaker extraction with dynamic token allocation
- `database.py` - Database manager with fuzzy deduplication
- `extract_only.py` - Extract speakers from already-scraped events
- `merge_duplicates.py` - Standalone utility to merge duplicate speakers

### Generated Files
- `speakers.db` - SQLite database (created after first run, gitignored)
- `speakers_export_*.csv` - Timestamped CSV exports (gitignored)

### Configuration
- `.env` - Your API key (create from template, gitignored)
- `CLAUDE.md` - Instructions for Claude Code when working on this project
- `requirements.txt` - Python dependencies

**Legacy files (non-functional):**
- `main.py` - Original HTTP-based version (broken - 403 errors)
- `scraper.py` - Original HTTP scraper (broken - 403 errors)

## Why Selenium?

The Asia Society website blocks simple scrapers (403 Forbidden error). Selenium solves this by:

- Opening a real Chrome browser
- Navigating like a human would
- Executing JavaScript on the page
- Looking completely legitimate to the website

It's a bit slower than simple HTTP requests, but it actually works!

## Database Structure

### Events Table
- Event ID, URL, title, date, location
- Full body text and raw HTML
- Processing status

### Speakers Table
- Speaker ID, name, title, affiliation
- Biographical info
- First seen / last updated dates

### Event-Speakers Table
- Links speakers to events
- Stores role in event (keynote, panelist, moderator, etc.)

## Cost Estimation

Using Claude Sonnet 4.5:
- Input: ~$3 per million tokens
- Output: ~$15 per million tokens

### Real-World Costs (from 200-event build)

**Typical event processing:**
- Small event (~20k chars): ~$0.20 per event
- Medium event (~50k chars): ~$0.30-0.40 per event
- Large multi-panel event (~100k chars): ~$0.50 per event

**Total for 200 events:** ~$60-70
- Includes scraping, extraction, and duplicate cleanup
- Cost scales with event complexity
- Auto-pagination is free (just scraping, no API calls)

**Speaker tagging (optional):**
- ~$0.02-0.05 per speaker
- For 428 speakers: ~$10-20 additional

## Tips

1. **Start small**: Test with 3-5 events first
2. **Watch it work**: Say 'y' when asked if you want to watch the browser on first run
3. **Review results**: Check if speaker extraction is working well
4. **Adjust as needed**: The AI extraction can be tuned if needed
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

## Recent Achievements (January 21, 2026)

Successfully built comprehensive speaker database with major improvements:

### Database Built
- ✅ 200 events from 15+ global locations
- ✅ 428 unique speakers extracted
- ✅ 502 speaker-event connections
- ✅ 100% extraction success rate (0 failed events)

### Technical Improvements
- 🚀 Smart auto-pagination (automatically finds new events across pages)
- 🚀 Fuzzy deduplication (intelligent speaker matching)
- 🚀 Dynamic token allocation (handles large multi-panel events)
- 🚀 Automatic duplicate cleanup after extraction
- 🚀 Global event coverage (not region-specific)
- 🚀 Location extraction from URLs

### High-Profile Speakers Included
Hillary Clinton, Nadia Murad, Elaine Chao, Lucy Liu, Shashi Tharoor, Padma Lakshmi, Ustad Amjad Ali Khan, Raj Subramaniam, Andy Summers, and 419 more...

## Quick Command Reference

```bash
# Install everything
pip3 install -r requirements.txt

# Set up API key
cp .env.template .env
# (then edit .env with your key)

# Run with recommended options
python3 main_selenium.py -e 10 --stats --export
```

---

**Last Updated:** January 21, 2026
**Database Version:** v1.0 (200 events)
**Built with:** Claude Code + Sonnet 4.5
