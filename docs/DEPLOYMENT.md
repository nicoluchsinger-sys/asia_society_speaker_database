# Deployment Guide

Complete guide to deploying the Asia Society Speaker Database to Railway.

## Overview

The application is deployed on **Railway** with:
- ✅ **Web service** - Flask app with search interface
- ✅ **Persistent volume** - SQLite database storage
- ✅ **Automated pipeline** - Scrapes 10 events + enriches 20 speakers twice daily (6 AM/PM UTC)
- ✅ **Monthly refresh** - Updates stale speaker data (>6 months old) on 1st of each month
- ✅ **Zero maintenance** - Fully automated via APScheduler

**Estimated Cost:** $5-9/month (Railway hosting + API calls)

---

## Prerequisites

1. **GitHub Account** - For Railway deployment
2. **API Keys:**
   - Anthropic API key (for speaker extraction) - Get from https://console.anthropic.com
   - OpenAI API key (for embeddings) - Get from https://platform.openai.com
3. **Railway Account** - Sign up at https://railway.app (free to start)

---

## Quick Start (10 Minutes)

### Step 1: Deploy to Railway

1. Go to https://railway.app
2. Click **"Sign up with GitHub"**
3. Click **"New Project"** → **"Deploy from GitHub repo"**
4. Select your repository: `asia_society_speaker_database`
5. Name it: `speaker-database`

Railway will automatically detect the Dockerfile and start building.

### Step 2: Configure Environment Variables

Once deployed, click on the service and add these variables in the **Variables** tab:

```bash
# Required API Keys
ANTHROPIC_API_KEY=sk-ant-xxxxx    # Your Anthropic key
OPENAI_API_KEY=sk-xxxxx            # Your OpenAI key

# Application Settings
PORT=5001                           # Flask port (Railway auto-detects)
SITE_PASSWORD=your_secure_password  # Password for web interface
CONTACT_EMAIL=your@email.com        # Contact email shown on FAQ page (optional)

# Optional: Customize pipeline lock timeout (default: 1800 seconds = 30 min)
PIPELINE_LOCK_TIMEOUT_SECONDS=1800
```

Railway will automatically redeploy after adding variables.

### Step 3: Create Volume for Database

1. In Railway project dashboard, click **"+ New"**
2. Select **"Volume"**
3. Configure:
   - **Name:** `speaker-db-volume`
   - **Mount Path:** `/data`
   - **Service:** Connect to your web service
4. Click **"Create"**

The application automatically uses `/data/speakers.db` on Railway (or `./speakers.db` locally).

### Step 4: Upload Database (Optional)

If you have an existing database:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and link
railway login
railway link

# Upload database
railway run --service web bash -c 'cat > /data/speakers.db' < speakers.db
```

Or let the automated pipeline build the database from scratch (will scrape 10 events twice daily).

### Step 5: Generate Public URL

1. Click on your service
2. Go to **Settings** → **Networking**
3. Click **"Generate Domain"**
4. Save the URL (e.g., `speaker-database-production.up.railway.app`)

**Done!** Visit your URL to access the search interface. 🎉

---

## How It Works

### Automated Pipeline

The Flask app (`web_app/app.py`) runs two automated jobs via APScheduler:

**1. Daily Scraping & Enrichment**
- **Schedule:** Twice daily at 6:00 AM and 6:00 PM UTC
- **Actions:**
  - Scrapes 10 new Asia Society events
  - Extracts speakers using Claude AI
  - Enriches 20 existing speaker profiles
  - Updates search indexes
- **Cost:** ~$0.50-1.00 per run
- **Logs:** Check Railway logs for status

**2. Monthly Speaker Refresh**
- **Schedule:** 1st of each month at 3:00 AM UTC
- **Actions:**
  - Finds speakers with stale data (>6 months old)
  - Refreshes demographics, locations, languages
  - Detects affiliation/title changes via web search + AI
  - Auto-applies high-confidence changes (>85%)
- **Batch Size:** 20 speakers per month
- **Cost:** ~$0.046 per month

### Distributed Locking

When multiple Railway instances run (e.g., horizontal scaling), the app uses SQLite-based distributed locks to prevent concurrent pipeline execution:
- `pipeline_lock` table - Prevents duplicate scraping jobs
- `refresh_lock` table - Prevents duplicate refresh jobs
- Automatic stale lock detection (clears locks older than configured timeout)

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | - | Claude AI for speaker extraction |
| `OPENAI_API_KEY` | Yes | - | OpenAI for semantic embeddings |
| `SITE_PASSWORD` | No | `asiasociety123` | Web interface password |
| `CONTACT_EMAIL` | No | `contact@example.com` | Contact email shown on FAQ page |
| `PORT` | No | `5001` | Flask server port |
| `PIPELINE_LOCK_TIMEOUT_SECONDS` | No | `1800` | Lock timeout in seconds (30 min) |

### Database Location

The app automatically detects the environment:
- **Railway (production):** `/data/speakers.db` (volume mount)
- **Local (development):** `./speakers.db` (project root)

---

## Monitoring

### Check Pipeline Status

Visit these endpoints (authenticated):

```bash
# Overall statistics
https://your-app.railway.app/api/stats

# Pipeline lock status (debugging)
https://your-app.railway.app/admin/lock-status

