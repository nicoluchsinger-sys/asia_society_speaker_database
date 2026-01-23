"""
CLI tool for enriching speaker data with demographics, locations, and languages
Uses web search and Claude AI to extract information
"""

import argparse
import time
from datetime import datetime
from database import SpeakerDatabase
from speaker_enricher import SpeakerEnricher


def enrich_speakers(
    batch_size=10,
    limit=None,
    skip_existing=True,
    verbose=True
):
    """
    Enrich speakers with demographics, locations, and languages

    Args:
        batch_size: Number of speakers to process before showing progress
        limit: Maximum number of speakers to process (None = all)
        skip_existing: Skip speakers that already have enrichment data
        verbose: Print progress messages
    """
    # Get list of speakers to process (then close connection)
    db = SpeakerDatabase()
    speakers_data = db.get_all_speakers()

    if not speakers_data:
        if verbose:
            print("No speakers found in database!")
        db.close()
        return

    # Filter out speakers with existing enrichment if requested
    if skip_existing:
        speakers_to_process = []
        for speaker_data in speakers_data:
            speaker_id = speaker_data[0]
            demographics = db.get_speaker_demographics(speaker_id)
            if not demographics:
                speakers_to_process.append(speaker_data)
        speakers_data = speakers_to_process

    db.close()  # Close initial connection

    if limit:
        speakers_data = speakers_data[:limit]

    if not speakers_data:
        if verbose:
            print("✓ All speakers already enriched!")
        return

    total = len(speakers_data)
    if verbose:
        print(f"Enriching {total} speakers")
        print(f"Batch size: {batch_size}")
        print("=" * 60)

    start_time = time.time()
    total_tokens = 0
    processed = 0
    succeeded = 0
    failed = 0

    enricher = SpeakerEnricher()

    # Process speakers
    for i, speaker_data in enumerate(speakers_data, 1):
        speaker_id, name, title, affiliation, bio, first_seen, last_updated = speaker_data

        if verbose and i % batch_size == 1:
            print(f"\nProcessing batch {(i-1)//batch_size + 1} (speakers {i}-{min(i+batch_size-1, total)}/{total})...")

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

            # Perform enrichment
            result = enricher.enrich_speaker(speaker)

            if result['success']:
                # Open fresh database connection for saving
                # This prevents long-held connections that cause locking issues
                db = SpeakerDatabase()

                try:
                    # Save demographics
                    demographics = result.get('demographics', {})
                    if demographics and any([
                        demographics.get('gender'),
                        demographics.get('nationality'),
                        demographics.get('birth_year')
                    ]):
                        db.save_speaker_demographics(
                            speaker_id,
                            gender=demographics.get('gender'),
                            gender_confidence=demographics.get('gender_confidence'),
                            nationality=demographics.get('nationality'),
                            nationality_confidence=demographics.get('nationality_confidence'),
                            birth_year=demographics.get('birth_year')
                        )

                    # Save locations
                    locations = result.get('locations', [])
                    for loc in locations:
                        db.save_speaker_location(
                            speaker_id,
                            location_type=loc.get('location_type', 'unknown'),
                            city=loc.get('city'),
                            country=loc.get('country'),
                            region=loc.get('region'),
                            is_primary=loc.get('is_primary', False),
                            confidence=loc.get('confidence'),
                            source='web_search'
                        )

                    # Save languages
                    languages = result.get('languages', [])
                    for lang in languages:
                        db.save_speaker_language(
                            speaker_id,
                            language=lang.get('language'),
                            proficiency=lang.get('proficiency'),
                            confidence=lang.get('confidence'),
                            source='web_search'
                        )

                    succeeded += 1
                    if verbose:
                        print("✓")

                except Exception as db_error:
                    failed += 1
                    if verbose:
                        print(f"✗ (DB error: {str(db_error)[:50]})")
                finally:
                    # Always close connection after each speaker
                    db.close()

                # Track usage
                usage = enricher.get_last_usage()
                if usage:
                    total_tokens += usage['input_tokens'] + usage['output_tokens']

            else:
                failed += 1
                if verbose:
                    error_msg = result.get('error', 'Unknown error')
                    print(f"✗ ({error_msg[:50]})")

        except Exception as e:
            failed += 1
            if verbose:
                print(f"✗ (Exception: {str(e)[:50]})")

        processed += 1

    elapsed = time.time() - start_time

    # Print summary
    if verbose:
        print("\n" + "=" * 60)
        print("Summary")
        print("=" * 60)
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

        print("\n✓ Enrichment complete!")


def show_enrichment_stats(verbose=True):
    """Show statistics about enrichment coverage"""
    db = SpeakerDatabase()

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
        print("\n" + "=" * 60)
        print("Enrichment Statistics")
        print("=" * 60)
        print(f"Total speakers: {total_speakers}")
        print(f"Speakers with demographics: {demographics_count} ({demographics_count/total_speakers*100:.1f}%)")
        print(f"Speakers with locations: {locations_count} ({locations_count/total_speakers*100:.1f}%)")
        print(f"Speakers with languages: {languages_count} ({languages_count/total_speakers*100:.1f}%)")

        # Show sample enriched speakers
        cursor.execute('''
            SELECT s.name, d.gender, d.nationality
            FROM speakers s
            JOIN speaker_demographics d ON s.speaker_id = d.speaker_id
            LIMIT 5
        ''')
        samples = cursor.fetchall()

        if samples:
            print("\nSample enriched speakers:")
            for name, gender, nationality in samples:
                print(f"  - {name}: {gender or 'N/A'}, {nationality or 'N/A'}")

        print("=" * 60)

    db.close()


def clear_enrichment_data(verbose=True):
    """Clear all enrichment data from database"""
    db = SpeakerDatabase()

    if verbose:
        response = input("WARNING: This will delete all enrichment data. Are you sure? (yes/no): ")
        if response.lower() != 'yes':
            print("Operation cancelled.")
            db.close()
            return

    cursor = db.conn.cursor()

    cursor.execute('DELETE FROM speaker_demographics')
    cursor.execute('DELETE FROM speaker_locations')
    cursor.execute('DELETE FROM speaker_languages')

    db.conn.commit()

    if verbose:
        print("✓ All enrichment data cleared.")

    db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Enrich speaker data with demographics, locations, and languages',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python enrich_speakers.py --limit 10         # Enrich first 10 unenriched speakers
  python enrich_speakers.py --all             # Enrich all unenriched speakers
  python enrich_speakers.py --stats           # Show enrichment statistics
  python enrich_speakers.py --clear           # Clear all enrichment data
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
    parser.add_argument('--clear', action='store_true',
                       help='Clear all enrichment data (use with caution!)')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress progress messages')

    args = parser.parse_args()

    verbose = not args.quiet

    if args.stats:
        show_enrichment_stats(verbose)
    elif args.clear:
        clear_enrichment_data(verbose)
    else:
        skip_existing = args.skip_existing and not args.force

        enrich_speakers(
            batch_size=args.batch_size,
            limit=args.limit,
            skip_existing=skip_existing,
            verbose=verbose
        )
