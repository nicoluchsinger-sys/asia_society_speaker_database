# Server Deployment Guide - Automated Speaker Pipeline

## Goal
Run the speaker scraping and enrichment pipeline consistently on a remote server to scale from 443 to 1000+ speakers without depending on your local machine.

---

## Infrastructure Options

### Option 1: Simple VPS (Recommended for Start)
**Best for:** Getting started quickly, predictable costs

**Providers:**
- **DigitalOcean** Droplet ($12-24/month)
- **Linode** ($12-24/month)
- **AWS Lightsail** ($10-20/month)
- **Hetzner** ($5-15/month, EU-based)

**Specs needed:**
- **RAM:** 2-4 GB minimum (for Chrome/Selenium)
- **CPU:** 2 cores minimum
- **Storage:** 25-50 GB SSD
- **OS:** Ubuntu 22.04 LTS

**Pros:**
- Simple setup
- Predictable monthly cost
- Full control
- Easy to debug

**Cons:**
- Need to manage OS updates
- Single point of failure
- Manual scaling

### Option 2: Serverless (AWS Lambda / Google Cloud Functions)
**Best for:** Cost optimization, infrequent scraping

**Providers:**
- AWS Lambda + EventBridge
- Google Cloud Functions + Scheduler
- Azure Functions

**Pros:**
- Pay per execution (potentially cheaper)
- Auto-scaling
- No server management

**Cons:**
- **Selenium is difficult** (need to package Chrome + chromedriver)
- Cold starts (slower)
- 15-minute execution limits (Lambda)
- More complex setup
- Harder to debug

### Option 3: Docker Container on Cloud (Recommended for Scale)
**Best for:** Production-grade deployment, easy scaling

**Providers:**
- AWS ECS/Fargate
- Google Cloud Run
- DigitalOcean App Platform
- Render.com

**Pros:**
- Consistent environment
- Easy to scale
- Can run locally for testing
- Reproducible deployments

**Cons:**
- Docker learning curve
- Slightly higher complexity

---

## Recommended Approach: VPS with Docker + Cron

This gives you the best balance of simplicity, cost, and reliability.

---

## Step-by-Step Deployment Plan

### Phase 1: Prepare Application for Server Deployment

#### 1.1 Create Dockerfile

**File:** `Dockerfile`

```dockerfile
FROM python:3.11-slim

# Install system dependencies for Selenium + Chrome
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    unzip \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libx11-6 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxshmfence1 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# Install ChromeDriver
RUN CHROMEDRIVER_VERSION=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE) \
    && wget -q https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip \
    && unzip chromedriver_linux64.zip \
    && mv chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    && rm chromedriver_linux64.zip

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./
COPY web_app/ ./web_app/

# Create directory for database
RUN mkdir -p /data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99

# Volume for persistent database
VOLUME /data

# Default command (can be overridden)
CMD ["python3", "main_selenium.py", "-e", "10", "--stats"]
```

#### 1.2 Create docker-compose.yml

**File:** `docker-compose.yml`

```yaml
version: '3.8'

services:
  scraper:
    build: .
    container_name: speaker_scraper
    volumes:
      - ./data:/data
      - ./speakers.db:/app/speakers.db
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    command: python3 main_selenium.py -e 20 --stats
    restart: unless-stopped

  enricher:
    build: .
    container_name: speaker_enricher
    volumes:
      - ./data:/data
      - ./speakers.db:/app/speakers.db
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    command: python3 enrich_speakers_v2.py --limit 50
    restart: "no"
    depends_on:
      - scraper

  embeddings:
    build: .
    container_name: speaker_embeddings
    volumes:
      - ./data:/data
      - ./speakers.db:/app/speakers.db
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    command: python3 generate_embeddings.py --provider openai --limit 100
    restart: "no"
    depends_on:
      - enricher

  web:
    build: .
    container_name: speaker_web
    ports:
      - "5001:5001"
    volumes:
      - ./data:/data
      - ./speakers.db:/app/speakers.db
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    command: python3 web_app/app.py
    restart: unless-stopped
```

#### 1.3 Create Automation Script

**File:** `run_pipeline.sh`

```bash
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
```

Make it executable:
```bash
chmod +x run_pipeline.sh
```

---

### Phase 2: Server Setup

#### 2.1 Provision Server

**DigitalOcean Example:**
```bash
# Create a $12/month droplet (2GB RAM, 1 vCPU)
# Or $24/month (4GB RAM, 2 vCPU) - Recommended for Selenium

# Choose:
# - OS: Ubuntu 22.04 LTS
# - Region: Closest to you
# - Add SSH key
```

**Access server:**
```bash
ssh root@your-server-ip
```

#### 2.2 Initial Server Configuration

