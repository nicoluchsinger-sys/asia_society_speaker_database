# Railway Quick Start (5 Minutes)

Get your speaker database online in 5 minutes.

## Step 1: Sign Up & Create Project (2 min)

1. Go to https://railway.app
2. Click "Sign up with GitHub"
3. Click "New Project" → "Deploy from GitHub repo"
4. Select: `asia_society_speaker_database`
5. Name it: `speaker-database`

Railway will automatically start building and deploying!

---

## Step 2: Configure Web Service (2 min)

Once build completes:

1. Click on the deployed service
2. **Generate Public Domain:**
   - Settings tab → "Networking" section
   - Click "Generate Domain"
   - Save the URL (e.g., `speaker-database-production.up.railway.app`)

3. **Add Environment Variables:**
   - Click "Variables" tab
   - Add these:
     ```
     ANTHROPIC_API_KEY=<your_key>
     OPENAI_API_KEY=<your_key>
     PORT=5001
     ```

4. **Set Start Command:**
   - Settings tab → "Deploy" section
   - Start Command: `python3 web_app/app.py`
   - Click "Deploy" to redeploy with new command

---

## Step 3: Create Volume & Upload Database (3 min)

**Create Volume:**
1. Project dashboard → Click "+ New"
2. Select "Volume"
3. Name: `speaker-db-volume`
4. Mount path: `/app`
5. Connect to your `web` service

**Upload Database:**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and link to project
railway login
cd /Users/nicoluchsinger/coding/speaker_database
railway link

# Select your project when prompted

# Upload database
railway shell --service web
# Inside shell:
exit
# Back on local:
railway run --service web bash -c 'cat > /app/speakers.db' < speakers.db
```

---

## Step 4: Test It Works! (1 min)

1. Visit your Railway domain in browser
2. You should see the search interface
3. Search for a speaker (try "Chen" or "Liu")
4. Check stats: Add `/api/stats` to your URL

**If it works, you're done! 🎉**

---

## What You Have Now

✅ Web interface accessible at your Railway domain
✅ 443 speakers searchable
✅ Automatic deployments on git push
✅ SSL/HTTPS included
✅ No server management needed

---

## Next: Add Background Worker for Scaling

Once the web interface works, follow **RAILWAY_DEPLOYMENT.md** Phase 2 to add the scraping service and scale to 1000+ speakers.

---

## Troubleshooting

**"Application failed to respond"**
- Check "Variables" tab has all environment variables
- Check "Deploy" logs for errors
- Verify start command is set correctly

**"Database not found"**
- Verify volume is created and connected
- Check volume mount path is `/app`
- Try uploading database again

**Build fails**
- Check Dockerfile is present in repo
- Verify all Python dependencies in requirements.txt
- Check Railway build logs for specific errors

**Need help?**
- Railway Discord: https://discord.gg/railway
- Railway Docs: https://docs.railway.app
- Check RAILWAY_DEPLOYMENT.md for detailed guide
