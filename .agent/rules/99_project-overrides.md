---
trigger: always_on
---

# 99_project-overrides.md - Speaker Database Project

## Project Overview
This is a Python-based speaker database and search system for Asia Society events.

**What This Project Does:**
- Scrapes speaker information from Asia Society event pages
- Uses Claude AI to extract structured speaker data
- Stores data in SQLite database with semantic search
- Provides Flask web interface for searching speakers

## Technology Stack (Different from Standard)

### Backend & Scripting
- **Language**: Python 3.x (NOT TypeScript/Node.js)
- **Web Framework**: Flask (NOT Next.js)
- **Database**: SQLite (NOT PostgreSQL)
- **ORM**: Raw SQL / SQLite3 (NOT Prisma)
- **Web Scraping**: Selenium with Chrome
- **AI Services**: Claude AI (Anthropic) for extraction, OpenAI for embeddings

### Frontend
- **Framework**: Flask templates (Jinja2), NOT React
- **Styling**: Custom CSS or Tailwind (if applicable)
- **JavaScript**: Vanilla JS or minimal libraries

## What Stays the Same from Standard Instructions

Even though the tech stack is different, these principles still apply:

### From 00_meta.md - Core Behavior
✅ **All applies** - Teaching approach, asking questions, explaining decisions, safety warnings

### From 20_development.md - Code Quality
✅ **Adapted for Python:**
- Generous comments explaining code
- Clear function/variable naming
- Error handling with try/except
- Type hints where helpful (not strict requirement)
- Documentation strings for functions

### From 30_security.md - Security
✅ **All applies:**
- Environment variables for API keys (.env file)
- Never hardcode secrets
- Validate user input
- Warn before destructive operations
- Use proper authentication for admin features

### From 40_git.md - Version Control
✅ **All applies:**
- Conventional commit messages (feat:, fix:, etc.)
- Regular commits
- Clear commit descriptions
- Git safety rules

## Python-Specific Standards

### Code Style
```python
# Follow PEP 8 style guide
# Use docstrings for functions

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
    pass
```

### File Organization
```
speaker_database/
├── database.py           # Database operations
├── speaker_search.py     # Search functionality
├── embedding_engine.py   # AI embeddings
├── selenium_scraper.py   # Web scraping
├── enrich_speakers.py    # Data enrichment
├── web_app/             # Flask web interface
│   ├── app.py           # Flask routes
│   ├── templates/       # HTML templates
│   └── static/          # CSS/JS/images
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (NOT committed)
└── speakers.db          # SQLite database
```

### Dependencies Management
```bash
# Use requirements.txt for dependencies
pip freeze > requirements.txt

# Virtual environment recommended
python -m venv venv
source venv/bin/activate  # Mac/Linux
```

### Database Operations
```python
# Use context managers for database connections
import sqlite3

def get_speakers():
    """Get all speakers from database."""
    with sqlite3.connect('speakers.db') as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM speakers')
        return cursor.fetchall()
```

### Error Handling
```python
# Python error handling
try:
    result = scrape_event(url)
except requests.RequestException as e:
    logger.error(f"Failed to scrape {url}: {e}")
    # Handle error gracefully
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
    # Log full traceback for debugging
```

## Environment Variables
```python
# Use python-dotenv for environment variables
from dotenv import load_dotenv
import os

load_dotenv()

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
```

## Testing (Python)
```python
# Use pytest for testing
# File: test_database.py

import pytest
from database import SpeakerDatabase

def test_add_speaker():
    """Test adding a speaker to database."""
    db = SpeakerDatabase(':memory:')  # In-memory test database
    speaker_id = db.add_speaker('John Doe', 'CEO', 'Company Inc')
    assert speaker_id is not None
```

## Admin Panel
Since this is a Flask app, admin functionality would be:
- Flask routes for admin actions (e.g., `/admin/speakers`)
- Template-based forms for CRUD operations
- Simple authentication with Flask-Login (if needed)

## What to Ignore from Standard Instructions

❌ **10_stack.md** - Ignore Next.js/TypeScript/Prisma specifics
❌ **50_ui-design.md** - React component patterns (but Tailwind principles may apply)
❌ **60_backend-admin.md** - Next.js service layer (use Python modules instead)

## Project-Specific Rules

### Speaker Data
- Never delete speaker records, mark as archived
- Maintain event-speaker relationships carefully
- Keep scraped HTML for reference/debugging

### Scraping
- Respect rate limits (don't hammer the website)
- Handle pagination carefully
- Store raw HTML before extraction
- Log all scraping activity

### AI Operations
- Claude AI for extraction (structured data from HTML)
- OpenAI for embeddings (semantic search)
- Handle API errors gracefully with retries
- Log token usage for cost tracking

### Database
- SQLite for simplicity (no server needed)
- Use transactions for multi-step operations
- Regular backups (provide backup script)
- Index key fields for search performance

## Development Workflow

1. **Virtual Environment**: Always activate before working
2. **Dependencies**: Update requirements.txt when adding packages
3. **Database**: Don't commit speakers.db (too large, has data)
4. **Environment**: Keep .env.example updated
5. **Testing**: Run tests before committing

## Deployment Notes

Currently runs locally. For deployment:
- Consider using Gunicorn for production Flask server
- SQLite fine for moderate traffic
- Could migrate to PostgreSQL if needed at scale
- Environment variables via hosting platform

## Summary

This project uses Python/Flask, not Next.js/TypeScript. Apply the **principles** from standard instructions (comments, security, git workflow, teaching approach) but adapt the **implementation** for Python ecosystem.

When in doubt, ask: "How would this be done in Python/Flask?" rather than following Next.js patterns.
