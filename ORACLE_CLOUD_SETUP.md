# Oracle Cloud Free Tier Deployment - $0/month Forever

## What You Get (Free Forever)

Oracle Cloud's "Always Free" tier includes:
- **2 AMD VMs** (1GB RAM each) OR **1 Ampere ARM VM** (4 cores, 24GB RAM!)
- **200GB block storage** (100GB per VM)
- **10TB/month outbound data transfer**
- **No credit card required** after trial

**Recommended:** Use the ARM VM (4 cores + 24GB RAM for free is insane!)

---

## Step-by-Step Setup

### Step 1: Create Oracle Cloud Account (10 minutes)

1. Go to https://www.oracle.com/cloud/free/
2. Click "Start for free"
3. Fill in details:
   - Email
   - Country
   - Create password
4. Choose "Home Region" (can't change later!)
   - Pick closest to you or your users
   - US East (Ashburn) or Europe (Frankfurt) recommended
5. Complete phone verification
6. Enter payment info (required for trial, but won't be charged)
   - $300 free credits for 30 days (unused after that)
   - Always Free resources remain free forever

7. Wait 5-10 minutes for account provisioning

---

### Step 2: Create Compute Instance (15 minutes)

1. **Go to Compute → Instances**
   - Click "Create Instance"

2. **Name your instance:**
   - Name: `speaker-database`

3. **Choose Image and Shape:**
   - **Image:** Ubuntu 22.04 (Minimal is fine)
   - **Shape:** Click "Change Shape"
     - Select "Ampere" (ARM)
     - Choose: `VM.Standard.A1.Flex`
     - **OCPU count:** 4 (max for free tier)
     - **Memory (GB):** 24 (max for free tier)
     - ✅ This is FREE FOREVER!

4. **Networking:**
   - Keep defaults (creates new VCN)
   - Make sure "Assign a public IPv4 address" is checked ✅

5. **Add SSH Keys:**
   - Click "Generate a key pair for me"
   - Download both:
     - Private key: `ssh-key-YYYY-MM-DD.key`
     - Public key: `ssh-key-YYYY-MM-DD.key.pub`
   - Save to `~/.ssh/` folder

6. **Boot Volume:**
   - Keep default (50GB is plenty)

7. **Click "Create"**
   - Wait 1-2 minutes for instance to provision

8. **Note your Public IP:**
   - Copy the "Public IP address" shown (e.g., 123.45.67.89)

---

### Step 3: Configure Firewall (5 minutes)

Oracle Cloud has TWO firewalls you need to open:

#### A) Oracle Cloud Security List

1. Go to **Networking → Virtual Cloud Networks**
2. Click your VCN (usually "vcn-YYYYMMDD-HHMM")
3. Click **Security Lists** → **Default Security List**
4. Click **Add Ingress Rules**

**Add this rule:**
```
Source CIDR: 0.0.0.0/0
IP Protocol: TCP
Destination Port Range: 5001
Description: Flask web app
```

Click "Add Ingress Rules"

#### B) Ubuntu Firewall (iptables)

We'll do this via SSH in next step.

---

### Step 4: Connect to Your Instance (5 minutes)

#### On Mac/Linux:

```bash
# Make SSH key readable
chmod 400 ~/.ssh/ssh-key-YYYY-MM-DD.key

# Connect (replace with your IP and key filename)
ssh -i ~/.ssh/ssh-key-YYYY-MM-DD.key ubuntu@YOUR_PUBLIC_IP
```

#### On Windows:

Use PuTTY or Windows Terminal:
```powershell
ssh -i C:\Users\YourName\.ssh\ssh-key-YYYY-MM-DD.key ubuntu@YOUR_PUBLIC_IP
```

**You're now in the server!**

---

### Step 5: Configure Server Firewall (2 minutes)

Once connected via SSH, run these commands:

```bash
# Open port 5001 for web app
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5001 -j ACCEPT

# Save firewall rules (persist across reboots)
sudo netfilter-persistent save

# OR if that doesn't work:
sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

---

### Step 6: Install Dependencies (10 minutes)

Run these commands on the server:

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Python and tools
sudo apt-get install -y python3 python3-pip git wget curl unzip

# Install Chrome (for Selenium)
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt-get install -y ./google-chrome-stable_current_amd64.deb
rm google-chrome-stable_current_amd64.deb

# Install ChromeDriver
CHROMEDRIVER_VERSION=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE)
wget https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
sudo mv chromedriver /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver
rm chromedriver_linux64.zip

# Verify installations
google-chrome --version
chromedriver --version
python3 --version
```

---

### Step 7: Deploy Application (10 minutes)

```bash
# Clone repository
cd ~
git clone https://github.com/nicoluchsinger-sys/asia_society_speaker_database.git
cd asia_society_speaker_database

# Create .env file with your API keys
nano .env
```

**Add your API keys to `.env`:**
```
ANTHROPIC_API_KEY=sk-ant-xxxxx
OPENAI_API_KEY=sk-xxxxx
```

Save with `Ctrl+X`, then `Y`, then `Enter`

```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Make scripts executable
chmod +x run_pipeline.sh backup_database.sh health_check.sh

# Test the app (scrape 3 events to test)
python3 main_selenium.py -e 3 --stats
```

If that works, you'll see speakers extracted!

---

### Step 8: Start Web Interface (5 minutes)

#### Option A: Quick Test (foreground)

```bash
cd ~/asia_society_speaker_database/web_app
python3 app.py
```

Visit: `http://YOUR_PUBLIC_IP:5001`

Press `Ctrl+C` to stop

#### Option B: Run in Background (production)

```bash
cd ~/asia_society_speaker_database

# Install screen (for keeping processes running)
sudo apt-get install -y screen

# Start web app in screen session
screen -S webapp
cd ~/asia_society_speaker_database/web_app
python3 app.py

# Detach from screen: Press Ctrl+A then D

# To reattach later:
screen -r webapp
```

#### Option C: Systemd Service (best for production)

Create service file:
```bash
sudo nano /etc/systemd/system/speaker-web.service
```

Add this content:
```ini
[Unit]
Description=Speaker Database Web App
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/asia_society_speaker_database/web_app
ExecStart=/usr/bin/python3 /home/ubuntu/asia_society_speaker_database/web_app/app.py
Restart=always
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Save and enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable speaker-web
sudo systemctl start speaker-web

# Check status
sudo systemctl status speaker-web

# View logs
sudo journalctl -u speaker-web -f
```

**Your web app is now running!**
Visit: `http://YOUR_PUBLIC_IP:5001`

---

### Step 9: Set Up Automated Scraping (5 minutes)

```bash
# Edit crontab
crontab -e

# If asked, choose nano (option 1)

# Add this line at the bottom:
0 2 * * * cd /home/ubuntu/asia_society_speaker_database && ./run_pipeline.sh >> /var/log/speaker_pipeline.log 2>&1

# Save and exit (Ctrl+X, Y, Enter)

# Verify cron job was added
crontab -l
```

This will run the pipeline daily at 2 AM.

---

### Step 10: Test Everything (5 minutes)

```bash
# Run pipeline once manually
cd ~/asia_society_speaker_database
./run_pipeline.sh

# This will:
# 1. Scrape 20 events
# 2. Extract speakers
# 3. Enrich speakers with tags/demographics
# 4. Generate embeddings
# 5. Show statistics
```

Watch it run! This might take 10-20 minutes depending on how many speakers are found.

---

## Quick Reference Commands

### Check if web app is running:
```bash
sudo systemctl status speaker-web
# OR
curl http://localhost:5001
```

### View web app logs:
```bash
sudo journalctl -u speaker-web -f
```

### View pipeline logs:
```bash
tail -f /var/log/speaker_pipeline.log
```

### Check database stats:
```bash
cd ~/asia_society_speaker_database
python3 -c "from database import SpeakerDatabase; db = SpeakerDatabase(); stats = db.get_statistics(); print(f'Speakers: {stats[\"total_speakers\"]}, Events: {stats[\"total_events\"]}'); db.close()"
```

### Run pipeline manually:
```bash
cd ~/asia_society_speaker_database
./run_pipeline.sh
```

### Restart web app:
```bash
sudo systemctl restart speaker-web
```

### SSH back in:
```bash
ssh -i ~/.ssh/ssh-key-YYYY-MM-DD.key ubuntu@YOUR_PUBLIC_IP
```

---

## Important: Keep Your Instance Active

⚠️ **Oracle deactivates unused Always Free instances after 90 days of inactivity.**

**To prevent deactivation:**
1. Visit your web app at least once every 90 days
2. Or SSH in occasionally
3. Set a calendar reminder for every 2 months

**Inactivity = No HTTP traffic, no SSH connections, no API calls**

---

## Optional: Add a Domain Name

Instead of `http://123.45.67.89:5001`, use `http://speakers.yourdomain.com`:

1. **Buy domain** ($12/year from Namecheap, Google Domains, etc.)

2. **Add DNS A record:**
   ```
   Type: A
   Name: speakers
   Value: YOUR_PUBLIC_IP
   TTL: 300
   ```

3. **Install nginx reverse proxy:**
   ```bash
   sudo apt-get install -y nginx

   sudo nano /etc/nginx/sites-available/speakers
   ```

   Add:
   ```nginx
   server {
       listen 80;
       server_name speakers.yourdomain.com;

       location / {
           proxy_pass http://localhost:5001;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

   Enable:
   ```bash
   sudo ln -s /etc/nginx/sites-available/speakers /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

4. **Open port 80:**
   ```bash
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
   sudo netfilter-persistent save
   ```

   Also add port 80 in Oracle Cloud Security List (same as Step 3A)

5. **Optional: Add SSL (HTTPS):**
   ```bash
   sudo apt-get install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d speakers.yourdomain.com
   ```

Now visit: `https://speakers.yourdomain.com`

---

## Backup Strategy

### Automatic Daily Backups:

```bash
# Add backup to cron (daily at 1 AM)
crontab -e

# Add this line:
0 1 * * * cd /home/ubuntu/asia_society_speaker_database && ./backup_database.sh >> /var/log/backup.log 2>&1
```

### Manual Backup:

```bash
cd ~/asia_society_speaker_database
./backup_database.sh
```

Backups stored in: `~/asia_society_speaker_database/backups/`

### Download Backup to Your Computer:

```bash
# On your local machine:
scp -i ~/.ssh/ssh-key-YYYY-MM-DD.key ubuntu@YOUR_PUBLIC_IP:/home/ubuntu/asia_society_speaker_database/backups/speakers_*.db.gz ~/Downloads/
```

---

## Troubleshooting

### Can't connect to web app from browser?

1. **Check if app is running:**
   ```bash
   sudo systemctl status speaker-web
   curl http://localhost:5001
   ```

2. **Check Oracle Cloud Security List:**
   - Go to Networking → VCN → Security Lists
   - Verify port 5001 is open (0.0.0.0/0)

3. **Check Ubuntu firewall:**
   ```bash
   sudo iptables -L -n | grep 5001
   ```

4. **Check app logs:**
   ```bash
   sudo journalctl -u speaker-web -f
   ```

### Selenium fails?

```bash
# Check Chrome installation
google-chrome --version
chromedriver --version

# Test Selenium
cd ~/asia_society_speaker_database
python3 -c "from selenium import webdriver; options = webdriver.ChromeOptions(); options.add_argument('--headless'); driver = webdriver.Chrome(options=options); print('Selenium works!'); driver.quit()"
```

### Out of disk space?

```bash
# Check disk usage
df -h

# Clean old backups (keep last 7 days)
find ~/asia_society_speaker_database/backups/ -name "speakers_*.db.gz" -mtime +7 -delete

# Clean apt cache
sudo apt-get clean
```

### ARM architecture issues?

Most Python packages work on ARM, but if you get errors:

```bash
# Some packages may need compilation
sudo apt-get install -y build-essential python3-dev

# Retry pip install
pip3 install -r requirements.txt
```

---

## Upgrading from Free Tier (If Needed Later)

If you outgrow the free tier (unlikely for few dozen users):

1. **Upgrade instance shape** (pay-as-you-go)
   - Go to Compute → Instances
   - Click instance → More Actions → Edit
   - Change shape to bigger size

2. **Or migrate to paid VPS:**
   - Export database: `./backup_database.sh`
   - Deploy to Hetzner ($4.50/month)
   - Import database

---

## Cost Tracking

**Free Forever Resources:**
- ✅ Compute: 4-core ARM instance (or 2x 1GB AMD)
- ✅ Storage: 200GB total
- ✅ Network: 10TB/month outbound

**If you exceed Always Free limits:**
- Oracle will notify you
- You can set spending limits ($0 = hard stop)
- For this app, you won't exceed limits

---

## Monthly Checklist

- [ ] Visit web app (prevents deactivation)
- [ ] Check logs: `tail -f /var/log/speaker_pipeline.log`
- [ ] Verify cron is running: `crontab -l`
- [ ] Check database stats
- [ ] Download backup (optional)

---

## Summary

**Total Cost:** $0/month
**Setup Time:** ~1 hour
**Resources:** 4 cores, 24GB RAM, 100GB storage (insane for free!)
**Perfect For:** Proof of concept, personal use, low traffic

**Your speaker database is now running 24/7 for FREE!**

Visit: `http://YOUR_PUBLIC_IP:5001`

---

## Next Steps

1. ✅ Complete setup (Steps 1-10)
2. ✅ Test web interface
3. ✅ Run pipeline to get to 1000 speakers
4. ✅ Share with your few dozen users
5. ✅ Monitor usage for 1-2 months
6. 🔄 Migrate to paid VPS later if needed (or stay free!)

**Questions? Issues? Check troubleshooting section or the other deployment docs.**
