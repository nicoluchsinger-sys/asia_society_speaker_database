# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Asia Society Speaker Database Builder - an AI-powered tool that scrapes event pages from Asia Society's global events website using Selenium, extracts speaker information using Claude AI, and stores data in SQLite. Covers events from all Asia Society locations worldwide.

## Assistant Behavior

When working on this project, Claude should:

1. **Teach, Don't Just Code** - Explain the "why" behind decisions and implementation choices
2. **Comment Generously** - Add docstrings to all functions, explain complex logic with inline comments
3. **Ask When Unclear** - If requirements are ambiguous, ask questions before implementing
4. **Warn About Risks** - Before any destructive operation (deleting data, dropping tables, etc.), explicitly warn and ask for confirmation
5. **MVP First** - Get basic functionality working, test it, then refine
6. **Document Changes** - Update relevant documentation when making significant changes

See `.agent/rules/00_meta.md` for complete behavioral guidelines.

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

## Code Standards (Python)

### Docstrings Required
```python
def extract_speakers(event_html: str) -> list[dict]:
    """
    Extract speaker information from event HTML using Claude AI.

    Args:
        event_html: Raw HTML content from event page

    Returns:
        List of speaker dictionaries with name, title, affiliation

    Raises:
        APIError: If Claude API call fails
    """
    # Implementation
```

### Error Handling
- Always use try/except for external operations (API calls, file I/O, database operations)
- Log errors with context for debugging
- Provide user-friendly error messages
- Handle specific exceptions before generic Exception

### Type Hints
- Add type hints to function signatures where helpful
- Not required to be as strict as TypeScript, but use when it improves clarity

### Comments
- Explain the "why", not the "what"
- Document non-obvious business logic
- Add TODOs for future improvements
- Explain any workarounds or edge case handling

See `.agent/rules/20_development.md` for complete coding standards (adapted for Python).

## Security Practices

### Environment Variables
- **NEVER hardcode API keys or secrets in code**
- Store all sensitive credentials in `.env` file
- Use `python-dotenv` to load environment variables
- Keep `.env.example` updated (without real secrets)
- Ensure `.env` is in `.gitignore`

### Input Validation
- Validate all user input before processing
- Sanitize data before database queries (use parameterized queries)
- Validate file uploads (type, size)
- Handle malformed data gracefully

### Dangerous Operations
Before running operations that could cause data loss:
- Backup database
- Warn the user explicitly
- Require explicit confirmation
- Document recovery procedures

See `.agent/rules/30_security.md` for complete security guidelines.

## Git Workflow

### Commit Message Format
Use conventional commit format:
```
type: brief description

Optional longer explanation of what and why
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code restructuring without functional change
- `docs:` - Documentation changes
- `chore:` - Maintenance (dependencies, config)
- `test:` - Adding or updating tests

**Examples:**
```bash
git commit -m "feat: add natural language search with semantic embeddings"
git commit -m "fix: resolve duplicate speaker detection edge case"
git commit -m "refactor: extract deduplication logic into separate module"
```

### When to Commit
- Commit often - small, logical units of work
- Before switching tasks
- After completing a feature
- Before trying risky changes

See `.agent/rules/40_git.md` for complete Git guidelines.

## Project Structure

```
speaker_database/
├── .agent/rules/          # AI assistant instructions
├── database.py            # SQLite database operations
├── speaker_search.py      # Search functionality
├── embedding_engine.py    # AI embeddings for semantic search
├── selenium_scraper.py    # Web scraping logic
├── speaker_extractor.py   # Claude AI extraction
├── enrich_speakers.py     # Speaker data enrichment
├── query_parser.py        # Natural language query parsing
├── web_app/              # Flask web interface
│   ├── app.py           # Flask routes and server
│   ├── templates/       # HTML templates
│   └── static/          # CSS, JS, images
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables (NOT committed)
├── .env.example         # Template for .env (safe to commit)
├── speakers.db          # SQLite database (NOT committed)
└── CLAUDE.md            # This file
```

## Technology Stack

**Note:** This project uses Python/Flask, NOT the standard Next.js/TypeScript stack mentioned in `.agent/rules/10_stack.md`.

### Backend
- **Language:** Python 3.x
- **Web Framework:** Flask (for web interface)
- **Database:** SQLite3
- **ORM:** Raw SQL with context managers
- **Web Scraping:** Selenium with Chrome WebDriver

### AI Services
- **Claude AI** (Anthropic): Speaker extraction from HTML
- **OpenAI Embeddings**: Semantic search functionality

### Frontend (Web Interface)
- **Templates:** Jinja2 (Flask templates)
- **Styling:** Tailwind CSS (optional) or custom CSS
- **JavaScript:** Vanilla JS or minimal libraries

See `.agent/rules/99_project-overrides.md` for details on how standard rules are adapted for this Python project.

## Development Workflow

### Setup
1. Create and activate virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Mac/Linux
   # or
   venv\Scripts\activate  # Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create `.env` file from template:
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

### Before Committing
- [ ] Code runs without errors
- [ ] Added docstrings to new functions
- [ ] Added comments for complex logic
- [ ] Error handling is in place
- [ ] No API keys or secrets in code
- [ ] Updated requirements.txt if added packages
- [ ] Tested changes manually

### Database Changes
- Always backup database before schema changes
- Use transactions for multi-step operations
- Test migrations on test database first
- Document schema changes

## Environment Setup

Required environment variables in `.env` file:
```bash
# Claude AI for speaker extraction
ANTHROPIC_API_KEY=your_anthropic_key_here

# OpenAI for embeddings (semantic search)
OPENAI_API_KEY=your_openai_key_here
```

See `.env.example` for template.
