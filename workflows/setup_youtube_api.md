# Youtube Audit MASTER OG - API Setup

## Objective

Configure YouTube Data API v3 and Google Sheets API access for the Youtube Audit MASTER OG system.

## Prerequisites

- Google account
- Access to Google Cloud Console
- ~15-20 minutes

---

## Part 1: YouTube Data API v3 Setup

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click the project dropdown at the top (next to "Google Cloud")
3. Click **"NEW PROJECT"**
4. Enter project details:
   - **Project name:** `Youtube Audit MASTER OG` (or your preferred name)
   - **Organization:** Leave as default
5. Click **"CREATE"**
6. Wait for project creation (10-30 seconds)
7. Ensure the new project is selected (check top navigation bar)

### Step 2: Enable YouTube Data API v3

1. In the search bar at the top, type: `YouTube Data API v3`
2. Click on **"YouTube Data API v3"** in the results
3. Click the blue **"ENABLE"** button
4. Wait for enablement (5-10 seconds)

### Step 3: Create API Key

1. In the left sidebar, click **"Credentials"**
2. Click **"CREATE CREDENTIALS"** at the top
3. Select **"API key"**
4. A popup will appear with your API key - **COPY IT IMMEDIATELY**
5. Click **"RESTRICT KEY"** (important for security)

### Step 4: Restrict API Key (Security Best Practice)

1. Under **"API restrictions"**, select **"Restrict key"**
2. In the dropdown, find and check **"YouTube Data API v3"**
3. Optionally, under **"Application restrictions"**, you can:
   - Leave as "None" for testing
   - Set "IP addresses" for production (restrict to your server IPs)
4. Click **"SAVE"**

### Step 5: Add API Key to .env File

1. Open `/Applications/Youtube Audit MASTER OG/.env`
2. Replace `your_youtube_api_key_here` with your actual API key:
   ```env
   YOUTUBE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
   ```
3. Save the file

### Step 6: Understand API Quotas

**Important Quota Information:**

- **Daily Quota:** 10,000 units per day (free tier)
- **Cost per audit:** ~35-40 units
- **Daily capacity:** ~250 audits per day

**What uses quota:**
- Fetching channel info: 1 unit
- Listing videos: 1 unit per 50 videos
- Getting video details: 1 unit per 50 videos

**If you exceed quota:**
- Error: `quotaExceeded`
- Quota resets at midnight Pacific Time
- Solutions:
  1. Wait for quota reset
  2. Create additional project with new API key
  3. Request quota increase (usually approved for legitimate use)

---

## Part 2: Google Sheets API Setup

### Step 1: Enable Google Sheets API

1. In the same Google Cloud project, search for: `Google Sheets API`
2. Click on **"Google Sheets API"**
3. Click **"ENABLE"**

### Step 2: Enable Google Drive API

(Required for creating new spreadsheets)

1. Search for: `Google Drive API`
2. Click on **"Google Drive API"**
3. Click **"ENABLE"**

### Step 3: Configure OAuth Consent Screen

1. In the left sidebar, click **"OAuth consent screen"**
2. Select **"External"** user type
3. Click **"CREATE"**
4. Fill in required fields:
   - **App name:** `Youtube Audit MASTER OG`
   - **User support email:** Your email
   - **Developer contact information:** Your email
