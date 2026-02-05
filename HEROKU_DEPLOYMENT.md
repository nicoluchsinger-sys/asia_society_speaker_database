# Heroku & PaaS Platform Deployment Analysis

## TL;DR

**Can it work?** Yes, but with significant modifications.

**Should you use it?** Depends on your priorities:
- ✅ Use Heroku/PaaS if: You want managed infrastructure, easy deployment
- ❌ Avoid Heroku/PaaS if: You want simplicity, lowest cost, keep SQLite

**Recommended PaaS alternatives:**
1. **Render.com** (Best for this project) - Has persistent disks, supports SQLite ✅
2. **Fly.io** - Has persistent volumes, good pricing
3. **Railway.app** - Easy setup, but ephemeral storage (need PostgreSQL)
4. **Heroku** - Classic choice, but most expensive and needs PostgreSQL

---

## Major Issues with Heroku

### 1. **Ephemeral Filesystem** ⚠️ (CRITICAL)

**Problem:**
- Heroku dynos have ephemeral filesystems
- Filesystem is wiped every time dyno restarts (at least daily)
- **Your SQLite database would be deleted every day!**

**Solutions:**
- **Option A:** Migrate from SQLite to PostgreSQL (Heroku Postgres add-on)
- **Option B:** Store SQLite on external storage (S3) and sync on startup/shutdown
- **Option C:** Use a different platform with persistent disks (Render.com, Fly.io)

### 2. **Selenium/Chrome Setup** 🔧

**Problem:**
- Chrome and ChromeDriver not included by default
- Need to use buildpacks

**Solution:**
```bash
# Add buildpacks for Chrome support
heroku buildpacks:add --index 1 heroku/python
heroku buildpacks:add --index 2 https://github.com/heroku/heroku-buildpack-google-chrome
heroku buildpacks:add --index 3 https://github.com/heroku/heroku-buildpack-chromedriver
```

This works but adds complexity.

### 3. **Scheduled Jobs** 📅

**Problem:**
- No native cron support
- Need to use Heroku Scheduler add-on
- Free tier: 1 job per app
- Paid tier: $5/month for unlimited jobs

**Solution:**
```bash
heroku addons:create scheduler:standard
```

Then configure jobs via dashboard or CLI.

### 4. **Request Timeouts** ⏱️

**Problem:**
- 30-second request timeout for web dynos
- Scraping 50 events can take 10+ minutes
- Web scraping must run as background worker, not web process

**Solution:**
- Run scraper as worker dyno (separate from web)
- Use Heroku Scheduler or custom worker process

### 5. **Cost** 💰

**Heroku pricing:**
- Eco dyno: $5/month per dyno (sleeps after 30 min inactivity)
- Basic dyno: $7/month per dyno (no sleeping)
- Standard: $25-50/month per dyno

**For this project you need:**
- 1 web dyno (for Flask app): $7/month
- 1 worker dyno (for scraping): $7/month (or use Scheduler)
- Heroku Postgres (for database): Free tier available (10k rows limit) or $9/month for 1M rows
- Heroku Scheduler: Free for 1 job, $5/month for unlimited
- **Total: $14-28/month minimum**

**Compare to VPS:**
- Hetzner 3GB: $8/month (includes everything)
- DigitalOcean 4GB: $24/month (includes everything)

---

## Platform Comparison

| Platform | Persistent Storage | SQLite Support | Chrome/Selenium | Cron Jobs | Cost/Month | Difficulty |
|----------|-------------------|----------------|-----------------|-----------|------------|------------|
| **Render.com** | ✅ Yes (Disks) | ✅ Yes | ✅ Buildpack | ✅ Cron Jobs | $7-15 | ⭐⭐ Easy |
| **Fly.io** | ✅ Yes (Volumes) | ✅ Yes | ✅ Docker | ✅ Native | $3-15 | ⭐⭐⭐ Medium |
| **Railway.app** | ❌ Ephemeral | ❌ No (need Postgres) | ✅ Docker | ✅ Cron | $5-20 | ⭐⭐ Easy |
| **Heroku** | ❌ Ephemeral | ❌ No (need Postgres) | ⚠️ Buildpacks | ⚠️ Scheduler ($5) | $14-28 | ⭐⭐⭐ Medium |
| **VPS** (Hetzner) | ✅ Yes | ✅ Yes | ✅ Docker/Native | ✅ Cron | $8 | ⭐⭐ Easy |
| **VPS** (DigitalOcean) | ✅ Yes | ✅ Yes | ✅ Docker/Native | ✅ Cron | $24 | ⭐⭐ Easy |

**Winner: Render.com** (if you want PaaS) or **Hetzner VPS** (if you want cheapest)

---

## Render.com Deployment (Recommended PaaS)

**Why Render.com:**
- ✅ Persistent disks (keep SQLite database)
- ✅ Native cron jobs (free)
- ✅ Docker support (use existing Dockerfile)
- ✅ Free tier available (limited resources)
- ✅ Simpler than Heroku
- ✅ Better pricing ($7/month for basic, $15/month for standard)

