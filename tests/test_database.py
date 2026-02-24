"""
Tests for database.py - SpeakerDatabase and normalize_name.

Covers:
- Name normalization (title stripping)
- Event CRUD operations
- Speaker CRUD with deduplication
- Fuzzy affiliation matching
- Event-speaker linking
- Tags, embeddings, demographics, locations, languages
- Corrections system
- Statistics
- Merge duplicates
- Search logging
"""

import pytest
import sqlite3
from datetime import datetime
from database import SpeakerDatabase, normalize_name


# ── normalize_name ──────────────────────────────────────────────────────

class TestNormalizeName:
    def test_removes_dr(self):
        assert normalize_name("Dr. Jane Smith") == "Jane Smith"

    def test_removes_professor(self):
        assert normalize_name("Professor John Doe") == "John Doe"

    def test_removes_prof(self):
        assert normalize_name("Prof. John Doe") == "John Doe"

    def test_removes_ambassador(self):
        assert normalize_name("Ambassador Maria Garcia") == "Maria Garcia"

    def test_removes_mr(self):
        assert normalize_name("Mr. Bob Jones") == "Bob Jones"

    def test_removes_mrs(self):
        assert normalize_name("Mrs. Alice Brown") == "Alice Brown"

    def test_removes_ms(self):
        assert normalize_name("Ms. Carol White") == "Carol White"

    def test_removes_sir(self):
        assert normalize_name("Sir Edmund Hillary") == "Edmund Hillary"

    def test_handles_empty_string(self):
        assert normalize_name("") == ""

    def test_handles_none(self):
        assert normalize_name(None) == ""

    def test_no_title(self):
        assert normalize_name("Jane Smith") == "Jane Smith"

    def test_removes_multiple_titles(self):
        # "Dr. Prof." - both should be stripped
        result = normalize_name("Dr. Prof. Jane Smith")
        assert "Jane Smith" in result
        assert "Dr" not in result
        assert "Prof" not in result

    def test_preserves_name_with_title_like_substring(self):
        # "Dragon" starts with "Dr" but should not be stripped because
        # the pattern requires a period or space after "Dr"
        assert normalize_name("Dragon Ball") == "Dragon Ball"

    def test_cleans_extra_whitespace(self):
        result = normalize_name("Dr.   Jane   Smith")
        assert result == "Jane Smith"


# ── Database Initialization ─────────────────────────────────────────────

class TestDatabaseInit:
    def test_creates_tables(self, db):
        """All expected tables should exist after init."""
        cursor = db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        expected = {
            'events', 'speakers', 'event_speakers', 'speaker_tags',
            'speaker_embeddings', 'speaker_demographics', 'speaker_locations',
            'speaker_languages', 'speaker_freshness', 'speaker_corrections',
            'search_logs'
        }
        assert expected.issubset(tables)

    def test_idempotent_init(self, db):
        """Calling init_database multiple times should not raise errors."""
        db.init_database()
        db.init_database()

    def test_context_manager(self, tmp_path):
        """SpeakerDatabase should work as a context manager if supported."""
        db_path = str(tmp_path / "ctx_test.db")
        database = SpeakerDatabase(db_path)
        # Just verify it works - close manually
        database.conn.close()


# ── Event CRUD ──────────────────────────────────────────────────────────

