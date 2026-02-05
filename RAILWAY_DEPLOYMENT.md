# Railway Deployment Guide

Complete guide to deploying the Speaker Database to Railway with zero sysadmin.

## Overview

**Architecture:**
- **Service 1 (Web)**: Flask application for search interface
- **Service 2 (Scraper)**: Background worker for long-running scraping tasks
- **Shared Volume**: SQLite database accessible to both services

**Cost:** $10-15/month during scaling phase, then $5-8/month for maintenance

---

## Phase 1: Initial Setup (10 minutes)

### 1.1 Create Railway Account

1. Go to https://railway.app
2. Sign up with GitHub account (recommended)
3. Verify email address

### 1.2 Create New Project

1. Click "New Project"
2. Select "Deploy from GitHub repo"
3. Connect your GitHub account if not already connected
4. Select repository: `nicoluchsinger-sys/asia_society_speaker_database`
5. Name project: `speaker-database`

### 1.3 Configure Web Service

Railway will automatically detect your Dockerfile and start building.

**Update Service Settings:**
1. Click on the deployed service
2. Go to "Settings" tab
3. **Service Name**: Change to `web`
4. **Start Command**: Add under "Deploy" section:
   ```
   python3 web_app/app.py
   ```
5. **Public Networking**: Click "Generate Domain"
   - This creates a public URL like `speaker-database-production.up.railway.app`

**Add Environment Variables:**
1. Go to "Variables" tab
2. Add these variables:
   ```
   ANTHROPIC_API_KEY=your_key_here
   OPENAI_API_KEY=your_key_here
   PORT=5001
   ```
3. Click "Add" for each

**Create Persistent Volume:**
1. Go to "Data" tab (or click "+ New" in project view)
2. Select "Volume"
3. **Name**: `speaker-db-volume`
4. **Mount Path**: `/app`
5. Connect to `web` service

### 1.4 Upload Database

Since Railway doesn't have easy file upload, we'll use Railway CLI:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Or with brew (Mac)
brew install railway

# Login
railway login

# Link to your project
cd /Users/nicoluchsinger/coding/speaker_database
railway link

# Upload database (Railway will prompt to select service - choose 'web')
railway run --service web bash -c "cat > /app/speakers.db" < speakers.db
```

**Alternative Method (if CLI doesn't work):**
1. Temporarily add upload endpoint to Flask app
2. Deploy and use curl to upload
3. Remove upload endpoint after

### 1.5 Test Web Service

1. Visit your Railway domain (e.g., `https://speaker-database-production.up.railway.app`)
2. You should see the search interface
3. Try searching for a speaker to verify database is loaded
4. Check `/api/stats` endpoint to see current speaker count

---

## Phase 2: Add Background Worker (15 minutes)

### 2.1 Create Second Service

1. In Railway project dashboard, click "+ New"
2. Select "GitHub Repo"
3. Choose same repository: `asia_society_speaker_database`
4. Railway will create a second service

### 2.2 Configure Scraper Service

