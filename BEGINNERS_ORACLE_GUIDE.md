# Complete Beginner's Guide to Oracle Cloud Deployment

## What We're Going To Do

We're going to:
1. Create a free Oracle Cloud account
2. Create a virtual computer (server) in the cloud
3. Install your speaker database on that server
4. Make it accessible from anywhere via a web browser
5. Set it to automatically update daily

**Total time:** 1-2 hours
**Cost:** $0 (forever free)
**Prior experience needed:** None!

---

## Part 1: Create Oracle Cloud Account (15 minutes)

### Step 1.1: Go to Oracle Cloud Website

1. Open your web browser (Chrome, Firefox, Safari - any will work)
2. Go to: **https://www.oracle.com/cloud/free/**
3. You'll see a page with "Start for free" button

### Step 1.2: Click "Start for free"

1. Click the big blue **"Start for free"** button
2. You'll be taken to a registration form

### Step 1.3: Fill Out Registration Form

Fill in these fields:

**Country/Territory:**
- Select your country from dropdown (this determines pricing and data center location)

**First Name & Last Name:**
- Enter your real name

**Email:**
- Use a valid email address (you'll need to verify it)
- Example: `yourname@gmail.com`

**Password:**
- Create a strong password (at least 12 characters)
- Must include: uppercase, lowercase, number, and special character
- Example format: `MyPassword123!@#`

**Company Name:**
- Can be anything - even "Personal" or your name
- This doesn't matter for free tier

**Cloud Account Name:**
- This becomes part of your URL
- Must be unique across all Oracle Cloud
- Use lowercase letters and numbers only (no spaces or special characters)
- Example: `nico-speaker-db-2026`
- **Write this down** - you'll need it to login later

**Home Region:**
- **IMPORTANT:** This can't be changed later!
- Choose the region closest to you or your users
- Options:
  - **US East (Ashburn)** - Good for North America
  - **US West (Phoenix)** - Good for West Coast
  - **Europe (Frankfurt)** - Good for Europe
  - **Asia Pacific (Mumbai)** - Good for Asia
  - Many others available

**Recommendation:** Pick the one geographically closest to you

### Step 1.4: Verify Your Email

1. Check your email inbox (the email you provided)
2. You'll get an email from Oracle titled "Verify your email"
3. Click the **"Verify email"** link in the email
4. This takes you back to Oracle's website

### Step 1.5: Phone Verification

1. Enter your mobile phone number
2. Click "Text me a code" or "Call me with a code"
3. Enter the 6-digit code you receive
4. Click "Verify"

### Step 1.6: Payment Information

**Don't worry - this is just for verification. You won't be charged!**

1. Enter credit card or PayPal information
2. Oracle will do a $1 authorization (immediately refunded)
3. This is required even for the free tier
4. Free tier resources will **never** charge you

**What you get with Always Free:**
- Compute: 4-core ARM VM with 24GB RAM (or 2x 1GB AMD VMs)
- Storage: 200GB
- Network: 10TB/month transfer
- These are **completely free forever**

### Step 1.7: Review and Complete

1. Review the terms and conditions (you can actually skip reading, but you must check the box)
2. Check the box "I have reviewed and accept..."
3. Click **"Start my free trial"**

### Step 1.8: Wait for Account Provisioning

1. You'll see a screen saying "Setting up your tenancy..."
2. This takes 5-10 minutes
3. You can close the browser tab - you'll get an email when ready
4. Email subject: "Get Started Now with Oracle Cloud"

### Step 1.9: First Login

1. Once you get the email, click the link or go to: **https://cloud.oracle.com/**
2. Enter your **Cloud Account Name** (the one you created in Step 1.3)
3. Click **"Next"**
4. Enter your **email** and **password**
5. Click **"Sign In"**

**You're now in the Oracle Cloud Console!**

---

## Part 2: Create Your Virtual Server (20 minutes)

### Step 2.1: Navigate to Compute Instances

You're now looking at the Oracle Cloud dashboard (it's a bit overwhelming, but we'll guide you through it).

1. Look at the left sidebar - there's a "hamburger menu" (three horizontal lines) at the top left
2. Click the **hamburger menu (≡)**
3. A menu slides out from the left
4. Scroll down and find **"Compute"**
5. Click **"Compute"** (it expands to show more options)
6. Click **"Instances"**

You're now on the "Instances" page (this is where we'll create our virtual server).

