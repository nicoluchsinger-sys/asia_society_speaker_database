"""
Consolidated pipeline for scheduled execution on Railway

Runs twice daily (6 AM/PM UTC) to:
1. Scrape 20 events using TWO-PHASE strategy:
   - Phase 1: NEW events (pages 0-5, captures recent publications)
   - Phase 2: HISTORICAL backfill (auto-calculated start page, works through history)
2. Extract speakers from new events
3. Generate embeddings for new speakers
4. Enrich NEW speakers first (priority)
5. Enrich 20 existing speakers (backfill)

Two-phase scraping handles dynamic pagination where new events push older
ones to higher page numbers. Historical scraper auto-adjusts based on DB size.

Designed to complete within 25 minutes to fit Railway's execution limits.
Tracks API costs and logs progress.
"""

import os
import sys
import time
import logging
from datetime import datetime, timezone
from database import SpeakerDatabase
from selenium_scraper import SeleniumEventScraper
from speaker_extractor import SpeakerExtractor
from speaker_tagger import SpeakerTagger
from generate_embeddings import generate_embeddings

# Configure logging for pipeline - log to both console and file
log_file = 'pipeline_debug.log'
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler(log_file, mode='a')  # File output (append mode)
    ]
)
logger = logging.getLogger(__name__)


class PipelineStats:
    """Track pipeline execution statistics and costs"""

    def __init__(self):
        self.start_time = datetime.now()
        self.events_scraped = 0
        self.speakers_extracted = 0
        self.speakers_enriched = 0
        self.existing_enriched = 0
        self.embeddings_generated = 0

        # API costs (based on current pricing - all using Claude 3 Haiku)
        self.extraction_cost_per_event = 0.0025  # per event (Claude 3 Haiku)
        self.embedding_cost_per_speaker = 0.00001  # per speaker (text-embedding-3-small)
        self.enrichment_cost_per_speaker = 0.0008  # per speaker (Claude 3 Haiku + web search)

        # Track costs by service
        self.extraction_cost = 0.0  # Claude for extraction
        self.embedding_cost = 0.0   # OpenAI for embeddings
        self.enrichment_cost = 0.0  # Claude + DDG for enrichment
        self.total_cost = 0.0

    def add_extraction(self, event_count):
        self.events_scraped += event_count
        cost = event_count * self.extraction_cost_per_event
        self.extraction_cost += cost
        self.total_cost += cost
        return cost

    def add_embeddings(self, speaker_count):
        self.embeddings_generated += speaker_count
        cost = speaker_count * self.embedding_cost_per_speaker
        self.embedding_cost += cost
        self.total_cost += cost
        return cost

    def add_enrichment(self, speaker_count, is_existing=False):
        if is_existing:
            self.existing_enriched += speaker_count
        else:
            self.speakers_enriched += speaker_count
        cost = speaker_count * self.enrichment_cost_per_speaker
        self.enrichment_cost += cost
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
    """Log message using proper logging (captured by Railway)"""
    logger.info(message)


