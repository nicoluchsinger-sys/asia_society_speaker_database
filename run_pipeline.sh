#!/bin/bash
set -e

echo "=========================================="
echo "Speaker Pipeline - $(date)"
echo "=========================================="

# Configuration
EVENTS_PER_RUN=20
ENRICH_BATCH=50
EMBEDDING_BATCH=100

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Step 1: Scrape events
echo ""
echo "1. Scraping $EVENTS_PER_RUN new events..."
python3 main_selenium.py -e $EVENTS_PER_RUN --stats --export

# Step 2: Enrich speakers (only new ones)
echo ""
echo "2. Enriching speakers (batch: $ENRICH_BATCH)..."
python3 enrich_speakers_v2.py --limit $ENRICH_BATCH

# Step 3: Generate embeddings (only missing ones)
echo ""
echo "3. Generating embeddings (batch: $EMBEDDING_BATCH)..."
python3 generate_embeddings.py --provider openai --limit $EMBEDDING_BATCH

# Step 4: Export statistics
echo ""
echo "4. Database statistics:"
python3 -c "from database import SpeakerDatabase; db = SpeakerDatabase(); stats = db.get_statistics(); print(f'Speakers: {stats[\"total_speakers\"]}, Events: {stats[\"total_events\"]}, Tags: {stats[\"total_tags\"]}'); db.close()"

echo ""
echo "Pipeline complete!"
echo "=========================================="
