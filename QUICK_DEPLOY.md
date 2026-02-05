# Quick Deployment Guide

## Prerequisites
- Server with 4GB RAM (DigitalOcean, Linode, Hetzner, etc.)
- Ubuntu 22.04 LTS
- SSH access
- Your API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY)

---

## Option 1: Docker Deployment (Recommended)

### 1. On your server:

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo apt-get install -y docker-compose

# Clone repository
cd /opt
sudo git clone https://github.com/nicoluchsinger-sys/asia_society_speaker_database.git speaker_database
cd speaker_database

# Create .env file
nano .env
```

Add your API keys to `.env`:
```
ANTHROPIC_API_KEY=sk-ant-xxxxx
OPENAI_API_KEY=sk-xxxxx
```

```bash
# Build and test
sudo docker build -t speaker-pipeline .

# Test run (scrape 5 events)
sudo docker run --rm -v $(pwd)/speakers.db:/app/speakers.db \
  --env-file .env \
  speaker-pipeline python3 main_selenium.py -e 5 --stats

# Start web interface
sudo docker-compose up -d web
```

Web interface now running at: `http://your-server-ip:5001`

### 2. Set up automated scraping:

```bash
# Make scripts executable
chmod +x run_pipeline.sh backup_database.sh health_check.sh

# Add to cron (run daily at 2 AM)
crontab -e
```

Add this line:
```
0 2 * * * cd /opt/speaker_database && ./run_pipeline.sh >> /var/log/speaker_pipeline.log 2>&1
```

### 3. Test pipeline:

```bash
# Run once manually
./run_pipeline.sh

# Check logs
tail -f /var/log/speaker_pipeline.log
```

Done! Pipeline will run automatically every day.

---

## Option 2: Direct Python Deployment

### 1. Install dependencies:

```bash
# System packages
sudo apt-get update && sudo apt-get install -y \
    python3 python3-pip wget curl gnupg unzip

# Install Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb

# Install ChromeDriver
CHROMEDRIVER_VERSION=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE)
wget https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
sudo mv chromedriver /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver

# Python packages
cd /opt/speaker_database
pip3 install -r requirements.txt
```

### 2. Set up environment:

```bash
# Create .env file
nano .env
```

Add your API keys.

### 3. Test:

```bash
python3 main_selenium.py -e 5 --stats
```

### 4. Automate:

Same cron setup as Docker option.

---

## Quick Commands

### Run full pipeline once:
```bash
./run_pipeline.sh
```

### Scrape 50 events (fast growth):
```bash
python3 main_selenium.py -e 50 --stats --export
```

### Enrich all speakers:
```bash
python3 enrich_speakers_v2.py
```

### Generate embeddings:
```bash
python3 generate_embeddings.py --provider openai
```

### Start web interface:
```bash
cd web_app && python3 app.py
```

### Backup database:
```bash
./backup_database.sh
```

### Health check:
```bash
./health_check.sh
```

---

## Timeline to 1000 Speakers

Current: **443 speakers**
Goal: **1000 speakers**
Need: **~557 more speakers** (~260 more events)

### Aggressive Schedule (1 week):
```bash
# Add to cron: 3x per day, 50 events each
0 2,10,18 * * * cd /opt/speaker_database && python3 main_selenium.py -e 50 --stats --export
```

Result: 150 events/day = 6-7 days to 1000 speakers

### Balanced Schedule (2 weeks):
```bash
# Add to cron: 2x per day, 30 events each
0 2,14 * * * cd /opt/speaker_database && python3 main_selenium.py -e 30 --stats --export
```

Result: 60 events/day = 13 days to 1000 speakers

### Maintenance Mode (after 1000):
```bash
# Add to cron: 1x per day, 20 events
0 2 * * * cd /opt/speaker_database && ./run_pipeline.sh
```

Result: Keep database fresh with new events

---

## Cost Estimate

### Server:
- **DigitalOcean 4GB:** $24/month
- **Hetzner CPX21 (3GB):** $8/month ⭐ Cheapest

### API Costs (443→1000):
- **One-time growth:** ~$20
- **Monthly maintenance:** ~$5

**Total first month:** $28-44
**Total ongoing:** $13-29/month

---

## Monitoring

### Check database size:
```bash
du -h speakers.db
```

### Check speaker count:
```bash
python3 -c "from database import SpeakerDatabase; db = SpeakerDatabase(); stats = db.get_statistics(); print(f'Speakers: {stats[\"total_speakers\"]}'); db.close()"
```

### View logs:
```bash
tail -f /var/log/speaker_pipeline.log
```

### Check web interface:
```bash
curl http://localhost:5001/api/stats
```

---

## Troubleshooting

### Chrome fails:
```bash
google-chrome --version
chromedriver --version
```

### Database locked:
```bash
# Check for running processes
ps aux | grep python

# Kill if needed
pkill -f "python3 main_selenium.py"
```

### Out of memory:
```bash
# Add swap space
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Cron not running:
```bash
# Check cron logs
tail -f /var/log/syslog | grep CRON

# Make scripts executable
chmod +x *.sh
```

---

## Security Checklist

- [ ] Use SSH keys (disable password auth)
- [ ] Set up firewall: `sudo ufw allow 22,5001/tcp && sudo ufw enable`
- [ ] Keep API keys in `.env` (not in code)
- [ ] Set up database backups
- [ ] Monitor logs regularly
- [ ] Update system: `sudo apt-get update && sudo apt-get upgrade`

---

## Next Steps After 1000 Speakers

1. **Switch to maintenance mode** (1x daily scraping)
2. **Set up alerting** (email/Slack on failures)
3. **Consider PostgreSQL** (if hitting SQLite limits)
4. **Add more monitoring** (Uptime Robot, Healthchecks.io)
5. **Optimize costs** (use cheaper server if possible)

---

## Support

Full documentation: `DEPLOYMENT_GUIDE.md`
Pipeline overview: `SPEAKER_PIPELINE_OVERVIEW.md`
Web interface docs: `web_app/README.md`
