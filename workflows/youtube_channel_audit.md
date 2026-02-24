# Youtube Audit MASTER OG - Workflow SOP

## Objective

Analyze a YouTube channel's top 30 videos and generate comprehensive optimization recommendations for visibility and engagement.

## Prerequisites

- YouTube Data API v3 configured (see `setup_youtube_api.md`)
- Python dependencies installed
- Channel URL ready for analysis

## Inputs Required

- **YouTube Channel URL** (required)
  - Supported formats:
    - `https://youtube.com/@channelname`
    - `https://youtube.com/channel/UCxxxxxxxx`
    - `https://youtube.com/c/channelname`
    - `https://youtube.com/user/username`

## Expected Outputs

1. **Excel Report** (primary deliverable)
   - Professional multi-tab spreadsheet (`.xlsx`)
   - 11 tabs: Summary, Scoring, Checklist, Quick Wins, Before/After, Performance, Titles, Tags, Engagement, Schedule, Action Items
   - Location: `.tmp/youtube_audits/{channel_id}/audit_report.xlsx`

2. **Markdown Summary** (secondary deliverable)
   - Executive summary in markdown format
   - Location: `.tmp/youtube_audits/{channel_id}/report.md`
   - Version-controllable, portable format

## Tools Used

1. `tools/youtube_fetch_channel_data.py` - Fetch data from YouTube API
2. `tools/youtube_analyze_videos.py` - Analyze videos and generate recommendations
3. `tools/export_to_excel.py` - Export to Excel workbook
4. `tools/generate_markdown_report.py` - Generate markdown summary

---

## Step-by-Step Process

### Step 1: Validate Channel URL

**Agent Action:** Validate the channel URL format

**Validation Checks:**
- URL is properly formatted
- Matches one of the supported patterns
- Protocol is HTTPS

**If Invalid:**
- Provide clear error message
- Show examples of valid URL formats
- Ask user to provide corrected URL

### Step 2: Fetch Channel Data

**Tool:** `youtube_fetch_channel_data.py`

**Command:**
```bash
python3 tools/youtube_fetch_channel_data.py "https://youtube.com/@channelname"
```

**What It Does:**
- Validates and parses channel URL
- Calls YouTube Data API v3 to fetch:
  - Channel metadata (subscribers, total views, etc.)
  - Top 30 videos sorted by view count
  - Video details (title, description, tags, statistics)
- Saves to: `.tmp/youtube_audits/{channel_id}/raw_data.json`

**Success Indicators:**
- Script completes without errors
- `raw_data.json` file created
- Contains channel info + 30 videos (or all available if <30)
- API quota used: ~35-40 units

**Common Errors:**
- `quotaExceeded`: Daily API limit reached → Wait until midnight PT or use different API key
- `channelNotFound`: Invalid channel URL → Verify URL and retry
- `networkError`: Connection issues → Check internet and retry

### Step 3: Analyze Videos

**Tool:** `youtube_analyze_videos.py`

**Command:**
```bash
python3 tools/youtube_analyze_videos.py .tmp/youtube_audits/{channel_id}/raw_data.json
```

**What It Does:**
- Reads `raw_data.json`
- Performs 4 analysis modules:
  1. **Title & Description Optimization**
     - Length analysis
     - Keyword patterns
     - SEO effectiveness
  2. **Tags & Metadata Effectiveness**
     - Tag quantity and quality
     - Consistency analysis
     - Category usage
  3. **Engagement Metrics Analysis**
     - Engagement rate calculation
     - Top vs. bottom performers
     - Pattern identification
  4. **Upload Schedule & Consistency**
     - Frequency analysis
     - Consistency scoring
     - Best performing days
- Generates specific, actionable recommendations
- Saves to: `.tmp/youtube_audits/{channel_id}/analysis.json`

**Success Indicators:**
- Script completes without errors
- `analysis.json` file created
- Contains all 4 analysis modules
- Recommendations are specific and actionable

**Common Errors:**
- `missingDataFile`: raw_data.json not found → Ensure Step 2 completed successfully
- `invalidData`: Malformed JSON → Re-run Step 2
- `analysisError`: Edge case in data → Review error message, may need to handle manually

