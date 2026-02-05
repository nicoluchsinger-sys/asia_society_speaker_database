#!/bin/bash

# Check if database exists
if [ ! -f speakers.db ]; then
    echo "ERROR: Database not found"
    exit 1
fi

# Check speaker count
SPEAKER_COUNT=$(python3 -c "from database import SpeakerDatabase; db = SpeakerDatabase(); stats = db.get_statistics(); print(stats['total_speakers']); db.close()")

echo "Current speaker count: $SPEAKER_COUNT"

# Alert if count is decreasing (data loss?)
LAST_COUNT_FILE="/tmp/last_speaker_count.txt"
if [ -f "$LAST_COUNT_FILE" ]; then
    LAST_COUNT=$(cat "$LAST_COUNT_FILE")
    if [ "$SPEAKER_COUNT" -lt "$LAST_COUNT" ]; then
        echo "WARNING: Speaker count decreased from $LAST_COUNT to $SPEAKER_COUNT"
        # Send alert (email, Slack, etc.)
    fi
fi

echo "$SPEAKER_COUNT" > "$LAST_COUNT_FILE"

# Check for failed events
FAILED_COUNT=$(python3 -c "from database import SpeakerDatabase; db = SpeakerDatabase(); cursor = db.conn.cursor(); cursor.execute('SELECT COUNT(*) FROM events WHERE processing_status = \"failed\"'); print(cursor.fetchone()[0]); db.close()")

if [ "$FAILED_COUNT" -gt 10 ]; then
    echo "WARNING: $FAILED_COUNT failed events"
fi

echo "Health check passed"
exit 0
