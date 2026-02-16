"""
Freshness manager for tracking speaker data staleness and managing refreshes
"""

import argparse
from datetime import datetime, timedelta
from database import SpeakerDatabase
from speaker_enricher import UnifiedSpeakerEnricher
import time


class FreshnessManager:
    def __init__(self, db_path='speakers.db'):
        """Initialize freshness manager"""
        self.db = SpeakerDatabase(db_path)
        self.enricher = UnifiedSpeakerEnricher()

    def calculate_staleness(self, last_enrichment_date: str, event_count: int = 0) -> float:
        """
        Calculate staleness score for a speaker (0.0 = fresh, 1.0 = very stale)

        Args:
            last_enrichment_date: ISO timestamp of last enrichment
            event_count: Number of events speaker has participated in

        Returns:
            Staleness score (0.0 to 1.0+)
        """
        if not last_enrichment_date:
            return 1.0  # Never enriched = fully stale

        # Calculate days since enrichment
        enrichment_dt = datetime.fromisoformat(last_enrichment_date)
        days_old = (datetime.now() - enrichment_dt).days

        # Base staleness: 1 year = 1.0 staleness
        staleness = days_old / 365.0

        # Adjustment for high-profile speakers (more events = ages faster)
        if event_count > 10:
            staleness *= 1.5  # High-profile speakers age 50% faster
        elif event_count > 5:
            staleness *= 1.2  # Active speakers age 20% faster

        return min(staleness, 2.0)  # Cap at 2.0

    def calculate_priority(self, speaker_id: int, staleness: float, event_count: int) -> float:
        """
        Calculate refresh priority for a speaker

        Args:
            speaker_id: Speaker ID
            staleness: Staleness score
            event_count: Number of events

        Returns:
            Priority score (higher = more urgent to refresh)
        """
        # Base priority from staleness
        priority = staleness

        # Boost priority for speakers with many events
        if event_count > 10:
            priority += 0.5
        elif event_count > 5:
            priority += 0.3

        # Boost priority for speakers with tags
        tags = self.db.get_speaker_tags(speaker_id)
        if len(tags) >= 3:
            priority += 0.2

        return priority

    def update_freshness_tracking(self, verbose=True):
        """
        Update freshness tracking for all speakers

        Calculates staleness and priority scores
        """
        cursor = self.db.conn.cursor()

        # Get all speakers with their enrichment dates
        cursor.execute('''
            SELECT s.speaker_id, d.enriched_at
            FROM speakers s
            LEFT JOIN speaker_demographics d ON s.speaker_id = d.speaker_id
        ''')
        speakers_data = cursor.fetchall()

        if verbose:
            print(f"Updating freshness tracking for {len(speakers_data)} speakers...")
            print("=" * 60)

        updated = 0

        for speaker_id, enriched_at in speakers_data:
            # Get event count
            events = self.db.get_speaker_events(speaker_id)
            event_count = len(events) if events else 0

            # Calculate staleness
            staleness = self.calculate_staleness(enriched_at, event_count)

            # Calculate priority
            priority = self.calculate_priority(speaker_id, staleness, event_count)

            # Determine if refresh is needed (staleness > 0.6)
            needs_refresh = staleness > 0.6

            # Calculate next refresh date
            if enriched_at:
                enrichment_dt = datetime.fromisoformat(enriched_at)
                # High priority: refresh in 6 months, normal: 1 year
                refresh_interval = 180 if priority > 1.5 else 365
                next_refresh = enrichment_dt + timedelta(days=refresh_interval)
                next_refresh_str = next_refresh.isoformat()
            else:
                next_refresh_str = datetime.now().isoformat()

            # Save to database
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO speaker_freshness
                    (speaker_id, last_enrichment_date, staleness_score, needs_refresh,
                     priority_score, next_refresh_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (speaker_id, enriched_at, staleness, needs_refresh, priority, next_refresh_str))
                updated += 1
            except Exception as e:
                if verbose:
                    print(f"Error updating speaker {speaker_id}: {e}")

        self.db.conn.commit()

        if verbose:
            print(f"✓ Updated freshness tracking for {updated} speakers")

    def get_refresh_report(self, limit=20, verbose=True):
        """
        Generate a report of speakers needing refresh

        Args:
            limit: Number of speakers to include in report
            verbose: Print report
        """
        cursor = self.db.conn.cursor()

        # Get speakers needing refresh, ordered by priority
        cursor.execute('''
            SELECT s.speaker_id, s.name, s.affiliation,
                   f.staleness_score, f.priority_score, f.last_enrichment_date
            FROM speaker_freshness f
            JOIN speakers s ON f.speaker_id = s.speaker_id
            WHERE f.needs_refresh = 1
            ORDER BY f.priority_score DESC
            LIMIT ?
        ''', (limit,))

        results = cursor.fetchall()

        if verbose:
            print("\n" + "=" * 60)
            print(f"Speakers Needing Refresh (Top {limit})")
            print("=" * 60)

            if not results:
                print("\nNo speakers need refresh at this time.")
            else:
                for i, (speaker_id, name, affiliation, staleness, priority, last_enriched) in enumerate(results, 1):
                    print(f"\n{i}. {name} (ID: {speaker_id})")
                    if affiliation:
                        print(f"   Affiliation: {affiliation}")
                    print(f"   Staleness: {staleness:.2f}")
                    print(f"   Priority: {priority:.2f}")
                    if last_enriched:
                        days_ago = (datetime.now() - datetime.fromisoformat(last_enriched)).days
                        print(f"   Last enriched: {days_ago} days ago")
                    else:
                        print(f"   Last enriched: Never")

            print("\n" + "=" * 60)

        return results

    def refresh_stale_speakers(self, limit=10, min_priority=1.0, verbose=True):
        """
        Refresh data for stale speakers

        Args:
            limit: Maximum number of speakers to refresh
            min_priority: Minimum priority score to refresh
            verbose: Print progress
        """
        cursor = self.db.conn.cursor()

        # Get speakers to refresh
        cursor.execute('''
            SELECT s.speaker_id, s.name, s.title, s.affiliation, s.bio,
                   f.priority_score
            FROM speaker_freshness f
            JOIN speakers s ON f.speaker_id = s.speaker_id
            WHERE f.needs_refresh = 1 AND f.priority_score >= ?
            ORDER BY f.priority_score DESC
            LIMIT ?
        ''', (min_priority, limit))

        speakers = cursor.fetchall()

        if not speakers:
            if verbose:
                print("No speakers need refresh at this time.")
            return

        if verbose:
            print(f"Refreshing {len(speakers)} stale speakers...")
            print("=" * 60)

        succeeded = 0
        failed = 0

        for i, (speaker_id, name, title, affiliation, bio, priority) in enumerate(speakers, 1):
            if verbose:
                print(f"\n{i}/{len(speakers)}: {name} (Priority: {priority:.2f})...", end=" ")

            try:
                # Build speaker dict
                speaker = {
                    'speaker_id': speaker_id,
                    'name': name,
                    'title': title,
                    'affiliation': affiliation,
                    'bio': bio
                }

                # Perform enrichment
                result = self.enricher.enrich_speaker(speaker)

                if result['success']:
                    # Save updated data
                    demographics = result.get('demographics', {})
                    if demographics:
                        self.db.save_speaker_demographics(
                            speaker_id,
                            gender=demographics.get('gender'),
                            gender_confidence=demographics.get('gender_confidence'),
                            nationality=demographics.get('nationality'),
                            nationality_confidence=demographics.get('nationality_confidence'),
                            birth_year=demographics.get('birth_year')
                        )

                    # Update locations and languages
                    for loc in result.get('locations', []):
                        self.db.save_speaker_location(
                            speaker_id,
                            location_type=loc.get('location_type', 'unknown'),
                            city=loc.get('city'),
                            country=loc.get('country'),
                            region=loc.get('region'),
                            is_primary=loc.get('is_primary', False),
                            confidence=loc.get('confidence'),
                            source='refresh'
                        )

                    for lang in result.get('languages', []):
                        self.db.save_speaker_language(
                            speaker_id,
                            language=lang.get('language'),
                            proficiency=lang.get('proficiency'),
                            confidence=lang.get('confidence'),
                            source='refresh'
                        )

                    # Update freshness tracking
                    cursor.execute('''
                        UPDATE speaker_freshness
                        SET last_enrichment_date = ?,
                            staleness_score = 0.0,
                            needs_refresh = 0,
                            priority_score = 0.0,
                            next_refresh_date = ?
                        WHERE speaker_id = ?
                    ''', (datetime.now().isoformat(),
                          (datetime.now() + timedelta(days=365)).isoformat(),
                          speaker_id))

                    succeeded += 1
                    if verbose:
                        print("✓")

                else:
                    failed += 1
                    if verbose:
                        print(f"✗ ({result.get('error', 'Unknown error')[:50]})")

            except Exception as e:
                failed += 1
                if verbose:
                    print(f"✗ (Exception: {str(e)[:50]})")

            # Rate limiting
            time.sleep(1.5)

        self.db.conn.commit()

        if verbose:
            print("\n" + "=" * 60)
            print("Refresh Summary")
            print("=" * 60)
            print(f"Succeeded: {succeeded}")
            print(f"Failed: {failed}")
            print("\n✓ Refresh complete!")

    def close(self):
        """Close database connection"""
        self.db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Manage speaker data freshness and refreshes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python freshness_manager.py --update         # Update freshness scores
  python freshness_manager.py --report         # Show stale speakers report
  python freshness_manager.py --refresh-stale --limit 10  # Refresh 10 stale speakers
        """
    )

    parser.add_argument('--update', action='store_true',
                       help='Update freshness tracking for all speakers')
    parser.add_argument('--report', action='store_true',
                       help='Show report of speakers needing refresh')
    parser.add_argument('--refresh-stale', action='store_true',
                       help='Refresh stale speakers')
    parser.add_argument('--limit', type=int, default=10,
                       help='Limit for refresh operations (default: 10)')
    parser.add_argument('--min-priority', type=float, default=1.0,
                       help='Minimum priority score for refresh (default: 1.0)')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress progress messages')

    args = parser.parse_args()

    verbose = not args.quiet

    manager = FreshnessManager()

    try:
        if args.update:
            manager.update_freshness_tracking(verbose)
        elif args.report:
            manager.get_refresh_report(limit=args.limit, verbose=verbose)
        elif args.refresh_stale:
            manager.refresh_stale_speakers(
                limit=args.limit,
                min_priority=args.min_priority,
                verbose=verbose
            )
        else:
            parser.print_help()
    finally:
        manager.close()