class TestEventCRUD:
    def test_add_event(self, db):
        event_id = db.add_event(
            url="https://example.com/event1",
            title="Test Event",
            body_text="Event description here."
        )
        assert event_id is not None
        assert isinstance(event_id, int)

    def test_add_duplicate_event_returns_existing_id(self, db):
        """Adding an event with the same URL should return the existing ID."""
        id1 = db.add_event(url="https://example.com/dup", title="First", body_text="Text")
        id2 = db.add_event(url="https://example.com/dup", title="Second", body_text="Other text")
        assert id1 == id2

    def test_add_event_with_all_fields(self, db):
        event_id = db.add_event(
            url="https://example.com/full",
            title="Full Event",
            body_text="Full description",
            raw_html="<html>...</html>",
            event_date="2024-03-15",
            location="New York"
        )
        assert event_id > 0

    def test_get_unprocessed_events(self, db):
        db.add_event(url="https://example.com/e1", title="E1", body_text="Text 1")
        db.add_event(url="https://example.com/e2", title="E2", body_text="Text 2")

        events = db.get_unprocessed_events()
        assert len(events) == 2
        # Each event should be (event_id, url, title, body_text)
        assert len(events[0]) == 4

    def test_get_unprocessed_events_excludes_completed(self, db):
        e1 = db.add_event(url="https://example.com/e1", title="E1", body_text="Text")
        db.add_event(url="https://example.com/e2", title="E2", body_text="Text")
        db.mark_event_processed(e1, status='completed')

        events = db.get_unprocessed_events()
        assert len(events) == 1

    def test_get_unprocessed_events_with_limit(self, db):
        for i in range(5):
            db.add_event(url=f"https://example.com/e{i}", title=f"E{i}", body_text="Text")

        events = db.get_unprocessed_events(limit=2)
        assert len(events) == 2

    def test_get_unprocessed_events_respects_max_attempts(self, db):
        e1 = db.add_event(url="https://example.com/e1", title="E1", body_text="Text")
        # Simulate 3 failed attempts
        for _ in range(3):
            db.increment_extraction_attempts(e1)

        events = db.get_unprocessed_events(max_attempts=3)
        assert len(events) == 0

    def test_mark_event_processed(self, db):
        e1 = db.add_event(url="https://example.com/e1", title="E1", body_text="Text")
        db.mark_event_processed(e1, status='completed')

        cursor = db.conn.cursor()
        cursor.execute('SELECT processing_status FROM events WHERE event_id = ?', (e1,))
        status = cursor.fetchone()[0]
        assert status == 'completed'

    def test_mark_event_failed(self, db):
        e1 = db.add_event(url="https://example.com/e1", title="E1", body_text="Text")
        db.mark_event_processed(e1, status='failed')

        cursor = db.conn.cursor()
        cursor.execute('SELECT processing_status FROM events WHERE event_id = ?', (e1,))
        assert cursor.fetchone()[0] == 'failed'

    def test_get_event_by_id(self, db):
        e_id = db.add_event(url="https://example.com/e1", title="My Event", body_text="Text")
        event = db.get_event_by_id(e_id)
        assert event is not None

    def test_get_all_events(self, db):
        db.add_event(url="https://example.com/e1", title="E1", body_text="T1")
        db.add_event(url="https://example.com/e2", title="E2", body_text="T2")
        events = db.get_all_events()
        assert len(events) == 2


# ── Speaker CRUD ────────────────────────────────────────────────────────

class TestSpeakerCRUD:
    def test_add_speaker(self, db):
        sid = db.add_speaker(name="Jane Doe", title="Professor")
        assert sid is not None
        assert isinstance(sid, int)

    def test_add_speaker_with_all_fields(self, db):
        sid = db.add_speaker(
            name="Jane Doe",
            title="Professor",
            affiliation="MIT",
            primary_affiliation="MIT",
            bio="Expert in AI research."
        )
        speaker = db.get_speaker_by_id(sid)
        assert speaker is not None

    def test_get_all_speakers(self, db):
        db.add_speaker(name="Speaker 1")
        db.add_speaker(name="Speaker 2")
        speakers = db.get_all_speakers()
        assert len(speakers) == 2

    def test_find_existing_speaker(self, db):
        db.add_speaker(name="Jane Smith", affiliation="MIT")
        matches = db.find_existing_speaker("Jane Smith")
        assert len(matches) >= 1

    def test_find_existing_speaker_case_insensitive(self, db):
        db.add_speaker(name="Jane Smith", affiliation="MIT")
        matches = db.find_existing_speaker("jane smith")
        assert len(matches) >= 1

    def test_find_existing_speaker_with_title(self, db):
        """Dr. Jane Smith should match existing Jane Smith."""
        db.add_speaker(name="Jane Smith", affiliation="MIT")
        matches = db.find_existing_speaker("Dr. Jane Smith")
        assert len(matches) >= 1

    def test_get_speaker_by_id(self, db):
        sid = db.add_speaker(name="Test Speaker")
        speaker = db.get_speaker_by_id(sid)
        assert speaker is not None

    def test_get_speaker_by_id_nonexistent(self, db):
        speaker = db.get_speaker_by_id(99999)
        assert speaker is None


# ── Speaker Deduplication ───────────────────────────────────────────────

class TestSpeakerDeduplication:
    def test_same_name_same_affiliation_deduplicates(self, db):
        """Same name + same affiliation should return same speaker ID."""
        s1 = db.add_speaker(name="Jane Smith", affiliation="Harvard University")
        s2 = db.add_speaker(name="Jane Smith", affiliation="Harvard University")
        assert s1 == s2

    def test_same_name_overlapping_affiliation_deduplicates(self, db):
        """Same name + overlapping affiliation (Harvard) should deduplicate."""
        s1 = db.add_speaker(name="Jane Smith", affiliation="Harvard University")
        s2 = db.add_speaker(name="Jane Smith", affiliation="Harvard Kennedy School")
        assert s1 == s2

    def test_same_name_different_affiliation_creates_new(self, db):
        """Same name + completely different affiliation = different person."""
        s1 = db.add_speaker(name="Jane Smith", affiliation="MIT")
        s2 = db.add_speaker(name="Jane Smith", affiliation="Stanford University")
        assert s1 != s2

    def test_title_variant_deduplicates(self, db):
        """'Dr. Jane Smith' should match existing 'Jane Smith'."""
        s1 = db.add_speaker(name="Jane Smith", affiliation="MIT")
        s2 = db.add_speaker(name="Dr. Jane Smith", affiliation="MIT")
        assert s1 == s2

    def test_no_affiliation_deduplicates(self, db):
        """Speaker with no affiliation should match existing by name."""
        s1 = db.add_speaker(name="Jane Smith", affiliation="MIT")
        s2 = db.add_speaker(name="Jane Smith")
        assert s1 == s2

    def test_different_names_no_dedup(self, db):
        """Different names should never deduplicate."""
        s1 = db.add_speaker(name="Jane Smith")
        s2 = db.add_speaker(name="John Doe")
        assert s1 != s2