### Step 2.2: Click "Create Instance"

1. You'll see a big blue button that says **"Create instance"**
2. Click it

You're now on the "Create compute instance" page.

### Step 2.3: Name Your Instance

At the top, you'll see a field labeled **"Name"**.

1. Click in the name field
2. Replace the default name with: `speaker-database`
3. This is just a label - you can name it anything you want

### Step 2.4: Choose the Best Free Instance (IMPORTANT!)

This is the most important step - we want the powerful ARM instance!

**Placement section:**
- Leave as default (no changes needed)

**Image and shape section:**
This is where we configure the computer's "brain" and operating system.

1. Look for **"Image"** - it probably says "Oracle Linux" by default
2. Click the **"Change Image"** button

**Choose Image popup appears:**

1. Click **"Ubuntu"** (on the left side menu)
2. Select **"Canonical Ubuntu 22.04"** (should be near the top)
3. Ignore the "Minimal" version - use the regular one
4. Click **"Select Image"** button at the bottom

You're back at the main form.

Now for the "shape" (this is the computer's power):

1. Look for **"Shape"** section (below Image)
2. You'll see something like "VM.Standard.E2.1.Micro"
3. Click **"Change Shape"** button

**Choose Shape popup appears:**

1. On the left side, you'll see "Instance type"
2. Click **"Virtual machine"** (should already be selected)
3. Below that, you'll see "Shape series"
4. Click **"Ampere"** (this is the ARM processor - MUCH better than the default!)

**After clicking Ampere:**

1. You'll see a list of shapes
2. Find and select **"VM.Standard.A1.Flex"**
3. Below that, you'll see sliders or input boxes for:
   - **Number of OCPUs:** Set to **4** (drag slider or type 4)
   - **Amount of memory (GB):** Set to **24** (drag slider or type 24)

These are the maximum free tier amounts!

4. On the right side, you should see **"Always Free-eligible"** with a green checkmark ✅
5. Click **"Select Shape"** button at the bottom

You're back at the main form.

### Step 2.5: Networking Configuration

Scroll down to the **"Networking"** section.

**Primary VNIC information:**
1. Leave everything as default
2. Make sure **"Assign a public IPv4 address"** is **checked** ✅
   - This is CRITICAL - without this, you can't access your server from the internet!

If you see "Create new virtual cloud network" - that's perfect, leave it.

### Step 2.6: SSH Keys (How You'll Access the Server)

Scroll down to **"Add SSH keys"** section.

**What are SSH keys?**
Think of SSH keys like a special secure key pair:
- **Private key** = Your house key (keep this secret!)
- **Public key** = Your door lock (goes on the server)

Oracle can generate these for you automatically:

1. Select **"Generate a key pair for me"** (radio button should be selected)
2. Click **"Save private key"** button
   - A file downloads named something like: `ssh-key-2026-01-26.key`
   - **VERY IMPORTANT:** Save this file somewhere safe!
   - Save it to your `Downloads` folder or Desktop (we'll move it later)
3. Click **"Save public key"** button
   - A file downloads named something like: `ssh-key-2026-01-26.key.pub`
   - Also save this file

**Critical:** If you lose the private key, you can't access your server! Keep it safe.

### Step 2.7: Boot Volume (Storage)

Scroll down to **"Boot volume"** section.

1. Leave everything as default
2. Default is usually 50GB (plenty for our needs)
3. Make sure **"Specify a custom boot volume size"** is NOT checked

### Step 2.8: Create the Instance!

1. Scroll to the very bottom
2. You should see a big blue button: **"Create"**
3. Click **"Create"**

**What happens next:**
- You'll be taken to the "Instance Details" page
- You'll see an orange icon that says "PROVISIONING"
- This takes 1-2 minutes

**Wait until you see:**
- Green icon that says "RUNNING" ✅

### Step 2.9: Copy Your Public IP Address

Once your instance is RUNNING:

1. On the "Instance Details" page, look for **"Instance access"** section
2. You'll see **"Public IP address"**
3. It will be something like: `123.45.67.89`
4. **Click the "Copy" button** next to the IP address
5. Paste this into a text file or note - you'll need it many times!

**Example:** `123.45.67.89` ← This is what an IP address looks like

---

## Part 3: Open the Firewall (10 minutes)

Your server is now running, but Oracle blocks all incoming traffic by default. We need to open port 5001 (where our web app will run).

### Step 3.1: Navigate to Your VCN

VCN = Virtual Cloud Network (Oracle's name for the network your server is on)

1. From your instance details page, scroll down to **"Primary VNIC"** section
2. You'll see a line that says **"Subnet:"** followed by a link (like "subnet-20260126-1234")
3. Click that subnet link

You're now on the Subnet Details page.

### Step 3.2: Find Security Lists

1. On the left side of the subnet page, look for **"Security Lists"**
2. Click **"Security Lists"**
3. You'll see a list (probably just one item called "Default Security List for vcn-...")
4. Click on that **"Default Security List"** link

You're now on the Security List Details page.

### Step 3.3: Add Ingress Rule

**Ingress = Traffic coming INTO your server**

1. Look for a section called **"Ingress Rules"**
2. You'll see a button: **"Add Ingress Rules"**
3. Click **"Add Ingress Rules"**

A popup appears titled "Add Ingress Rules".

Fill in these fields:

**Source Type:**
- Leave as **"CIDR"** (should be default)

**Source CIDR:**
- Type: `0.0.0.0/0`
- This means "allow from anywhere on the internet"

**IP Protocol:**
- Leave as **"TCP"** (should be default)

**Source Port Range:**
- Leave **blank** (don't type anything)

**Destination Port Range:**
- Type: `5001`
- This is the port our web app runs on

**Description:**
- Type: `Flask web app`
- This is just a note for yourself

Click **"Add Ingress Rules"** button at the bottom.

You should now see your new rule in the list of Ingress Rules!

---

## Part 4: Connect to Your Server (15 minutes)

Now we need to actually connect to the server to set it up. We'll use SSH (Secure Shell).

### Step 4.1: Move Your SSH Key to the Right Place

Remember those SSH key files you downloaded? We need to move them.

**On Mac:**

1. Open **Finder**
2. Go to your **Downloads** folder (or wherever you saved the keys)
3. Find the file `ssh-key-2026-01-26.key` (the date will match when you created it)
4. Press **Command + Shift + G** (this opens "Go to folder")
5. Type: `~/.ssh` and press Enter
   - If it says "folder doesn't exist", open **Terminal** (we'll use it next anyway) and type:
     ```bash
     mkdir -p ~/.ssh
     ```
     Press Enter, then try step 5 again
6. Drag your `ssh-key-2026-01-26.key` file into the `.ssh` folder
7. Rename it to something simple like: `oracle-key.key` (optional, but easier to type)

**On Windows:**

1. Open **File Explorer**
2. Go to your **Downloads** folder
3. Find the file `ssh-key-2026-01-26.key`
4. Create a folder: `C:\Users\YourUsername\.ssh\` (if it doesn't exist)
5. Move the key file there
6. Rename it to: `oracle-key.key` (optional)

### Step 4.2: Open Terminal (Mac) or PowerShell (Windows)

**On Mac:**
1. Press **Command + Space** (opens Spotlight)
2. Type: `terminal`
3. Press **Enter**
4. A black or white window appears - this is Terminal!

**On Windows:**
1. Click Start menu
2. Type: `powershell`
3. Click **"Windows PowerShell"** (the blue icon)
4. A blue window appears - this is PowerShell!

### Step 4.3: Set Correct Permissions on SSH Key (Mac/Linux Only)

**Mac/Linux users only** (Windows users skip to Step 4.4):

SSH keys need special security permissions. Type this command:

```bash
chmod 400 ~/.ssh/oracle-key.key
```

Press **Enter**.

**What this does:** Makes the key file read-only by you, so it's secure.

**You should see:** Nothing! No output = success.

### Step 4.4: Connect to Your Server

Now for the exciting part - connecting to your server!

**Replace these two things in the command below:**
1. `oracle-key.key` - Change if you named your key file differently
2. `YOUR_IP_HERE` - Replace with your actual public IP (the one you copied earlier, like `123.45.67.89`)

**On Mac/Linux:**
```bash
ssh -i ~/.ssh/oracle-key.key ubuntu@YOUR_IP_HERE
```

**On Windows:**
```bash
ssh -i C:\Users\YourUsername\.ssh\oracle-key.key ubuntu@YOUR_IP_HERE
```

**Example (Mac):**
```bash
ssh -i ~/.ssh/oracle-key.key ubuntu@123.45.67.89
```

Press **Enter**.

**What you'll see:**

First time connecting, you'll see a message like:
```
The authenticity of host '123.45.67.89' can't be established.
ED25519 key fingerprint is SHA256:xxxxxxxxxxxxx
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

Type: `yes` and press Enter.

**Then you'll see:**
```
Welcome to Ubuntu 22.04.3 LTS (GNU/Linux 5.15.0-1045-oracle aarch64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/advantage

ubuntu@speaker-database:~$
```

**You're in! 🎉**

That `ubuntu@speaker-database:~$` is called the "prompt". It means you're now typing commands on your server, not your local computer!

---

## Part 5: Open Ubuntu Firewall (5 minutes)

Oracle Cloud has TWO firewalls:
1. ✅ Oracle Cloud Security List (we just did this in Part 3)
2. ⏳ Ubuntu's built-in firewall (we'll do this now)

You're still connected via SSH from Part 4, right? Good!

Type this command:

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5001 -j ACCEPT
```

Press **Enter**.

**What this does:** Opens port 5001 in Ubuntu's firewall so web traffic can reach your app.

**You might see:** A prompt asking for a password. If so, type your Oracle Cloud password and press Enter.

Now save the firewall rules so they persist after reboot:

```bash
sudo netfilter-persistent save
```

Press **Enter**.

**You should see:**
```
run-parts: executing /usr/share/netfilter-persistent/plugins.d/15-ip4tables save
run-parts: executing /usr/share/netfilter-persistent/plugins.d/25-ip6tables save
```

Success!

---

## Part 6: Install Required Software (20 minutes)

Now we need to install everything the speaker database needs to run.

**You're still in your SSH session, right?** Good! Keep that Terminal/PowerShell window open.

### Step 6.1: Update System Packages

First, we update Ubuntu to the latest versions:

```bash
sudo apt-get update
```

Press **Enter**.

**You'll see:** Lots of text scrolling by, lines starting with "Get:" or "Hit:". This is normal!

**Wait for it to finish** (15-30 seconds). You'll see the prompt again: `ubuntu@speaker-database:~$`

Now upgrade everything:

```bash
sudo apt-get upgrade -y
```

Press **Enter**.

**You'll see:** More text scrolling. This might take 2-5 minutes.

**The `-y` flag** means "automatically answer yes to all prompts".

**Wait for it to finish.** You'll see the prompt again.

### Step 6.2: Install Basic Tools

```bash
sudo apt-get install -y python3 python3-pip git wget curl unzip
```

Press **Enter**.

**What this installs:**
- `python3` - The programming language our app uses
- `python3-pip` - Tool to install Python packages
- `git` - Tool to download code from GitHub
- `wget` & `curl` - Tools to download files from the internet
- `unzip` - Tool to extract zip files

**Wait for it to finish** (1-2 minutes).

### Step 6.3: Install Google Chrome

Our scraper uses Selenium with Chrome to browse websites. Let's install Chrome:

```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
```

Press **Enter**.

**You'll see:** A progress bar downloading Chrome.

**Wait for it to finish.** You'll see: `'google-chrome-stable_current_amd64.deb' saved`

Now install it:

```bash
sudo apt-get install -y ./google-chrome-stable_current_amd64.deb
```

Press **Enter**.

**Wait for it to finish** (30 seconds).

Clean up the installer file:

```bash
rm google-chrome-stable_current_amd64.deb
```

Press **Enter**.

Verify Chrome is installed:

```bash
google-chrome --version
```

Press **Enter**.

**You should see:** Something like `Google Chrome 120.0.6099.129`

Success! ✅

### Step 6.4: Install ChromeDriver

ChromeDriver lets Selenium control Chrome. Let's install it:

Get the latest version number:

```bash
CHROMEDRIVER_VERSION=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE)
```

Press **Enter**.

**You won't see any output** - that's normal. It just saved the version number to a variable.

Download ChromeDriver:

```bash
wget https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip
```

Press **Enter**.

**You'll see:** Downloading progress.

Unzip it:

```bash
unzip chromedriver_linux64.zip
```

Press **Enter**.

**You should see:** `inflating: chromedriver`

Move it to the right place:

```bash
sudo mv chromedriver /usr/local/bin/
```

Press **Enter**.

Make it executable:

```bash
sudo chmod +x /usr/local/bin/chromedriver
```

Press **Enter**.

Clean up:

```bash
rm chromedriver_linux64.zip
```

Press **Enter**.

Verify ChromeDriver is installed:

```bash
chromedriver --version
```

Press **Enter**.

**You should see:** Something like `ChromeDriver 120.0.6099.129`

Success! ✅

---

## Part 7: Download and Set Up Your Application (10 minutes)

### Step 7.1: Clone Your Repository from GitHub

Make sure you're in your home directory:

```bash
cd ~
```

Press **Enter**.

**What this does:** `cd` means "change directory". `~` is a shortcut for your home directory.

Now download your code from GitHub:

```bash
git clone https://github.com/nicoluchsinger-sys/asia_society_speaker_database.git
```

Press **Enter**.

**You'll see:** Text like "Cloning into 'asia_society_speaker_database'..." and a progress bar.

**Wait for it to finish.** You'll see: "Resolving deltas: 100%, done."

Go into the directory:

```bash
cd asia_society_speaker_database
```

Press **Enter**.

### Step 7.2: Create Environment File with Your API Keys

Now we need to add your API keys. This is where you'll put your Anthropic and OpenAI keys.

Open the nano text editor (a simple text editor that works in Terminal):

```bash
nano .env
```

Press **Enter**.

**You'll see:** A blank screen with a menu at the bottom showing keyboard shortcuts.

Type the following **exactly** (replace with your actual keys):

```
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
OPENAI_API_KEY=sk-your-actual-key-here
```

**Where to find your API keys:**

**Anthropic Key:**
1. Go to https://console.anthropic.com/
2. Login
3. Click "API Keys" in the left menu
4. Copy your key (starts with `sk-ant-`)

**OpenAI Key:**
1. Go to https://platform.openai.com/api-keys
2. Login
3. Click "Create new secret key"
4. Copy your key (starts with `sk-`)

After typing your keys into nano:

**Save the file:**
1. Press **Ctrl + X** (hold Control, press X)
2. You'll see: "Save modified buffer?"
3. Press **Y** (for yes)
4. You'll see: "File Name to Write: .env"
5. Press **Enter**

**You should see:** Back at the normal prompt.

Verify the file was created:

```bash
cat .env
```

Press **Enter**.

**You should see:** Your two API keys printed on screen.

### Step 7.3: Install Python Dependencies

Your application needs various Python libraries. Let's install them:

```bash
pip3 install -r requirements.txt
```

Press **Enter**.

**You'll see:** Lots of text scrolling showing packages being installed.

**This takes 3-5 minutes.** Lines like:
```
Collecting anthropic>=0.25.0
  Downloading anthropic-0.25.0-py3-none-any.whl
Installing collected packages: ...
```

**Wait for it to finish.** You'll see: "Successfully installed ..."

### Step 7.4: Make Scripts Executable

Some files need permission to run as scripts:

```bash
chmod +x run_pipeline.sh backup_database.sh health_check.sh
```

Press **Enter**.

**You won't see any output** - that's normal. No output = success!

---

## Part 8: Test Everything (10 minutes)

Let's make sure everything works before setting up the automatic parts!

### Step 8.1: Test Basic Scraping

Let's scrape just 3 events as a test:

```bash
python3 main_selenium.py -e 3 --stats
```

Press **Enter**.

**What you'll see:**
```
==============================================================
ASIA SOCIETY SPEAKER DATABASE BUILDER
==============================================================

🌐 STEP 1: SCRAPING EVENTS FROM WEBSITE (SELENIUM)
======================================================================
Starting Selenium scraper (headless mode)...
Fetching page 1 of past events...
Processing event 1: [Event Title]
```

And more... This will take 2-5 minutes.

**You should eventually see:**
```
📊 SUMMARY
Total speakers extracted: X
New speakers added: X
```

If you see this, **everything is working!** 🎉

If you see errors, let me know what they say.

### Step 8.2: Check Database Was Created

```bash
ls -lh speakers.db
```

Press **Enter**.

**You should see:** A line like `-rw-r--r-- 1 ubuntu ubuntu 256K Jan 26 10:30 speakers.db`

This means your database was created successfully!

### Step 8.3: Quick Database Stats

```bash
python3 -c "from database import SpeakerDatabase; db = SpeakerDatabase(); stats = db.get_statistics(); print(f'Speakers: {stats[\"total_speakers\"]}, Events: {stats[\"total_events\"]}'); db.close()"
```

Press **Enter**.

**You should see:** Something like `Speakers: 3, Events: 3`

Perfect! ✅

---

## Part 9: Start the Web Application (10 minutes)

Now let's start the web interface so you can access it from your browser!

### Step 9.1: Quick Test (Foreground)

First, let's test it works:

```bash
cd ~/asia_society_speaker_database/web_app
python3 app.py
```

Press **Enter**.

**You'll see:**
```
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5001
 * Running on http://10.0.0.x:5001
```

**Leave this running!**

### Step 9.2: Test in Your Browser

On your **local computer** (not the server), open a web browser and go to:

```
http://YOUR_IP_HERE:5001
```

Replace `YOUR_IP_HERE` with your actual server IP (like `123.45.67.89`)

**Example:** `http://123.45.67.89:5001`

**You should see:** Your speaker database web interface! 🎉

Try searching for something!

### Step 9.3: Stop the Test

Go back to your Terminal/PowerShell window where Flask is running.

Press **Ctrl + C** (hold Control, press C)

**You'll see:** The Flask app stops and you're back at the prompt.

### Step 9.4: Set Up as a Service (Runs Forever)

Now we'll make it run permanently in the background.

Create a service file:

```bash
sudo nano /etc/systemd/system/speaker-web.service
```

Press **Enter**.

**You'll see:** Nano text editor opens (empty file).

**Copy and paste this entire block** (or type it carefully):

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

**Save the file:**
1. Press **Ctrl + X**
2. Press **Y**
3. Press **Enter**

Now enable and start the service:

```bash
sudo systemctl daemon-reload
```

Press **Enter**.

```bash
sudo systemctl enable speaker-web
```

Press **Enter**.

**You'll see:** `Created symlink ...`

```bash
sudo systemctl start speaker-web
```

Press **Enter**.

Check if it's running:

```bash
sudo systemctl status speaker-web
```

Press **Enter**.

**You should see:**
```
● speaker-web.service - Speaker Database Web App
     Loaded: loaded
     Active: active (running) since ...
```

Look for the green text **"active (running)"** ✅

Press **Q** to exit the status view.

### Step 9.5: Test Again in Browser

Go to your browser again and visit:

```
http://YOUR_IP_HERE:5001
```

**It should still work!** And now it's running permanently in the background.

---

## Part 10: Set Up Automatic Daily Updates (5 minutes)

Let's make the scraper run automatically every day at 2 AM to fetch new events and speakers.

### Step 10.1: Edit Crontab

Crontab = Cron Table = Schedule of automatic tasks

```bash
crontab -e
```

Press **Enter**.

**You'll see:** A prompt asking "Select an editor"

```
Select an editor.  To change later, run 'select-editor'.
  1. /bin/nano        <---- easiest
  2. /usr/bin/vim.basic
  3. /usr/bin/vim.tiny
  4. /bin/ed

Choose 1-4 [1]:
```

Type **1** and press **Enter** (for nano, the easiest editor).

**You'll see:** Nano opens with some commented lines (lines starting with #).

Press the **Down Arrow** key until you're at the bottom (below all the # comment lines).

Add this line (type it exactly):

```
0 2 * * * cd /home/ubuntu/asia_society_speaker_database && ./run_pipeline.sh >> /var/log/speaker_pipeline.log 2>&1
```

**What this means:**
- `0 2 * * *` = Run at 2:00 AM every day
- `cd /home/ubuntu/asia_society_speaker_database` = Go to your app directory
- `&&` = Then...
- `./run_pipeline.sh` = Run the pipeline script
- `>> /var/log/speaker_pipeline.log 2>&1` = Save output to log file

**Save the file:**
1. Press **Ctrl + X**
2. Press **Y**
3. Press **Enter**

**You should see:** `crontab: installing new crontab`

Verify it was added:

```bash
crontab -l
```

Press **Enter**.

**You should see:** Your cron job line printed out.

Success! ✅

### Step 10.2: Test the Pipeline Manually (Optional)

Want to see it run now instead of waiting until 2 AM? Run it manually:

```bash
cd ~/asia_society_speaker_database
./run_pipeline.sh
```

Press **Enter**.

**This will take 15-30 minutes** depending on how many speakers it finds. You'll see:
```
==========================================
Speaker Pipeline - Fri Jan 26 10:30:00 UTC 2026
==========================================

1. Scraping 20 new events...
```

It will:
1. Scrape 20 events
2. Extract speakers
3. Enrich them with tags/demographics
4. Generate embeddings
5. Show statistics

**You can press Ctrl+C to cancel if you want**, or let it finish.

---

## Part 11: You're Done! 🎉

### What You Have Now

✅ A powerful server (4 cores, 24GB RAM) running 24/7 for **FREE**
✅ Your speaker database web interface accessible at `http://YOUR_IP:5001`
✅ Automatic daily scraping at 2 AM (adds ~20 events + speakers per day)
✅ Automatic enrichment (tags, demographics, locations, languages)
✅ Natural language search powered by AI

### Key Information to Save

**📝 Write these down somewhere safe:**

1. **Your Public IP:** `YOUR_IP_HERE`
2. **Your SSH Key Location:** `~/.ssh/oracle-key.key`
3. **Web Interface URL:** `http://YOUR_IP_HERE:5001`
4. **SSH Command:** `ssh -i ~/.ssh/oracle-key.key ubuntu@YOUR_IP_HERE`

### Useful Commands

**To SSH into your server:**
```bash
ssh -i ~/.ssh/oracle-key.key ubuntu@YOUR_IP_HERE
```

**Check if web app is running:**
```bash
sudo systemctl status speaker-web
```

**View web app logs:**
```bash
sudo journalctl -u speaker-web -f
```
(Press Ctrl+C to stop viewing logs)

**View pipeline logs:**
```bash
tail -f /var/log/speaker_pipeline.log
```
(Press Ctrl+C to stop viewing logs)

**Check database statistics:**
```bash
cd ~/asia_society_speaker_database
python3 -c "from database import SpeakerDatabase; db = SpeakerDatabase(); stats = db.get_statistics(); print(stats); db.close()"
```

**Run pipeline manually:**
```bash
cd ~/asia_society_speaker_database
./run_pipeline.sh
```

**Restart web app:**
```bash
sudo systemctl restart speaker-web
```

---

## Important Reminders

### ⚠️ Keep Your Instance Active

Oracle deactivates unused Always Free instances after **90 days of zero activity**.

**To prevent this:**
- Visit your web interface (`http://YOUR_IP:5001`) at least once every 2-3 months
- Or SSH in occasionally
- Set a calendar reminder!

**"Activity" means:** HTTP requests, SSH connections, or API calls

### Timeline to 1000 Speakers

Current rate: ~20 events per day = ~10-15 speakers per day

To reach 1000 speakers from ~443:
- **Need:** ~557 more speakers (~260 more events)
- **At 20 events/day:** ~13 days
- **At 50 events/day:** ~5 days

**To speed up (optional):**

Edit crontab to run 3 times per day:

```bash
crontab -e
```

Change the line to:
```
0 2,10,18 * * * cd /home/ubuntu/asia_society_speaker_database && ./run_pipeline.sh >> /var/log/speaker_pipeline.log 2>&1
```

This runs at 2 AM, 10 AM, and 6 PM = 60 events/day = reach 1000 in ~4-5 days

---

## What's Next?

1. **Share your web interface** with your users:
   - Give them the URL: `http://YOUR_IP:5001`
   - They can search for speakers immediately!

2. **Monitor growth:**
   - Check database stats weekly
   - View logs to ensure scraping is working

3. **Optional improvements:**
   - Add a domain name (costs $12/year)
   - Add SSL/HTTPS for security
   - Customize the frontend

4. **After reaching 1000 speakers:**
   - Consider upgrading to a $4.50/month VPS for guaranteed reliability
   - Or stay on Oracle Free (it's plenty powerful!)

---

## Getting Help

If something doesn't work:

1. **Check the detailed guide:** `ORACLE_CLOUD_SETUP.md`
2. **Check logs:**
   ```bash
   sudo journalctl -u speaker-web -f
   tail -f /var/log/speaker_pipeline.log
   ```
3. **Look for error messages** - they usually tell you what's wrong

Common issues:
- **Can't access web app:** Check firewalls (Oracle Security List + Ubuntu iptables)
- **Selenium fails:** Check Chrome and ChromeDriver installation
- **Database errors:** Check .env file has correct API keys
- **Out of disk space:** Run backups cleanup script

---

## Congratulations! 🎉

You've successfully deployed a production application to the cloud!

This is a real achievement - you now have:
- A cloud server running 24/7
- An AI-powered web application
- Automated data collection
- Professional-grade deployment

**Your speaker database is live at:** `http://YOUR_IP:5001`

Enjoy! 🚀
