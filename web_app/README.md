# Asia Society Speaker Database - Web Interface

A clean web interface for searching and browsing the Asia Society speaker database using natural language queries.

## Quick Start

```bash
# From the web_app directory
python3 app.py
```

Then open your browser to: **http://localhost:5001**

## Features

### Natural Language Search
- Search for speakers using conversational queries
- Example: "3 speakers on chinese economy, ideally women from Europe"
- Semantic search powered by OpenAI embeddings
- Intelligent ranking with preference bonuses

### Search Options
- **Result Limit**: Choose 5, 10, 20, or 50 results
- **Show Explanations**: See why each speaker matched your query
- **Example Queries**: Click to try pre-made searches

### Speaker Profiles
Click any speaker to view:
- Full biography
- Expertise tags with confidence scores
- Demographics (gender, nationality, birth year)
- Location information
- Languages spoken
- Complete event history

### Database Statistics
Click "Stats" in the navigation to see:
- Total speakers: 443
- Tagged speakers: 448
- Total events: 204
- Total tags: 1,344

## Tech Stack

- **Backend**: Flask 3.1.2
- **Frontend**: Vanilla JavaScript + Tailwind CSS
- **Database**: SQLite (speakers.db)
- **Search**: SpeakerSearch class with OpenAI embeddings

## API Endpoints

### POST /api/search
Search for speakers

**Request:**
```json
{
  "query": "climate policy experts",
  "limit": 10,
  "explain": true
}
```

**Response:**
```json
{
  "success": true,
  "query": "climate policy experts",
  "count": 10,
  "results": [...]
}
```

### GET /speaker/:id
View speaker detail page (HTML)

### GET /api/stats
Get database statistics (JSON)

## Keyboard Shortcuts

- **Ctrl/Cmd + K**: Focus search box
- **Enter**: Submit search
- **Escape**: Close stats modal

## Example Searches

Try these queries:
- "3 speakers on chinese economy"
- "climate policy experts"
- "women in tech policy"
- "mandarin-speaking economists"
- "geopolitics experts from Asia"
- "5 climate policy experts, ideally from Asia"

## Configuration

The app runs on port 5001 by default. To change:

```python
# In app.py
if __name__ == '__main__':
    app.run(debug=True, port=YOUR_PORT, host='0.0.0.0')
```

## Requirements

- Python 3.7+
- Flask 3.0+
- python-dotenv 1.0+
- OpenAI API key in .env file
- Existing speakers.db with embeddings

## Troubleshooting

**Port already in use:**
```bash
# Kill existing Flask processes
pkill -f "python3 app.py"
```

**Database not found:**
The app looks for `speakers.db` in the parent directory. Make sure it exists at:
```
speaker_database/
├── speakers.db
└── web_app/
    └── app.py
```

**Search not working:**
Ensure you have:
1. OpenAI API key in `.env` file
2. Speaker embeddings generated (run `generate_embeddings.py`)
3. All dependencies installed (`pip3 install -r requirements-web.txt`)

## Development

The app runs in debug mode by default, which means:
- Auto-reload on file changes
- Detailed error messages
- Template auto-reload

For production, set `debug=False` and use a production WSGI server like Gunicorn.

## Browser Compatibility

Tested on:
- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

Works on desktop, tablet, and mobile devices.
