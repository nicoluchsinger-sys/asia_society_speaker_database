#!/usr/bin/env python3
"""
Merge duplicate speakers in the database.
Finds speakers with the same name and merges them into a single record.
"""

from database import SpeakerDatabase, normalize_name
from collections import defaultdict


def find_duplicate_groups(db):
    """
    Find all speaker names that have multiple entries.

    Now uses name normalization to detect duplicates like:
    - "Jane Smith" and "Dr. Jane Smith"
    - "John Doe" and "Prof. John Doe"
    """
    cursor = db.conn.cursor()
    cursor.execute('SELECT speaker_id, name FROM speakers')

    # Group speakers by normalized name
    groups = defaultdict(list)
    for speaker_id, name in cursor.fetchall():
        normalized = normalize_name(name).lower()
        groups[normalized].append(speaker_id)

    # Return only groups with duplicates
    duplicate_groups = []
    for normalized_name, speaker_ids in groups.items():
        if len(speaker_ids) > 1:
            # Format as (normalized_name, comma-separated IDs) to match original return format
            duplicate_groups.append((normalized_name, ','.join(map(str, speaker_ids))))

    return duplicate_groups


def get_speaker_details(db, speaker_id):
    """Get full details for a speaker."""
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT speaker_id, name, title, affiliation, primary_affiliation, bio, first_seen
        FROM speakers
        WHERE speaker_id = ?
    ''', (speaker_id,))
    return cursor.fetchone()


def get_event_count(db, speaker_id):
    """Count how many events a speaker is linked to."""
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM event_speakers WHERE speaker_id = ?
    ''', (speaker_id,))
    return cursor.fetchone()[0]


def merge_speakers(db, speaker_ids, dry_run=True):
    """
    Merge multiple speaker records into one.
    Keeps the record with the most complete information.
    """
    cursor = db.conn.cursor()

    # Get details for all speakers
    speakers = [get_speaker_details(db, sid) for sid in speaker_ids]

    # Score each speaker by completeness
    def completeness_score(s):
        score = 0
        if s[2]:  # title
            score += 1
        if s[3]:  # affiliation
            score += len(s[3])  # longer affiliation = more info
        if s[4]:  # primary_affiliation
            score += 1
        if s[5]:  # bio
            score += len(s[5]) if s[5] else 0
        return score

    # Sort by completeness, most complete first
    speakers_sorted = sorted(speakers, key=completeness_score, reverse=True)
    primary = speakers_sorted[0]
    primary_id = primary[0]
    duplicates = speakers_sorted[1:]

    print(f"\n  Primary (keeping): ID={primary_id}, name='{primary[1]}'")
    print(f"    affiliation: {primary[3]}")
    print(f"    events linked: {get_event_count(db, primary_id)}")

    # Merge info from duplicates into primary
    merged_title = primary[2]
    merged_affiliation = primary[3]
    merged_primary_aff = primary[4]
    merged_bio = primary[5]

    for dup in duplicates:
        dup_id = dup[0]
        print(f"  Duplicate (merging): ID={dup_id}, name='{dup[1]}'")
        print(f"    affiliation: {dup[3]}")
        print(f"    events linked: {get_event_count(db, dup_id)}")

        # Take longer/more complete values
        if dup[2] and (not merged_title or len(dup[2]) > len(merged_title)):
            merged_title = dup[2]
        if dup[3] and (not merged_affiliation or len(dup[3]) > len(merged_affiliation)):
            merged_affiliation = dup[3]
        if dup[4] and not merged_primary_aff:
            merged_primary_aff = dup[4]
        if dup[5] and (not merged_bio or len(dup[5]) > len(merged_bio)):
            merged_bio = dup[5]

    if dry_run:
        print(f"  [DRY RUN] Would update primary speaker with merged info")
        print(f"  [DRY RUN] Would reassign {sum(get_event_count(db, d[0]) for d in duplicates)} event links")
        print(f"  [DRY RUN] Would delete {len(duplicates)} duplicate records")
        return

    # Update primary speaker with merged info
    cursor.execute('''
        UPDATE speakers
        SET title = ?, affiliation = ?, primary_affiliation = ?, bio = ?, last_updated = datetime('now')
        WHERE speaker_id = ?
    ''', (merged_title, merged_affiliation, merged_primary_aff, merged_bio, primary_id))

    # Reassign event_speakers links from duplicates to primary
    for dup in duplicates:
        dup_id = dup[0]

        # Get existing event links for the duplicate
        cursor.execute('''
            SELECT event_id, role_in_event, extracted_info
            FROM event_speakers
            WHERE speaker_id = ?
        ''', (dup_id,))
        event_links = cursor.fetchall()

        for event_id, role, info in event_links:
            # Check if primary already linked to this event
            cursor.execute('''
                SELECT 1 FROM event_speakers
                WHERE event_id = ? AND speaker_id = ?
            ''', (event_id, primary_id))

            if cursor.fetchone():
                # Already linked, just delete the duplicate link
                cursor.execute('''
                    DELETE FROM event_speakers
                    WHERE event_id = ? AND speaker_id = ?
                ''', (event_id, dup_id))
            else:
                # Reassign to primary
                cursor.execute('''
                    UPDATE event_speakers
                    SET speaker_id = ?
                    WHERE event_id = ? AND speaker_id = ?
                ''', (primary_id, event_id, dup_id))

        # Delete the duplicate speaker record
        cursor.execute('DELETE FROM speakers WHERE speaker_id = ?', (dup_id,))
        print(f"  Deleted duplicate speaker ID={dup_id}")

    db.conn.commit()
    print(f"  Merged {len(duplicates)} duplicates into speaker ID={primary_id}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Merge duplicate speakers')
    parser.add_argument('--execute', action='store_true', help='Actually perform the merge (default is dry-run)')
    args = parser.parse_args()

    dry_run = not args.execute

    db = SpeakerDatabase()

    print("Finding duplicate speakers...")
    duplicate_groups = find_duplicate_groups(db)

    if not duplicate_groups:
        print("No duplicates found!")
        return

    print(f"Found {len(duplicate_groups)} names with duplicates")

    if dry_run:
        print("\n=== DRY RUN MODE (use --execute to apply changes) ===\n")
    else:
        print("\n=== EXECUTING MERGE ===\n")

    for normalized_name, id_str in duplicate_groups:
        speaker_ids = [int(x) for x in id_str.split(',')]
        print(f"\nProcessing: '{normalized_name}' ({len(speaker_ids)} records)")
        merge_speakers(db, speaker_ids, dry_run=dry_run)

    if dry_run:
        print("\n\nDry run complete. Run with --execute to apply changes.")
    else:
        print("\n\nMerge complete!")

        # Show final count
        cursor = db.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM speakers')
        print(f"Total speakers in database: {cursor.fetchone()[0]}")


if __name__ == '__main__':
    main()
