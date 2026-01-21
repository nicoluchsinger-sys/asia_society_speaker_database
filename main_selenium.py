"""
Main script to scrape events and extract speaker information (Selenium version)
With optional timing and API cost tracking (--stats flag)
"""

import os
import argparse
import time
from datetime import datetime
from database import SpeakerDatabase
from selenium_scraper import SeleniumEventScraper
from speaker_extractor import SpeakerExtractor
from speaker_tagger import SpeakerTagger
import json


# Anthropic pricing (as of 2024) - per million tokens
PRICING = {
    'claude-sonnet-4-20250514': {
        'input': 3.00,   # $3 per 1M input tokens
        'output': 15.00  # $15 per 1M output tokens
    }
}


class PipelineStats:
    """Track timing and API usage across pipeline steps"""

    def __init__(self, enabled=True):
        self.enabled = enabled
        self.steps = {}
        self.current_step = None
        self.start_time = None
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.api_calls = 0

    def start_step(self, name):
        if not self.enabled:
            return
        self.current_step = name
        self.start_time = time.time()
        self.steps[name] = {
            'start': self.start_time,
            'duration': 0,
            'input_tokens': 0,
            'output_tokens': 0,
            'api_calls': 0,
            'items_processed': 0
        }

    def end_step(self, items_processed=0):
        if not self.enabled or not self.current_step:
            return
        duration = time.time() - self.start_time
        self.steps[self.current_step]['duration'] = duration
        self.steps[self.current_step]['items_processed'] = items_processed
        self.current_step = None

    def add_api_usage(self, input_tokens, output_tokens):
        if not self.enabled:
            return
        if self.current_step and self.current_step in self.steps:
            self.steps[self.current_step]['input_tokens'] += input_tokens
            self.steps[self.current_step]['output_tokens'] += output_tokens
            self.steps[self.current_step]['api_calls'] += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.api_calls += 1

    def print_summary(self):
        if not self.enabled or not self.steps:
            return

        print("\n" + "="*70)
        print("📊 PIPELINE EXECUTION SUMMARY")
        print("="*70)

        total_duration = sum(s['duration'] for s in self.steps.values())

        print(f"\n⏱️  TIMING")
        print("-"*70)
        for name, data in self.steps.items():
            duration = data['duration']
            items = data['items_processed']
            pct = (duration / total_duration * 100) if total_duration > 0 else 0
            items_str = f" ({items} items)" if items > 0 else ""
            print(f"  {name:30} {duration:8.2f}s  ({pct:5.1f}%){items_str}")
        print("-"*70)
        print(f"  {'TOTAL':30} {total_duration:8.2f}s")

        if self.api_calls > 0:
            print(f"\n🤖 API USAGE")
            print("-"*70)
            print(f"  Total API calls:        {self.api_calls:,}")
            print(f"  Total input tokens:     {self.total_input_tokens:,}")
            print(f"  Total output tokens:    {self.total_output_tokens:,}")
            print(f"  Total tokens:           {self.total_input_tokens + self.total_output_tokens:,}")

            print(f"\n💰 ESTIMATED COST (Claude Sonnet)")
            print("-"*70)
            pricing = PRICING['claude-sonnet-4-20250514']
            input_cost = (self.total_input_tokens / 1_000_000) * pricing['input']
            output_cost = (self.total_output_tokens / 1_000_000) * pricing['output']
            total_cost = input_cost + output_cost
            print(f"  Input tokens cost:      ${input_cost:.4f}")
            print(f"  Output tokens cost:     ${output_cost:.4f}")
            print(f"  TOTAL COST:             ${total_cost:.4f}")

            # Per-step breakdown
            print(f"\n📈 API USAGE BY STEP")
            print("-"*70)
            for name, data in self.steps.items():
                if data['api_calls'] > 0:
                    step_input = data['input_tokens']
                    step_output = data['output_tokens']
                    step_cost = (step_input / 1_000_000) * pricing['input'] + \
                               (step_output / 1_000_000) * pricing['output']
                    print(f"  {name}:")
                    print(f"    API calls: {data['api_calls']}, Tokens: {step_input + step_output:,}, Cost: ${step_cost:.4f}")


