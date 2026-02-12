"""
CLI tool for unified speaker enrichment
Extracts tags + demographics + locations + languages in ONE pass
Saves ~50% cost and time vs separate tagging + enrichment
"""

import argparse
import time
import os
from datetime import datetime
from database import SpeakerDatabase
from speaker_enricher_v2 import UnifiedSpeakerEnricher


def get_db_path():
    """Get database path - /data/speakers.db on Railway, ./speakers.db locally"""
    if os.path.exists('/data'):
        return '/data/speakers.db'
    return './speakers.db'


def enrich_speakers(
    batch_size=10,
    limit=None,
    skip_existing=True,
    verbose=True
):
    """
    Unified enrichment: tags + demographics + locations + languages in one pass

    Args:
        batch_size: Number of speakers to process before showing progress
        limit: Maximum number of speakers to process (None = all)
        skip_existing: Skip speakers that already have enrichment data
        verbose: Print progress messages
    """
    # Get list of speakers to process (then close connection)
    db = SpeakerDatabase(get_db_path())
    all_speakers = db.get_all_speakers()

    if not all_speakers:
        if verbose:
            print("No speakers found in database!")
        db.close()
        return

    # Filter out speakers with existing enrichment if requested
    if skip_existing:
        speakers_to_process = []
        for speaker_data in all_speakers:
            speaker_id = speaker_data[0]
            # Check for either demographics OR tags
            demographics = db.get_speaker_demographics(speaker_id)
            tags = db.get_speaker_tags(speaker_id)
            if not demographics and not tags:
                speakers_to_process.append(speaker_data)
        speakers_data = speakers_to_process
    else:
        speakers_data = all_speakers

    db.close()  # Close initial connection

    if limit:
        speakers_data = speakers_data[:limit]

    if not speakers_data:
        if verbose:
            print("✓ All speakers already enriched!")
        return

    total = len(speakers_data)
    if verbose:
        print("="*70)
        print("🔄 UNIFIED SPEAKER ENRICHMENT")
        print("="*70)
        print(f"\nProcessing: {total} speakers")
        print(f"Batch size: {batch_size}")
        print(f"\nExtracting in ONE pass:")
        print("  • Expertise tags (3 per speaker)")
        print("  • Demographics (gender, nationality)")
        print("  • Locations (city, country, region)")
        print("  • Languages (with proficiency)")
        print("="*70)

    start_time = time.time()
    total_tokens = 0
    processed = 0
    succeeded = 0
    failed = 0

    enricher = UnifiedSpeakerEnricher()

    # Process speakers
    for i, speaker_data in enumerate(speakers_data, 1):
        speaker_id, name, title, affiliation, bio, first_seen, last_updated = speaker_data

        if verbose and i % batch_size == 1:
            print(f"\nBatch {(i-1)//batch_size + 1} (speakers {i}-{min(i+batch_size-1, total)}/{total})...")

        try:
            # Build speaker dict
            speaker = {
                'speaker_id': speaker_id,
                'name': name,
                'title': title,
                'affiliation': affiliation,
                'bio': bio
            }

            if verbose:
                print(f"  {i}/{total}: {name}...", end=" ")

            # Perform unified enrichment
            # Open fresh database connection for this speaker
            db = SpeakerDatabase(get_db_path())

            try:
                result = enricher.enrich_speaker(speaker_id, db)

                if result['success']:
                    succeeded += 1
                    if verbose:
                        tags_str = ', '.join([t['text'] for t in result['tags']])
                        print(f"✓ ({tags_str})")
                else:
                    failed += 1
                    if verbose:
                        error_msg = result.get('error', 'Unknown error')
                        print(f"✗ ({error_msg[:50]})")

            finally:
                db.close()  # Always close connection after each speaker

            # Track usage
            usage = enricher.get_last_usage()
            if usage:
                total_tokens += usage['input_tokens'] + usage['output_tokens']

        except Exception as e:
            failed += 1
            if verbose:
                print(f"✗ (Exception: {str(e)[:50]})")

        processed += 1

        # Rate limiting already handled in enricher
        # time.sleep(1.5)

    elapsed = time.time() - start_time

    # Print summary
    if verbose:
        print("\n" + "="*70)
        print("📊 SUMMARY")
        print("="*70)
        print(f"Speakers processed: {processed}/{total}")
        print(f"  Succeeded: {succeeded}")
        print(f"  Failed: {failed}")
        print(f"Total tokens used: {total_tokens:,}")

        # Calculate cost (Claude Sonnet 4: $3/1M input + $15/1M output, approximate 50/50 split)
        # Conservative estimate: $9 per 1M tokens average
        cost = (total_tokens / 1_000_000) * 9
        print(f"Estimated cost: ${cost:.2f}")

        print(f"Time elapsed: {elapsed:.1f}s")
        if processed > 0:
            print(f"Avg time per speaker: {elapsed/processed:.1f}s")

        # Check database stats (open fresh connection)
        db = SpeakerDatabase(get_db_path())
        stats = db.get_statistics()

        # Count enriched speakers
        cursor = db.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM speaker_demographics')
        demographics_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(DISTINCT speaker_id) FROM speaker_locations')
        locations_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(DISTINCT speaker_id) FROM speaker_languages')
        languages_count = cursor.fetchone()[0]

        db.close()

        print(f"\n📊 Updated Database Status:")
        print(f"  Total speakers: {stats['total_speakers']}")
        print(f"  Tagged speakers: {stats['tagged_speakers']}")
        print(f"  With demographics: {demographics_count}")
        print(f"  With locations: {locations_count}")
        print(f"  With languages: {languages_count}")

        print("\n✓ Enrichment complete!")


