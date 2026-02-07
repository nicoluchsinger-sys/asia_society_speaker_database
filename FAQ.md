# Frequently Asked Questions (FAQ)

## What is this database?

The Asia Society Speaker Database is a searchable collection of speakers who have participated in Asia Society events worldwide. It helps you discover experts, thought leaders, and practitioners across various fields related to Asia and global affairs.

Currently, the database contains **{{total_speakers}} speakers** from **{{total_events}} events** spanning from {{oldest_event_date}} to {{newest_event_date}}.

## How does it work?

The system automatically monitors Asia Society's global events website and builds profiles of speakers who participate in their programs. It uses AI to understand speaker expertise, extract biographical information, and make the data searchable through natural language queries.

## How is the data collected?

The database is built entirely through automated processes:

1. **Event Discovery**: A web scraper checks Asia Society's events page twice daily (6 AM and 6 PM UTC) to find new events
2. **Speaker Extraction**: AI analyzes each event page to identify speakers and extract their information (name, title, affiliation, bio)
3. **Enrichment**: Additional context is gathered, including:
   - Expertise tags based on speaking topics
   - Geographic information (when available)
   - Demographic data (handled conservatively to maintain accuracy)
4. **Search Indexing**: Speaker profiles are converted into semantic embeddings that enable intelligent search

All data comes from publicly available information on Asia Society's website.

## How does the search work?

The search combines two approaches to find the most relevant speakers:

**1. Exact Name Matching**
If you search for a specific person by name (e.g., "James Crabtree"), the system will find exact or partial matches.

**2. Semantic Search**
When you search by topic or expertise (e.g., "climate policy experts" or "Southeast Asia trade"), the system understands the meaning of your query and finds speakers with relevant experience, even if they don't use those exact words.

**3. Smart Ranking**
Results are ranked by:
- Topic relevance (how well expertise matches your query)
- Name matches (get highest priority)
- Profile quality (speakers with detailed bios and multiple events rank higher)
- Activity level (frequent speakers at Asia Society events)

You can also filter by preferences like location, language, or other criteria mentioned in your query (e.g., "female economists in China").

## How often is the database updated?

The database updates automatically **twice per day**:
- **6:00 AM UTC** - Morning update
- **6:00 PM UTC** - Evening update

Each update:
- Scrapes up to 10 new events
- Extracts speakers from those events
- Enriches up to 20 existing speaker profiles with additional context
- Updates search indexes

This means newly announced Asia Society events typically appear within 12 hours.

## What information is stored for each speaker?

Each speaker profile may include:

**Core Information** (extracted from event pages):
- Full name
- Professional title
- Current affiliation/organization
- Biography
- Speaking topics and roles at events

**Enriched Data** (added through automated analysis):
- Expertise tags (e.g., "trade policy", "climate change", "China economics")
- Geographic location (when clearly stated in bio or affiliation)
- Languages spoken (when mentioned)
- Career background and credentials

**Note**: We only store information that is publicly available on Asia Society's website. No personal contact information (email, phone numbers) is collected.

## How accurate is the data?

The system prioritizes **accuracy over completeness**:

- **Speaker Extraction**: Uses advanced AI (Claude Sonnet 4) to carefully extract information from event pages, with ~95% accuracy
- **Deduplication**: Automatically merges duplicate entries when the same person appears at multiple events (fuzzy matching on name + affiliation)
- **Conservative Enrichment**: Only adds demographic or location data when confidence is high (e.g., only 37% of speakers have location data because we won't guess)
- **Source Tracking**: All enriched data includes confidence scores and timestamps

## Can I export or download data?

Authenticated users can:
- View individual speaker profiles
- Browse event details
- Use the search interface
- View aggregate statistics

Bulk data exports are not available to prevent misuse.

## What technology powers this?

For those interested in the technical details:

- **Web Scraping**: Selenium WebDriver (to handle dynamic content)
- **Speaker Extraction**: Anthropic Claude AI (Sonnet 4 model)
- **Search**: OpenAI embeddings with hybrid name/semantic matching
- **Database**: SQLite (simple, reliable, portable)
- **Web Interface**: Flask + Tailwind CSS
- **Hosting**: Railway (with automated deployments)
- **Cost**: ~$8-10/month (mostly AI API calls)

The entire system is built with Python and runs on a single small server.

## Who built this?

This database was created as a research tool to make Asia Society's speaker network more discoverable. It demonstrates how AI and automation can help surface expertise and facilitate connections.

The system is maintained by Nico Luchsinger (nico.luchsinger@gmail.com)
