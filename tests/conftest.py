"""
Shared test fixtures for the speaker database test suite.

Provides reusable fixtures for:
- In-memory SQLite database (fast, isolated per test)
- Mock API clients (Anthropic, OpenAI)
- Sample data (events, speakers, HTML)
"""

import sys
import os
import pytest
import sqlite3

# Add project root to path so tests can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SpeakerDatabase


@pytest.fixture
def db(tmp_path):
    """
    Create a fresh SpeakerDatabase backed by a temporary file.

    Each test gets its own isolated database that is automatically
    cleaned up after the test completes.
    """
    db_path = str(tmp_path / "test_speakers.db")
    database = SpeakerDatabase(db_path)
    yield database
    database.conn.close()


@pytest.fixture
def db_with_data(db):
    """
    Database pre-populated with sample events and speakers for testing
    queries, statistics, and relationships.
    """
    # Add sample events
    e1 = db.add_event(
        url="https://asiasociety.org/events/climate-summit-2024",
        title="Climate Summit 2024",
        body_text="A summit on climate change featuring expert speakers.",
        event_date="2024-03-15",
        location="New York"
    )
    e2 = db.add_event(
        url="https://asiasociety.org/events/ai-future-panel",
        title="The Future of AI in Asia",
        body_text="Panel discussion on artificial intelligence trends.",
        event_date="2024-04-20",
        location="Hong Kong"
    )
    e3 = db.add_event(
        url="https://asiasociety.org/events/trade-forum",
        title="US-China Trade Forum",
        body_text="Forum on trade relations between US and China.",
        event_date="2024-05-10",
        location="Washington"
    )

    # Add sample speakers
    s1 = db.add_speaker(
        name="Jane Smith",
        title="Professor of Climate Science",
        affiliation="Columbia University",
        primary_affiliation="Columbia University",
        bio="Leading climate researcher with 20 years of experience."
    )
    s2 = db.add_speaker(
        name="John Chen",
        title="CEO",
        affiliation="TechAsia Inc.",
        primary_affiliation="TechAsia Inc.",
        bio="Technology entrepreneur focused on AI in Southeast Asia."
    )
    s3 = db.add_speaker(
        name="Maria Garcia",
        title="Senior Fellow",
        affiliation="Brookings Institution",
        primary_affiliation="Brookings Institution",
        bio="Expert on international trade policy."
    )

    # Link speakers to events
    db.link_speaker_to_event(e1, s1, role_in_event="keynote speaker")
    db.link_speaker_to_event(e2, s2, role_in_event="panelist")
    db.link_speaker_to_event(e2, s1, role_in_event="moderator")
    db.link_speaker_to_event(e3, s3, role_in_event="keynote speaker")
    db.link_speaker_to_event(e3, s2, role_in_event="panelist")

    return db, {
        'events': {'e1': e1, 'e2': e2, 'e3': e3},
        'speakers': {'s1': s1, 's2': s2, 's3': s3}
    }


@pytest.fixture
def sample_event_html():
    """Sample HTML for testing event page parsing."""
    return """
    <html>
    <head>
        <meta property="og:title" content="Climate Policy Summit 2024 | Asia Society" />
        <title>Climate Policy Summit 2024 | Asia Society</title>
    </head>
    <body>
        <h1 class="event-title">Climate Policy Summit 2024</h1>
        <div class="event-details-wdgt">
            <span class="date">March 15, 2024</span>
            <span class="location">New York</span>
        </div>
        <article>
            <div class="content">
                <p>Join us for a discussion on climate policy featuring leading experts
                from around the world. This event will explore the latest developments
                in climate science and policy responses.</p>
                <p>Speakers include Dr. Jane Smith, Professor of Climate Science at
                Columbia University, who will deliver the keynote address on recent
                climate modeling breakthroughs.</p>
                <p>The panel discussion will feature John Chen, CEO of TechAsia Inc.,
                discussing green technology innovations in Asia.</p>
            </div>
        </article>
    </body>
    </html>
    """


@pytest.fixture
def sample_extraction_response():
    """Sample Claude API response for speaker extraction."""
    return {
        "speakers": [
            {
                "name": "Jane Smith",
                "title": "Professor of Climate Science",
                "affiliation": "Columbia University",
                "primary_affiliation": "Columbia University",
                "role_in_event": "keynote speaker",
                "bio": "Expert on climate modeling breakthroughs"
            },
            {
                "name": "John Chen",
                "title": "CEO",
                "affiliation": "TechAsia Inc.",
                "primary_affiliation": "TechAsia Inc.",
                "role_in_event": "panelist",
                "bio": "Discusses green technology innovations in Asia"
            }
        ],
        "event_summary": "A climate policy summit featuring discussions on climate science and green technology."
    }