### Render.com Setup

**1. Create `render.yaml`:**

```yaml
databases:
  - name: speaker-database
    plan: starter
    databaseName: speakers
    user: appuser

services:
  - type: web
    name: speaker-web
    env: docker
    dockerfilePath: ./Dockerfile
    dockerCommand: python3 web_app/app.py
    plan: starter
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: OPENAI_API_KEY
        sync: false
    disk:
      name: speaker-data
      mountPath: /data
      sizeGB: 10

  - type: worker
    name: speaker-scraper
    env: docker
    dockerfilePath: ./Dockerfile
    dockerCommand: python3 main_selenium.py -e 20 --stats
    plan: starter
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: OPENAI_API_KEY
        sync: false
    disk:
      name: speaker-data
      mountPath: /data
      sizeGB: 10

  - type: cron
    name: daily-scraper
    env: docker
    dockerfilePath: ./Dockerfile
    schedule: "0 2 * * *"
    dockerCommand: ./run_pipeline.sh
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: OPENAI_API_KEY
        sync: false
    disk:
      name: speaker-data
      mountPath: /data
      sizeGB: 10
```

**2. Deploy:**

```bash
# Connect Render to GitHub repo
# Render auto-deploys on git push

# Or use Render CLI
render deploy
```

**Cost:** $7-15/month (depending on resources)

---

## Fly.io Deployment

**Why Fly.io:**
- ✅ Persistent volumes
- ✅ Docker-based (use existing Dockerfile)
- ✅ Very cheap ($3-5/month possible)
- ✅ Global edge network
- ❌ More complex than Render

### Fly.io Setup

**1. Install Fly CLI:**
```bash
curl -L https://fly.io/install.sh | sh
fly auth login
```

**2. Create `fly.toml`:**

```toml
app = "speaker-database"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[env]
  PORT = "5001"

[mounts]
  source = "speaker_data"
  destination = "/data"
  initial_size = "10gb"

[[services]]
  http_checks = []
  internal_port = 5001
  protocol = "tcp"
  script_checks = []

  [[services.ports]]
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

[deploy]
  strategy = "rolling"
```

**3. Deploy:**

```bash
# Create app
fly apps create speaker-database

# Create volume for persistent data
fly volumes create speaker_data --size 10 --region iad

# Set secrets
fly secrets set ANTHROPIC_API_KEY=your_key
fly secrets set OPENAI_API_KEY=your_key

# Deploy
fly deploy

# Set up cron job (use Fly Machines API or external service)
```

**Cost:** $3-15/month (depending on resources + volume)

---

## Heroku Deployment (If You Must)

### Prerequisites

You'll need to:
1. **Migrate from SQLite to PostgreSQL** (significant work)
2. Add Heroku-specific buildpacks
3. Modify database.py to use PostgreSQL instead of SQLite
4. Set up Heroku Scheduler for cron jobs

### Modified Files for Heroku

#### 1. `Procfile`
```
web: python3 web_app/app.py
worker: python3 main_selenium.py -e 20 --stats
```

#### 2. Add buildpacks
```bash
heroku buildpacks:add --index 1 heroku/python
heroku buildpacks:add --index 2 https://github.com/heroku/heroku-buildpack-google-chrome
heroku buildpacks:add --index 3 https://github.com/heroku/heroku-buildpack-chromedriver
```

#### 3. Modify `database.py` for PostgreSQL

You'd need to replace SQLite with PostgreSQL using `psycopg2`:

```python
import os
import psycopg2
from psycopg2.extras import DictCursor

class SpeakerDatabase:
    def __init__(self):
        # Use Heroku DATABASE_URL
        database_url = os.getenv('DATABASE_URL')
        # Heroku uses postgres://, psycopg2 needs postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)

        self.conn = psycopg2.connect(database_url, cursor_factory=DictCursor)
        self.init_database()

    # ... rest needs major refactoring for PostgreSQL
```

This is **~200 lines of changes** across database.py and all SQL queries.

#### 4. Deploy

```bash
# Create Heroku app
heroku create speaker-database

# Add PostgreSQL
heroku addons:create heroku-postgresql:essential-0

# Add Scheduler
heroku addons:create scheduler:standard

# Set environment variables
heroku config:set ANTHROPIC_API_KEY=your_key
heroku config:set OPENAI_API_KEY=your_key

# Deploy
git push heroku main

# Configure scheduler
heroku addons:open scheduler
# Add job: python3 run_pipeline.sh (runs daily)
```

**Cost:** $14-28/month minimum

---

## Migration Effort Comparison

| Platform | Code Changes | Complexity | Time Estimate |
|----------|--------------|------------|---------------|
| **Render.com** | None (use SQLite) | Low | 1-2 hours |
| **Fly.io** | None (use SQLite) | Medium | 2-4 hours |
| **Railway.app** | PostgreSQL migration | High | 4-8 hours |
| **Heroku** | PostgreSQL migration | High | 4-8 hours |
| **VPS** (Docker) | None | Low | 1-2 hours |
| **VPS** (Direct) | None | Very Low | 30 minutes |

