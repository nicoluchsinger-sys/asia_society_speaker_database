# Automated Refresh Setup

This document explains how to set up **fully automated** speaker data refresh on a monthly schedule.

## Overview

The monthly refresh script (`monthly_refresh.sh`) re-enriches speaker profiles that haven't been updated in over 6 months. This ensures that speaker affiliations, titles, locations, and demographics remain current as people change roles and organizations.

**✅ Fully Automated:** Runs via cron with `--non-interactive` flag - no manual confirmation required. Set it and forget it!

## What Gets Refreshed

For each stale speaker (>6 months since last enrichment):
- **Demographics**: Gender, nationality, birth year (re-enriched)
- **Locations**: Current city, country, region (re-enriched)
- **Languages**: Languages spoken (re-enriched)
- **✨ Affiliation**: Detects job moves and institutional changes via web search + AI verification
- **✨ Title**: Detects promotions and role changes via web search + AI verification

Changes are auto-applied if confidence >85%, otherwise saved as pending suggestions.

## Manual Usage

```bash
# Refresh up to 20 stale speakers (>6 months old)
./monthly_refresh.sh

# Or use the Python script directly for more control
python3 refresh_stale_speakers.py --limit 20 --months 6  # Interactive (asks for confirmation)
python3 refresh_stale_speakers.py --limit 20 --months 6 --non-interactive  # For automation (no prompts)
python3 refresh_stale_speakers.py --dry-run  # Preview without changes
```

## Automated Setup (Cron)

### Option 1: Monthly Cron Job (Recommended)

Add to crontab to run on the 1st of each month at 3 AM:

```bash
# Edit crontab
crontab -e

# Add this line (adjust path to your installation):
0 3 1 * * cd /path/to/speaker_database && ./monthly_refresh.sh >> /var/log/speaker_refresh.log 2>&1
```

**Explanation:**
- `0 3 1 * *` = Run at 3:00 AM on the 1st day of every month
- `cd /path/to/speaker_database` = Change to project directory
- `./monthly_refresh.sh` = Run the refresh script (uses `--non-interactive` flag)
- `>> /var/log/speaker_refresh.log 2>&1` = Append output to log file

**✅ Fully Automated:** The script uses `--non-interactive` mode, so it runs completely hands-off with no confirmation prompts. The refresh will execute automatically every month.

### Option 2: Integrate into Existing Daily Pipeline

If you already have a daily pipeline running, you can add monthly refresh logic:

```bash
# In run_pipeline.sh, add this check:
DAY_OF_MONTH=$(date +%d)
if [ "$DAY_OF_MONTH" == "01" ]; then
    echo "Running monthly speaker refresh..."
    python3 refresh_stale_speakers.py --limit 20 --months 6
fi
```

## Verify Cron Setup

After adding the cron job:

```bash
# List your cron jobs
crontab -l

# Check recent runs in the log
tail -50 /var/log/speaker_refresh.log

# Manually test the script
cd /path/to/speaker_database
./monthly_refresh.sh
```

## Cost Estimates

- **Per speaker**: ~$0.0023 (using Claude Haiku)
  - Demographics refresh: ~$0.0008
  - Affiliation/title check: ~$0.0015
- **Monthly batch (20 speakers)**: ~$0.046
- **Annual cost**: ~$0.55 (assuming 20 speakers/month)

## Monitoring

Check the stats page to see:
- Number of stale speakers needing refresh
- Last refresh run timestamp
- Total refresh cost this month

Or query from command line:

```bash
python3 -c "
from database import SpeakerDatabase
db = SpeakerDatabase()
stats = db.get_enhanced_statistics()
print(f'Stale speakers: {stats[\"stale_speakers_count\"]}')
print(f'Refresh cost: \${stats[\"stale_refresh_cost\"]}')
db.close()
"
```

## Troubleshooting

### Cron job not running

1. Check cron service is running:
   ```bash
   sudo systemctl status cron  # Linux
   # or
   sudo launchctl list | grep cron  # macOS
   ```

2. Check cron logs:
   ```bash
   tail -f /var/log/syslog | grep CRON  # Linux
   tail -f /var/log/system.log | grep cron  # macOS
   ```

3. Verify script permissions:
   ```bash
   ls -la monthly_refresh.sh
   # Should show: -rwxr-xr-x (executable)
   ```

### Environment variables not loaded

Make sure your `.env` file is in the project directory and readable:

```bash
cd /path/to/speaker_database
ls -la .env
# Should exist and contain ANTHROPIC_API_KEY and OPENAI_API_KEY
```

### Script fails with import errors

Ensure Python packages are installed in the environment that cron uses:

```bash
# Install in system Python or activate virtualenv first
pip3 install -r requirements.txt
```

For virtualenv, modify cron command:
```bash
0 3 1 * * cd /path/to/speaker_database && source venv/bin/activate && ./monthly_refresh.sh >> /var/log/speaker_refresh.log 2>&1
```

## Adjusting Refresh Frequency

You can adjust the refresh threshold by editing `monthly_refresh.sh`:

```bash
STALE_MONTHS=6       # Change to 3, 12, etc.
BATCH_SIZE=20        # Increase for faster refresh
```

Or change the cron schedule:

```bash
# Every 2 weeks (1st and 15th):
0 3 1,15 * * cd /path/to/speaker_database && ./monthly_refresh.sh

# Quarterly (January, April, July, October):
0 3 1 1,4,7,10 * cd /path/to/speaker_database && ./monthly_refresh.sh
```

## Best Practices

1. **Start small**: Begin with `BATCH_SIZE=20` to avoid API rate limits
2. **Monitor costs**: Check monthly API usage on the stats page
3. **Review logs**: Periodically check `/var/log/speaker_refresh.log` for errors
4. **Test dry-run**: Use `--dry-run` flag before making changes to large batches
5. **Backup first**: Run `./backup_database.sh` before major refresh operations
