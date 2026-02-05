# Oracle Cloud Quick Start - TL;DR Version

## 30-Minute Setup Guide

### 1. Create Oracle Account (5 min)
- https://www.oracle.com/cloud/free/
- Sign up, verify email/phone
- Choose home region (can't change later!)

### 2. Create Instance (5 min)
- **Compute → Instances → Create Instance**
- Name: `speaker-database`
- Shape: **Ampere VM.Standard.A1.Flex** (4 OCPU, 24GB RAM - FREE!)
- Image: Ubuntu 22.04
- Download SSH keys
- Note Public IP

### 3. Open Firewall (2 min)
- **Networking → VCN → Security Lists → Add Ingress Rule**
- Source: `0.0.0.0/0`
- Port: `5001`
- Save

### 4. SSH In (1 min)
```bash
chmod 400 ~/Downloads/ssh-key-*.key
ssh -i ~/Downloads/ssh-key-*.key ubuntu@YOUR_IP
```

### 5. Install Everything (10 min)
```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb

# Install ChromeDriver
CHROMEDRIVER_VERSION=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE)
wget https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
sudo mv chromedriver /usr/local/bin/ && sudo chmod +x /usr/local/bin/chromedriver

# Install Python + Git
sudo apt-get install -y python3-pip git

# Clone repo
cd ~ && git clone https://github.com/nicoluchsinger-sys/asia_society_speaker_database.git
cd asia_society_speaker_database

# Install Python packages
pip3 install -r requirements.txt
```

### 6. Configure App (2 min)
```bash
# Create .env file
nano .env
```

Add:
```
ANTHROPIC_API_KEY=sk-ant-xxxxx
OPENAI_API_KEY=sk-xxxxx
```

Save: `Ctrl+X`, `Y`, `Enter`

### 7. Open Ubuntu Firewall (1 min)
```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5001 -j ACCEPT
sudo netfilter-persistent save
```

### 8. Start Web App (2 min)
```bash
# Quick test
cd ~/asia_society_speaker_database/web_app
python3 app.py
```

Visit: `http://YOUR_IP:5001` ✅

### 9. Run as Service (2 min)
Press `Ctrl+C` to stop test, then:

```bash
sudo tee /etc/systemd/system/speaker-web.service > /dev/null <<EOF
[Unit]
Description=Speaker Database Web App
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/asia_society_speaker_database/web_app
ExecStart=/usr/bin/python3 app.py
Restart=always
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable speaker-web
sudo systemctl start speaker-web
```

**Web app now runs 24/7!**

### 10. Set Up Cron (1 min)
```bash
crontab -e
# Choose nano (1)

# Add at bottom:
0 2 * * * cd /home/ubuntu/asia_society_speaker_database && ./run_pipeline.sh >> /var/log/speaker_pipeline.log 2>&1
```

**Done! Your speaker database is live at `http://YOUR_IP:5001`**

---

## Quick Commands

### Check if running:
```bash
sudo systemctl status speaker-web
```

### View logs:
```bash
sudo journalctl -u speaker-web -f
```

### Run pipeline manually:
```bash
cd ~/asia_society_speaker_database
./run_pipeline.sh
```

### Check database:
```bash
cd ~/asia_society_speaker_database
python3 -c "from database import SpeakerDatabase; db = SpeakerDatabase(); stats = db.get_statistics(); print(stats); db.close()"
```

---

## Important Reminder

⚠️ **Use your instance at least once every 90 days** or Oracle deactivates it!

Set a calendar reminder to visit your web app every 2 months.

---

## Full Documentation

For detailed troubleshooting, see: `ORACLE_CLOUD_SETUP.md`
