"""
Consolidated pipeline for scheduled execution on Railway

Runs every 2 hours to:
1. Scrape 10 new events
2. Extract speakers from new events
3. Generate embeddings for new speakers
4. Enrich NEW speakers first (priority)
5. Enrich 10 existing untagged speakers (backfill)

Designed to complete within 25 minutes to fit Railway's execution limits.
Tracks API costs and logs progress.
"""

import os
import sys
import time
from datetime import datetime
from database import SpeakerDatabase
from selenium_scraper import SeleniumEventScraper
from speaker_extractor import SpeakerExtractor
from speaker_tagger import SpeakerTagger
from generate_embeddings import generate_embeddings


class PipelineStats:
    """Track pipeline execution statistics and costs"""

    def __init__(self):
        self.start_time = datetime.now()
        self.events_scraped = 0
        self.speakers_extracted = 0
        self.speakers_enriched = 0
        self.existing_enriched = 0
        self.embeddings_generated = 0

        # API costs (based on current pricing)
        self.extraction_cost = 0.015  # per event
        self.embedding_cost = 0.00001  # per speaker (text-embedding-3-small)
        self.enrichment_cost = 0.0075  # per speaker (web search + Claude)

        self.total_cost = 0.0

    def add_extraction(self, event_count):
        self.events_scraped += event_count
        cost = event_count * self.extraction_cost
        self.total_cost += cost
        return cost

    def add_embeddings(self, speaker_count):
        self.embeddings_generated += speaker_count
        cost = speaker_count * self.embedding_cost
        self.total_cost += cost
        return cost

    def add_enrichment(self, speaker_count, is_existing=False):
        if is_existing:
            self.existing_enriched += speaker_count
        else:
            self.speakers_enriched += speaker_count
        cost = speaker_count * self.enrichment_cost
        self.total_cost += cost
        return cost

    def get_duration(self):
        return (datetime.now() - self.start_time).total_seconds()

    def print_summary(self):
        duration = self.get_duration()
        print("\n" + "="*70)
        print("PIPELINE EXECUTION SUMMARY")
        print("="*70)
        print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        print(f"\nEvents scraped: {self.events_scraped}")
        print(f"Speakers extracted: {self.speakers_extracted}")
        print(f"Embeddings generated: {self.embeddings_generated}")
        print(f"New speakers enriched: {self.speakers_enriched}")
        print(f"Existing speakers enriched: {self.existing_enriched}")
        print(f"\nTotal API cost: ${self.total_cost:.4f}")
        print("="*70)


def get_db_path():
    """Get database path - /data/speakers.db on Railway, ./speakers.db locally"""
    if os.path.exists('/data'):
        return '/data/speakers.db'
    else:
        return 'speakers.db'


def log(message):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def scrape_events(db, event_limit=10):
    """
    Scrape new events from Asia Society

    Returns:
        int: Number of events scraped
    """
    log(f"Starting scraping of {event_limit} events...")

    scraper = SeleniumEventScraper()
    try:
        results = scraper.scrape_events(
            db=db,
            limit=event_limit,
            max_pages='auto'
        )

        scraped_count = results.get('new_events', 0)
        log(f"Scraping complete: {scraped_count} new events")
        return scraped_count

    except Exception as e:
        log(f"ERROR during scraping: {e}")
        return 0
    finally:
        scraper.close()


def extract_speakers(db):
    """
    Extract speakers from pending events

    Returns:
        int: Number of speakers extracted
    """
    log("Starting speaker extraction...")

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        log("ERROR: ANTHROPIC_API_KEY not found")
        return 0

    extractor = SpeakerExtractor(api_key=api_key)

    pending_events = db.get_unprocessed_events()
    if not pending_events:
        log("No pending events to process")
        return 0

    log(f"Processing {len(pending_events)} pending events...")

    initial_speaker_count = db.get_statistics()['total_speakers']

    for event in pending_events:
        event_id = event[0]
        event_title = event[1]

        try:
            result = extractor.extract_speakers_from_event(event_id, db)
            if result['success']:
                log(f"  Extracted {len(result['speakers'])} speakers from: {event_title[:50]}")
            else:
                log(f"  FAILED: {event_title[:50]}")
        except Exception as e:
            log(f"  ERROR processing event {event_id}: {e}")

    final_speaker_count = db.get_statistics()['total_speakers']
    new_speakers = final_speaker_count - initial_speaker_count

    log(f"Extraction complete: {new_speakers} new speakers added")
    return new_speakers


def generate_speaker_embeddings(db):
    """
    Generate embeddings for speakers without them

    Returns:
        int: Number of embeddings generated
    """
    log("Generating embeddings for new speakers...")

    initial_count = db.count_embeddings()

    try:
        generate_embeddings(batch_size=50, provider='openai', verbose=False)
    except Exception as e:
        log(f"ERROR generating embeddings: {e}")
        return 0

    final_count = db.count_embeddings()
    new_embeddings = final_count - initial_count

    log(f"Embedding generation complete: {new_embeddings} new embeddings")
    return new_embeddings


