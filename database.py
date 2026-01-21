"""
Database management for Asia Society events and speakers
"""

import sqlite3
from datetime import datetime
import json

class SpeakerDatabase:
    def __init__(self, db_path='speakers.db'):
        self.db_path = db_path
        self.conn = None
        self.init_database()
    
    def init_database(self):
        """Initialize database with required tables"""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        
        # Events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                event_date TEXT,
                location TEXT,
                body_text TEXT,
                raw_html TEXT,
                scraped_at TEXT,
                processed_at TEXT,
                processing_status TEXT DEFAULT 'pending'
            )
        ''')
        
        # Speakers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS speakers (
                speaker_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                title TEXT,
                affiliation TEXT,
                primary_affiliation TEXT,
                bio TEXT,
                first_seen TEXT,
                last_updated TEXT,
                UNIQUE(name, primary_affiliation)
            )
        ''')

        # Migration: add primary_affiliation column if it doesn't exist
        cursor.execute("PRAGMA table_info(speakers)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'primary_affiliation' not in columns:
            cursor.execute('ALTER TABLE speakers ADD COLUMN primary_affiliation TEXT')
            # Copy affiliation to primary_affiliation for existing records
            cursor.execute('UPDATE speakers SET primary_affiliation = affiliation WHERE primary_affiliation IS NULL')
        
        # Event-Speaker relationship table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_speakers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                speaker_id INTEGER,
                role_in_event TEXT,
                extracted_info TEXT,
                FOREIGN KEY (event_id) REFERENCES events(event_id),
                FOREIGN KEY (speaker_id) REFERENCES speakers(speaker_id),
                UNIQUE(event_id, speaker_id)
            )
        ''')

        # Speaker tags table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS speaker_tags (
                tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                speaker_id INTEGER NOT NULL,
                tag_text TEXT NOT NULL,
                confidence_score REAL,
                source TEXT,
                created_at TEXT,
                FOREIGN KEY (speaker_id) REFERENCES speakers(speaker_id),
                UNIQUE(speaker_id, tag_text)
            )
        ''')

        # Add tagging_status column to speakers table if it doesn't exist
        cursor.execute("PRAGMA table_info(speakers)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'tagging_status' not in columns:
            cursor.execute('ALTER TABLE speakers ADD COLUMN tagging_status TEXT DEFAULT "pending"')

        self.conn.commit()
    
    def add_event(self, url, title, body_text, raw_html=None, event_date=None, location='Switzerland'):
        """Add a new event to the database"""
        cursor = self.conn.cursor()
        scraped_at = datetime.now().isoformat()
        
        try:
            cursor.execute('''
                INSERT INTO events (url, title, event_date, location, body_text, raw_html, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (url, title, event_date, location, body_text, raw_html, scraped_at))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Event already exists
            cursor.execute('SELECT event_id FROM events WHERE url = ?', (url,))
            return cursor.fetchone()[0]
    
    def get_unprocessed_events(self):
        """Get all events that haven't been processed for speaker extraction yet"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT event_id, url, title, body_text 
            FROM events 
            WHERE processing_status = 'pending'
        ''')
        return cursor.fetchall()
    
    def _normalize_text(self, text):
        """Normalize text for comparison: lowercase, remove punctuation, split into words"""
        if not text:
            return set()
        import re
        # Lowercase and remove punctuation
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        # Split into words and filter short ones
        words = set(w for w in text.split() if len(w) > 2)
        return words

    def _affiliations_overlap(self, aff1, aff2):
        """Check if two affiliations likely refer to the same person"""
        # If both are empty/None, consider them matching
        if not aff1 and not aff2:
            return True
        # If one is empty, be lenient and match
        if not aff1 or not aff2:
            return True

        words1 = self._normalize_text(aff1)
        words2 = self._normalize_text(aff2)

        if not words1 or not words2:
            return True

        # Check for significant word overlap
        overlap = words1 & words2
        # If any meaningful words overlap, consider it a match
        # Exclude very common words
        common_words = {'the', 'and', 'for', 'university', 'center', 'institute', 'school', 'college'}
        meaningful_overlap = overlap - common_words

        if meaningful_overlap:
            return True

        # Also check if one contains a significant portion of the other
        min_words = min(len(words1), len(words2))
        if min_words > 0 and len(overlap) >= min_words * 0.5:
            return True

        return False

    def find_existing_speaker(self, name):
        """Find an existing speaker by name, returns (speaker_id, affiliation) or None"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT speaker_id, affiliation, primary_affiliation
            FROM speakers
            WHERE LOWER(name) = LOWER(?)
        ''', (name,))
        return cursor.fetchall()

    def add_speaker(self, name, title=None, affiliation=None, primary_affiliation=None, bio=None):
        """Add a speaker or return existing speaker_id. Uses fuzzy matching on name + affiliation."""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()

        # Use affiliation as primary_affiliation fallback
        if primary_affiliation is None:
            primary_affiliation = affiliation

        # First, check if a speaker with the same name exists
        existing = self.find_existing_speaker(name)

        if existing:
            # Check each existing speaker for affiliation overlap
            for speaker_id, existing_aff, existing_primary_aff in existing:
                # Compare affiliations
                new_aff = affiliation or primary_affiliation or ''
                old_aff = existing_aff or existing_primary_aff or ''

                if self._affiliations_overlap(new_aff, old_aff):
                    # Found a match - update the existing record with any new info
                    # Merge affiliations if new one has more info
                    merged_affiliation = existing_aff
                    if affiliation and (not existing_aff or len(affiliation) > len(existing_aff)):
                        merged_affiliation = affiliation

                    merged_bio = bio
                    cursor.execute('SELECT bio FROM speakers WHERE speaker_id = ?', (speaker_id,))
                    existing_bio = cursor.fetchone()[0]
                    if existing_bio and (not bio or len(existing_bio) > len(bio)):
                        merged_bio = existing_bio

                    cursor.execute('''
                        UPDATE speakers
                        SET last_updated = ?,
                            affiliation = COALESCE(?, affiliation),
                            bio = COALESCE(?, bio),
                            title = COALESCE(?, title)
                        WHERE speaker_id = ?
                    ''', (now, merged_affiliation, merged_bio, title, speaker_id))
                    self.conn.commit()
                    return speaker_id

        # No matching speaker found - create new one
        try:
            cursor.execute('''
                INSERT INTO speakers (name, title, affiliation, primary_affiliation, bio, first_seen, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, title, affiliation, primary_affiliation, bio, now, now))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Race condition or exact match - get existing ID
            cursor.execute('''
                SELECT speaker_id FROM speakers
                WHERE name = ? AND (primary_affiliation = ? OR (primary_affiliation IS NULL AND ? IS NULL))
            ''', (name, primary_affiliation, primary_affiliation))
            result = cursor.fetchone()
            if result:
                return result[0]
            # Fallback: just get any speaker with this name
            cursor.execute('SELECT speaker_id FROM speakers WHERE LOWER(name) = LOWER(?)', (name,))
            result = cursor.fetchone()
            if result:
                return result[0]
    
    def link_speaker_to_event(self, event_id, speaker_id, role_in_event=None, extracted_info=None):
        """Link a speaker to an event"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO event_speakers (event_id, speaker_id, role_in_event, extracted_info)
                VALUES (?, ?, ?, ?)
            ''', (event_id, speaker_id, role_in_event, extracted_info))
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Link already exists, update it
            cursor.execute('''
                UPDATE event_speakers 
                SET role_in_event = ?, extracted_info = ?
                WHERE event_id = ? AND speaker_id = ?
            ''', (role_in_event, extracted_info, event_id, speaker_id))
            self.conn.commit()
    
    def mark_event_processed(self, event_id, status='completed'):
        """Mark an event as processed"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE events 
            SET processing_status = ?, processed_at = ?
            WHERE event_id = ?
        ''', (status, datetime.now().isoformat(), event_id))
        self.conn.commit()
    
    def get_all_speakers(self):
        """Get all speakers from database"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT speaker_id, name, title, affiliation, bio, first_seen, last_updated
            FROM speakers
            ORDER BY name
        ''')
        return cursor.fetchall()
    
    def get_speaker_events(self, speaker_id):
        """Get all events for a specific speaker"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT e.event_id, e.title, e.event_date, e.url, es.role_in_event
            FROM events e
            JOIN event_speakers es ON e.event_id = es.event_id
            WHERE es.speaker_id = ?
            ORDER BY e.event_date DESC
        ''', (speaker_id,))
        return cursor.fetchall()
    
    def get_event_speakers(self, event_id):
        """Get all speakers for a specific event"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT s.speaker_id, s.name, s.title, s.affiliation, es.role_in_event
            FROM speakers s
            JOIN event_speakers es ON s.speaker_id = es.speaker_id
            WHERE es.event_id = ?
        ''', (event_id,))
        return cursor.fetchall()
    
    def get_statistics(self):
        """Get database statistics"""
        cursor = self.conn.cursor()

        stats = {}

        cursor.execute('SELECT COUNT(*) FROM events')
        stats['total_events'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM events WHERE processing_status = "completed"')
        stats['processed_events'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM speakers')
        stats['total_speakers'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM event_speakers')
        stats['total_connections'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(DISTINCT speaker_id) FROM speaker_tags')
        stats['tagged_speakers'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM speaker_tags')
        stats['total_tags'] = cursor.fetchone()[0]

        return stats

    def add_speaker_tag(self, speaker_id, tag_text, confidence=None, source='web_search'):
        """Add a tag to a speaker"""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()

        try:
            cursor.execute('''
                INSERT INTO speaker_tags (speaker_id, tag_text, confidence_score, source, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (speaker_id, tag_text.lower().strip(), confidence, source, now))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Tag already exists for this speaker
            return None

    def get_speaker_tags(self, speaker_id):
        """Get all tags for a speaker"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT tag_text, confidence_score, source, created_at
            FROM speaker_tags
            WHERE speaker_id = ?
            ORDER BY confidence_score DESC
        ''', (speaker_id,))
        return cursor.fetchall()

    def get_untagged_speakers(self):
        """Get all speakers that haven't been tagged yet"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT speaker_id, name, title, affiliation, primary_affiliation, bio
            FROM speakers
            WHERE tagging_status = 'pending' OR tagging_status IS NULL
        ''')
        return cursor.fetchall()

    def mark_speaker_tagged(self, speaker_id, status='completed'):
        """Mark a speaker's tagging status"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE speakers
            SET tagging_status = ?
            WHERE speaker_id = ?
        ''', (status, speaker_id))
        self.conn.commit()

    def get_speaker_by_id(self, speaker_id):
        """Get a speaker by ID"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT speaker_id, name, title, affiliation, primary_affiliation, bio
            FROM speakers
            WHERE speaker_id = ?
        ''', (speaker_id,))
        return cursor.fetchone()

    def reset_speaker_tagging_status(self):
        """Reset all speakers to pending tagging status"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE speakers SET tagging_status = 'pending'")
        cursor.execute("DELETE FROM speaker_tags")
        self.conn.commit()

    def merge_duplicates(self, verbose=False):
        """
        Find and merge duplicate speakers (same name, different records).
        Returns the number of duplicates merged.
        """
        cursor = self.conn.cursor()

        # Find duplicate groups
        cursor.execute('''
            SELECT LOWER(name) as normalized_name, GROUP_CONCAT(speaker_id) as ids
            FROM speakers
            GROUP BY LOWER(name)
            HAVING COUNT(*) > 1
        ''')
        duplicate_groups = cursor.fetchall()

        if not duplicate_groups:
            return 0

        merged_count = 0

        for normalized_name, id_str in duplicate_groups:
            speaker_ids = [int(x) for x in id_str.split(',')]

            # Get details for all speakers in this group
            speakers = []
            for sid in speaker_ids:
                cursor.execute('''
                    SELECT speaker_id, name, title, affiliation, primary_affiliation, bio
                    FROM speakers WHERE speaker_id = ?
                ''', (sid,))
                speakers.append(cursor.fetchone())

            # Score by completeness (longer affiliation/bio = more info)
            def completeness_score(s):
                score = 0
                if s[2]: score += 1  # title
                if s[3]: score += len(s[3])  # affiliation length
                if s[4]: score += 1  # primary_affiliation
                if s[5]: score += len(s[5]) if s[5] else 0  # bio length
                return score

            speakers_sorted = sorted(speakers, key=completeness_score, reverse=True)
            primary = speakers_sorted[0]
            primary_id = primary[0]
            duplicates = speakers_sorted[1:]

            if verbose:
                print(f"Merging '{primary[1]}': keeping ID={primary_id}, merging {len(duplicates)} duplicates")

            # Merge info from duplicates into primary
            merged_title = primary[2]
            merged_affiliation = primary[3]
            merged_primary_aff = primary[4]
            merged_bio = primary[5]

            for dup in duplicates:
                if dup[2] and (not merged_title or len(dup[2]) > len(merged_title)):
                    merged_title = dup[2]
                if dup[3] and (not merged_affiliation or len(dup[3]) > len(merged_affiliation)):
                    merged_affiliation = dup[3]
                if dup[4] and not merged_primary_aff:
                    merged_primary_aff = dup[4]
                if dup[5] and (not merged_bio or len(dup[5]) > len(merged_bio)):
                    merged_bio = dup[5]

            # Update primary speaker with merged info
            cursor.execute('''
                UPDATE speakers
                SET title = ?, affiliation = ?, primary_affiliation = ?, bio = ?, last_updated = datetime('now')
                WHERE speaker_id = ?
            ''', (merged_title, merged_affiliation, merged_primary_aff, merged_bio, primary_id))

            # Reassign event links and delete duplicates
            for dup in duplicates:
                dup_id = dup[0]

                # Get event links for the duplicate
                cursor.execute('''
                    SELECT event_id, role_in_event, extracted_info
                    FROM event_speakers WHERE speaker_id = ?
                ''', (dup_id,))
                event_links = cursor.fetchall()

                for event_id, role, info in event_links:
                    # Check if primary already linked to this event
                    cursor.execute('''
                        SELECT 1 FROM event_speakers
                        WHERE event_id = ? AND speaker_id = ?
                    ''', (event_id, primary_id))

                    if cursor.fetchone():
                        # Already linked, delete duplicate link
                        cursor.execute('''
                            DELETE FROM event_speakers
                            WHERE event_id = ? AND speaker_id = ?
                        ''', (event_id, dup_id))
                    else:
                        # Reassign to primary
                        cursor.execute('''
                            UPDATE event_speakers SET speaker_id = ?
                            WHERE event_id = ? AND speaker_id = ?
                        ''', (primary_id, event_id, dup_id))

                # Delete the duplicate speaker record
                cursor.execute('DELETE FROM speakers WHERE speaker_id = ?', (dup_id,))
                merged_count += 1

        self.conn.commit()
        return merged_count

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
