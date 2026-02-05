# Quick Start with Gemini Embeddings (FREE!)

The search system now uses **Google Gemini embeddings** by default - completely FREE for up to 1500 requests/day!

## Setup (3 steps, 5 minutes)

### Step 1: Get Gemini API Key (2 minutes)

1. Visit https://aistudio.google.com/app/apikey
2. Click "Create API Key"
3. Copy your API key
4. Add to `.env` file:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

### Step 2: Install Dependencies (1 minute)

```bash
pip3 install google-generativeai
# Or install all:
pip3 install -r requirements.txt
```

### Step 3: Generate Embeddings (2-3 minutes)

```bash
python3 generate_embeddings.py
```

Expected output:
```
✓ Using Gemini embeddings (FREE, 1500 requests/day, 768 dimensions)
Generating embeddings for 443 speakers
Batch size: 50
============================================================

Processing batch 1 (1-50/443)...
  ✓ Generated 50 embeddings
  ...

============================================================
Summary
============================================================
Speakers processed: 443/443
Total tokens used: ~50,000
Estimated cost: FREE (Gemini)
Time elapsed: 120s

✓ Embedding generation complete!
```

**That's it!** Now you can search:

```bash
python3 search_speakers.py "climate policy experts"
python3 search_speakers.py "3 speakers on chinese economy"
```

---

## Provider Comparison

| Provider | Cost | Quality | Speed | Setup |
|----------|------|---------|-------|-------|
| **Gemini** ✅ | **FREE** (1500/day) | Excellent | Fast | You have key |
| OpenAI | $0.02/1M tokens (~$0.02 total) | Excellent | Fast | You have key |
| Voyage | $0.06/1M tokens (~$0.05 total) | Excellent | Fast | Need new key |

All three providers have excellent quality for this use case. **Gemini is recommended** since it's free and you already have the API key.

---

## Switching Providers (Optional)

If you want to use OpenAI or Voyage instead:

```bash
# Use OpenAI embeddings
python3 generate_embeddings.py --provider openai

# Use Voyage embeddings
python3 generate_embeddings.py --provider voyage
```

The system will automatically fall back to the next provider if one fails:
- Try Gemini first → If fails, try OpenAI → If fails, try Voyage

---

## Technical Details

### What Changed?

**embedding_engine.py:**
- Now supports 3 providers: Gemini (default), OpenAI, Voyage
- Automatic fallback if preferred provider fails
- Provider-specific optimizations (Gemini uses `retrieval_document` task type)

**generate_embeddings.py:**
- Added `--provider` flag
- Auto-detects provider and shows cost accordingly
- Updated cost calculations

**Requirements:**
- Removed: `voyageai` (optional now)
- Added: `google-generativeai`, `openai`

### Gemini Specifics

**Model:** `text-embedding-004` (latest, 768 dimensions)
**API:** Google AI Studio / Vertex AI
**Rate Limits:** 1500 requests/day (free tier)
**Pricing:** FREE for your use case

**For 443 speakers:**
- Requests needed: ~443 (one per speaker)
- Well within free tier (1500/day)
- Cost: $0.00

### Quality Comparison

All three providers use state-of-the-art transformer models:

**Semantic Understanding:**
- ✅ All understand "chinese economy" ≈ "China trade policy"
- ✅ All excel at retrieval tasks
- ✅ Differences are marginal (<2% on benchmarks)

**For your use case (443 speakers, simple queries):**
- Quality difference is negligible
- Speed is similar
- **Gemini wins on cost** (free!)

---

## Troubleshooting

### "GEMINI_API_KEY not found"

**Solution:**
1. Check if `.env` has the key:
   ```bash
   cat .env | grep GEMINI_API_KEY
   ```
2. If missing, add it:
   ```bash
   echo 'GEMINI_API_KEY=your_key_here' >> .env
   ```
3. Get key from: https://aistudio.google.com/app/apikey

### "google.generativeai not installed"

**Solution:**
```bash
pip3 install google-generativeai
```

### Gemini fails, want to use OpenAI instead

**Solution:**
```bash
# Add OpenAI key to .env if not already there
echo 'OPENAI_API_KEY=your_key_here' >> .env

# Generate with OpenAI
python3 generate_embeddings.py --provider openai
```

### Rate limit exceeded (1500/day)

This shouldn't happen for initial setup (only 443 speakers), but if you're regenerating frequently:

**Solution:**
1. Wait 24 hours for rate limit to reset
2. Or switch to OpenAI (no daily limit, just pay per use):
   ```bash
   python3 generate_embeddings.py --provider openai
   ```

---

## Next Steps

After embeddings are generated:

### 1. Test Search
```bash
python3 search_speakers.py "climate experts"
python3 search_speakers.py "technology policy specialists" --explain
python3 search_speakers.py --list
```

### 2. Optional: Enrich Speakers
Add demographics, location, languages (~$5-10 for all 443):
```bash
python3 enrich_speakers.py --limit 10  # Test first
python3 enrich_speakers.py --all       # Full enrichment
```

### 3. Optional: Track Freshness
Monitor data staleness and schedule refreshes:
```bash
python3 freshness_manager.py --update
python3 freshness_manager.py --report
```

---

## Why Gemini?

**You asked:** "Why Voyage? I already have Gemini and OpenAI keys."

**You're right!** The original plan used Voyage based on benchmarks, but:

1. **Cost:** Gemini is FREE (vs $0.05 with Voyage)
2. **Quality:** All modern embeddings are excellent
3. **Convenience:** You already have the API key
4. **Overkill:** Quality differences don't matter for 443 speakers

**The honest truth:** For your use case, Gemini is perfect. The system now defaults to Gemini with OpenAI as fallback.

---

## Summary

✅ **Default:** Gemini (free, excellent quality)
✅ **Fallback:** OpenAI (cheap, excellent quality)
✅ **Optional:** Voyage (slightly more expensive)
✅ **Flexible:** Easy to switch between providers

**Total setup time:** 5 minutes
**Total cost:** $0.00 (with Gemini)

Now go generate those embeddings and start searching! 🚀
