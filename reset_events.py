"""
Reset failed events back to pending status.

This utility script resets events that failed during speaker extraction back to
'pending' status, allowing them to be re-processed. This is useful when:

- Extraction failed due to API errors (rate limits, timeouts, etc.)
- Extraction logic was updated and you want to retry failed events
- Testing changes to the speaker extraction algorithm

⚠️ NOTE: This does NOT delete any existing speaker data. It only resets the
processing status flag, allowing the events to be re-extracted. Any speakers
already extracted from these events will remain in the database.

Use with caution: Re-extracting events that already have speakers may create
duplicates if the deduplication logic doesn't match them correctly.
"""

from database import SpeakerDatabase
import sys


def main():
    """Main function to reset failed events with user confirmation."""
    try:
        with SpeakerDatabase() as db:
            # Show current database statistics
            stats = db.get_statistics()
            print("=" * 60)
            print("RESET FAILED EVENTS UTILITY")
            print("=" * 60)
            print("\nCurrent database statistics:")
            print(f"  Total events: {stats['total_events']}")
            print(f"  Processed: {stats['processed_events']}")
            print(f"  Pending: {stats['total_events'] - stats['processed_events']}")

            # Count failed events specifically
            cursor = db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM events WHERE processing_status = 'failed'")
            failed_count = cursor.fetchone()[0]

            print(f"\n  Failed events: {failed_count}")

            if failed_count == 0:
                print("\n✓ No failed events to reset. All events are either completed or pending.")
                return

            # Show sample of events
            cursor.execute('SELECT event_id, title, processing_status FROM events LIMIT 5')
            events = cursor.fetchall()

            print("\nSample of events in database (first 5):")
            for event_id, title, status in events:
                title_truncated = title[:50] + "..." if len(title) > 50 else title
                print(f"  ID {event_id}: {title_truncated} - Status: {status}")

            # Show warning and request confirmation
            print("\n" + "=" * 60)
            print("⚠️  WARNING")
            print("=" * 60)
            print(f"\nThis will reset {failed_count} failed event(s) to 'pending' status.")
            print("\nWhat this means:")
            print("  • These events will be re-processed by extract_only.py")
            print("  • New speaker data may be extracted")
            print("  • Existing speaker records will NOT be deleted")
            print("  • Deduplication logic will attempt to match existing speakers")
            print("\nThis is generally safe but may create duplicate speakers if")
            print("the extraction produces different results than before.")

            # Request confirmation
            print("\n" + "=" * 60)
            response = input(f"\nReset {failed_count} failed events to pending? (yes/no): ").strip().lower()

            if response != 'yes':
                print("\n✗ Operation cancelled. No changes made.")
                return

            # Perform the reset
            print(f"\nResetting {failed_count} failed events to pending...")
            cursor.execute("""
                UPDATE events
                SET processing_status = 'pending', processed_at = NULL
                WHERE processing_status = 'failed'
            """)
            db.conn.commit()

            print(f"✓ Successfully reset {failed_count} events to pending status.")
            print("\nYou can now run:")
            print("  python3 extract_only.py")
            print("\nto re-process these events.")

    except KeyboardInterrupt:
        print("\n\n✗ Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()