---

## SQLite vs PostgreSQL Trade-offs

### Keep SQLite (Render.com, Fly.io, VPS)
**Pros:**
- ✅ No code changes needed
- ✅ Simple file-based database
- ✅ Easy backups (just copy file)
- ✅ Good performance for this scale
- ✅ Works great up to 100k+ speakers

**Cons:**
- ❌ Limited concurrency (not an issue for this app)
- ❌ No network access (not needed)

### Migrate to PostgreSQL (Heroku, Railway)
**Pros:**
- ✅ Better for multi-user concurrent access
- ✅ More scalable long-term
- ✅ Better for complex queries
- ✅ Industry standard

**Cons:**
- ❌ Requires code changes (~200 lines)
- ❌ More complex to manage
- ❌ Adds cost ($9+/month)
- ❌ Migration effort (4-8 hours)

**For 1000 speakers:** SQLite is perfectly fine. PostgreSQL is overkill.

---

## Recommended Decision Matrix

### Choose **VPS (Hetzner/DigitalOcean)** if:
- ✅ You want simplest deployment (no code changes)
- ✅ You want lowest cost ($8/month)
- ✅ You're comfortable with basic server management
- ✅ You want full control

### Choose **Render.com** if:
- ✅ You want managed platform (no server management)
- ✅ You want to keep SQLite (no code changes)
- ✅ You're okay with $15/month cost
- ✅ You want easy deployment

### Choose **Fly.io** if:
- ✅ You want cheapest PaaS ($3-5/month possible)
- ✅ You're comfortable with Docker
- ✅ You want global edge network
- ✅ You don't mind slightly more complex setup

### Choose **Heroku** if:
- ✅ You're already familiar with Heroku
- ✅ You don't mind migrating to PostgreSQL (4-8 hours work)
- ✅ You're okay with $14-28/month cost
- ✅ You want the "classic" PaaS experience

### Avoid **Railway.app** for this project:
- ❌ No persistent storage (need PostgreSQL migration)
- ❌ Not cheaper than Heroku
- Better alternatives exist (Render.com)

---

## My Recommendation

**For your use case (scaling to 1000 speakers):**

### 🥇 **Best: Traditional VPS (Hetzner)**
- **Cost:** $8/month
- **Effort:** 1 hour setup
- **Maintenance:** Low (cron handles everything)
- **Scalability:** Good (works up to 10k+ speakers)
- **Why:** Simplest, cheapest, most control

### 🥈 **Second: Render.com**
- **Cost:** $15/month
- **Effort:** 2 hours setup
- **Maintenance:** Very low (fully managed)
- **Scalability:** Good
- **Why:** Best PaaS for this project (persistent disks + SQLite)

### 🥉 **Third: Fly.io**
- **Cost:** $5-10/month
- **Effort:** 3 hours setup
- **Maintenance:** Low
- **Scalability:** Excellent
- **Why:** Cheap PaaS, but more complex than Render

### ❌ **Avoid: Heroku**
- **Cost:** $14-28/month
- **Effort:** 6-10 hours (PostgreSQL migration)
- **Maintenance:** Medium
- **Scalability:** Good
- **Why:** Most expensive, requires most changes, no unique benefits

---

## Quick Comparison Table

| Factor | VPS (Hetzner) | Render.com | Fly.io | Heroku |
|--------|---------------|------------|--------|--------|
| **Monthly Cost** | $8 | $15 | $5-10 | $14-28 |
| **Setup Time** | 1 hour | 2 hours | 3 hours | 6-10 hours |
| **Code Changes** | None | None | None | Major (PostgreSQL) |
| **Maintenance** | Low | Very Low | Low | Medium |
| **Complexity** | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Scalability** | Good | Good | Excellent | Good |
| **Persistent Storage** | ✅ Native | ✅ Disks | ✅ Volumes | ❌ Need PostgreSQL |
| **SQLite Support** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No |
| **Cron Jobs** | ✅ Native | ✅ Native | ⚠️ External | ⚠️ Scheduler ($5) |
| **Docker Support** | ✅ Yes | ✅ Yes | ✅ Native | ⚠️ Buildpacks |

---

## Sample Render.com Deployment Files

I can create Render.com deployment files if you're interested. It would add:

**New files:**
- `render.yaml` - Render configuration
- `docs/RENDER_DEPLOY.md` - Render-specific instructions

**Changes:**
- Update Dockerfile to support Render's environment
- Update run_pipeline.sh to work with Render's disk mounts

Want me to create these files?

---

## Bottom Line

**Yes, Heroku and similar platforms CAN work**, but:

1. **Heroku specifically:** ❌ Not recommended (expensive, requires PostgreSQL migration)
2. **Render.com:** ✅ Great option (persistent disks, keeps SQLite, $15/month)
3. **Fly.io:** ✅ Good option (cheapest PaaS at $5-10/month, but more complex)
4. **Traditional VPS:** ✅ Still the best (simplest, cheapest at $8/month)

For getting to 1000 speakers quickly and cheaply, **stick with VPS or try Render.com**.