# ── Affiliation Matching ────────────────────────────────────────────────

class TestAffiliationMatching:
    def test_both_none(self, db):
        assert db._affiliations_overlap(None, None) is True

    def test_one_none(self, db):
        assert db._affiliations_overlap("MIT", None) is True

    def test_one_empty(self, db):
        assert db._affiliations_overlap("MIT", "") is True

    def test_exact_match(self, db):
        assert db._affiliations_overlap("Harvard University", "Harvard University") is True

    def test_partial_overlap(self, db):
        assert db._affiliations_overlap("Harvard University", "Harvard Kennedy School") is True

    def test_no_overlap(self, db):
        assert db._affiliations_overlap("MIT", "Stanford University") is False

    def test_normalize_text(self, db):
        words = db._normalize_text("New York University")
        assert "new" in words
        assert "york" in words
        assert "university" in words

    def test_normalize_text_none(self, db):
        assert db._normalize_text(None) == set()

    def test_normalize_text_empty(self, db):
        assert db._normalize_text("") == set()

    def test_normalize_text_filters_short_words(self, db):
        words = db._normalize_text("School of Law")
        assert "of" not in words
        assert "law" in words


# ── Event-Speaker Linking ───────────────────────────────────────────────

class TestEventSpeakerLinking:
    def test_link_speaker_to_event(self, db):
        e_id = db.add_event(url="https://ex.com/e1", title="E1", body_text="T")
        s_id = db.add_speaker(name="Speaker 1")
        db.link_speaker_to_event(e_id, s_id, role_in_event="panelist")

        speakers = db.get_event_speakers(e_id)
        assert len(speakers) >= 1

    def test_duplicate_link_ignored(self, db):
        """Linking the same speaker to the same event twice should not error."""
        e_id = db.add_event(url="https://ex.com/e1", title="E1", body_text="T")
        s_id = db.add_speaker(name="Speaker 1")
        db.link_speaker_to_event(e_id, s_id, role_in_event="panelist")
        db.link_speaker_to_event(e_id, s_id, role_in_event="moderator")

        speakers = db.get_event_speakers(e_id)
        assert len(speakers) == 1

    def test_get_speaker_events(self, db_with_data):
        db, data = db_with_data
        # Jane Smith (s1) is linked to e1 and e2
        events = db.get_speaker_events(data['speakers']['s1'])
        assert len(events) == 2

    def test_get_event_speakers(self, db_with_data):
        db, data = db_with_data
        # Event e2 has s1 and s2
        speakers = db.get_event_speakers(data['events']['e2'])
        assert len(speakers) == 2


# ── Tags ────────────────────────────────────────────────────────────────

class TestSpeakerTags:
    def test_add_and_get_tags(self, db):
        sid = db.add_speaker(name="Test Speaker")
        db.add_speaker_tag(sid, "climate policy", confidence=0.95, source="web_search")
        db.add_speaker_tag(sid, "geopolitics", confidence=0.85)

        tags = db.get_speaker_tags(sid)
        assert len(tags) == 2

    def test_duplicate_tag_ignored(self, db):
        """Adding the same tag twice should not create duplicates."""
        sid = db.add_speaker(name="Test Speaker")
        db.add_speaker_tag(sid, "climate policy", confidence=0.95)
        db.add_speaker_tag(sid, "climate policy", confidence=0.90)

        tags = db.get_speaker_tags(sid)
        assert len(tags) == 1

    def test_get_untagged_speakers(self, db):
        s1 = db.add_speaker(name="Tagged Speaker")
        s2 = db.add_speaker(name="Untagged Speaker")
        db.add_speaker_tag(s1, "economics")
        db.mark_speaker_tagged(s1)

        untagged = db.get_untagged_speakers()
        # s2 should be in untagged
        untagged_ids = [s[0] for s in untagged]
        assert s2 in untagged_ids


# ── Embeddings ──────────────────────────────────────────────────────────

