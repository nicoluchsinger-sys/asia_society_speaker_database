#!/usr/bin/env python3
"""
Test script to scrape events from global Asia Society page into a test database
"""

import csv
from datetime import datetime
from database import SpeakerDatabase
from selenium_scraper import SeleniumEventScraper

# Use a test database
TEST_DB = 'speakers_test.db'

print("="*70)
print("TEST SCRAPE - Global Asia Society Events")
print("="*70)
print(f"\nUsing test database: {TEST_DB}")
print("This will NOT affect your main speakers.db\n")

# Create test database
db = SpeakerDatabase(db_path=TEST_DB)

# Scrape 30 events from global page
scraper = SeleniumEventScraper(
    base_url="https://asiasociety.org/events/past",
    headless=True
)

print("Scraping 30 events from global Asia Society events page...")
count = scraper.scrape_events(db, limit=30, max_pages=None)

print(f"\n✓ Scraped {count} events")

# Export events to CSV
cursor = db.conn.cursor()
cursor.execute('''
    SELECT
        event_id,
        title,
        event_date,
        location,
        url,
        processing_status,
        LENGTH(body_text) as content_size,
        scraped_at
    FROM events
    ORDER BY event_date DESC, event_id DESC
''')

events = cursor.fetchall()

filename = f'test_events_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['Event ID', 'Title', 'Event Date', 'Location', 'URL', 'Status', 'Content Size', 'Scraped At'])

    for event in events:
        writer.writerow(event)

print(f"\n✓ Exported {len(events)} events to {filename}")

# Show location breakdown
cursor.execute('''
    SELECT location, COUNT(*) as count
    FROM events
    GROUP BY location
    ORDER BY count DESC
''')

print("\nLocation breakdown:")
for location, count in cursor.fetchall():
    print(f"  {location}: {count} events")

# Show date range
cursor.execute('''
    SELECT MIN(event_date), MAX(event_date)
    FROM events
    WHERE event_date IS NOT NULL
''')
min_date, max_date = cursor.fetchone()
print(f"\nDate range: {min_date} to {max_date}")

print("\nFirst 10 events:")
for i, event in enumerate(events[:10], 1):
    event_id, title, event_date, location, url, status, size, scraped = event
    print(f"{i}. [{event_date or 'No date'}] ({location}) {title[:50]}...")

db.close()

print(f"\n✓ Test complete. Test database saved as: {TEST_DB}")
print(f"✓ Events exported to: {filename}")