### Step 4: Export to Excel

**Tool:** `export_to_excel.py`

**Command:**
```bash
python3 tools/export_to_excel.py \
  .tmp/youtube_audits/{channel_id}/raw_data.json \
  .tmp/youtube_audits/{channel_id}/analysis.json
```

**What It Does:**
- Reads both JSON files
- Creates a local Excel workbook with 11 formatted tabs
- Includes:
  1. Summary
  2. Scoring Methodology
  3. Audit Checklist
  4. Quick Wins
  5. Before After
  6. Video Performance
  7. Title Description Audit
  8. Tags Metadata
  9. Engagement Analysis
  10. Upload Schedule
  11. Action Items
- Saves to: `.tmp/youtube_audits/{channel_id}/audit_report.xlsx`

**Success Indicators:**
- Excel file is created successfully
- All 11 tabs are populated with data
- Formatting applied correctly

**Common Errors:**
- `permissionError`: Cannot write file → Check folder permissions and retry
- `fileInUse`: Workbook open in Excel while exporting → close file and retry

### Step 5: Generate Markdown Report

**Tool:** `generate_markdown_report.py`

**Command:**
```bash
python3 tools/generate_markdown_report.py \
  .tmp/youtube_audits/{channel_id}/raw_data.json \
  .tmp/youtube_audits/{channel_id}/analysis.json
```

**What It Does:**
- Reads both JSON files
- Generates executive summary in markdown format
- Includes:
  - Channel health score
  - Key metrics overview
  - Top 5 recommendations
  - Detailed analysis by category
  - Top and bottom performers
  - Prioritized action items
- Saves to: `.tmp/youtube_audits/{channel_id}/report.md`
- Also outputs to console for immediate review

**Success Indicators:**
- Markdown file created
- Report is comprehensive and well-formatted
- Recommendations are prioritized
- Tables render correctly

**Common Errors:**
- `missingData`: Required fields not in JSON → Check analysis.json completeness
- `formatError`: Markdown syntax issue → Review output, may need to escape special characters

### Step 6: Present Results to User

**Agent Action:** Deliver both outputs to user

**Deliverables:**
1. **Excel Workbook Path**
   - Primary deliverable for detailed analysis
   - Location: `.tmp/youtube_audits/{channel_id}/audit_report.xlsx`
   - Can be shared with clients as a file attachment

2. **Markdown Report Path**
   - Secondary deliverable for quick review
   - Location: `.tmp/youtube_audits/{channel_id}/report.md`
   - Can be converted to PDF, committed to git, etc.

**Presentation Format:**
```
✅ Youtube Audit MASTER OG Complete!

📊 Excel Report:
Location: .tmp/youtube_audits/{channel_id}/audit_report.xlsx

📄 Markdown Summary:
Location: .tmp/youtube_audits/{channel_id}/report.md

📈 Key Findings:
- Channel Health Score: X/10
- Top Recommendation: [...]
- Videos Analyzed: 30
- API Quota Used: ~XX units
```

---

## Error Handling Procedures

### Error: API Quota Exceeded

**Symptoms:**
- Error message: `quotaExceeded`
- Occurs during Step 2 (data fetching)

**Solutions:**
1. Check remaining quota in Google Cloud Console
2. Wait until midnight Pacific Time (quota resets daily)
3. Create additional API key in different Google Cloud project
4. Request quota increase (usually approved for legitimate use)

**Prevention:**
- Monitor daily usage
- Plan audits within quota limits (~250 per day)

### Error: Invalid Channel URL

**Symptoms:**
- Error message: `channelNotFound` or `invalidURL`
- Occurs during Step 1-2

**Solutions:**
1. Verify URL format matches supported patterns
2. Check if channel exists and is public
3. Try alternative URL format (e.g., @username vs /channel/)

**Prevention:**
- Validate URL format before starting audit
- Provide examples of valid URLs to user

### Error: Excel Export Failed

**Symptoms:**
- Error message: `permissionError` or `fileInUse`
- Occurs during Step 4

**Solutions:**
1. Verify output directory exists and is writable
2. Close any open workbook with the same filename
3. Re-run Step 4 with a custom output filename