def scrape_events(db, event_limit=20):
    """
    Two-phase scraping strategy:
    1. NEW EVENTS: Capture recently published events (pages 0-N)
    2. HISTORICAL BACKFILL: Systematically fill in historical events

    Returns:
        tuple: (total_scraped_count, list_of_newly_scraped_event_ids)
    """
    log(f"Starting two-phase scraping (target: {event_limit} events total)...")

    total_scraped = 0
    newly_scraped_ids = []

    # Get event IDs before scraping to identify new ones
    cursor = db.conn.cursor()
    cursor.execute('SELECT event_id FROM events')
    existing_ids_before = set(row[0] for row in cursor.fetchall())

    # PHASE 1: Scrape new events (recent publications)
    log("Phase 1: Scraping new events...")
    scraper_new = SeleniumEventScraper()
    try:
        new_count = scraper_new.scrape_events(
            db=db,
            limit=None,  # No limit - get all new events
            mode='new',
            max_pages=5  # Check first 5 pages max
        )
        total_scraped += new_count
        log(f"  → Found {new_count} new events")
    except Exception as e:
        log(f"  ERROR in new events scraper: {e}")
    finally:
        scraper_new.close()

    # PHASE 2: Historical backfill (if we haven't met limit yet)
    remaining = event_limit - total_scraped
    if remaining > 0:
        log(f"Phase 2: Historical backfill ({remaining} events needed)...")
        scraper_historical = SeleniumEventScraper()
        try:
            historical_count = scraper_historical.scrape_events(
                db=db,
                limit=remaining,
                mode='historical',
                max_pages='auto'
            )
            total_scraped += historical_count
            log(f"  → Found {historical_count} historical events")
        except Exception as e:
            log(f"  ERROR in historical scraper: {e}")
        finally:
            scraper_historical.close()

    # Get newly scraped event IDs by finding the difference
    cursor.execute('SELECT event_id FROM events')
    existing_ids_after = set(row[0] for row in cursor.fetchall())
    newly_scraped_ids = list(existing_ids_after - existing_ids_before)

    log(f"Scraping complete: {total_scraped} total events ({new_count} new + {total_scraped - new_count} historical)")
    log(f"  Event IDs to extract immediately: {newly_scraped_ids[:5]}..." if len(newly_scraped_ids) > 5 else f"  Event IDs to extract immediately: {newly_scraped_ids}")

    return total_scraped, newly_scraped_ids


def extract_speakers(db, newly_scraped_ids=None, pending_limit=None):
    """
    Extract speakers from pending events

    Args:
        newly_scraped_ids: List of event IDs that were just scraped (process these first)
        pending_limit: Maximum number of ADDITIONAL pending events to process (retries)

    Returns:
        tuple: (num_speakers_extracted, num_events_processed)
    """
    log("Starting speaker extraction...")

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        log("ERROR: ANTHROPIC_API_KEY not found")
        return 0, 0

    extractor = SpeakerExtractor(api_key=api_key)

    # Build list of events to process
    events_to_process = []

    # 1. Add newly scraped events (process immediately)
    if newly_scraped_ids:
        cursor = db.conn.cursor()
        placeholders = ','.join('?' * len(newly_scraped_ids))
        cursor.execute(f'''
            SELECT event_id, url, title, body_text
            FROM events
            WHERE event_id IN ({placeholders})
            AND processing_status = 'pending'
        ''', newly_scraped_ids)
        new_events = cursor.fetchall()
        events_to_process.extend(new_events)
        log(f"Processing {len(new_events)} newly scraped events...")

    # 2. Add older pending events (retries), excluding the ones we just scraped
    if pending_limit and pending_limit > 0:
        exclude_ids = set(newly_scraped_ids) if newly_scraped_ids else set()
        cursor = db.conn.cursor()

        # Get older pending events, excluding newly scraped ones
        if exclude_ids:
            placeholders = ','.join('?' * len(exclude_ids))
            cursor.execute(f'''
                SELECT event_id, url, title, body_text
                FROM events
                WHERE processing_status = 'pending'
                AND event_id NOT IN ({placeholders})
                AND (extraction_attempts IS NULL OR extraction_attempts < 3)
                ORDER BY extraction_attempts ASC, event_id ASC
                LIMIT ?
            ''', (*exclude_ids, pending_limit))
        else:
            cursor.execute('''
                SELECT event_id, url, title, body_text
                FROM events
                WHERE processing_status = 'pending'
                AND (extraction_attempts IS NULL OR extraction_attempts < 3)
                ORDER BY extraction_attempts ASC, event_id ASC
                LIMIT ?
            ''', (pending_limit,))

        retry_events = cursor.fetchall()
        events_to_process.extend(retry_events)
        if retry_events:
            log(f"Processing {len(retry_events)} older pending events (retries)...")

    if not events_to_process:
        log("No pending events to process")
        return 0, 0

    events_processed = len(events_to_process)
    log(f"Total events to process: {events_processed}")

    initial_speaker_count = db.get_statistics()['total_speakers']

    for event in events_to_process:
        event_id = event[0]
        event_url = event[1]      # URL (was incorrectly labeled as event_title)
        event_title = event[2]    # Actual title
        body_text = event[3]

        # Increment attempt counter before processing (prevents infinite retries)
        db.increment_extraction_attempts(event_id)

        try:
            result = extractor.extract_speakers(event_title, body_text)

            if result['success'] and result['speakers']:
                # Add each speaker to database
                for speaker_data in result['speakers']:
                    # Skip speakers with no name (Claude extraction issue)
                    speaker_name = speaker_data.get('name')
                    if not speaker_name or not speaker_name.strip():
                        log(f"  ⚠ Skipping speaker with no name: {speaker_data}")
                        continue

                    speaker_id = db.add_speaker(
                        name=speaker_name.strip(),
                        title=speaker_data.get('title'),
                        affiliation=speaker_data.get('affiliation'),
                        bio=speaker_data.get('bio')
                    )

                    # Link speaker to event
                    if speaker_id:
                        db.link_speaker_to_event(
                            event_id=event_id,
                            speaker_id=speaker_id,
                            role_in_event=speaker_data.get('role', 'speaker')
                        )

                # Mark event as completed
                db.mark_event_processed(event_id, 'completed')
                log(f"  ✓ Extracted {len(result['speakers'])} speakers from: {event_title}")
            else:
                db.mark_event_processed(event_id, 'failed')
                log(f"  ✗ FAILED: {event_title}")
                log(f"    URL: {event_url}")

        except Exception as e:
            log(f"  ERROR processing event {event_id}: {e}")
            db.mark_event_processed(event_id, 'failed')

    final_speaker_count = db.get_statistics()['total_speakers']
    new_speakers = final_speaker_count - initial_speaker_count

    log(f"Extraction complete: {new_speakers} new speakers added from {events_processed} events")
    return new_speakers, events_processed


