#!/usr/bin/env python3
"""
Reset API cost tracking to zero.

This clears the pipeline_runs table to restart cost tracking with
the new Haiku pricing model. Historical runs were calculated with
old Sonnet 4 pricing and are no longer accurate.
"""

import os
from database import SpeakerDatabase


def get_db_path():
    """Get database path - /data/speakers.db on Railway, ./speakers.db locally"""
    if os.path.exists('/data'):
        return '/data/speakers.db'
    else:
        return 'speakers.db'


def main():
    db_path = get_db_path()
    print(f"Resetting API cost tracking in: {db_path}")

    with SpeakerDatabase(db_path) as db:
        cursor = db.conn.cursor()

        # Check if pipeline_runs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_runs'")
        if not cursor.fetchone():
            print("No pipeline_runs table found - nothing to reset")
            return

        # Get current stats before reset
        cursor.execute('SELECT COUNT(*), COALESCE(SUM(total_cost), 0) FROM pipeline_runs')
        count, total_cost = cursor.fetchone()

        print(f"\nCurrent stats:")
        print(f"  Pipeline runs: {count}")
        print(f"  Total API costs: ${total_cost:.2f}")

        if count == 0:
            print("\nNo pipeline runs to reset")
            return

        # Clear the table
        cursor.execute('DELETE FROM pipeline_runs')
        db.conn.commit()

        print(f"\n✓ Reset complete - deleted {count} pipeline run records")
        print("  API cost tracking will start fresh with next pipeline run")
        print("  New runs will use correct Haiku pricing")


if __name__ == '__main__':
    main()
