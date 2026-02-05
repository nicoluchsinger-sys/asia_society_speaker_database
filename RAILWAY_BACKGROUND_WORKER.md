# Railway Background Worker Setup

Guide to adding a second Railway service for long-running scraping tasks.

## Overview

**Current Setup:**
- Service 1 (web): Flask application for search interface
- Database: 443 speakers, 204 events

**After Setup:**
- Service 1 (web): Flask application (unchanged)
- Service 2 (scraper): Background worker for scraping tasks
- Shared database: Both services access same SQLite database

**Why We Need This:**
- Web service has timeout limits (~15 minutes)
- Scraping 200 events takes 1-2 hours
- Background worker can run without timeout

---

## Step-by-Step Setup

### Step 1: Add Second Service to Railway

**In Railway Dashboard:**

1. Go to your project: `speaker-database`
2. Click **"+ New"** button (top right)
3. Select **"GitHub Repo"**
4. Choose: `nicoluchsinger-sys/asia_society_speaker_database`
5. Railway will create a second service

**Wait for build to complete (~3-5 minutes)**

---

### Step 2: Configure Scraper Service

**Click on the new service, then:**

#### 2.1 Rename Service

1. Go to **"Settings"** tab
2. Find **"Service Name"**
3. Change to: `scraper`
4. Click checkmark to save

#### 2.2 Set Start Command

1. Still in **"Settings"** tab
2. Find **"Deploy"** section
3. Set **"Custom Start Command"**:
   ```bash
   sleep infinity
   ```
   *(This keeps the service running without doing anything - we'll trigger scraping manually)*

4. Click checkmark to save

#### 2.3 Disable Public Networking

1. Still in **"Settings"** tab
2. Find **"Networking"** section
3. Make sure **"Public Networking"** is **OFF** (scraper doesn't need a public URL)

---

### Step 3: Add Environment Variables

**In the scraper service:**

1. Go to **"Variables"** tab
2. Add these variables (same as web service):

```
ANTHROPIC_API_KEY=***REMOVED***

OPENAI_API_KEY=***REMOVED***
```

3. Click **"Add"** for each variable

**Railway will redeploy automatically** after adding variables.

---

### Step 4: Share Database Between Services

This is the **critical step** - both services need to access the same database file.

**Important:** Railway doesn't have a built-in "shared volume" feature like Docker Compose. We need to use a workaround:

#### Option A: Use Railway Volume (Recommended)

1. In project view, click **"+ New"**
2. Select **"Volume"**
3. Name: `speaker-db-shared`
4. Click **"Create"**

5. **Connect to Web Service:**
   - Click on `web` service
   - Go to **"Variables"** tab
   - Click **"+ New Variable"** → **"+ Add Volume"**
   - Select `speaker-db-shared`
   - Mount path: `/app/speakers.db`

6. **Connect to Scraper Service:**
   - Click on `scraper` service
   - Go to **"Variables"** tab
   - Click **"+ New Variable"** → **"+ Add Volume"**
   - Select `speaker-db-shared`
   - Mount path: `/app/speakers.db`

**Note:** You'll need to re-upload the database to the volume after this change.

#### Option B: Database Sync via Network (Alternative)

If Railway volumes don't work as expected, we can use a different approach:
- Keep database in web service only
- Scraper writes to a temporary database
- Merge databases after scraping completes

*(We'll try Option A first)*

---

### Step 5: Test Background Worker

Once setup is complete, test the scraper service:

#### Using Railway CLI:

```bash
# Run a small test scrape (5 events)
railway run --service scraper bash -c './railway_scraper.sh 5'
```

#### Using Railway Dashboard:

1. Click on `scraper` service
2. Go to **"Deployments"** tab
3. Click on latest deployment
4. Click **"View Logs"**
5. In the logs view, you'll see a **"Shell"** button - click it
6. In the shell, run:
   ```bash
   ./railway_scraper.sh 5
   ```

**What to expect:**
- Browser launches (headless)
- Scrapes 5 events
- Extracts speakers
- Shows updated statistics

---

## Running Scraping Sessions

### Small Test (5 events):
```bash
railway run --service scraper bash -c './railway_scraper.sh 5'
```

### Full Scraping Session (200 events):
```bash
railway run --service scraper bash -c './railway_scraper.sh 200'
```

**Runtime:** ~1-2 hours for 200 events

---

## Monitoring Progress

### Check Logs:
```bash
railway logs --service scraper
```

### Check Database Stats:

Visit your web interface:
```
https://asiasocietyspeakerdatabase-production.up.railway.app/api/stats
```

Should show increasing speaker/event counts as scraping progresses.

---

## Troubleshooting

### "Database locked" Error

**Cause:** Both services trying to write to database simultaneously

**Solution:** Only run scraper when web service is idle (no active searches)

### "Chrome/Selenium not found"

**Cause:** Dockerfile dependencies not installed

**Solution:** Verify scraper service is using the same Dockerfile as web service

### Scraper Service Keeps Restarting

**Cause:** No start command or invalid command

**Solution:** Ensure start command is `sleep infinity` in Settings

### Can't Access Shared Database

**Cause:** Volume not properly mounted

**Solution:**
- Check volume is connected to both services
- Verify mount paths are identical: `/app/speakers.db`
- Try redeploying both services

---

## Cost Estimate

**During scaling (2 services running):**
- Web service: $5/month
- Scraper service: $5/month
- Volume: $1/month
- **Total: ~$11/month**

**After scaling (remove scraper):**
- Web service only: $5/month
- Volume: $1/month
- **Total: ~$6/month**

---

## Next Steps

After successful background worker setup:

1. ✅ Run test scraping session (5 events)
2. ⏳ Run 4 full sessions (200 events each)
3. ⏳ Scale to 1000+ speakers
4. ⏳ Remove scraper service
5. ⏳ Add cron job to web service for daily maintenance

---

## Quick Reference

**Start scraping:**
```bash
railway run --service scraper bash -c './railway_scraper.sh 200'
```

**Check progress:**
```bash
railway logs --service scraper --follow
```

**Check database stats:**
```bash
curl https://asiasocietyspeakerdatabase-production.up.railway.app/api/stats
```