def generate_speaker_embeddings(db):
    """
    Generate embeddings for speakers without them

    Returns:
        int: Number of embeddings generated
    """
    log("Generating embeddings for new speakers...")

    # Commit transaction so embeddings can see newly added speakers
    db.conn.commit()

    initial_count = db.count_embeddings()

    try:
        # Pass database path to ensure correct database is used
        generate_embeddings(batch_size=50, provider='openai', verbose=False, db_path=db.db_path)
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

    # Commit transaction so enrichment can see newly added speakers
    db.conn.commit()

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

        except TimeoutError as e:
            log(f"  TIMEOUT enriching {name}: {e}")
            db.mark_speaker_tagged(speaker_id, 'failed')
        except Exception as e:
            log(f"  ERROR enriching {name}: {e}")
            # Try to mark as failed, but don't crash if this fails
            try:
                db.mark_speaker_tagged(speaker_id, 'failed')
            except:
                pass

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

        except TimeoutError as e:
            log(f"  TIMEOUT enriching {speaker_name}: {e}")
            db.mark_speaker_tagged(speaker_id, 'failed')
        except Exception as e:
            log(f"  ERROR enriching {speaker_name}: {e}")
            # Try to mark as failed, but don't crash if this fails
            try:
                db.mark_speaker_tagged(speaker_id, 'failed')
            except:
                pass

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
            extraction_cost REAL DEFAULT 0,
            embedding_cost REAL DEFAULT 0,
            enrichment_cost REAL DEFAULT 0,
            total_cost REAL,
            success BOOLEAN
        )
    """)

    # Migrate existing table - add cost breakdown columns if they don't exist
    cursor.execute("PRAGMA table_info(pipeline_runs)")
    existing_columns = [row[1] for row in cursor.fetchall()]

    if 'extraction_cost' not in existing_columns:
        cursor.execute("ALTER TABLE pipeline_runs ADD COLUMN extraction_cost REAL DEFAULT 0")
    if 'embedding_cost' not in existing_columns:
        cursor.execute("ALTER TABLE pipeline_runs ADD COLUMN embedding_cost REAL DEFAULT 0")
    if 'enrichment_cost' not in existing_columns:
        cursor.execute("ALTER TABLE pipeline_runs ADD COLUMN enrichment_cost REAL DEFAULT 0")

    cursor.execute("""
        INSERT INTO pipeline_runs (
            timestamp, duration_seconds, events_scraped, speakers_extracted,
            embeddings_generated, new_speakers_enriched, existing_speakers_enriched,
            extraction_cost, embedding_cost, enrichment_cost, total_cost, success
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now(timezone.utc).isoformat(),
        stats.get_duration(),
        stats.events_scraped,
        stats.speakers_extracted,
        stats.embeddings_generated,
        stats.speakers_enriched,
        stats.existing_enriched,
        stats.extraction_cost,
        stats.embedding_cost,
        stats.enrichment_cost,
        stats.total_cost,
        True
    ))

    db.conn.commit()
    log("Pipeline run saved to database")


