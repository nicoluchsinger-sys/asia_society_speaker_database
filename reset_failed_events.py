#!/usr/bin/env python3
"""
One-time script to reset failed events back to pending status.

Use this after fixing bugs that caused extraction failures, to give
those events another chance at speaker extraction.

IMPORTANT: Don't run this repeatedly - it's for one-time bug fixes.
For persistent failures, investigate the root cause instead.
"""

from database import SpeakerDatabase
import sys


def reset_failed_events(dry_run=True):
    """
    Reset events with processing_status='failed' back to 'pending'

    Args:
        dry_run: If True, just show what would be reset without actually doing it
    """
    db_path = 'speakers.db'

    with SpeakerDatabase(db_path) as db:
        cursor = db.conn.cursor()

        # Get count of failed events
        cursor.execute("SELECT COUNT(*) FROM events WHERE processing_status = 'failed'")
        failed_count = cursor.fetchone()[0]

        if failed_count == 0:
            print("✓ No failed events to reset")
            return

        # Get some examples
        cursor.execute("""
            SELECT event_id, title, url
            FROM events
            WHERE processing_status = 'failed'
            ORDER BY event_id DESC
            LIMIT 5
        """)
        examples = cursor.fetchall()

        print(f"Found {failed_count} failed events")
        print("\nExamples of events that will be reset:")
        print("-" * 80)
        for event_id, title, url in examples:
            print(f"  [{event_id}] {title[:60]}...")
            print(f"       {url}")

        if failed_count > 5:
            print(f"  ... and {failed_count - 5} more")

        if dry_run:
            print("\n⚠ DRY RUN MODE - No changes made")
            print("Run with --execute to actually reset these events")
            return

        # Actually reset the events
        cursor.execute("""
            UPDATE events
            SET processing_status = 'pending'
            WHERE processing_status = 'failed'
        """)
        db.conn.commit()

        print(f"\n✓ Reset {failed_count} events from 'failed' to 'pending'")
        print("These will be reprocessed in the next pipeline run")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Reset failed events to pending for reprocessing'
    )
    parser.add_argument('--execute', action='store_true',
                        help='Actually reset events (default is dry-run)')

    args = parser.parse_args()

    reset_failed_events(dry_run=not args.execute)