def enrich_new_speakers(db, stats):
    """
    Enrich speakers that were just added (no tagging_status yet)

    Returns:
        int: Number of speakers enriched
    """
    log("Enriching newly extracted speakers...")

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        log("ERROR: ANTHROPIC_API_KEY not found")
        return 0

    tagger = SpeakerTagger(api_key=api_key)

    # Get speakers without tagging status (newly added)
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT speaker_id, name
        FROM speakers
        WHERE tagging_status IS NULL OR tagging_status = 'pending'
        ORDER BY speaker_id DESC
    """)
    new_speakers = cursor.fetchall()

    if not new_speakers:
        log("No new speakers to enrich")
        return 0

    enriched_count = 0
    for speaker_id, name in new_speakers:
        try:
            result = tagger.tag_speaker(speaker_id, db)
            if result['success']:
                enriched_count += 1
                log(f"  Enriched: {name}")
            else:
                log(f"  FAILED: {name} - {result.get('error', 'Unknown error')}")

            # Rate limit
            time.sleep(tagger.search_delay)

        except Exception as e:
            log(f"  ERROR enriching {name}: {e}")

    log(f"New speaker enrichment complete: {enriched_count} enriched")
    return enriched_count


def enrich_existing_speakers(db, limit=10):
    """
    Enrich existing untagged speakers (backfill old data)

    Args:
        limit: Maximum number of speakers to enrich

    Returns:
        int: Number of speakers enriched
    """
    log(f"Enriching up to {limit} existing untagged speakers...")

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        log("ERROR: ANTHROPIC_API_KEY not found")
        return 0

    tagger = SpeakerTagger(api_key=api_key)

    # Get oldest untagged speakers (exclude newly added ones)
    untagged = db.get_untagged_speakers()

    if not untagged:
        log("No untagged speakers remaining")
        return 0

    # Limit to specified number
    speakers_to_enrich = untagged[:limit]

    enriched_count = 0
    for speaker_row in speakers_to_enrich:
        speaker_id = speaker_row[0]
        speaker_name = speaker_row[1]

        try:
            result = tagger.tag_speaker(speaker_id, db)
            if result['success']:
                enriched_count += 1
                log(f"  Enriched: {speaker_name}")
            else:
                log(f"  FAILED: {speaker_name} - {result.get('error', 'Unknown error')}")

            # Rate limit
            time.sleep(tagger.search_delay)

        except Exception as e:
            log(f"  ERROR enriching {speaker_name}: {e}")

    log(f"Existing speaker enrichment complete: {enriched_count}/{limit} enriched")
    return enriched_count


def save_pipeline_run(db, stats):
    """Save pipeline run statistics to database"""
    cursor = db.conn.cursor()

    # Create pipeline_runs table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            duration_seconds REAL,
            events_scraped INTEGER,
            speakers_extracted INTEGER,
            embeddings_generated INTEGER,
            new_speakers_enriched INTEGER,
            existing_speakers_enriched INTEGER,
            total_cost REAL,
            success BOOLEAN
        )
    """)

    cursor.execute("""
        INSERT INTO pipeline_runs (
            timestamp, duration_seconds, events_scraped, speakers_extracted,
            embeddings_generated, new_speakers_enriched, existing_speakers_enriched,
            total_cost, success
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        stats.get_duration(),
        stats.events_scraped,
        stats.speakers_extracted,
        stats.embeddings_generated,
        stats.speakers_enriched,
        stats.existing_enriched,
        stats.total_cost,
        True
    ))

    db.conn.commit()
    log("Pipeline run saved to database")


def run_pipeline(event_limit=10, existing_limit=10):
    """
    Run the complete pipeline

    Args:
        event_limit: Number of new events to scrape
        existing_limit: Number of existing speakers to enrich
    """
    stats = PipelineStats()

    print("\n" + "="*70)
    print("CONSOLIDATED PIPELINE - STARTING")
    print("="*70)
    print(f"Event limit: {event_limit}")
    print(f"Existing speaker limit: {existing_limit}")
    print("="*70)

    db_path = get_db_path()
    log(f"Using database: {db_path}")

    with SpeakerDatabase(db_path) as db:
        try:
            # Step 1: Scrape events
            scraped = scrape_events(db, event_limit=event_limit)
            if scraped > 0:
                stats.add_extraction(scraped)

            # Step 2: Extract speakers
            if scraped > 0:
                extracted = extract_speakers(db)
                stats.speakers_extracted = extracted

                # Step 3: Generate embeddings for new speakers
                if extracted > 0:
                    embeddings = generate_speaker_embeddings(db)
                    stats.add_embeddings(embeddings)

                    # Step 4: Enrich NEW speakers first (priority)
                    enriched_new = enrich_new_speakers(db, stats)
                    stats.add_enrichment(enriched_new, is_existing=False)

            # Step 5: Enrich existing untagged speakers (backfill)
            enriched_existing = enrich_existing_speakers(db, limit=existing_limit)
            stats.add_enrichment(enriched_existing, is_existing=True)

            # Save run statistics
            save_pipeline_run(db, stats)

            # Print summary
            stats.print_summary()

            return True

        except Exception as e:
            log(f"FATAL ERROR in pipeline: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Consolidated pipeline for scraping, extraction, and enrichment'
    )
    parser.add_argument('-e', '--events', type=int, default=10,
                        help='Number of events to scrape (default: 10)')
    parser.add_argument('-x', '--existing', type=int, default=10,
                        help='Number of existing speakers to enrich (default: 10)')
    parser.add_argument('--test', action='store_true',
                        help='Test mode: scrape 2 events, enrich 2 existing speakers')

    args = parser.parse_args()

    if args.test:
        log("Running in TEST mode (2 events, 2 existing speakers)")
        success = run_pipeline(event_limit=2, existing_limit=2)
    else:
        success = run_pipeline(event_limit=args.events, existing_limit=args.existing)

    sys.exit(0 if success else 1)