def run_pipeline(event_limit=10, existing_limit=10, pending_limit=5):
    """
    Run the complete pipeline

    Args:
        event_limit: Number of new events to scrape
        existing_limit: Number of existing speakers to enrich
        pending_limit: Number of pending/failed events to retry (default: 5)
    """
    stats = PipelineStats()

    print("\n" + "="*70)
    print("CONSOLIDATED PIPELINE - STARTING")
    print("="*70)
    print(f"Event limit: {event_limit}")
    print(f"Pending event limit: {pending_limit}")
    print(f"Existing speaker limit: {existing_limit}")
    print("="*70)

    db_path = get_db_path()
    log(f"Using database: {db_path}")

    with SpeakerDatabase(db_path) as db:
        try:
            # Step 1: Scrape events (adds to pending, returns IDs of newly scraped)
            scraped_count, newly_scraped_ids = scrape_events(db, event_limit=event_limit)
            stats.events_scraped = scraped_count

            # Step 2: Extract speakers from newly scraped events + older pending events
            # This processes ALL newly scraped events immediately, PLUS pending_limit retries
            extracted_speakers, events_processed = extract_speakers(
                db,
                newly_scraped_ids=newly_scraped_ids,
                pending_limit=pending_limit
            )
            stats.speakers_extracted = extracted_speakers

            # Track extraction cost (for all events actually processed via Claude API)
            extraction_cost = events_processed * stats.extraction_cost_per_event
            stats.extraction_cost += extraction_cost
            stats.total_cost += extraction_cost

            # Step 3: Enrich NEW speakers first (adds tags before embedding)
            if extracted_speakers > 0:
                enriched_new = enrich_new_speakers(db, stats)
                stats.add_enrichment(enriched_new, is_existing=False)

                # Step 4: Generate embeddings for new speakers (includes tags now!)
                embeddings = generate_speaker_embeddings(db)
                stats.add_embeddings(embeddings)

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
    parser.add_argument('-p', '--pending', type=int, default=5,
                        help='Number of pending/failed events to retry (default: 5)')
    parser.add_argument('-x', '--existing', type=int, default=10,
                        help='Number of existing speakers to enrich (default: 10)')
    parser.add_argument('--test', action='store_true',
                        help='Test mode: scrape 2 events, retry 2 pending, enrich 2 existing speakers')

    args = parser.parse_args()

    if args.test:
        log("Running in TEST mode (2 events, 2 pending, 2 existing speakers)")
        success = run_pipeline(event_limit=2, existing_limit=2, pending_limit=2)
    else:
        success = run_pipeline(event_limit=args.events, existing_limit=args.existing, pending_limit=args.pending)

    sys.exit(0 if success else 1)
