# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Asia Society Speaker Database Builder - an AI-powered tool that scrapes event pages from Asia Society's global events website using Selenium, extracts speaker information using Claude AI, and stores data in SQLite. Covers events from all Asia Society locations worldwide.

## Commands

```bash
# Run main workflow with typical options
python3 main_selenium.py -e 10 --stats --export

# Common flags:
#   -e N          Scrape N new events (default: 5)
#   --stats       Show timing and API cost statistics
#   --export      Export speakers to CSV
#   -p N/auto     Max pages to scrape (default: auto - fetches as many pages as needed)
#   --tag         Tag speakers with expertise tags after extraction
#   --url URL     Custom base URL (default: global events page)

# Extract speakers from already-scraped events only
python3 extract_only.py

# Merge duplicate speakers (standalone utility)
python3 merge_duplicates.py --execute

# Test Claude API connectivity
python3 test_api.py

# Reset failed events back to pending status
python3 reset_events.py

# Install dependencies
pip3 install -r requirements.txt
```

## Architecture

### Core Modules

- **main_selenium.py** - Interactive CLI orchestrating the scraping and extraction pipeline
- **selenium_scraper.py** - Selenium-based web scraper with anti-bot detection measures; scrapes from `https://asiasociety.org/events/past` (global events from all locations)
- **speaker_extractor.py** - Claude API client using `claude-sonnet-4-20250514` for intelligent speaker extraction from event text
- **database.py** - SQLite database manager with context manager support (`SpeakerDatabase`)

### Data Flow

1. `main_selenium.py` orchestrates the workflow
2. `selenium_scraper.py` fetches event pages → stores in `events` table
3. `speaker_extractor.py` processes unprocessed events → extracts speakers via Claude API
4. Results stored in `speakers` and `event_speakers` tables

### Database Schema (speakers.db)

- **events** - Scraped event pages with `processing_status` (pending/completed/failed)
- **speakers** - Deduplicated with fuzzy affiliation matching (name + affiliation overlap)
- **event_speakers** - Junction table linking speakers to events with `role_in_event`
- **speaker_tags** - Expertise tags for speakers with confidence scores

### Key Features

- **Smart Auto-Pagination** - Automatically fetches additional pages when current page has all scraped events
- **Fuzzy Deduplication** - Matches speakers by name + affiliation overlap (e.g., "NYU" matches "New York University")
- **Dynamic Token Allocation** - Scales max_tokens (2k→4k→8k) based on event size for large multi-panel events
- **Automatic Cleanup** - Runs `merge_duplicates()` after extraction to catch any deduplication edge cases
- **Location Extraction** - Automatically extracts event location from URL (Switzerland, New York, Hong Kong, Texas, etc.)

### Legacy Code (Non-functional)

- `main.py` and `scraper.py` - Original HTTP-based scraper, broken due to 403 errors; use `main_selenium.py` instead

## Environment Setup

Requires `ANTHROPIC_API_KEY` in `.env` file:
```
ANTHROPIC_API_KEY=your_key_here
```