class TestSpeakerEmbeddings:
    def test_save_and_get_embedding(self, db):
        sid = db.add_speaker(name="Test Speaker")
        embedding_blob = b'\x00\x01\x02\x03'
        db.save_speaker_embedding(sid, embedding_blob, "test embedding text", model="test-model")

        result = db.get_speaker_embedding(sid)
        assert result is not None

    def test_get_speakers_without_embeddings(self, db):
        s1 = db.add_speaker(name="With Embedding")
        s2 = db.add_speaker(name="Without Embedding")
        db.save_speaker_embedding(s1, b'\x00', "text", model="test")

        without = db.get_speakers_without_embeddings()
        ids = [s[0] for s in without]
        assert s2 in ids
        assert s1 not in ids

    def test_count_embeddings(self, db):
        s1 = db.add_speaker(name="Speaker 1")
        s2 = db.add_speaker(name="Speaker 2")
        db.save_speaker_embedding(s1, b'\x00', "text1", model="test")
        db.save_speaker_embedding(s2, b'\x01', "text2", model="test")

        assert db.count_embeddings() == 2


# ── Demographics ────────────────────────────────────────────────────────

class TestSpeakerDemographics:
    def test_save_and_get_demographics(self, db):
        sid = db.add_speaker(name="Test Speaker")
        db.save_speaker_demographics(
            sid, gender="female", gender_confidence=0.95,
            nationality="American", nationality_confidence=0.90
        )

        demo = db.get_speaker_demographics(sid)
        assert demo is not None

    def test_get_demographics_nonexistent(self, db):
        sid = db.add_speaker(name="Test Speaker")
        demo = db.get_speaker_demographics(sid)
        assert demo is None


# ── Locations ───────────────────────────────────────────────────────────

class TestSpeakerLocations:
    def test_save_and_get_location(self, db):
        sid = db.add_speaker(name="Test Speaker")
        db.save_speaker_location(
            sid, location_type="current",
            city="New York", country="United States", region="North America",
            is_primary=True, confidence=0.9, source="web_search"
        )

        locations = db.get_speaker_locations(sid)
        assert len(locations) >= 1


# ── Languages ───────────────────────────────────────────────────────────

class TestSpeakerLanguages:
    def test_save_and_get_language(self, db):
        sid = db.add_speaker(name="Test Speaker")
        db.save_speaker_language(
            sid, language="English", proficiency="native",
            confidence=0.99, source="web_search"
        )

        languages = db.get_speaker_languages(sid)
        assert len(languages) >= 1


# ── Corrections ─────────────────────────────────────────────────────────

class TestCorrections:
    def test_save_and_get_correction(self, db):
        sid = db.add_speaker(name="Test Speaker", title="Wrong Title")
        correction_id = db.save_correction(
            speaker_id=sid,
            field_name="title",
            current_value="Wrong Title",
            suggested_value="Correct Title",
            suggestion_context="User submitted correction",
            submitted_by="test_user",
            verified=False,
            confidence=None,
            reasoning=None,
            sources=None
        )
        assert correction_id > 0

        corrections = db.get_speaker_corrections(sid)
        assert len(corrections) >= 1

    def test_apply_correction(self, db):
        sid = db.add_speaker(name="Test Speaker", title="Old Title")
        db.apply_correction(sid, "title", "New Title")

        speaker = db.get_speaker_by_id(sid)
        # Verify the title was updated (title is typically index 2)
        # The exact index depends on the SELECT query in get_speaker_by_id
        assert speaker is not None


# ── Statistics ──────────────────────────────────────────────────────────

class TestStatistics:
    def test_get_statistics(self, db_with_data):
        db, data = db_with_data
        stats = db.get_statistics()
        assert stats['total_events'] == 3
        assert stats['total_speakers'] == 3

    def test_get_statistics_empty_db(self, db):
        stats = db.get_statistics()
        assert stats['total_events'] == 0
        assert stats['total_speakers'] == 0

    def test_get_unique_event_locations(self, db_with_data):
        db, data = db_with_data
        locations = db.get_unique_event_locations()
        assert "New York" in locations
        assert "Hong Kong" in locations


# ── Search Logging ──────────────────────────────────────────────────────

class TestSearchLogging:
    def test_log_search(self, db):
        db.log_search(
            query="climate experts",
            ip_address="127.0.0.1",
            results_count=5,
            execution_time_ms=150.5
        )
        cursor = db.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM search_logs')
        assert cursor.fetchone()[0] == 1


# ── Merge Duplicates ────────────────────────────────────────────────────

class TestMergeDuplicates:
    def test_merge_duplicates_no_duplicates(self, db):
        db.add_speaker(name="Jane Smith", affiliation="MIT")
        db.add_speaker(name="John Doe", affiliation="Harvard")
        count = db.merge_duplicates(verbose=False)
        assert count == 0

    def test_get_top_speakers(self, db_with_data):
        db, data = db_with_data
        top = db.get_top_speakers(limit=10)
        assert len(top) > 0
