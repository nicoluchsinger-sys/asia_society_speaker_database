# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Asia Society Switzerland Speaker Database Builder - an AI-powered tool that scrapes event pages from Asia Society Switzerland's website using Selenium, extracts speaker information using Claude AI, and stores data in SQLite.

## Commands

```bash
# Run main workflow (scrape events + extract speakers)
python3 main_selenium.py

# Extract speakers from already-scraped events only
python3 extract_only.py

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
- **selenium_scraper.py** - Selenium-based web scraper with anti-bot detection measures; scrapes from `https://asiasociety.org/switzerland/events/past`
- **speaker_extractor.py** - Claude API client using `claude-sonnet-4-20250514` for intelligent speaker extraction from event text
- **database.py** - SQLite database manager with context manager support (`SpeakerDatabase`)

### Data Flow

1. `main_selenium.py` orchestrates the workflow
2. `selenium_scraper.py` fetches event pages → stores in `events` table
3. `speaker_extractor.py` processes unprocessed events → extracts speakers via Claude API
4. Results stored in `speakers` and `event_speakers` tables

### Database Schema (speakers.db)

- **events** - Scraped event pages with `processing_status` (pending/completed/failed)
- **speakers** - Deduplicated by (name, affiliation) unique constraint
- **event_speakers** - Junction table linking speakers to events with `role_in_event`

### Legacy Code (Non-functional)

- `main.py` and `scraper.py` - Original HTTP-based scraper, broken due to 403 errors; use `main_selenium.py` instead

## Environment Setup

Requires `ANTHROPIC_API_KEY` in `.env` file:
```
ANTHROPIC_API_KEY=your_key_here
```
