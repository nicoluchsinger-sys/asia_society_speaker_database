# Frequently Asked Questions (FAQ)

## What is this database, and why does it exist?

The Asia Society Speaker Database is a searchable collection of speakers who have participated in Asia Society events worldwide. It helps you discover experts, thought leaders, and practitioners across various fields related to Asia and global affairs.

Currently, the database contains **{{total_speakers}} speakers** from **{{total_events}} events** spanning from {{oldest_event_date}} to {{newest_event_date}}.

The database solves a fundamental problem: A global database of speakers would be great to have for a distributed organization like Asia Society, but building and maintaining it manually was never viable. This automated approach leverages the fact that most information is already public - either on the Asia Society website, or on the wider web. It uses AI to extract speaker information from published events, and to regularly enrich and update their profiles. The result is a comprehensive database that updates automatically for a total cost of around $8 per month (see breakdown below).

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
   - Languages spoken (when mentioned)
4. **Search Indexing**: Speaker profiles are converted into semantic embeddings that enable intelligent search
   - Embeddings include biographical data, expertise tags, and **event participation history**
   - Each speaker's 10 most recent events are included with titles and topic descriptions
   - This enables topic-based discovery (e.g., finding "climate experts" finds speakers from climate events)

All data comes from publicly available information on Asia Society's website.

## How does the search work?

The search combines multiple approaches to find the most relevant speakers:

**1. Exact Name Matching**
If you search for a specific person by name (e.g., "James Crabtree"), the system will find exact or partial matches.

**2. Semantic Search with Event Context**
When you search by topic or expertise (e.g., "climate policy experts" or "Southeast Asia trade"), the system understands the meaning of your query and finds speakers based on:
- Their biographical information and expertise tags
- **Events they've participated in** - including event titles and topics
- Speaking roles (keynote speakers, panelists, moderators)

This means searching for "climate experts" will find speakers who participated in climate-related events, even if their bio doesn't explicitly mention climate.

**3. Smart Ranking**
Results are ranked by:
- Topic relevance (how well expertise and event history matches your query)
- Name matches (get highest priority)
- Profile quality (speakers with detailed bios and multiple events rank higher)
- Activity level (frequent speakers rank higher, keynote speakers especially)

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

Additionally, existing speaker profile are reviewed and updated every six months.

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

The system prioritizes **accuracy over completeness** and takes a conservative approach in profile enrichment. Only if the system has a high degree of confidence that information is accurate is it added to a profile. This means that some profiles are missing information that couldn't be verified with confidence. But this is a fully automated system that runs without human review, so it's always possible that the data contains errors or outdated information.

## Can I update a speaker record?

Yes you can suggest edits for any speaker on their profile page. The system will try to verify the information using a web search, and update the profile if it is confident the information is accurate. If verification is not possible, your suggested edit will be attached to the speaker profile as a comment.

## What technology powers this?

For those interested in the technical details:

- **Web Scraping**: Selenium WebDriver (to handle dynamic content)
- **Speaker Extraction**: Anthropic Claude AI (Sonnet 4 model for extraction)
- **Speaker Enrichment**: Claude 3 Haiku (91% cheaper than Sonnet 4, equivalent quality)
- **Search**: OpenAI embeddings with hybrid name/semantic matching + event context
- **Database**: SQLite (simple, reliable, portable)
- **Web Interface**: Flask + Tailwind CSS
- **Hosting**: Railway (with automated deployments)


The entire system is built with Python and runs on a single small server. 

## How much does it cost?

The database uses the Anthropic and OpenAI APIs for various tasks. Each call to the APIs costs a little bit of money. Here is an estimated breakdown of monthly costs:

- **Speaker Extraction**: 600 events x $0.0025 = $1.50
- **Speaker enrichment**: 600 speakers x $0.0023 = $1.38
- **Embedding new speakers**: 360 speakers x $0.00002 = $0.001
- **Search costs**: 150 queries x $0.0006 = $0.09
- **Hosting**: Railway.com Hobby plan = $5

The total monthly costs are around $8.


## Who built this?

This database was created as a research tool to make Asia Society's speaker network more discoverable. It demonstrates how AI and automation can help surface expertise and facilitate connections. It was built using Claude Code by Nico Luchsinger ({{contact_email}}).
