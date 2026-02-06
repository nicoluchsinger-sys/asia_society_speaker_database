"""
Database management for Asia Society events and speakers.

This module provides the SpeakerDatabase class which handles all SQLite operations
for storing and querying event and speaker data. It includes intelligent deduplication
logic that uses fuzzy affiliation matching to prevent duplicate speaker records.
"""

import sqlite3
from datetime import datetime
import json
from typing import Optional, List, Tuple, Dict, Any

class SpeakerDatabase:
    """
    Main database interface for speaker and event data.

    This class manages a SQLite database with tables for:
    - Events: Scraped event pages from Asia Society
    - Speakers: Deduplicated speaker records
    - Event-Speaker links: Many-to-many relationship
    - Speaker tags: Expertise/topic tags
    - Speaker embeddings: Vector embeddings for semantic search
    - Speaker demographics: Gender, nationality, birth year
    - Speaker locations: Geographic information
    - Speaker languages: Language proficiency data

    The database uses fuzzy affiliation matching during speaker insertion to avoid
    creating duplicate records for speakers who appear at multiple events with
    slight variations in their affiliation names.
    """

    def __init__(self, db_path: str = 'speakers.db'):
        """
        Initialize database connection and create tables if needed.

        Args:
            db_path: Path to SQLite database file (default: 'speakers.db')
        """
        self.db_path = db_path
        self.conn = None
        self.init_database()

    def init_database(self) -> None:
        """
        Initialize database with required tables and run migrations.

        Creates all necessary tables if they don't exist and applies any schema
        migrations (like adding new columns to existing tables). This is safe to
        run multiple times - it only creates missing structures.
        """
        # check_same_thread=False is safe here because we create new connections per request
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
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

        # Speaker embeddings table (for semantic search)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS speaker_embeddings (
                speaker_id INTEGER PRIMARY KEY,
                embedding_model TEXT NOT NULL DEFAULT 'voyage-3',
                embedding BLOB NOT NULL,
                embedding_text TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (speaker_id) REFERENCES speakers(speaker_id) ON DELETE CASCADE
            )
        ''')

        # Speaker demographics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS speaker_demographics (
                speaker_id INTEGER PRIMARY KEY,
                gender TEXT,
                gender_confidence REAL,
                nationality TEXT,
                nationality_confidence REAL,
                birth_year INTEGER,
                enriched_at TEXT,
                FOREIGN KEY (speaker_id) REFERENCES speakers(speaker_id) ON DELETE CASCADE
            )
        ''')

        # Speaker locations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS speaker_locations (
                location_id INTEGER PRIMARY KEY AUTOINCREMENT,
                speaker_id INTEGER NOT NULL,
                location_type TEXT NOT NULL,
                city TEXT,
                country TEXT,
                region TEXT,
                is_primary BOOLEAN DEFAULT 0,
                confidence REAL,
                source TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (speaker_id) REFERENCES speakers(speaker_id) ON DELETE CASCADE
            )
        ''')

        # Speaker languages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS speaker_languages (
                language_id INTEGER PRIMARY KEY AUTOINCREMENT,
                speaker_id INTEGER NOT NULL,
                language TEXT NOT NULL,
                proficiency TEXT,
                confidence REAL,
                source TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (speaker_id) REFERENCES speakers(speaker_id) ON DELETE CASCADE
            )
        ''')

        # Speaker freshness tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS speaker_freshness (
                speaker_id INTEGER PRIMARY KEY,
                last_refreshed TEXT NOT NULL,
                refresh_count INTEGER DEFAULT 1,
                needs_refresh BOOLEAN DEFAULT 0,
                priority_score REAL DEFAULT 0,
                FOREIGN KEY (speaker_id) REFERENCES speakers(speaker_id) ON DELETE CASCADE
            )
        ''')

        # Add tagging_status column to speakers table if it doesn't exist
        cursor.execute("PRAGMA table_info(speakers)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'tagging_status' not in columns:
            cursor.execute('ALTER TABLE speakers ADD COLUMN tagging_status TEXT DEFAULT "pending"')

        # Add performance indexes for fuzzy matching and filtering at scale
        # These become critical with 1000+ speakers to prevent O(n) lookups
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_speakers_name_lower ON speakers(LOWER(name))')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_status ON events(processing_status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_event_speakers_speaker ON event_speakers(speaker_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_event_speakers_event ON event_speakers(event_id)')

        # Indexes for search-related tables
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_embeddings_speaker ON speaker_embeddings(speaker_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_demographics_speaker ON speaker_demographics(speaker_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_locations_speaker ON speaker_locations(speaker_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_locations_primary ON speaker_locations(is_primary)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_languages_speaker ON speaker_languages(speaker_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_freshness_needs_refresh ON speaker_freshness(needs_refresh)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_freshness_priority ON speaker_freshness(priority_score)')

        # Migration: add cost breakdown columns to pipeline_runs if they don't exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_runs'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(pipeline_runs)")
            existing_columns = [row[1] for row in cursor.fetchall()]

            if 'extraction_cost' not in existing_columns:
                cursor.execute("ALTER TABLE pipeline_runs ADD COLUMN extraction_cost REAL DEFAULT 0")
            if 'embedding_cost' not in existing_columns:
                cursor.execute("ALTER TABLE pipeline_runs ADD COLUMN embedding_cost REAL DEFAULT 0")
            if 'enrichment_cost' not in existing_columns:
                cursor.execute("ALTER TABLE pipeline_runs ADD COLUMN enrichment_cost REAL DEFAULT 0")

        self.conn.commit()
    
    def add_event(self, url: str, title: str, body_text: str, raw_html: Optional[str] = None,
                  event_date: Optional[str] = None, location: str = 'Unknown') -> int:
        """
        Add a new event to the database or return existing event ID.

        This method is idempotent - calling it multiple times with the same URL
        will not create duplicate records. The URL serves as a unique identifier.

        Args:
            url: Event page URL (must be unique)
            title: Event title
            body_text: Extracted text content from event page
            raw_html: Optional raw HTML for reference/debugging
            event_date: Event date in ISO format (YYYY-MM-DD)
            location: Event location (default: 'Unknown')

        Returns:
            event_id (int): The ID of the newly created or existing event

        Note:
            If an event with the same URL already exists, returns that event's ID
            rather than raising an error. This makes the scraper idempotent.
        """
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
            # URL already exists - this is expected behavior when re-running scraper
            # Return the existing event ID rather than failing
            cursor.execute('SELECT event_id FROM events WHERE url = ?', (url,))
            return cursor.fetchone()[0]
    
    def get_unprocessed_events(self) -> List[Tuple]:
        """
        Get all events that haven't been processed for speaker extraction yet.

        Returns:
            List of tuples: (event_id, url, title, body_text) for each pending event

        Note:
            Only returns events with processing_status = 'pending'.
            Events marked 'completed' or 'failed' are excluded.
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT event_id, url, title, body_text
            FROM events
            WHERE processing_status = 'pending'
        ''')
        return cursor.fetchall()

    def _normalize_text(self, text: Optional[str]) -> set:
        """
        Normalize text for fuzzy affiliation comparison.

        This is used for intelligent deduplication of speakers. By normalizing
        affiliation text, we can detect that "NYU", "New York University", and
        "New York University School of Law" all refer to the same institution.

        Process:
        1. Convert to lowercase
        2. Remove all punctuation
        3. Split into words
        4. Filter out short words (≤2 chars) to remove noise like "of", "at"

        Args:
            text: Text to normalize (affiliation name, etc.)

        Returns:
            Set of normalized words, empty set if text is None/empty

        Example:
            >>> db._normalize_text("New York University")
            {'new', 'york', 'university'}
            >>> db._normalize_text("NYU School of Law")
            {'nyu', 'school', 'law'}
        """
        if not text:
            return set()
        import re
        # Lowercase and remove punctuation
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        # Split into words and filter short ones
        words = set(w for w in text.split() if len(w) > 2)
        return words

    def _affiliations_overlap(self, aff1: Optional[str], aff2: Optional[str]) -> bool:
        """
        Determine if two affiliations likely refer to the same institution/organization.

        This is the core logic for preventing duplicate speaker records. When a speaker
        appears at multiple events, their affiliation might be written differently each time:
        - "Harvard University" vs "Harvard" vs "Harvard Kennedy School"
        - "NYU" vs "New York University"
        - "Council on Foreign Relations" vs "CFR"

        This function uses fuzzy matching to detect when affiliations refer to the same
        organization, allowing us to merge speaker records intelligently.

        Strategy:
        1. If both affiliations are empty/None → Match (same person, affiliation not mentioned)
        2. If one is empty → Match (be lenient, assume same person)
        3. Normalize both affiliations to word sets
        4. Check for meaningful word overlap (excluding common words like "university")
        5. Check if one affiliation contains 50%+ of the other's words

        Args:
            aff1: First affiliation string
            aff2: Second affiliation string

        Returns:
            True if affiliations likely refer to same organization, False otherwise

        Examples:
            >>> db._affiliations_overlap("Harvard University", "Harvard Kennedy School")
            True  # Shares "harvard"
            >>> db._affiliations_overlap("NYU", "New York University")
            False  # No word overlap, but this is a known limitation
            >>> db._affiliations_overlap("MIT", "Stanford University")
            False  # Different institutions
        """
        # Handle None/empty cases - be lenient to avoid creating unnecessary duplicates
        # when affiliation information is missing or incomplete
        if not aff1 and not aff2:
            return True
        if not aff1 or not aff2:
            return True

        words1 = self._normalize_text(aff1)
        words2 = self._normalize_text(aff2)

        if not words1 or not words2:
            return True

        # Calculate word overlap between the two affiliations
        overlap = words1 & words2

        # Filter out very common words that don't help identify specific institutions
        # Words like "university", "center" appear in many affiliations and aren't distinctive
        common_words = {'the', 'and', 'for', 'university', 'center', 'institute', 'school', 'college'}
        meaningful_overlap = overlap - common_words

        # If we found any distinctive words in common, consider it a match
        if meaningful_overlap:
            return True

        # Alternative check: if one affiliation contains a significant portion (50%+)
        # of the other's words (including common words), it's likely the same institution
        # This handles cases like "Harvard" vs "Harvard University"
        min_words = min(len(words1), len(words2))
        if min_words > 0 and len(overlap) >= min_words * 0.5:
            return True

        return False

    def find_existing_speaker(self, name: str) -> List[Tuple[int, str, str]]:
        """
        Find all existing speaker records with matching name (case-insensitive).

        This returns ALL speakers with the given name, not just one. The caller
        (typically add_speaker) then uses affiliation matching to determine which
        of these records (if any) represents the same person.

        Args:
            name: Speaker name to search for

        Returns:
            List of tuples: (speaker_id, affiliation, primary_affiliation)
            Empty list if no speakers found with this name

        Note:
            Name matching is case-insensitive but must be exact (no fuzzy matching).
            "John Smith" will match "JOHN SMITH" but not "Jon Smith".
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT speaker_id, affiliation, primary_affiliation
            FROM speakers
            WHERE LOWER(name) = LOWER(?)
        ''', (name,))
        return cursor.fetchall()

    def add_speaker(self, name: str, title: Optional[str] = None,
                   affiliation: Optional[str] = None,
                   primary_affiliation: Optional[str] = None,
                   bio: Optional[str] = None) -> int:
        """
        Add a speaker to the database or return existing speaker ID if duplicate detected.

        This is the most complex function in the database layer. It implements intelligent
        deduplication to prevent creating duplicate speaker records when the same person
        appears at multiple events.

        Deduplication Strategy:
        1. Search for existing speakers with exact same name (case-insensitive)
        2. For each match, compare affiliations using fuzzy matching
        3. If affiliation overlap detected → update existing record, return its ID
        4. If no matches found → create new speaker record

        When updating an existing record:
        - Merge affiliations (keep longer/more detailed one)
        - Merge bio (keep longer one)
        - Update title if new one provided
        - Update last_updated timestamp

        Args:
            name: Speaker's full name (required)
            title: Professional title (e.g., "CEO", "Professor")
            affiliation: Full affiliation string, may list multiple organizations
            primary_affiliation: Single main organization for deduplication
            bio: Biographical information

        Returns:
            speaker_id (int): ID of created or matched existing speaker

        Raises:
            sqlite3.IntegrityError: In rare race conditions (handled internally)

        Examples:
            # First occurrence
            >>> db.add_speaker("Jane Doe", affiliation="Harvard University")
            1

            # Second occurrence with similar affiliation - returns same ID
            >>> db.add_speaker("Jane Doe", affiliation="Harvard Kennedy School")
            1  # Matched to existing record

            # Different affiliation - creates new record
            >>> db.add_speaker("Jane Doe", affiliation="Stanford University")
            2  # New record, different institution
        """
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
    
    def link_speaker_to_event(self, event_id: int, speaker_id: int,
                             role_in_event: Optional[str] = None,
                             extracted_info: Optional[str] = None) -> None:
        """
        Create or update a link between a speaker and an event.

        This function is idempotent - calling it multiple times with the same
        event_id and speaker_id will update the existing link rather than fail.

        Args:
            event_id: Event ID
            speaker_id: Speaker ID
            role_in_event: Speaker's role (e.g., "keynote", "panelist", "moderator")
            extracted_info: Additional JSON-encoded information extracted by Claude

        Note:
            If the link already exists, updates the role_in_event and extracted_info
            fields rather than creating a duplicate.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO event_speakers (event_id, speaker_id, role_in_event, extracted_info)
                VALUES (?, ?, ?, ?)
            ''', (event_id, speaker_id, role_in_event, extracted_info))
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Link already exists (duplicate event_id + speaker_id)
            # Update with new information rather than failing
            cursor.execute('''
                UPDATE event_speakers
                SET role_in_event = ?, extracted_info = ?
                WHERE event_id = ? AND speaker_id = ?
            ''', (role_in_event, extracted_info, event_id, speaker_id))
            self.conn.commit()

    def mark_event_processed(self, event_id: int, status: str = 'completed') -> None:
        """
        Mark an event as processed (or failed) after speaker extraction.

        Args:
            event_id: Event ID to update
            status: Processing status ('completed', 'failed', or custom value)

        Note:
            Also sets the processed_at timestamp to current time.
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE events
            SET processing_status = ?, processed_at = ?
            WHERE event_id = ?
        ''', (status, datetime.now().isoformat(), event_id))
        self.conn.commit()

    def get_all_speakers(self) -> List[Tuple]:
        """
        Get all speakers from database, ordered alphabetically by name.

        Returns:
            List of tuples: (speaker_id, name, title, affiliation, bio, first_seen, last_updated)
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT speaker_id, name, title, affiliation, bio, first_seen, last_updated
            FROM speakers
            ORDER BY name
        ''')
        return cursor.fetchall()

    def get_speaker_events(self, speaker_id: int) -> List[Tuple]:
        """
        Get all events where a specific speaker participated.

        Args:
            speaker_id: Speaker ID

        Returns:
            List of tuples: (event_id, title, event_date, url, role_in_event)
            Ordered by event_date descending (most recent first)
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT e.event_id, e.title, e.event_date, e.url, es.role_in_event
            FROM events e
            JOIN event_speakers es ON e.event_id = es.event_id
            WHERE es.speaker_id = ?
            ORDER BY e.event_date DESC
        ''', (speaker_id,))
        return cursor.fetchall()

    def get_event_speakers(self, event_id: int) -> List[Tuple]:
        """
        Get all speakers who participated in a specific event.

        Args:
            event_id: Event ID

        Returns:
            List of tuples: (speaker_id, name, title, affiliation, role_in_event)
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT s.speaker_id, s.name, s.title, s.affiliation, es.role_in_event
            FROM speakers s
            JOIN event_speakers es ON s.speaker_id = es.speaker_id
            WHERE es.event_id = ?
        ''', (event_id,))
        return cursor.fetchall()

    def get_statistics(self) -> Dict[str, int]:
        """
        Get database statistics for all tables.

        Returns:
            Dictionary with keys:
            - total_events: Total events scraped
            - processed_events: Events with completed speaker extraction
            - total_speakers: Total deduplicated speakers
            - total_connections: Total event-speaker links
            - tagged_speakers: Speakers with at least one tag
            - total_tags: Total tag records
        """
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

    def get_enhanced_statistics(self) -> Dict:
        """
        Get enhanced database statistics including enrichment progress and costs

        Returns:
            Dictionary with comprehensive stats including:
            - Basic counts (events, speakers, tags)
            - Enrichment progress (enriched vs remaining)
            - Embeddings count
            - API costs (total and by service)
            - Recent activity (last 7 days)
        """
        cursor = self.conn.cursor()
        stats = {}

        # Basic counts
        cursor.execute('SELECT COUNT(*) FROM events')
        stats['total_events'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM events WHERE processing_status = "completed"')
        stats['processed_events'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM speakers')
        stats['total_speakers'] = cursor.fetchone()[0]

        # Enrichment progress
        cursor.execute('SELECT COUNT(*) FROM speakers WHERE tagging_status = "completed"')
        stats['enriched_speakers'] = cursor.fetchone()[0]
        stats['unenriched_speakers'] = stats['total_speakers'] - stats['enriched_speakers']
        stats['enrichment_percentage'] = round(
            (stats['enriched_speakers'] / stats['total_speakers'] * 100) if stats['total_speakers'] > 0 else 0,
            1
        )

        # Embeddings
        cursor.execute('SELECT COUNT(*) FROM speaker_embeddings')
        stats['speakers_with_embeddings'] = cursor.fetchone()[0]

        # Tags
        cursor.execute('SELECT COUNT(DISTINCT speaker_id) FROM speaker_tags')
        stats['tagged_speakers'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM speaker_tags')
        stats['total_tags'] = cursor.fetchone()[0]

        # Pipeline runs and costs (if table exists)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_runs'")
        if cursor.fetchone():
            # Total costs
            cursor.execute('SELECT COALESCE(SUM(total_cost), 0) FROM pipeline_runs')
            stats['total_api_cost'] = round(cursor.fetchone()[0], 2)

            # Cost breakdown by service (if columns exist)
            try:
                cursor.execute('''
                    SELECT
                        COALESCE(SUM(extraction_cost), 0),
                        COALESCE(SUM(embedding_cost), 0),
                        COALESCE(SUM(enrichment_cost), 0)
                    FROM pipeline_runs
                ''')
                row = cursor.fetchone()
                stats['cost_breakdown'] = {
                    'extraction': round(row[0], 4),
                    'embeddings': round(row[1], 4),
                    'enrichment': round(row[2], 4)
                }
            except sqlite3.OperationalError:
                # Columns don't exist yet, will be added on next pipeline run
                stats['cost_breakdown'] = {
                    'extraction': 0,
                    'embeddings': 0,
                    'enrichment': 0
                }

            # Last 7 days of activity
            from datetime import datetime, timedelta
            seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()

            cursor.execute('''
                SELECT
                    COALESCE(SUM(events_scraped), 0),
                    COALESCE(SUM(speakers_extracted), 0),
                    COALESCE(SUM(new_speakers_enriched + existing_speakers_enriched), 0),
                    COALESCE(SUM(total_cost), 0)
                FROM pipeline_runs
                WHERE timestamp > ?
            ''', (seven_days_ago,))

            row = cursor.fetchone()
            stats['last_7_days'] = {
                'events_scraped': row[0],
                'speakers_extracted': row[1],
                'speakers_enriched': row[2],
                'api_cost': round(row[3], 2)
            }

            # Most recent run
            cursor.execute('''
                SELECT timestamp, events_scraped, speakers_extracted,
                       new_speakers_enriched, existing_speakers_enriched, total_cost
                FROM pipeline_runs
                ORDER BY timestamp DESC
                LIMIT 1
            ''')
            last_run = cursor.fetchone()
            if last_run:
                stats['last_pipeline_run'] = {
                    'timestamp': last_run[0],
                    'events_scraped': last_run[1],
                    'speakers_extracted': last_run[2],
                    'new_speakers_enriched': last_run[3],
                    'existing_speakers_enriched': last_run[4],
                    'cost': round(last_run[5], 4)
                }
        else:
            stats['total_api_cost'] = 0
            stats['last_7_days'] = {
                'events_scraped': 0,
                'speakers_extracted': 0,
                'speakers_enriched': 0,
                'api_cost': 0
            }

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

    def enrich_speaker_data(self, speaker_id, enriched_title=None, enriched_bio=None):
        """
        Update speaker with enriched data from web search

        Args:
            speaker_id: Speaker ID
            enriched_title: Updated job title (or None to skip)
            enriched_bio: Enriched biography (or None to skip)
        """
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()

        # Build UPDATE query dynamically based on what's being enriched
        updates = []
        params = []

        if enriched_title:
            updates.append('title = ?')
            params.append(enriched_title)

        if enriched_bio:
            updates.append('bio = ?')
            params.append(enriched_bio)

        if updates:
            updates.append('last_updated = ?')
            params.append(now)
            params.append(speaker_id)

            query = f"UPDATE speakers SET {', '.join(updates)} WHERE speaker_id = ?"
            cursor.execute(query, params)
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

    def reset_speaker_tagging_status(self) -> None:
        """
        ⚠️ DESTRUCTIVE OPERATION ⚠️
        Reset all speakers to pending tagging status and DELETE all existing tags.

        This operation:
        1. Sets tagging_status = 'pending' for ALL speakers
        2. DELETES ALL records from speaker_tags table

        Use this when:
        - Changing the tagging algorithm and want to re-tag everyone
        - Testing the tagging system
        - Fixing errors in existing tags

        ⚠️ WARNING: This CANNOT be undone. All tag data will be permanently lost.
        Consider backing up the database before running this operation.
        """
        cursor = self.conn.cursor()
        cursor.execute("UPDATE speakers SET tagging_status = 'pending'")
        cursor.execute("DELETE FROM speaker_tags")
        self.conn.commit()

    # ========== Embedding Methods ==========

    def save_speaker_embedding(self, speaker_id, embedding_blob, embedding_text, model='voyage-3'):
        """Save embedding for a speaker"""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()

        try:
            cursor.execute('''
                INSERT INTO speaker_embeddings (speaker_id, embedding_model, embedding, embedding_text, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (speaker_id, model, embedding_blob, embedding_text, now))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Update existing embedding
            cursor.execute('''
                UPDATE speaker_embeddings
                SET embedding = ?, embedding_text = ?, embedding_model = ?, created_at = ?
                WHERE speaker_id = ?
            ''', (embedding_blob, embedding_text, model, now, speaker_id))
            self.conn.commit()
            return True

    def get_speaker_embedding(self, speaker_id):
        """Get embedding for a specific speaker"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT embedding, embedding_text, embedding_model, created_at
            FROM speaker_embeddings
            WHERE speaker_id = ?
        ''', (speaker_id,))
        return cursor.fetchone()

    def get_all_embeddings(self):
        """Get all speaker embeddings (speaker_id, embedding pairs)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT speaker_id, embedding
            FROM speaker_embeddings
        ''')
        return cursor.fetchall()

    def get_speakers_without_embeddings(self):
        """Get all speakers that don't have embeddings yet"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT s.speaker_id, s.name, s.title, s.affiliation, s.primary_affiliation, s.bio
            FROM speakers s
            LEFT JOIN speaker_embeddings e ON s.speaker_id = e.speaker_id
            WHERE e.speaker_id IS NULL
        ''')
        return cursor.fetchall()

    def count_embeddings(self):
        """Count how many speakers have embeddings"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM speaker_embeddings')
        return cursor.fetchone()[0]

    # ========== Enrichment Methods ==========

    def save_speaker_demographics(self, speaker_id, gender=None, gender_confidence=None,
                                  nationality=None, nationality_confidence=None, birth_year=None):
        """Save demographic information for a speaker"""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()

        try:
            cursor.execute('''
                INSERT INTO speaker_demographics
                (speaker_id, gender, gender_confidence, nationality, nationality_confidence, birth_year, enriched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (speaker_id, gender, gender_confidence, nationality, nationality_confidence, birth_year, now))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Update existing
            cursor.execute('''
                UPDATE speaker_demographics
                SET gender = ?, gender_confidence = ?, nationality = ?,
                    nationality_confidence = ?, birth_year = ?, enriched_at = ?
                WHERE speaker_id = ?
            ''', (gender, gender_confidence, nationality, nationality_confidence, birth_year, now, speaker_id))
            self.conn.commit()
            return True

    def get_speaker_demographics(self, speaker_id):
        """Get demographic information for a speaker"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT gender, gender_confidence, nationality, nationality_confidence, birth_year, enriched_at
            FROM speaker_demographics
            WHERE speaker_id = ?
        ''', (speaker_id,))
        return cursor.fetchone()

    def save_speaker_location(self, speaker_id, location_type, city=None, country=None,
                             region=None, is_primary=False, confidence=None, source=None):
        """Save location information for a speaker"""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute('''
            INSERT INTO speaker_locations
            (speaker_id, location_type, city, country, region, is_primary, confidence, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (speaker_id, location_type, city, country, region, is_primary, confidence, source, now))
        self.conn.commit()
        return cursor.lastrowid

    def get_speaker_locations(self, speaker_id):
        """Get all locations for a speaker"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT location_id, location_type, city, country, region, is_primary, confidence, source, created_at
            FROM speaker_locations
            WHERE speaker_id = ?
            ORDER BY is_primary DESC, confidence DESC
        ''', (speaker_id,))
        return cursor.fetchall()

    def save_speaker_language(self, speaker_id, language, proficiency=None, confidence=None, source=None):
        """Save language information for a speaker"""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()

        try:
            cursor.execute('''
                INSERT INTO speaker_languages
                (speaker_id, language, proficiency, confidence, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (speaker_id, language, proficiency, confidence, source, now))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Language already exists for this speaker, update it
            cursor.execute('''
                UPDATE speaker_languages
                SET proficiency = ?, confidence = ?, source = ?, created_at = ?
                WHERE speaker_id = ? AND language = ?
            ''', (proficiency, confidence, source, now, speaker_id, language))
            self.conn.commit()
            return None

    def get_speaker_languages(self, speaker_id):
        """Get all languages for a speaker"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT language, proficiency, confidence, source, created_at
            FROM speaker_languages
            WHERE speaker_id = ?
            ORDER BY confidence DESC
        ''', (speaker_id,))
        return cursor.fetchall()

    def merge_duplicates(self, verbose: bool = False) -> int:
        """
        Find and merge duplicate speaker records (same name, different IDs).

        This is a cleanup function that catches any duplicates that slipped through
        the fuzzy matching in add_speaker(). It's typically run after bulk speaker
        extraction to consolidate records.

        Process:
        1. Find all speakers with duplicate names (case-insensitive)
        2. For each duplicate group:
           a. Score records by completeness (more info = higher score)
           b. Keep the most complete record as "primary"
           c. Merge information from duplicates into primary
           d. Reassign all event links to primary
           e. Delete duplicate records

        Information Merging Strategy:
        - Title: Keep longest/most detailed
        - Affiliation: Keep longest/most detailed
        - Primary affiliation: Use from primary unless missing
        - Bio: Keep longest

        Args:
            verbose: If True, print merge operations as they happen

        Returns:
            Number of duplicate records merged (deleted)

        Note:
            This operation modifies speaker_ids. Any external references to deleted
            speaker IDs will be updated to point to the merged primary ID.

        Example:
            If we have:
            - ID 1: "Jane Doe", affiliation="Harvard", bio=""
            - ID 2: "Jane Doe", affiliation="Harvard University", bio="Professor of..."

            After merge:
            - ID 2 becomes primary (more complete)
            - ID 1's event links reassigned to ID 2
            - ID 1 deleted
            - Returns: 1 (one duplicate merged)
        """
        cursor = self.conn.cursor()

        # Find all speaker names that have multiple records
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

            # Fetch full records for all speakers in this duplicate group
            speakers = []
            for sid in speaker_ids:
                cursor.execute('''
                    SELECT speaker_id, name, title, affiliation, primary_affiliation, bio
                    FROM speakers WHERE speaker_id = ?
                ''', (sid,))
                speakers.append(cursor.fetchone())

            # Score each record by completeness - the most complete record becomes primary
            # This ensures we keep the record with the most information
            def completeness_score(s):
                score = 0
                if s[2]: score += 1  # Has title
                if s[3]: score += len(s[3])  # Affiliation length
                if s[4]: score += 1  # Has primary_affiliation
                if s[5]: score += len(s[5]) if s[5] else 0  # Bio length
                return score

            speakers_sorted = sorted(speakers, key=completeness_score, reverse=True)
            primary = speakers_sorted[0]
            primary_id = primary[0]
            duplicates = speakers_sorted[1:]

            if verbose:
                print(f"Merging '{primary[1]}': keeping ID={primary_id}, merging {len(duplicates)} duplicates")

            # Merge information from all duplicates into the primary record
            # Always prefer longer/more detailed information
            merged_title = primary[2]
            merged_affiliation = primary[3]
            merged_primary_aff = primary[4]
            merged_bio = primary[5]

            for dup in duplicates:
                # Keep longer title
                if dup[2] and (not merged_title or len(dup[2]) > len(merged_title)):
                    merged_title = dup[2]
                # Keep longer affiliation string
                if dup[3] and (not merged_affiliation or len(dup[3]) > len(merged_affiliation)):
                    merged_affiliation = dup[3]
                # Fill in primary affiliation if missing
                if dup[4] and not merged_primary_aff:
                    merged_primary_aff = dup[4]
                # Keep longer bio
                if dup[5] and (not merged_bio or len(dup[5]) > len(merged_bio)):
                    merged_bio = dup[5]

            # Update the primary record with merged information
            cursor.execute('''
                UPDATE speakers
                SET title = ?, affiliation = ?, primary_affiliation = ?, bio = ?, last_updated = datetime('now')
                WHERE speaker_id = ?
            ''', (merged_title, merged_affiliation, merged_primary_aff, merged_bio, primary_id))

            # Reassign all event links from duplicates to primary, then delete duplicates
            for dup in duplicates:
                dup_id = dup[0]

                # Get all events linked to this duplicate
                cursor.execute('''
                    SELECT event_id, role_in_event, extracted_info
                    FROM event_speakers WHERE speaker_id = ?
                ''', (dup_id,))
                event_links = cursor.fetchall()

                for event_id, role, info in event_links:
                    # Check if primary is already linked to this event
                    cursor.execute('''
                        SELECT 1 FROM event_speakers
                        WHERE event_id = ? AND speaker_id = ?
                    ''', (event_id, primary_id))

                    if cursor.fetchone():
                        # Primary already linked - just delete the duplicate link
                        cursor.execute('''
                            DELETE FROM event_speakers
                            WHERE event_id = ? AND speaker_id = ?
                        ''', (event_id, dup_id))
                    else:
                        # Reassign the link to primary speaker
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