def load_api_key():
    """Load API key from .env file or environment"""
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('ANTHROPIC_API_KEY='):
                    key = line.split('=', 1)[1].strip()
                    os.environ['ANTHROPIC_API_KEY'] = key
                    return key
    return os.getenv('ANTHROPIC_API_KEY')


def scrape_events(db, limit=None, headless=True, max_pages=1, base_url=None, stats=None):
    """Step 1: Scrape events from website using Selenium and save to database"""
    print("\n" + "🌐 STEP 1: SCRAPING EVENTS FROM WEBSITE (SELENIUM)")
    print("="*70)

    if stats:
        stats.start_step("1. Scraping")

    if base_url is None:
        base_url = "https://asiasociety.org/switzerland/events/past"

    scraper = SeleniumEventScraper(base_url=base_url, headless=headless)
    count = scraper.scrape_events(db, limit=limit, max_pages=max_pages)

    db_stats = db.get_statistics()
    print(f"\n📊 Current Database Status:")
    print(f"   Total events in database: {db_stats['total_events']}")
    print(f"   Unprocessed events: {db_stats['total_events'] - db_stats['processed_events']}")

    if stats:
        stats.end_step(count)

    return count


def extract_speakers(db, stats=None):
    """Step 2: Use AI to extract speakers from scraped events"""
    print("\n\n" + "🤖 STEP 2: EXTRACTING SPEAKERS WITH AI")
    print("="*70)

    if stats:
        stats.start_step("2. Extraction")

    api_key = load_api_key()
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY not found!")
        print("   Please create a .env file with: ANTHROPIC_API_KEY=your_key_here")
        if stats:
            stats.end_step(0)
        return 0

    print("✓ API key loaded")

    unprocessed = db.get_unprocessed_events()

    if not unprocessed:
        print("\n✓ All events have been processed!")
        if stats:
            stats.end_step(0)
        return 0

    print(f"\nFound {len(unprocessed)} unprocessed event(s)")
    print("-"*70)

    extractor = SpeakerExtractor(api_key=api_key)
    total_speakers = 0

    for event_id, url, title, body_text in unprocessed:
        print(f"\n📄 Processing Event ID {event_id}")
        print(f"   Title: {title[:70]}...")

        result = extractor.extract_speakers(title, body_text)

        # Track API usage
        if stats and hasattr(extractor, '_last_usage'):
            stats.add_api_usage(
                extractor._last_usage.get('input_tokens', 0),
                extractor._last_usage.get('output_tokens', 0)
            )

        if result['success']:
            speakers = result['speakers']
            print(f"   ✓ Found {len(speakers)} speaker(s)")

            for speaker_data in speakers:
                speaker_id = db.add_speaker(
                    name=speaker_data.get('name'),
                    title=speaker_data.get('title'),
                    affiliation=speaker_data.get('affiliation'),
                    primary_affiliation=speaker_data.get('primary_affiliation'),
                    bio=speaker_data.get('bio')
                )

                db.link_speaker_to_event(
                    event_id=event_id,
                    speaker_id=speaker_id,
                    role_in_event=speaker_data.get('role_in_event'),
                    extracted_info=json.dumps(speaker_data)
                )

                print(f"     - {speaker_data.get('name')} ({speaker_data.get('role_in_event', 'participant')})")
                total_speakers += 1

            db.mark_event_processed(event_id, 'completed')
        else:
            print(f"   ❌ Error: {result['error']}")
            db.mark_event_processed(event_id, 'failed')

    # Clean up any duplicates that slipped through fuzzy matching
    merged = db.merge_duplicates(verbose=True)

    print("\n" + "="*70)
    print(f"✓ Extraction complete: {total_speakers} speaker records created")
    if merged:
        print(f"✓ Merged {merged} duplicate speaker(s)")

    if stats:
        stats.end_step(total_speakers)

    return total_speakers