5. Click **"SAVE AND CONTINUE"**
6. On **"Scopes"** screen, click **"SAVE AND CONTINUE"** (we'll add scopes automatically)
7. On **"Test users"** screen:
   - Click **"ADD USERS"**
   - Enter your email address
   - Click **"ADD"**
8. Click **"SAVE AND CONTINUE"**
9. Review and click **"BACK TO DASHBOARD"**

### Step 4: Create OAuth 2.0 Credentials

1. Go to **"Credentials"** in the left sidebar
2. Click **"CREATE CREDENTIALS"**
3. Select **"OAuth client ID"**
4. For **"Application type"**, select **"Desktop app"**
5. **Name:** `Youtube Audit MASTER OG Desktop Client`
6. Click **"CREATE"**
7. A popup appears with your client ID and secret

### Step 5: Download Credentials

1. Click the **"DOWNLOAD JSON"** button in the popup
2. The file will download (named something like `client_secret_xxxxx.json`)
3. Rename it to `credentials.json`
4. Move it to `/Applications/Youtube Audit MASTER OG/credentials.json`

**Important:** Never commit this file to version control (it's already in .gitignore)

---

## Part 3: Install Python Dependencies

### Step 1: (Optional) Create Virtual Environment

Recommended to avoid conflicts with other Python projects:

```bash
cd "/Applications/Youtube Audit MASTER OG"
python3 -m venv venv
source venv/bin/activate
```

### Step 2: Install Dependencies

```bash
cd "/Applications/Youtube Audit MASTER OG"
pip3 install -r requirements.txt
```

Expected output: Installation progress for each package

**If errors occur:**
- Ensure Python 3.8+ is installed: `python3 --version`
- Try upgrading pip: `pip3 install --upgrade pip`
- Check for network connectivity

---

## Part 4: Verify Setup

### Test YouTube API Access

Create a quick test script:

```bash
python3 -c "
from googleapiclient.discovery import build
from dotenv import load_dotenv
import os

load_dotenv()
youtube = build('youtube', 'v3', developerKey=os.getenv('YOUTUBE_API_KEY'))
request = youtube.channels().list(part='snippet', id='UC_x5XG1OV2P6uZZ5FSM9Ttw')  # Google Developers channel
response = request.execute()
print('✅ YouTube API is working!')
print(f'Channel: {response[\"items\"][0][\"snippet\"][\"title\"]}')
"
```

**Expected output:**
```
✅ YouTube API is working!
Channel: Google for Developers
```

### Test Google Sheets API (OAuth)

This will be tested during first audit run when you execute `export_to_sheets.py`. The script will:
1. Open a browser window
2. Ask you to authorize the app
3. Save a token for future use

---

## Troubleshooting

### Issue: "API key not valid"

**Solutions:**
- Check that API key is correctly copied to .env
- Ensure YouTube Data API v3 is enabled
- Verify API key restrictions allow YouTube Data API v3

### Issue: "Daily Limit Exceeded"

**Solutions:**
- Wait until midnight Pacific Time (quota resets)
- Create new project with different API key
- Request quota increase from Google Cloud Console

### Issue: "Access Not Configured"

**Solutions:**
- Ensure all 3 APIs are enabled:
  - YouTube Data API v3
  - Google Sheets API
  - Google Drive API

### Issue: OAuth consent screen errors

**Solutions:**
- Ensure you added yourself as a test user
- Check that app is in "Testing" mode (not published)
- Verify OAuth client is "Desktop app" type

---

## Success Criteria

Setup is complete when:

- ✅ YouTube Data API v3 is enabled
- ✅ API key is created and added to .env
- ✅ Google Sheets API and Drive API are enabled
- ✅ OAuth credentials downloaded as credentials.json
- ✅ Python dependencies installed without errors
- ✅ Test script confirms YouTube API access works

---

## Next Steps

After completing this setup:

1. You're ready to use the YouTube audit tools
2. Read `workflows/youtube_channel_audit.md` for the main audit process
3. Run your first audit!

---

## API Cost Summary

**Free tier limits:**
- YouTube API: 10,000 units/day
- Google Sheets API: Very generous (unlikely to hit)
- Google Drive API: Very generous (unlikely to hit)

**Total monthly cost:** $0 for typical usage

---

## Security Best Practices

1. ✅ Never commit `.env` or `credentials.json` to version control
2. ✅ Restrict API key to only YouTube Data API v3
3. ✅ Keep OAuth consent screen in "Testing" mode (unless publishing publicly)
4. ✅ Regularly rotate API keys (every 90 days recommended)
5. ✅ Monitor quota usage in Google Cloud Console

---

**Setup Guide Version:** 1.0
**Last Updated:** February 11, 2026
