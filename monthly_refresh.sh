#!/bin/bash
set -e

echo "=========================================="
echo "Monthly Speaker Refresh - $(date)"
echo "=========================================="

# Configuration
STALE_MONTHS=6       # Refresh speakers older than 6 months
BATCH_SIZE=20        # Process 20 speakers per run
LOG_DIR="/var/log"   # Log directory (adjust for your environment)

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Log file with timestamp
LOG_FILE="${LOG_DIR}/speaker_refresh_$(date +%Y%m%d_%H%M%S).log"

echo "Log file: $LOG_FILE"
echo ""

# Run refresh script (non-interactive for automated execution)
echo "Refreshing stale speakers (>$STALE_MONTHS months old, batch: $BATCH_SIZE)..."
python3 refresh_stale_speakers.py --limit $BATCH_SIZE --months $STALE_MONTHS --non-interactive 2>&1 | tee -a "$LOG_FILE"

# Show updated statistics
echo ""
echo "Updated statistics:"
python3 -c "
from database import SpeakerDatabase
db = SpeakerDatabase()
stats = db.get_enhanced_statistics()
print(f'Total speakers: {stats[\"total_speakers\"]}')
print(f'Enriched speakers: {stats[\"enriched_speakers\"]}')
print(f'Stale speakers: {stats[\"stale_speakers_count\"]}')
print(f'Refresh cost estimate: \${stats[\"stale_refresh_cost\"]}')
db.close()
" | tee -a "$LOG_FILE"

echo ""
echo "Monthly refresh complete!"
echo "=========================================="