def show_stats(verbose=True):
    """Show statistics about enrichment coverage"""
    db = SpeakerDatabase(get_db_path())

    stats = db.get_statistics()
    total_speakers = stats['total_speakers']

    # Count enriched speakers
    cursor = db.conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM speaker_demographics')
    demographics_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(DISTINCT speaker_id) FROM speaker_locations')
    locations_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(DISTINCT speaker_id) FROM speaker_languages')
    languages_count = cursor.fetchone()[0]

    if verbose:
        print("\n" + "="*70)
        print("📊 ENRICHMENT STATISTICS")
        print("="*70)
        print(f"Total speakers: {total_speakers}")
        print(f"Tagged speakers: {stats['tagged_speakers']} ({stats['tagged_speakers']/total_speakers*100:.1f}%)")
        print(f"With demographics: {demographics_count} ({demographics_count/total_speakers*100:.1f}%)")
        print(f"With locations: {locations_count} ({locations_count/total_speakers*100:.1f}%)")
        print(f"With languages: {languages_count} ({languages_count/total_speakers*100:.1f}%)")

        # Count fully enriched (has ALL data)
        cursor.execute('''
            SELECT COUNT(DISTINCT s.speaker_id)
            FROM speakers s
            JOIN speaker_tags st ON s.speaker_id = st.speaker_id
            JOIN speaker_demographics sd ON s.speaker_id = sd.speaker_id
        ''')
        fully_enriched = cursor.fetchone()[0]
        print(f"Fully enriched (tags + demographics): {fully_enriched} ({fully_enriched/total_speakers*100:.1f}%)")

        # Calculate remaining
        cursor.execute('''
            SELECT COUNT(*)
            FROM speakers s
            WHERE s.speaker_id NOT IN (SELECT speaker_id FROM speaker_demographics)
            AND s.speaker_id NOT IN (SELECT DISTINCT speaker_id FROM speaker_tags)
        ''')
        remaining = cursor.fetchone()[0]
        print(f"\nRemaining to enrich: {remaining}")
        if remaining > 0:
            est_cost = (remaining * 0.01)
            est_time = (remaining * 1.5) / 60
            print(f"  Estimated cost: ${est_cost:.2f}")
            print(f"  Estimated time: ~{est_time:.1f} minutes")

        # Show sample enriched speakers
        cursor.execute('''
            SELECT s.name, GROUP_CONCAT(st.tag_text, ', ') as tags, d.gender, d.nationality
            FROM speakers s
            LEFT JOIN speaker_tags st ON s.speaker_id = st.speaker_id
            LEFT JOIN speaker_demographics d ON s.speaker_id = d.speaker_id
            WHERE st.tag_text IS NOT NULL OR d.gender IS NOT NULL
            GROUP BY s.speaker_id
            LIMIT 5
        ''')
        samples = cursor.fetchall()

        if samples:
            print("\nSample enriched speakers:")
            for name, tags, gender, nationality in samples:
                print(f"  • {name}")
                if tags:
                    print(f"    Tags: {tags}")
                if gender or nationality:
                    print(f"    Demographics: {gender or 'N/A'}, {nationality or 'N/A'}")

        print("="*70)

    db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Unified speaker enrichment (tags + demographics + locations + languages)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python enrich_speakers_v2.py --limit 10         # Enrich first 10 unenriched speakers
  python enrich_speakers_v2.py --all              # Enrich all unenriched speakers
  python enrich_speakers_v2.py --stats            # Show enrichment statistics
  python enrich_speakers_v2.py --force --limit 5  # Re-enrich 5 speakers
        """
    )

    parser.add_argument('--limit', type=int, default=None,
                       help='Maximum number of speakers to enrich')
    parser.add_argument('--all', action='store_true',
                       help='Enrich all unenriched speakers (no limit)')
    parser.add_argument('--batch-size', type=int, default=10,
                       help='Progress update frequency (default: 10)')
    parser.add_argument('--skip-existing', action='store_true', default=True,
                       help='Skip speakers that already have enrichment data (default: True)')
    parser.add_argument('--force', action='store_true',
                       help='Re-enrich speakers even if they have existing data')
    parser.add_argument('--stats', action='store_true',
                       help='Show enrichment statistics')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress progress messages')

    args = parser.parse_args()

    verbose = not args.quiet

    if args.stats:
        show_stats(verbose)
    else:
        skip_existing = args.skip_existing and not args.force

        enrich_speakers(
            batch_size=args.batch_size,
            limit=args.limit,
            skip_existing=skip_existing,
            verbose=verbose
        )
