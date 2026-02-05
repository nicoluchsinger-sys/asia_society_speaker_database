#!/bin/bash
# Railway Background Worker - Scraping Script
# Run this manually via Railway dashboard to scrape events

set -e

echo "=========================================="
echo "Railway Scraper - $(date)"
echo "=========================================="

# Get number of events from argument or use default
EVENTS=${1:-200}

echo "Scraping $EVENTS events..."
echo ""

# Ensure we can write to current directory
# Create empty database if it doesn't exist
if [ ! -f speakers.db ]; then
    echo "Creating database file..."
    touch speakers.db && chmod 666 speakers.db || echo "Warning: Could not set permissions"
fi

# Run scraping with extraction
python3 main_selenium.py -e $EVENTS --stats --headless

echo ""
echo "=========================================="
echo "Scraping complete!"
echo ""

# Show updated statistics
echo "Current database statistics:"
python3 -c "from database import SpeakerDatabase; db = SpeakerDatabase(); stats = db.get_statistics(); print(f'  Speakers: {stats[\"total_speakers\"]}'); print(f'  Events: {stats[\"total_events\"]}'); print(f'  Processed: {stats[\"processed_events\"]}'); db.close()"

echo "=========================================="