```bash
# Update system
apt-get update && apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt-get install -y docker-compose

# Create app user (don't run as root)
adduser --disabled-password --gecos "" appuser
usermod -aG docker appuser

# Create application directory
mkdir -p /opt/speaker_database
chown appuser:appuser /opt/speaker_database
```

#### 2.3 Deploy Application

```bash
# Switch to app user
su - appuser

# Clone repository (or upload files)
cd /opt/speaker_database
git clone https://github.com/nicoluchsinger-sys/asia_society_speaker_database.git .

# Or use rsync to upload from local:
# rsync -avz --exclude='.git' --exclude='speakers.db' --exclude='__pycache__' \
#   /Users/nicoluchsinger/coding/speaker_database/ \
#   appuser@your-server-ip:/opt/speaker_database/

# Create .env file with API keys
nano .env
# Add:
# ANTHROPIC_API_KEY=your_key_here
# OPENAI_API_KEY=your_key_here

# Build Docker image
docker build -t speaker-pipeline .

# Test run
docker run --rm -v $(pwd)/speakers.db:/app/speakers.db \
  --env-file .env \
  speaker-pipeline python3 main_selenium.py -e 5 --stats
```

---

### Phase 3: Automation with Cron

#### 3.1 Create Cron Job

```bash
# Edit crontab
crontab -e

# Add the following lines:

# Run scraper daily at 2 AM (scrape 20 events)
0 2 * * * cd /opt/speaker_database && ./run_pipeline.sh >> /var/log/speaker_pipeline.log 2>&1

# Alternative schedules:
# Every 6 hours:
# 0 */6 * * * cd /opt/speaker_database && ./run_pipeline.sh >> /var/log/speaker_pipeline.log 2>&1

# Twice daily (2 AM and 2 PM):
# 0 2,14 * * * cd /opt/speaker_database && ./run_pipeline.sh >> /var/log/speaker_pipeline.log 2>&1

# Weekly on Mondays at 3 AM (large batch):
# 0 3 * * 1 cd /opt/speaker_database && python3 main_selenium.py -e 50 --stats --export >> /var/log/speaker_pipeline.log 2>&1
```

#### 3.2 Set Up Log Rotation

**File:** `/etc/logrotate.d/speaker_pipeline`

```
/var/log/speaker_pipeline.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
```

---

### Phase 4: Monitoring & Alerting

#### 4.1 Create Health Check Script

**File:** `health_check.sh`

```bash
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
```

#### 4.2 Email Alerts (Optional)

Install mailutils:
```bash
apt-get install -y mailutils
```

Add to cron:
```bash
# Send summary email after each run
0 3 * * * cd /opt/speaker_database && ./run_pipeline.sh 2>&1 | mail -s "Speaker Pipeline Report" your@email.com
```

#### 4.3 Uptime Monitoring

Use a service like:
- **UptimeRobot** (free tier available)
- **Healthchecks.io** (free for 20 checks)
- **Better Stack** (formerly Uptime Robot)

Example with Healthchecks.io:
```bash
# Add to end of run_pipeline.sh
curl -fsS -m 10 --retry 5 https://hc-ping.com/your-unique-uuid
```

---

### Phase 5: Database Management

#### 5.1 Backup Strategy

**File:** `backup_database.sh`

```bash
#!/bin/bash

BACKUP_DIR="/opt/speaker_database/backups"
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="speakers_${DATE}.db"

mkdir -p "$BACKUP_DIR"

# Create backup
cp speakers.db "$BACKUP_DIR/$FILENAME"

# Compress
gzip "$BACKUP_DIR/$FILENAME"

# Keep only last 30 days
find "$BACKUP_DIR" -name "speakers_*.db.gz" -mtime +30 -delete

echo "Backup created: $FILENAME.gz"
```

Add to cron:
```bash
# Daily backup at 1 AM
0 1 * * * cd /opt/speaker_database && ./backup_database.sh >> /var/log/backup.log 2>&1
```

#### 5.2 Consider Upgrading to PostgreSQL (Optional)

For production scale (1000+ speakers), PostgreSQL is more robust:

**Pros:**
- Better concurrency
- More reliable backups
- Network accessible
- Better performance at scale

**Cons:**
- Additional setup complexity
- Slightly higher resource usage
- Need to migrate existing data

---

## Scaling to 1000 Speakers

### Timeline Estimation

Current state: **443 speakers** from **204 events**
Goal: **1000 speakers**
Need: **~557 more speakers** from **~260 more events**

**Scraping rate:**
- 20 events/day = **13 days** to 1000 speakers
- 50 events/day = **5 days** to 1000 speakers

**Recommended approach:**
```bash
# Week 1: Aggressive scraping
# Run 3x per day (50 events each) = 150 events/day
0 2,10,18 * * * cd /opt/speaker_database && python3 main_selenium.py -e 50 --stats

# After reaching 1000: Maintenance mode
# Run daily (20 events) to catch new speakers
0 2 * * * cd /opt/speaker_database && ./run_pipeline.sh
```