**Update Service Settings:**
1. Click on the new service
2. Go to "Settings" tab
3. **Service Name**: Change to `scraper`
4. **Start Command**: Leave empty for now (we'll trigger manually)
5. **Public Networking**: Don't enable (internal only)

**Add Environment Variables:**
1. Go to "Variables" tab
2. Add same variables as web service:
   ```
   ANTHROPIC_API_KEY=your_key_here
   OPENAI_API_KEY=your_key_here
   ```

**Connect to Shared Volume:**
1. Go to "Data" tab
2. Connect existing `speaker-db-volume`
3. **Mount Path**: `/app`
4. This allows scraper to write to same database as web service

### 2.3 Test Scraper Service

**Manually trigger a scraping task:**

```bash
# Using Railway CLI
railway run --service scraper python3 main_selenium.py -e 5 --stats --skip-extract
```

**Or via Railway Dashboard:**
1. Click on `scraper` service
2. Go to "Deployments" tab
3. Click on latest deployment
4. Open "Console" tab (terminal icon)
5. Run: `python3 main_selenium.py -e 5 --stats --skip-extract`

This will scrape 5 events as a test. Check the web interface to see if new events appear.

---

## Phase 3: Scale to 1000+ Speakers (1-2 weeks)

### Run Scraping Sessions

Over the next 1-2 weeks, run 4 scraping sessions:

**Session 1-4 (repeat 4 times):**
```bash
# Using Railway CLI (recommended)
railway run --service scraper python3 main_selenium.py -e 200 --stats --no-extract

# After scraping completes, extract speakers
railway run --service scraper python3 extract_only.py
```

**Each session:**
- Scraping: ~1 hour (200 events)
- Extraction: ~1-2 hours (depends on API)
- Cost: ~$3 per session (API costs)

**Monitor Progress:**
- Check web interface `/api/stats` endpoint between sessions
- Should see speaker count growing: 443 → ~600 → ~800 → ~1000 → ~1200+

---

## Phase 4: Simplify to Single Service (30 minutes)

Once you reach 1000+ speakers, simplify to single service:

### 4.1 Add Cron to Web Service

1. Go to `web` service settings
2. Add environment variable:
   ```
   CRON_SCHEDULE=0 2 * * *
   ```

### 4.2 Update Dockerfile for Cron (Optional)

For automatic daily scraping, we'd need to add a cron job. Simpler approach: use Railway's built-in cron:

1. Create a new service called `cron-scraper`
2. Set start command: `python3 main_selenium.py -e 20 --stats`
3. Under "Settings" → "Cron Schedule": `0 2 * * *` (runs at 2 AM daily)
4. Connect to shared volume

### 4.3 Remove Background Worker

1. Once satisfied with cron setup, delete the `scraper` service
2. Keep only `web` and `cron-scraper`
3. Or merge everything into single service if daily scraping is fast enough

**Cost After Simplification:** $5-8/month

---

## Maintenance & Monitoring

### Check Deployment Status
```bash
railway status
```

### View Logs
```bash
# Web service logs
railway logs --service web

# Scraper logs
railway logs --service scraper
```

### Manual Scraping (if needed)
```bash
railway run --service web python3 main_selenium.py -e 20 --stats
```

### Backup Database
```bash
# Download database from Railway
railway run --service web cat /app/speakers.db > speakers_backup.db
```

### Update Code
```bash
# Railway automatically deploys on git push
git add .
git commit -m "feat: some improvement"
git push origin main

# Railway detects push and redeploys automatically
```

---

## Troubleshooting

### "Database locked" Errors
- Both services trying to write simultaneously
- Solution: Only run scraper when web service is idle, or use separate databases and merge

### "Out of Memory" Errors
- Increase service memory in Railway dashboard
- Settings → Resources → Increase memory limit

### Selenium/Chrome Errors
- Railway may have issues with Chrome in Docker
- If persistent, fall back to Hetzner for scraping
- Keep web interface on Railway, scrape elsewhere

### Database Not Persisting
- Verify volume is correctly mounted to `/app`
- Check volume is connected to service
- Volume mount path must match Dockerfile WORKDIR

---

## Cost Breakdown

**During Scaling (Weeks 1-2):**
- Web service: $5/month
- Scraper service: $5/month
- Volume storage: $1/month
- API costs: $12 one-time
- **Total**: ~$23 for first month

**After Scaling (Maintenance):**
- Web service: $5/month
- Cron service: $2/month
- Volume storage: $1/month
- API costs: $2-3/month
- **Total**: $8-10/month

---

## Next Steps

1. ✅ Sign up for Railway
2. ✅ Deploy web service
3. ✅ Upload current database (443 speakers)
4. ✅ Test search interface works
5. ⏳ Add background worker service
6. ⏳ Run scaling sessions to 1000+ speakers
7. ⏳ Simplify to single/dual service with cron

---

## Support

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- This project on GitHub: https://github.com/nicoluchsinger-sys/asia_society_speaker_database
