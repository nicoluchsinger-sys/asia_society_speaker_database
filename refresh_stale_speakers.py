#!/usr/bin/env python3
"""
Refresh stale speaker demographics (>6 months old)

This script re-enriches speaker profiles that haven't been updated in over 6 months,
ensuring data remains current as affiliations and titles change over time.

Usage:
    python3 refresh_stale_speakers.py [--limit N] [--months N] [--dry-run]

Options:
    --limit N     Maximum number of speakers to refresh (default: 20)
    --months N    Age threshold in months (default: 6)
    --dry-run     Show what would be refreshed without making changes
"""

import os
import sys
import argparse
import time
from datetime import datetime
from database import SpeakerDatabase
from speaker_enricher import SpeakerEnricher

def refresh_stale_speakers(limit=20, months=6, dry_run=False):
    """
    Refresh demographics for stale speakers

    Args:
        limit: Maximum number of speakers to refresh
        months: Age threshold in months
        dry_run: If True, only show what would be refreshed

    Returns:
        Dictionary with refresh statistics
    """
    database = SpeakerDatabase()

    try:
        # Get stale speakers
        stale_speakers = database.get_stale_speakers(months=months, limit=limit)

        if not stale_speakers:
            print(f"✓ No stale speakers found (threshold: {months} months)")
            return {
                'total_found': 0,
                'refreshed': 0,
                'cost': 0
            }

        print(f"\nFound {len(stale_speakers)} stale speakers needing refresh")
        print(f"Threshold: >{months} months old")
        print("-" * 80)

        # Show what will be refreshed
        for speaker_id, name, affiliation, enriched_at, event_count in stale_speakers:
            age_str = enriched_at[:10] if enriched_at else "Never enriched"
            print(f"  [{speaker_id}] {name:40s} | {affiliation[:30]:30s} | {age_str} | {event_count} events")

        if dry_run:
            print("\n[DRY RUN] No changes made")
            estimated_cost = len(stale_speakers) * 0.0008  # Haiku pricing
            print(f"Estimated cost: ${estimated_cost:.4f}")
            return {
                'total_found': len(stale_speakers),
                'refreshed': 0,
                'cost': 0
            }

        # Confirm with user
        print(f"\nThis will re-enrich {len(stale_speakers)} speakers")
        estimated_cost = len(stale_speakers) * 0.0008
        print(f"Estimated cost: ${estimated_cost:.4f} (using Haiku)")
        response = input("\nProceed with refresh? [y/N]: ").strip().lower()

        if response not in ['y', 'yes']:
            print("Refresh cancelled")
            return {
                'total_found': len(stale_speakers),
                'refreshed': 0,
                'cost': 0
            }

        print("\nRefreshing speaker demographics...")
        print(f"Using Claude Haiku for cost efficiency (${estimated_cost:.4f} estimated)")

        # Initialize enricher
        enricher = SpeakerEnricher(model='claude-3-haiku-20240307')

        # Process each speaker
        refreshed_count = 0
        failed_count = 0
        total_tokens = 0

        for i, (speaker_id, name, affiliation, enriched_at, event_count) in enumerate(stale_speakers, 1):
            print(f"  {i}/{len(stale_speakers)}: {name}...", end=" ")

            try:
                # Get full speaker data
                cursor = database.conn.cursor()
                cursor.execute('''
                    SELECT name, title, affiliation, bio
                    FROM speakers
                    WHERE speaker_id = ?
                ''', (speaker_id,))
                row = cursor.fetchone()

                if not row:
                    print("✗ (Not found)")
                    failed_count += 1
                    continue

                speaker_name, title, affiliation, bio = row

                # Build speaker dict
                speaker = {
                    'speaker_id': speaker_id,
                    'name': speaker_name,
                    'title': title,
                    'affiliation': affiliation,
                    'bio': bio
                }

                # Perform enrichment
                result = enricher.enrich_speaker(speaker)

                if result['success']:
                    # Save demographics (this will update enriched_at timestamp)
                    demographics = result.get('demographics', {})
                    if demographics and any([
                        demographics.get('gender'),
                        demographics.get('nationality'),
                        demographics.get('birth_year')
                    ]):
                        database.save_speaker_demographics(
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
                        database.save_speaker_location(
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
                        database.save_speaker_language(
                            speaker_id,
                            language=lang.get('language'),
                            proficiency=lang.get('proficiency'),
                            confidence=lang.get('confidence'),
                            source='web_search'
                        )

                    refreshed_count += 1
                    total_tokens += result.get('tokens_used', 0)
                    print("✓")
                else:
                    failed_count += 1
                    error_msg = result.get('error', 'Unknown error')
                    print(f"✗ ({error_msg[:50]})")

            except Exception as e:
                failed_count += 1
                print(f"✗ (Error: {str(e)[:50]})")

            # Small delay to avoid rate limits
            if i < len(stale_speakers):
                time.sleep(0.5)

        # Calculate actual cost (Haiku pricing: $0.25/MTok input, $1.25/MTok output)
        # Approximate: ~800 tokens per enrichment with Haiku
        actual_cost = (total_tokens / 1_000_000) * 0.75  # Average of input/output rates

        print(f"\n✓ Refreshed {refreshed_count}/{len(stale_speakers)} speakers")
        print(f"Actual cost: ${actual_cost:.4f}")

        return {
            'total_found': len(stale_speakers),
            'refreshed': refreshed_count,
            'cost': actual_cost
        }

    finally:
        database.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Refresh stale speaker demographics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Refresh up to 20 speakers older than 6 months (default)
  python3 refresh_stale_speakers.py

  # Refresh up to 50 speakers older than 12 months
  python3 refresh_stale_speakers.py --limit 50 --months 12

  # Preview what would be refreshed without making changes
  python3 refresh_stale_speakers.py --dry-run
        """
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=20,
        help='Maximum number of speakers to refresh (default: 20)'
    )

    parser.add_argument(
        '--months',
        type=int,
        default=6,
        help='Age threshold in months (default: 6)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be refreshed without making changes'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.limit < 1:
        print("Error: --limit must be at least 1")
        sys.exit(1)

    if args.months < 1:
        print("Error: --months must be at least 1")
        sys.exit(1)

    # Run refresh
    try:
        stats = refresh_stale_speakers(
            limit=args.limit,
            months=args.months,
            dry_run=args.dry_run
        )

        # Summary
        print("\n" + "="*80)
        print("REFRESH SUMMARY")
        print("="*80)
        print(f"Stale speakers found: {stats['total_found']}")
        print(f"Speakers refreshed: {stats['refreshed']}")
        print(f"Total cost: ${stats['cost']:.4f}")
        print("="*80)

    except KeyboardInterrupt:
        print("\n\nRefresh cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