def tag_speakers(db, limit=None, stats=None):
    """Step 3: Tag speakers with expertise tags using web search and Claude AI"""
    print("\n\n" + "🏷️  STEP 3: TAGGING SPEAKERS WITH AI")
    print("="*70)

    if stats:
        stats.start_step("3. Tagging")

    api_key = load_api_key()
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY not found!")
        if stats:
            stats.end_step(0)
        return 0

    print("✓ API key loaded")

    untagged = db.get_untagged_speakers()

    if not untagged:
        print("\n✓ All speakers have been tagged!")
        if stats:
            stats.end_step(0)
        return 0

    if limit:
        untagged = untagged[:limit]
        print(f"\nLimiting to {limit} speaker(s)")

    print(f"\nFound {len(untagged)} untagged speaker(s)")
    print("-"*70)

    tagger = SpeakerTagger(api_key=api_key)
    tagged_count = 0

    for speaker_row in untagged:
        speaker_id = speaker_row[0]
        speaker_name = speaker_row[1]

        print(f"\n🏷️  Tagging: {speaker_name}")

        result = tagger.tag_speaker(speaker_id, db)

        # Track API usage
        if stats and hasattr(tagger, '_last_usage'):
            stats.add_api_usage(
                tagger._last_usage.get('input_tokens', 0),
                tagger._last_usage.get('output_tokens', 0)
            )

        if result['success']:
            tags_str = ', '.join([t['text'] for t in result['tags']])
            print(f"   ✓ Tags: {tags_str}")
            tagged_count += 1
        else:
            print(f"   ✗ Error: {result['error']}")

        time.sleep(1.5)  # Rate limiting for web search

    print("\n" + "="*70)
    print(f"✓ Tagging complete: {tagged_count} speakers tagged")

    if stats:
        stats.end_step(tagged_count)

    return tagged_count


def show_statistics(db):
    """Display database statistics and sample data"""
    print("\n\n" + "📊 DATABASE STATISTICS")
    print("="*70)

    db_stats = db.get_statistics()

    print(f"\nEvents:")
    print(f"  Total events: {db_stats['total_events']}")
    print(f"  Processed: {db_stats['processed_events']}")
    print(f"  Pending: {db_stats['total_events'] - db_stats['processed_events']}")

    print(f"\nSpeakers:")
    print(f"  Total unique speakers: {db_stats['total_speakers']}")
    print(f"  Tagged speakers: {db_stats['tagged_speakers']}")
    print(f"  Total tags: {db_stats['total_tags']}")
    print(f"  Total speaker-event connections: {db_stats['total_connections']}")

    speakers = db.get_all_speakers()
    if speakers:
        print(f"\n📋 Sample Speakers (showing first 10):")
        print("-"*70)
        for speaker in speakers[:10]:
            speaker_id, name, title, affiliation, bio, first_seen, last_updated = speaker
            print(f"\n  {name}")
            if title:
                print(f"    Title: {title}")
            if affiliation:
                print(f"    Affiliation: {affiliation}")

            events = db.get_speaker_events(speaker_id)
            if events:
                print(f"    Events: {len(events)}")

            tags = db.get_speaker_tags(speaker_id)
            if tags:
                tags_str = ', '.join([t[0] for t in tags])
                print(f"    Tags: {tags_str}")


def export_speakers_to_csv(db, stats=None):
    """Export all speakers to a CSV file"""
    import csv

    print("\n\n" + "💾 EXPORTING SPEAKERS TO CSV")
    print("="*70)

    if stats:
        stats.start_step("4. Export")

    speakers = db.get_all_speakers()

    if not speakers:
        print("No speakers to export")
        if stats:
            stats.end_step(0)
        return

    filename = f"speakers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['ID', 'Name', 'Title', 'Affiliation', 'Bio', 'Tags', 'First Seen', 'Last Updated', 'Number of Events'])

        for speaker in speakers:
            speaker_id, name, title, affiliation, bio, first_seen, last_updated = speaker
            events = db.get_speaker_events(speaker_id)
            tags = db.get_speaker_tags(speaker_id)
            tags_str = '; '.join([t[0] for t in tags]) if tags else ''

            writer.writerow([speaker_id, name, title or '', affiliation or '', bio or '', tags_str, first_seen, last_updated, len(events)])

    print(f"✓ Exported {len(speakers)} speakers to {filename}")

    if stats:
        stats.end_step(len(speakers))


