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
from affiliation_checker import AffiliationChecker
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def refresh_stale_speakers(limit=20, months=6, dry_run=False, non_interactive=False):
    """
    Refresh demographics for stale speakers

    Args:
        limit: Maximum number of speakers to refresh
        months: Age threshold in months
        dry_run: If True, only show what would be refreshed
        non_interactive: If True, skip confirmation prompt (for cron jobs)

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
            # Estimated cost: ~$0.0008 for demographics + ~$0.0015 for affiliation check
            estimated_cost = len(stale_speakers) * 0.0023
            print(f"Estimated cost: ${estimated_cost:.4f}")
            print("(Includes demographics refresh + affiliation/title verification)")
            return {
                'total_found': len(stale_speakers),
                'refreshed': 0,
                'affiliation_changes': 0,
                'title_changes': 0,
                'cost': 0
            }

        # Confirm with user (unless running non-interactively)
        print(f"\nThis will re-enrich {len(stale_speakers)} speakers")
        estimated_cost = len(stale_speakers) * 0.0023  # Demographics + affiliation check
        print(f"Estimated cost: ${estimated_cost:.4f} (using Haiku)")
        print("Includes: demographics, locations, languages, affiliation, and title verification")

        if not non_interactive:
            response = input("\nProceed with refresh? [y/N]: ").strip().lower()

            if response not in ['y', 'yes']:
                print("Refresh cancelled")
                return {
                    'total_found': len(stale_speakers),
                    'refreshed': 0,
                    'affiliation_changes': 0,
                    'title_changes': 0,
                    'cost': 0
                }
        else:
            print("\n[Non-interactive mode] Proceeding automatically...")

        print("\nRefreshing speaker data (demographics, locations, languages, affiliation, title)...")
        print(f"Using Claude Haiku for cost efficiency")

        # Initialize enricher and affiliation checker
        enricher = SpeakerEnricher(model='claude-3-haiku-20240307')
        affiliation_checker = AffiliationChecker(model='claude-3-haiku-20240307')

        # Tracking stats
        refreshed_count = 0
        failed_count = 0
        total_tokens = 0
        total_cost = 0.0
        affiliation_changes = 0
        title_changes = 0

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
                    total_cost += result.get('cost', 0)

                    # Check for affiliation/title changes
                    print("✓ (demographics)", end=" ")
                    print("checking affiliation/title...", end=" ")

                    try:
                        aff_check = affiliation_checker.check_current_affiliation(
                            speaker_name=speaker_name,
                            current_affiliation=affiliation,
                            current_title=title
                        )

                        total_tokens += aff_check.get('tokens_used', 0)
                        total_cost += aff_check.get('cost', 0)

                        changes_made = []

                        # Process affiliation change
                        if aff_check.get('affiliation_changed') and aff_check.get('new_affiliation'):
                            confidence = aff_check.get('affiliation_confidence', 0)

                            # Save correction (auto-apply if high confidence)
                            verified = confidence >= 0.85
                            correction_id = database.save_correction(
                                speaker_id=speaker_id,
                                field_name='affiliation',
                                current_value=affiliation,
                                suggested_value=aff_check['new_affiliation'],
                                suggestion_context="Detected during automated monthly refresh",
                                submitted_by="automated_refresh",
                                verified=verified,
                                confidence=confidence,
                                reasoning=aff_check.get('affiliation_reasoning', ''),
                                sources=aff_check.get('sources', [])
                            )

                            if verified:
                                database.apply_correction(speaker_id, 'affiliation', aff_check['new_affiliation'])
                                changes_made.append(f"affiliation→{aff_check['new_affiliation'][:20]}")
                                affiliation_changes += 1

                        # Process title change
                        if aff_check.get('title_changed') and aff_check.get('new_title'):
                            confidence = aff_check.get('title_confidence', 0)

                            # Save correction (auto-apply if high confidence)
                            verified = confidence >= 0.85
                            correction_id = database.save_correction(
                                speaker_id=speaker_id,
                                field_name='title',
                                current_value=title,
                                suggested_value=aff_check['new_title'],
                                suggestion_context="Detected during automated monthly refresh",
                                submitted_by="automated_refresh",
                                verified=verified,
                                confidence=confidence,
                                reasoning=aff_check.get('title_reasoning', ''),
                                sources=aff_check.get('sources', [])
                            )

                            if verified:
                                database.apply_correction(speaker_id, 'title', aff_check['new_title'])
                                changes_made.append(f"title→{aff_check['new_title'][:20]}")
                                title_changes += 1

                        if changes_made:
                            print(f"✓ ({', '.join(changes_made)})")
                        else:
                            print("✓ (no changes)")

                    except Exception as aff_error:
                        print(f"⚠ (affiliation check failed: {str(aff_error)[:30]})")

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

        print(f"\n✓ Refreshed {refreshed_count}/{len(stale_speakers)} speakers")
        print(f"Actual cost: ${total_cost:.4f}")
        print(f"Affiliation updates: {affiliation_changes}")
        print(f"Title updates: {title_changes}")

        return {
            'total_found': len(stale_speakers),
            'refreshed': refreshed_count,
            'affiliation_changes': affiliation_changes,
            'title_changes': title_changes,
            'cost': total_cost
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

  # Non-interactive mode for cron/automation (no confirmation prompt)
  python3 refresh_stale_speakers.py --limit 20 --non-interactive
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

    parser.add_argument(
        '--non-interactive',
        action='store_true',
        help='Skip confirmation prompt (for automated/cron execution)'
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
            dry_run=args.dry_run,
            non_interactive=args.non_interactive
        )

        # Summary
        print("\n" + "="*80)
        print("REFRESH SUMMARY")
        print("="*80)
        print(f"Stale speakers found: {stats['total_found']}")
        print(f"Speakers refreshed: {stats['refreshed']}")
        print(f"Affiliation updates applied: {stats.get('affiliation_changes', 0)}")
        print(f"Title updates applied: {stats.get('title_changes', 0)}")
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