### Cost Projection

**API Costs (443→1000 speakers):**
- Speaker extraction: 557 speakers × $0.015 = **$8.36**
- Unified enrichment: 557 speakers × $0.020 = **$11.14**
- Embeddings: 557 speakers × $0.00002 = **$0.01**
- **Total: ~$19.50** for 557 new speakers

**Server Costs:**
- DigitalOcean 4GB droplet: **$24/month**
- Alternative: Hetzner CPX21 (3GB): **$8/month**

**Total monthly cost: $24-32** (server + API usage for maintenance)

---

## Security Best Practices

### 1. Environment Variables

Never commit API keys! Use `.env` file:

```bash
# .env (add to .gitignore)
ANTHROPIC_API_KEY=sk-ant-xxxxx
OPENAI_API_KEY=sk-xxxxx
```

### 2. SSH Key Authentication

```bash
# Disable password authentication
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
sudo systemctl restart sshd
```

### 3. Firewall

```bash
# Allow only SSH and web app
ufw allow 22/tcp
ufw allow 5001/tcp
ufw enable
```

### 4. Restrict Web Access (Optional)

If you don't want public web access:

```bash
# Only allow localhost
ufw deny 5001/tcp

# Use SSH tunnel to access web interface:
ssh -L 5001:localhost:5001 appuser@your-server-ip
# Then visit http://localhost:5001 on your local machine
```

---

## Monitoring Dashboard (Optional)

Create a simple monitoring page:

**File:** `monitor.py`

```python
from flask import Flask, jsonify
from database import SpeakerDatabase
import os

app = Flask(__name__)

@app.route('/health')
def health():
    try:
        db = SpeakerDatabase()
        stats = db.get_statistics()
        db.close()

        return jsonify({
            'status': 'healthy',
            'speakers': stats['total_speakers'],
            'events': stats['total_events'],
            'tagged_speakers': stats['tagged_speakers'],
            'total_tags': stats['total_tags'],
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

Run as systemd service for always-on monitoring.

---

## Troubleshooting

### Issue: Selenium fails on server
**Solution:** Ensure Chrome is installed and running headless
```bash
# Test Chrome installation
google-chrome --version
chromedriver --version

# Run in headless mode (should be default)
python3 main_selenium.py -e 1 --headless
```

### Issue: Database locked errors
**Solution:** SQLite doesn't handle concurrent writes well
```python
# Option 1: Add busy timeout (already in database.py)
self.conn.execute("PRAGMA busy_timeout = 30000")

# Option 2: Use separate processes (current approach)
# Each script opens/closes its own connection

# Option 3: Upgrade to PostgreSQL
```

### Issue: Out of memory
**Solution:** Increase swap space
```bash
# Create 2GB swap file
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### Issue: Cron job not running
**Solution:** Check logs and permissions
```bash
# View cron logs
tail -f /var/log/syslog | grep CRON

# Check if script is executable
chmod +x run_pipeline.sh

# Test script manually
cd /opt/speaker_database && ./run_pipeline.sh
```

---

## Quick Start Checklist

- [ ] Provision server (DigitalOcean/Linode 4GB droplet)
- [ ] Install Docker and Docker Compose
- [ ] Upload application code
- [ ] Create `.env` file with API keys
- [ ] Build Docker image
- [ ] Test run pipeline manually
- [ ] Set up cron job for automation
- [ ] Configure log rotation
- [ ] Set up database backups
- [ ] Configure firewall (UFW)
- [ ] Set up monitoring/health checks
- [ ] Test SSH key authentication
- [ ] Run aggressive scraping (50 events 3x/day)
- [ ] Monitor logs daily for first week
- [ ] Switch to maintenance mode after 1000 speakers

---

## Cost Summary

| Item | Cost | Notes |
|------|------|-------|
| Server (4GB VPS) | $24/month | DigitalOcean, Linode |
| Server (3GB VPS) | $8/month | Hetzner (cheaper alternative) |
| API costs (growth) | ~$20 one-time | 443→1000 speakers |
| API costs (maintenance) | ~$5/month | New events/speakers |
| **Total (first month)** | **$52** | Server + growth |
| **Total (ongoing)** | **$29-32/month** | Server + maintenance |

**Cheaper alternative:** Use Hetzner + only $13/month total ongoing

---

## Next Steps

1. **Immediate:** Set up VPS and deploy application
2. **Week 1:** Run aggressive scraping (3x/day, 50 events each)
3. **Week 2:** Monitor and optimize
4. **After 1000:** Switch to maintenance mode (1x/day, 20 events)
5. **Optional:** Add PostgreSQL, monitoring dashboard, alerting

Ready to deploy? Start with Phase 1 (create Dockerfile) and I can help with any specific steps!
