"""
Tests for merge_duplicates.py and monitoring.py.

merge_duplicates.py:
- find_duplicate_groups
- get_speaker_details
- get_event_count
- merge_speakers (dry run and execution)

monitoring.py:
- PipelineMonitor initialization
- get_health_status
- get_database_stats
- verify_statistics
- _parse_datetime
"""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SpeakerDatabase
from merge_duplicates import find_duplicate_groups, get_speaker_details, get_event_count


# ── merge_duplicates.py ─────────────────────────────────────────────────

class TestFindDuplicateGroups:
    def test_no_duplicates(self, db):
        db.add_speaker(name="Jane Smith", affiliation="MIT")
        db.add_speaker(name="John Doe", affiliation="Harvard")
        groups = find_duplicate_groups(db)
        assert len(groups) == 0

    def test_finds_exact_name_duplicates(self, db):
        """Two speakers with same name but different affiliations (no overlap)."""
        # Force-insert to bypass deduplication
        cursor = db.conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            'INSERT INTO speakers (name, affiliation, primary_affiliation, first_seen) VALUES (?, ?, ?, ?)',
            ("Jane Smith", "MIT", "MIT", now)
        )
        cursor.execute(
            'INSERT INTO speakers (name, affiliation, primary_affiliation, first_seen) VALUES (?, ?, ?, ?)',
            ("Jane Smith", "Stanford", "Stanford", now)
        )
        db.conn.commit()

        groups = find_duplicate_groups(db)
        assert len(groups) >= 1

    def test_finds_title_variant_duplicates(self, db):
        """'Dr. Jane Smith' and 'Jane Smith' should be found as duplicates."""
        cursor = db.conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            'INSERT INTO speakers (name, affiliation, primary_affiliation, first_seen) VALUES (?, ?, ?, ?)',
            ("Jane Smith", "MIT", "MIT", now)
        )
        cursor.execute(
            'INSERT INTO speakers (name, affiliation, primary_affiliation, first_seen) VALUES (?, ?, ?, ?)',
            ("Dr. Jane Smith", "MIT", "MIT", now)
        )
        db.conn.commit()

        groups = find_duplicate_groups(db)
        assert len(groups) >= 1


class TestGetSpeakerDetails:
    def test_returns_details(self, db):
        sid = db.add_speaker(name="Jane Smith", title="Professor", affiliation="MIT")
        details = get_speaker_details(db, sid)
        assert details is not None
        # Should include speaker_id, name, title, affiliation, etc.
        assert details[1] == "Jane Smith"

    def test_nonexistent_speaker(self, db):
        details = get_speaker_details(db, 99999)
        assert details is None


class TestGetEventCount:
    def test_speaker_with_events(self, db):
        e_id = db.add_event(url="https://ex.com/e1", title="E1", body_text="T")
        s_id = db.add_speaker(name="Speaker 1")
        db.link_speaker_to_event(e_id, s_id, role_in_event="panelist")

        count = get_event_count(db, s_id)
        assert count == 1

    def test_speaker_with_no_events(self, db):
        s_id = db.add_speaker(name="Lonely Speaker")
        count = get_event_count(db, s_id)
        assert count == 0


# ── monitoring.py ───────────────────────────────────────────────────────

class TestPipelineMonitor:
    @pytest.fixture
    def monitor(self, tmp_path):
        """Create PipelineMonitor with a temporary database."""
        db_path = str(tmp_path / "test_monitor.db")
        # Initialize a database at this path
        database = SpeakerDatabase(db_path)
        database.conn.close()

        from monitoring import PipelineMonitor
        return PipelineMonitor(db_path=db_path)

    def test_init_with_custom_path(self, monitor):
        assert monitor.db_path is not None

    def test_parse_datetime_iso(self):
        from monitoring import PipelineMonitor
        dt = PipelineMonitor._parse_datetime("2024-03-15T10:30:00")
        assert dt is not None
        assert dt.year == 2024

    def test_parse_datetime_with_z(self):
        from monitoring import PipelineMonitor
        dt = PipelineMonitor._parse_datetime("2024-03-15T10:30:00Z")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_parse_datetime_none(self):
        from monitoring import PipelineMonitor
        dt = PipelineMonitor._parse_datetime(None)
        assert dt is None

    def test_parse_datetime_empty(self):
        from monitoring import PipelineMonitor
        dt = PipelineMonitor._parse_datetime("")
        assert dt is None

    @pytest.fixture
    def monitor_with_tables(self, tmp_path):
        """Create PipelineMonitor with all required tables."""
        import sqlite3
        db_path = str(tmp_path / "test_monitor_full.db")
        # Initialize base tables
        database = SpeakerDatabase(db_path)
        database.conn.close()

        # Create pipeline_runs table with proper schema
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT,
                completed_at TEXT,
                success BOOLEAN DEFAULT 0,
                events_scraped INTEGER DEFAULT 0,
                speakers_extracted INTEGER DEFAULT 0,
                speakers_enriched INTEGER DEFAULT 0,
                error_message TEXT,
                extraction_cost REAL DEFAULT 0,
                embedding_cost REAL DEFAULT 0,
                enrichment_cost REAL DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pipeline_lock (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                is_locked BOOLEAN NOT NULL DEFAULT 0,
                locked_at TEXT,
                locked_by TEXT
            )
        ''')
        cursor.execute('INSERT OR IGNORE INTO pipeline_lock (id, is_locked) VALUES (1, 0)')
        conn.commit()
        conn.close()

        from monitoring import PipelineMonitor
        return PipelineMonitor(db_path=db_path)

    def test_get_health_status(self, monitor_with_tables):
        """Should return health status without crashing."""
        status = monitor_with_tables.get_health_status()
        assert isinstance(status, dict)

    def test_get_backlog_trends(self, monitor_with_tables):
        """Should return backlog trends without crashing."""
        trends = monitor_with_tables.get_backlog_trends()
        assert isinstance(trends, dict)

    def test_get_error_patterns(self, monitor_with_tables):
        """Should return error patterns without crashing."""
        patterns = monitor_with_tables.get_error_patterns()
        assert isinstance(patterns, dict)
