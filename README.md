# Asia Society Switzerland - Speaker Database Builder

An AI-powered tool to scrape event information from Asia Society Switzerland's website and automatically extract speaker details using Claude AI.

**✨ NOW WITH SELENIUM - Bypasses 403 errors by using a real browser!**

## What This Does

1. **Scrapes Events**: Uses Selenium to open a real Chrome browser and download event pages
2. **Stores Content**: Saves all event data in a SQLite database
3. **Extracts Speakers**: Uses Claude AI to intelligently extract speaker names, titles, affiliations, and roles
4. **Builds Database**: Creates a searchable database of speakers and their event history

## Features

- ✅ Selenium-based scraping (bypasses anti-bot protection)
- ✅ AI-powered speaker extraction (understands context, not just pattern matching)
- ✅ SQLite database (easy to query, no server needed)
- ✅ Tracks speaker history across multiple events
- ✅ Export to CSV for analysis
- ✅ Resume capability (won't re-process already scraped events)
- ✅ Optional: Watch the browser work in real-time

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
python3 main_selenium.py
```

## Usage

When you run `main_selenium.py`, it will:

1. **Ask how many events to scrape** 
   - Enter a number (e.g., 10) or "all" for everything
   - First run: recommend starting with 3-5 to test

2. **Ask if you want to watch the browser**
   - 'y' = You'll see Chrome open and navigate (cool to watch!)
   - 'n' = Runs in background (faster, less distracting)

3. **Scrape event pages using Selenium**
   - Opens Chrome browser
   - Navigates to each event page like a human would
   - Downloads and saves to database
   - Shows progress for each event

4. **Ask if you want to extract speakers**
   - Uses Claude AI to analyze each event
   - Extracts speaker names, titles, affiliations, roles
   - Costs roughly $0.01-0.05 per event

5. **Show statistics**
   - Total events, speakers, connections

6. **Export to CSV** (optional)
   - Creates a spreadsheet of all speakers

## Files Overview

- `main_selenium.py` - **Main script (USE THIS ONE!)**
- `selenium_scraper.py` - Selenium-based web scraping
- `speaker_extractor.py` - AI speaker extraction
- `database.py` - Database management
- `speakers.db` - SQLite database (created after first run)
- `.env` - Your API key (don't commit this!)

**Old files (for reference):**
- `main.py` - Original version (doesn't work due to 403 errors)
- `scraper.py` - Original scraper (doesn't work due to 403 errors)

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

Typical event processing:
- ~2,000 input tokens (event text)
- ~300 output tokens (extracted speaker info)
- Cost: ~$0.01-0.05 per event

For 300 events: approximately $5-15 total

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

## Quick Command Reference

```bash
# Install everything
pip3 install -r requirements.txt

# Set up API key
cp .env.template .env
# (then edit .env with your key)

# Run the scraper
python3 main_selenium.py
```