# Search analytics
https://your-app.railway.app/admin/search-analytics
```

### View Logs

In Railway dashboard:
1. Click on your service
2. Go to **Deployments** tab
3. Click on latest deployment
4. View real-time logs

Look for:
- `✓ Scheduler initialized: pipeline runs at 6:00 and 18:00 UTC`
- `✓ Monthly refresh scheduled: runs 1st of each month at 3:00 AM UTC`
- `Starting scheduled pipeline run...`
- `✓ Scheduled pipeline completed successfully`

### Manual Pipeline Trigger

Trigger the pipeline manually for testing:

```bash
# Via API (authenticated)
curl -X POST https://your-app.railway.app/admin/run-pipeline \
  -b "session=your_session_cookie"
```

Or use the Railway CLI:
```bash
railway run --service web python3 -c "from pipeline_cron import run_pipeline; run_pipeline(event_limit=10, existing_limit=20)"
```

---

## Troubleshooting

### Pipeline Not Running

**Check lock status:**
```bash
curl https://your-app.railway.app/admin/lock-status
```

**Clear stuck lock:**
```bash
curl -X POST https://your-app.railway.app/admin/unlock
```

### Database Not Found

**Verify volume is mounted:**
1. Railway dashboard → Your service → Variables
2. Check that volume is connected
3. Verify mount path is `/data`

**Check database path in logs:**
```bash
# Should show: "Using database: /data/speakers.db"
railway logs
```

### High API Costs

**Review cost breakdown:**
- Check `/api/stats` endpoint for total costs
- Typical cost: $7-9/month for twice-daily runs
- Reduce `event_limit` or `existing_limit` in `web_app/app.py` lines 131, 228

**Reset cost tracking:**
```bash
curl -X POST https://your-app.railway.app/admin/reset-costs
```

### Application Crashes

**Check logs for errors:**
```bash
railway logs --service web
```

**Common issues:**
- Missing environment variables
- Database file permissions
- API key errors
- Memory limits (upgrade Railway plan if needed)

---

## Scaling & Optimization

### Horizontal Scaling

Railway supports multiple instances. The app handles this via distributed locking:
- Only one instance runs the pipeline at a time
- Lock timeout prevents stuck locks (default: 30 minutes)
- Logs show which instance acquired the lock

### Vertical Scaling

If you have a large database (>10,000 speakers):
1. Upgrade Railway plan for more RAM
2. Increase batch sizes in `pipeline_cron.py`
3. Consider using PostgreSQL instead of SQLite

### Cost Optimization

**Already optimized:**
- ✅ Uses Claude Haiku for enrichment (91% cheaper than Sonnet)
- ✅ Only enriches 20 speakers per run (not all)
- ✅ Monthly refresh instead of continuous

**Further optimization:**
- Reduce scraping frequency (modify cron triggers in `app.py`)
- Lower batch sizes (`event_limit=5` instead of 10)
- Disable monthly refresh if not needed

---

## Alternative Deployment (Self-Hosted)

If you prefer to self-host instead of Railway:

### Docker Deployment

```bash
# Build image
docker build -t speaker-database .

# Run with volume
docker run -d \
  -p 5001:5001 \
  -v speaker-data:/data \
  -e ANTHROPIC_API_KEY=your_key \
  -e OPENAI_API_KEY=your_key \
  -e SITE_PASSWORD=your_password \
  speaker-database
```

### Traditional Server (Ubuntu)

```bash
# Install dependencies
sudo apt update
sudo apt install python3 python3-pip chromium-browser chromium-chromedriver

# Clone repo
git clone https://github.com/your-username/speaker_database.git
cd speaker_database

# Install Python packages
pip3 install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run Flask app
python3 web_app/app.py
```

**Setup systemd service:**
```bash
sudo nano /etc/systemd/system/speaker-database.service
```

```ini
[Unit]
Description=Speaker Database Web App
After=network.target

[Service]
User=your_user
WorkingDirectory=/path/to/speaker_database
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 web_app/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable speaker-database
sudo systemctl start speaker-database
```

---

## Backup & Recovery

### Backup Database

```bash
# Via Railway CLI
railway run --service web cat /data/speakers.db > speakers_backup_$(date +%Y%m%d).db

# Or use the download endpoint (temporary, remove from production)
curl https://your-app.railway.app/admin/download-db > backup.db
```

### Restore Database

```bash
railway run --service web bash -c 'cat > /data/speakers.db' < backup.db
```

### Backup Automation

Add to your local cron (if using Railway CLI):
```bash
# Daily backup at 2 AM
0 2 * * * cd /path/to/backups && railway run --service web cat /data/speakers.db > speakers_$(date +\%Y\%m\%d).db
```

---

## Security Notes

### API Keys
- ✅ Never commit API keys to git
- ✅ Use Railway environment variables
- ✅ Rotate keys if exposed
- ✅ Monitor API usage for anomalies

### Database
- ✅ Contains publicly available information only
- ✅ No personal contact details (emails, phones)
- ✅ All data sourced from Asia Society website

### Web Interface
- ✅ Password protected (`SITE_PASSWORD` env var)
- ✅ Session-based authentication
- ✅ Consider adding IP whitelist for production

---

## Support

**Issues?** Check Railway logs first:
```bash
railway logs --service web
```

**Common Resources:**
- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Project Issues: GitHub repository issues page