**Prevention:**
- Keep export file closed while pipeline runs
- Avoid read-only directories

### Error: Missing or Corrupted Data Files

**Symptoms:**
- Error message: `missingDataFile` or `invalidData`
- Occurs during Steps 3-5

**Solutions:**
1. Check if previous steps completed successfully
2. Verify JSON files exist in `.tmp/youtube_audits/{channel_id}/`
3. Validate JSON syntax using: `python3 -m json.tool < file.json`
4. Re-run from Step 2 if data is corrupted

**Prevention:**
- Don't manually edit JSON files
- Ensure each step completes before proceeding

### Error: Network Timeout

**Symptoms:**
- Error message: `networkError` or `timeout`
- Can occur during any step involving API calls

**Solutions:**
1. Check internet connectivity
2. Retry the operation (tools have built-in retry logic)
3. Check Google Cloud status: https://status.cloud.google.com/

**Prevention:**
- Ensure stable internet connection
- Avoid running audits during known network issues

---

## Success Criteria

An audit is successful when:

- ✅ All 6 steps complete without errors
- ✅ Excel workbook is generated and opens correctly
- ✅ Markdown report is comprehensive and readable
- ✅ Recommendations are specific and actionable
- ✅ Top performers analysis identifies valid patterns
- ✅ Upload schedule analysis is accurate
- ✅ API quota usage is reasonable (~35-40 units)

---

## Quality Checks

Before delivering results, verify:

**Data Quality:**
- All 30 videos (or max available) are included
- Video statistics are present (views, likes, comments)
- Tags and metadata are captured (if available)
- Publish dates are correct

**Analysis Quality:**
- Recommendations make logical sense for the channel
- Top performers truly have higher engagement
- Keyword patterns are identified correctly
- Upload consistency score matches visual inspection

**Presentation Quality:**
- Excel formatting is professional
- Tabs and headers are readable
- Key metrics are easy to scan
- Markdown tables render properly

**Actionability:**
- Recommendations are specific (not vague)
- Action items are prioritized logically
- Expected impact is reasonable
- Effort estimates make sense

---

## Optimization Tips

### For Faster Audits

1. **Parallel Processing** (Future enhancement)
   - Currently sequential, could parallelize analysis modules

2. **Caching**
   - Save raw_data.json for re-analysis without API calls
   - Useful for testing analysis logic changes

3. **Batch Mode** (Future enhancement)
   - Audit multiple channels in one session
   - Share quota across audits efficiently

### For Better Recommendations

1. **Domain Knowledge**
   - Understand the channel's niche
   - Compare against niche benchmarks
   - Provide context-specific advice

2. **Trend Analysis** (Future enhancement)
   - Track changes over time
   - Identify improving/declining metrics
   - Show progress on recommendations

3. **Competitive Analysis** (Future enhancement)
   - Compare with similar channels
   - Identify gaps and opportunities
   - Benchmark performance

---

## Lessons Learned

(Update this section as you use the system)

**Date: [Date]**
- **Issue:** [What happened]
- **Solution:** [How it was resolved]
- **Prevention:** [How to avoid in future]

---

## Estimated Time

**Per Audit:**
- Setup time (first run only): ~5 minutes (API key + dependencies)
- Execution time: 1-3 minutes
- Review time: 10-15 minutes
- **Total:** ~12-20 minutes

---

## API Quota Usage Summary

**Per Audit:**
- Channel metadata: 1 unit
- Video list: 1 unit
- Video details: 1 unit
- **Total:** ~3-5 units

**Daily Capacity:**
- Free tier: 10,000 units/day
- Audits possible: ~250 per day
- Recommended: <200 per day (buffer for errors/retries)

---

## Next Steps

After completing an audit:

1. Review recommendations with user/client
2. Prioritize action items based on impact and effort
3. Implement high-priority changes
4. Re-audit after 30 days to measure improvement
5. Update "Lessons Learned" section with any issues encountered

---

**Workflow Version:** 1.0
**Last Updated:** February 11, 2026
**Maintained by:** WAT Framework / Agent Team
