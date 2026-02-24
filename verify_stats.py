"""
Verify pipeline statistics accuracy

This script checks if the numbers shown in the admin panel match actual database counts.
Run this to audit the accuracy of pipeline_runs statistics.
"""

import sqlite3
from datetime import datetime
import sys
import os

# Auto-detect database path
if os.path.exists('/data'):
    DB_PATH = '/data/speakers.db'
else:
    DB_PATH = 'speakers.db'

def verify_pipeline_stats():
    """Verify that pipeline_runs statistics match actual database state"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("=" * 70)
    print("PIPELINE STATISTICS VERIFICATION")
    print("=" * 70)

    # Get last 3 pipeline runs
    cursor.execute('''
        SELECT run_id, timestamp, events_scraped, speakers_extracted,
               new_speakers_enriched, existing_speakers_enriched,
               embeddings_generated, total_cost
        FROM pipeline_runs
        ORDER BY run_id DESC
        LIMIT 3
    ''')

    runs = cursor.fetchall()

    if not runs:
        print("\n❌ No pipeline runs found in database")
        return

    print(f"\n📊 Last {len(runs)} Pipeline Runs:")
    print("-" * 70)

    for run in runs:
        run_id, timestamp, events_scraped, speakers_extracted, new_enriched, existing_enriched, embeddings, cost = run

        print(f"\nRun #{run_id} - {timestamp}")
        print(f"  Events scraped: {events_scraped}")
        print(f"  Speakers extracted: {speakers_extracted}")
        print(f"  New speakers enriched: {new_enriched}")
        print(f"  Existing speakers enriched: {existing_enriched}")
        print(f"  Embeddings generated: {embeddings}")
        print(f"  Total cost: ${cost:.4f}")

    # Now verify the actual database state
    print("\n" + "=" * 70)
    print("ACTUAL DATABASE STATE")
    print("=" * 70)

    # Count total events
    cursor.execute("SELECT COUNT(*) FROM events")
    total_events = cursor.fetchone()[0]

    # Count events by status
    cursor.execute('''
        SELECT processing_status, COUNT(*)
        FROM events
        GROUP BY processing_status
    ''')
    events_by_status = dict(cursor.fetchall())

    print(f"\n📄 Events:")
    print(f"  Total: {total_events}")
    print(f"  Completed: {events_by_status.get('completed', 0)}")
    print(f"  Pending: {events_by_status.get('pending', 0)}")
    print(f"  Failed: {events_by_status.get('failed', 0)}")

    # Count total speakers
    cursor.execute("SELECT COUNT(*) FROM speakers")
    total_speakers = cursor.fetchone()[0]

    # Count speakers by tagging status
    cursor.execute('''
        SELECT
            CASE
                WHEN tagging_status IS NULL THEN 'untagged'
                ELSE tagging_status
            END as status,
            COUNT(*)
        FROM speakers
        GROUP BY status
    ''')
    speakers_by_status = dict(cursor.fetchall())

    print(f"\n👥 Speakers:")
    print(f"  Total: {total_speakers}")
    print(f"  Completed (enriched): {speakers_by_status.get('completed', 0)}")
    print(f"  Pending (unenriched): {speakers_by_status.get('pending', 0) + speakers_by_status.get('untagged', 0)}")
    print(f"  Failed: {speakers_by_status.get('failed', 0)}")

    # Count embeddings
    cursor.execute("SELECT COUNT(DISTINCT speaker_id) FROM speaker_embeddings")
    speakers_with_embeddings = cursor.fetchone()[0]

    print(f"\n🔢 Embeddings:")
    print(f"  Speakers with embeddings: {speakers_with_embeddings}")
    print(f"  Coverage: {speakers_with_embeddings / total_speakers * 100:.1f}%")

    # VERIFICATION: Check if last run numbers make sense
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)

    last_run = runs[0]
    run_id, timestamp, events_scraped, speakers_extracted, new_enriched, existing_enriched, embeddings, cost = last_run

    print(f"\nLast Run #{run_id}:")

    # Check 1: Were the events actually scraped?
    cursor.execute('''
        SELECT COUNT(*) FROM events
        WHERE datetime(first_scraped) >= datetime(?)
    ''', (timestamp,))
    events_scraped_since = cursor.fetchone()[0]

    if events_scraped_since >= events_scraped:
        print(f"  ✅ Events scraped ({events_scraped}) ≤ Events added since run ({events_scraped_since})")
    else:
        print(f"  ⚠️  MISMATCH: Events scraped ({events_scraped}) > Events added since run ({events_scraped_since})")

    # Check 2: Were speakers actually extracted?
    # This is harder to verify exactly, but we can check if speaker count increased
    print(f"  ℹ️  Speakers extracted: {speakers_extracted} (new speakers added to DB)")
    print(f"      Note: This counts NEW speakers only, not total speakers in events")

    # Check 3: Look for duplicate runs (same numbers)
    cursor.execute('''
        SELECT COUNT(*)
        FROM pipeline_runs
        WHERE events_scraped = ? AND speakers_extracted = ?
    ''', (events_scraped, speakers_extracted))
    duplicate_count = cursor.fetchone()[0]

    if duplicate_count > 1:
        print(f"  ⚠️  Found {duplicate_count} runs with identical stats ({events_scraped} events, {speakers_extracted} speakers)")
        print(f"      This could indicate:")
        print(f"        - Events contain the same speakers (lots of overlap/duplicates)")
        print(f"        - Scraper is finding the same events each time")
    else:
        print(f"  ✅ No duplicate runs found")

    # Show event IDs from recent runs to check for overlap
    print("\n" + "=" * 70)
    print("RECENT EVENT DETAILS")
    print("=" * 70)

    # Get events scraped in last 2 runs (by timestamp)
    if len(runs) >= 2:
        run1_time = runs[0][1]
        run2_time = runs[1][1]

        cursor.execute('''
            SELECT event_id, title, first_scraped
            FROM events
            WHERE datetime(first_scraped) >= datetime(?)
            ORDER BY first_scraped DESC
            LIMIT 10
        ''', (run2_time,))

        recent_events = cursor.fetchall()

        if recent_events:
            print(f"\nLast 10 events scraped (since {run2_time}):")
            for event_id, title, scraped_time in recent_events:
                print(f"  {event_id}: {title[:50]}... (scraped: {scraped_time})")
        else:
            print(f"\n⚠️  No events found scraped since {run2_time}")

    conn.close()
    print("\n" + "=" * 70)


if __name__ == '__main__':
    verify_pipeline_stats()