def main():
    """Main workflow"""
    parser = argparse.ArgumentParser(
        description='Asia Society Speaker Database Builder (Selenium Version)'
    )
    parser.add_argument('-e', '--events', type=str, default='5',
                        help='Number of events to scrape (number or "all", default: 5)')
    parser.add_argument('--headless', action='store_true', default=True,
                        help='Run browser in headless mode (default)')
    parser.add_argument('--no-headless', dest='headless', action='store_false',
                        help='Show browser window while scraping')
    parser.add_argument('--extract', action='store_true', default=True,
                        help='Extract speakers using AI (default)')
    parser.add_argument('--no-extract', dest='extract', action='store_false',
                        help='Skip speaker extraction')
    parser.add_argument('--export', action='store_true', default=False,
                        help='Export speakers to CSV')
    parser.add_argument('--skip-scrape', action='store_true', default=False,
                        help='Skip scraping, only run extraction/export on existing data')
    parser.add_argument('-p', '--pages', type=str, default='1',
                        help='Number of listing pages to scrape (number or "all", default: 1)')
    parser.add_argument('--tag', action='store_true', default=False,
                        help='Tag speakers with expertise tags after extraction')
    parser.add_argument('--tag-limit', type=int, default=None,
                        help='Limit number of speakers to tag (for testing)')
    parser.add_argument('--url', type=str, default=None,
                        help='Base URL for events (default: Switzerland events)')
    parser.add_argument('--stats', action='store_true', default=False,
                        help='Show timing and API cost statistics at the end')

    args = parser.parse_args()

    # Parse events limit
    if args.skip_scrape:
        limit = 0
    elif args.events.lower() == 'all':
        limit = None
    else:
        try:
            limit = int(args.events)
        except ValueError:
            limit = 5
            print(f"Invalid events value, using default: {limit}")

    # Parse pages limit
    if args.pages.lower() == 'all':
        max_pages = None
    else:
        try:
            max_pages = int(args.pages)
        except ValueError:
            max_pages = 1
            print(f"Invalid pages value, using default: {max_pages}")

    # Initialize stats tracker
    stats = PipelineStats(enabled=args.stats)

    print("="*70)
    print("ASIA SOCIETY - SPEAKER DATABASE BUILDER")
    print("(Selenium Version - bypasses 403 errors)")
    print("="*70)

    if args.stats:
        print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print("\nThis tool will:")
    print("1. Scrape event pages using Selenium (real browser)")
    print("2. Use AI to extract speaker information")
    print("3. Optionally tag speakers with expertise tags (--tag)")
    print("4. Store everything in a SQLite database")

    print("\n" + "-"*70)
    print("NOTE: This requires Chrome browser to be installed.")
    print("-"*70)

    # Use a single database connection for the entire pipeline
    with SpeakerDatabase() as db:
        # Step 1: Scrape events
        if args.skip_scrape:
            print("\nSkipping scraping (--skip-scrape)")
            scraped = 0
        else:
            scraped = scrape_events(
                db,
                limit=limit,
                headless=args.headless,
                max_pages=max_pages,
                base_url=args.url,
                stats=stats
            )
            if scraped == 0:
                print("\n⚠ No new events were scraped.")

        # Step 2: Extract speakers
        if args.extract:
            extract_speakers(db, stats=stats)
        else:
            print("\nSkipping speaker extraction.")

        # Step 3: Tag speakers (optional)
        if args.tag:
            tag_speakers(db, limit=args.tag_limit, stats=stats)
        else:
            print("\nSkipping speaker tagging. Use --tag to enable.")

        # Show results
        show_statistics(db)

        # Export option
        if args.export:
            export_speakers_to_csv(db, stats=stats)

    print("\n" + "="*70)
    print("✓ COMPLETE")
    print("="*70)
    print(f"\nDatabase saved as: speakers.db")
    print("You can:")
    print("  - Run this script again to scrape more events")
    print("  - View the database with SQLite browser")
    print("  - Use the database for further analysis")

    # Print stats summary if enabled
    stats.print_summary()


if __name__ == "__main__":
    main()
