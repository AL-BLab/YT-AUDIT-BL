#!/usr/bin/env python3
"""
Google Sheets Exporter
Creates professional Google Sheets report from analysis data

Creates 11 tabs:
1. Summary Dashboard
2. Scoring Methodology (explains how everything is scored)
3. Audit Checklist (diagnostic overview like Screaming Frog)
4. Quick Wins (immediate action items)
5. Before/After Examples (optimization examples)
6. Video Performance Data
7. Title & Description Audit
8. Tags & Metadata
9. Engagement Analysis
10. Upload Schedule
11. Action Items (prioritized recommendations)

Usage:
    python3 export_to_sheets.py path/to/raw_data.json path/to/analysis.json
"""

import sys
import json
from pathlib import Path
from datetime import datetime
import time
import gspread
from gspread_formatting import *
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Scopes needed for Google Sheets API
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]


class SheetsExporter:
    def __init__(self, credentials_path, token_path):
        """Initialize Google Sheets client with OAuth"""
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.client = None

    def authenticate(self):
        """Authenticate with Google Sheets API"""
        print("🔐 Authenticating with Google Sheets API...")

        creds = None

        # Load existing token if available
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("   Refreshing expired token...")
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise Exception(
                        f"Credentials file not found: {self.credentials_path}\n"
                        "Please download OAuth credentials from Google Cloud Console."
                    )

                print("   Opening browser for authorization...")
                print("   Please authorize the app in your browser.")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save credentials for future use
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())

        # Initialize gspread client
        self.client = gspread.authorize(creds)
        print("✅ Authentication successful!")

    def create_spreadsheet(self, channel_name):
        """Create new Google Spreadsheet"""
        date_str = datetime.now().strftime('%Y-%m-%d')
        title = f"YouTube Audit - {channel_name} - {date_str}"

        print(f"📄 Creating spreadsheet: {title}")
        spreadsheet = self.client.create(title)

        return spreadsheet

    def batch_format(self, worksheet, format_list):
        """
        Apply multiple formatting operations in a single batch request
        format_list: List of tuples (range, CellFormat)
        """
        if not format_list:
            return

        # Use gspread-formatting's batch_updater for efficient formatting
        from gspread_formatting import batch_updater

        with batch_updater(worksheet.spreadsheet) as batch:
            for range_name, cell_format in format_list:
                batch.format_cell_range(worksheet, range_name, cell_format)

    def create_summary_tab(self, sheet, channel, analysis):
        """Tab 1: Summary Dashboard"""
        print("   Creating Summary tab...")

        # Rename first sheet
        worksheet = sheet.get_worksheet(0)
        worksheet.update_title("Summary")

        # Prepare data
        health_score = analysis['channelHealthScore']
        summary = analysis['summary']

        # Header
        data = [
            ["YOUTUBE CHANNEL AUDIT - EXECUTIVE SUMMARY"],
            [""],
            ["Channel Information"],
            ["Channel Name", channel['title']],
            ["Subscribers", f"{channel['subscriberCount']:,}"],
            ["Total Videos", f"{channel['videoCount']:,}"],
            ["Total Views", f"{channel['viewCount']:,}"],
            [""],
            ["Audit Results"],
            ["Channel Health Score", f"{health_score}/100"],
            ["Videos Analyzed", len(analysis.get('videosAnalyzed', []))],
            ["Total Recommendations", summary['totalRecommendations']],
            ["High Priority Issues", summary['highPriority']],
            ["Medium Priority Issues", summary['mediumPriority']],
            ["Low Priority Issues", summary['lowPriority']],
            [""],
            ["Top 5 Recommendations"],
        ]

        # Add top 5 recommendations
        top_recommendations = analysis['allRecommendations'][:5]
        for i, rec in enumerate(top_recommendations, 1):
            data.append([
                f"{i}. [{rec['priority']}] {rec['category']}",
                rec['recommendation']
            ])

        # Write data
        worksheet.update('A1', data)

        # Apply formatting
        # Title
        fmt_title = CellFormat(
            backgroundColor=Color(0.2, 0.3, 0.5),
            textFormat=TextFormat(bold=True, fontSize=14, foregroundColor=Color(1, 1, 1)),
            horizontalAlignment='CENTER'
        )
        format_cell_range(worksheet, 'A1:B1', fmt_title)
        worksheet.merge_cells('A1:B1')

        # Section headers
        fmt_section = CellFormat(
            backgroundColor=Color(0.9, 0.9, 0.9),
            textFormat=TextFormat(bold=True, fontSize=11),
            borders=Borders(bottom=Border('SOLID'))
        )
        format_cell_range(worksheet, 'A3:B3', fmt_section)
        format_cell_range(worksheet, 'A9:B9', fmt_section)
        format_cell_range(worksheet, 'A17:B17', fmt_section)

        # Health score color coding
        if health_score >= 80:
            score_color = Color(0.7, 0.9, 0.7)  # Green
        elif health_score >= 60:
            score_color = Color(1, 0.9, 0.6)  # Yellow
        else:
            score_color = Color(1, 0.7, 0.7)  # Red

        fmt_score = CellFormat(
            backgroundColor=score_color,
            textFormat=TextFormat(bold=True, fontSize=12)
        )
        format_cell_range(worksheet, 'B10', fmt_score)

        # Column widths
        worksheet.columns_auto_resize(0, 1)

    def create_performance_tab(self, sheet, videos):
        """Tab 2: Video Performance Data"""
        print("   Creating Performance Data tab...")

        worksheet = sheet.add_worksheet("Video Performance", rows=100, cols=10)

        # Headers
        headers = [
            "Video URL",
            "Title",
            "Views",
            "Likes",
            "Comments",
            "Engagement Rate",
            "Published Date",
            "Tags Count",
            "Title Length",
            "Desc Length",
            "Performance Tier"
        ]

        # Sort videos by views
        sorted_videos = sorted(videos, key=lambda x: x['statistics']['viewCount'], reverse=True)

        # Determine performance tiers
        high_threshold = len(sorted_videos) // 3
        medium_threshold = 2 * len(sorted_videos) // 3

        # Prepare data
        data = [headers]
        for i, video in enumerate(sorted_videos):
            # Determine tier
            if i < high_threshold:
                tier = "High"
            elif i < medium_threshold:
                tier = "Medium"
            else:
                tier = "Low"

            # Calculate engagement rate
            stats = video['statistics']
            views = stats['viewCount']
            if views > 0:
                engagement_rate = ((stats['likeCount'] + stats['commentCount']) / views) * 100
            else:
                engagement_rate = 0.0

            # Create video URL
            video_url = f"https://youtube.com/watch?v={video['id']}"

            data.append([
                video_url,
                video['title'][:100],  # Truncate long titles
                video['statistics']['viewCount'],
                video['statistics']['likeCount'],
                video['statistics']['commentCount'],
                f"{engagement_rate:.2f}%",
                video['publishedAt'][:10],  # Date only
                len(video.get('tags', [])),
                len(video['title']),
                len(video['description']),
                tier
            ])

        # Write data
        worksheet.update('A1', data)

        # Format header
        fmt_header = CellFormat(
            backgroundColor=Color(0.2, 0.3, 0.5),
            textFormat=TextFormat(bold=True, foregroundColor=Color(1, 1, 1)),
            horizontalAlignment='CENTER'
        )
        format_cell_range(worksheet, 'A1:K1', fmt_header)

        # Apply conditional formatting to performance tiers
        worksheet.freeze(rows=1)

        # Column widths
        worksheet.columns_auto_resize(0, 10)

    def create_titles_tab(self, sheet, videos, analysis):
        """Tab 3: Title & Description Audit"""
        print("   Creating Title Audit tab...")

        worksheet = sheet.add_worksheet("Title & Description Audit", rows=100, cols=6)

        titles_analysis = analysis['analysisModules']['titlesAndDescriptions']

        # Headers
        data = [
            ["TITLE & DESCRIPTION ANALYSIS"],
            [""],
            ["Key Metrics"],
            ["Average Title Length", f"{titles_analysis['titleLengthAverage']} characters"],
            ["High Performers Avg Title", f"{titles_analysis['titleLengthHighPerformers']} characters"],
            ["Average Description Length", f"{titles_analysis['descriptionLengthAverage']} characters"],
            ["Videos with Timestamps", titles_analysis['videosWithTimestamps']],
            [""],
            ["Common Keywords in Top Performers"],
        ]

        # Add keywords
        for keyword, count in titles_analysis['commonKeywords']:
            data.append([keyword, count])

        data.append([""])
        data.append(["Video-by-Video Analysis"])
        data.append(["Video URL", "Title", "Title Length", "Desc Length", "Has Timestamps", "Views", "Status"])

        # Add video analysis
        for video in videos:
            title_len = len(video['title'])
            desc_len = len(video['description'])
            has_timestamps = "Yes" if any(c in video['description'] for c in ['0:', '1:', '2:', '3:', '4:', '5:', '6:', '7:', '8:', '9:']) else "No"

            # Determine status
            status = "Good"
            if title_len > 70 or title_len < 40:
                status = "Review Title Length"
            if desc_len < 100:
                status = "Expand Description"

            # Create video URL
            video_url = f"https://youtube.com/watch?v={video['id']}"

            data.append([
                video_url,
                video['title'][:80],
                title_len,
                desc_len,
                has_timestamps,
                video['statistics']['viewCount'],
                status
            ])

        # Write data
        worksheet.update('A1', data)

        # Formatting
        fmt_title = CellFormat(
            backgroundColor=Color(0.2, 0.3, 0.5),
            textFormat=TextFormat(bold=True, fontSize=14, foregroundColor=Color(1, 1, 1)),
            horizontalAlignment='CENTER'
        )
        format_cell_range(worksheet, 'A1:G1', fmt_title)
        worksheet.merge_cells('A1:G1')

        # Section headers
        fmt_section = CellFormat(
            backgroundColor=Color(0.9, 0.9, 0.9),
            textFormat=TextFormat(bold=True)
        )
        format_cell_range(worksheet, 'A3:B3', fmt_section)
        format_cell_range(worksheet, 'A9:B9', fmt_section)
        start_row = len(data) - len(videos)
        format_cell_range(worksheet, f'A{start_row}:G{start_row}', fmt_section)

        worksheet.freeze(rows=start_row)
        worksheet.columns_auto_resize(0, 6)

    def create_tags_tab(self, sheet, videos, analysis):
        """Tab 4: Tags & Metadata"""
        print("   Creating Tags tab...")

        worksheet = sheet.add_worksheet("Tags & Metadata", rows=100, cols=5)

        tags_analysis = analysis['analysisModules']['tagsAndMetadata']

        # Headers
        data = [
            ["TAGS & METADATA ANALYSIS"],
            [""],
            ["Key Metrics"],
            ["Average Tags Per Video", tags_analysis['averageTagCount']],
            ["Videos Without Tags", tags_analysis['videosWithoutTags']],
            ["Category Consistency", f"{tags_analysis['categoryConsistency']}%"],
            ["Most Common Category", tags_analysis['mostCommonCategory']],
            [""],
            ["Most Common Tags"],
        ]

        # Add common tags
        for tag, count in tags_analysis['commonTags']:
            data.append([tag, count, f"{(count/len(videos)*100):.1f}%"])

        data.append([""])
        data.append(["Video-by-Video Tag Analysis"])
        data.append(["Video URL", "Title", "Tag Count", "Tags Preview", "Views"])

        # Add video tag analysis
        for video in videos:
            tags = video.get('tags', [])
            tags_preview = ", ".join(tags[:5]) if tags else "(no tags)"
            video_url = f"https://youtube.com/watch?v={video['id']}"

            data.append([
                video_url,
                video['title'][:60],
                len(tags),
                tags_preview[:100],
                video['statistics']['viewCount']
            ])

        # Write data
        worksheet.update('A1', data)

        # Formatting
        fmt_title = CellFormat(
            backgroundColor=Color(0.2, 0.3, 0.5),
            textFormat=TextFormat(bold=True, fontSize=14, foregroundColor=Color(1, 1, 1)),
            horizontalAlignment='CENTER'
        )
        format_cell_range(worksheet, 'A1:F1', fmt_title)
        worksheet.merge_cells('A1:F1')

        worksheet.columns_auto_resize(0, 5)

    def create_engagement_tab(self, sheet, analysis):
        """Tab 5: Engagement Analysis"""
        print("   Creating Engagement tab...")

        worksheet = sheet.add_worksheet("Engagement Analysis", rows=100, cols=5)

        engagement = analysis['analysisModules']['engagement']

        # Headers
        data = [
            ["ENGAGEMENT ANALYSIS"],
            [""],
            ["Key Metrics"],
            ["Average Engagement Rate", f"{engagement['averageEngagementRate']}%"],
            ["Likes per 1000 Views", engagement['likesPerThousandViews']],
            ["Comments per 1000 Views", engagement['commentsPerThousandViews']],
            [""],
            ["Top 5 Most Engaging Videos"],
            ["Title", "Engagement Rate", "Views"]
        ]

        # Top performers
        for video in engagement['topPerformers']:
            data.append([
                video['title'][:70],
                f"{video['engagementRate']}%",
                video['views']
            ])

        data.append([""])
        data.append(["Bottom 5 Least Engaging Videos"])
        data.append(["Title", "Engagement Rate", "Views"])

        # Bottom performers
        for video in engagement['bottomPerformers']:
            data.append([
                video['title'][:70],
                f"{video['engagementRate']}%",
                video['views']
            ])

        # Write data
        worksheet.update('A1', data)

        # Formatting
        fmt_title = CellFormat(
            backgroundColor=Color(0.2, 0.3, 0.5),
            textFormat=TextFormat(bold=True, fontSize=14, foregroundColor=Color(1, 1, 1)),
            horizontalAlignment='CENTER'
        )
        format_cell_range(worksheet, 'A1:E1', fmt_title)
        worksheet.merge_cells('A1:E1')

        worksheet.columns_auto_resize(0, 4)

    def create_schedule_tab(self, sheet, analysis):
        """Tab 6: Upload Schedule"""
        print("   Creating Schedule tab...")

        worksheet = sheet.add_worksheet("Upload Schedule", rows=100, cols=4)

        schedule = analysis['analysisModules']['uploadSchedule']

        # Handle case where schedule analysis failed
        if 'error' in schedule:
            data = [
                ["UPLOAD SCHEDULE ANALYSIS"],
                [""],
                ["Error", schedule['error']]
            ]
            worksheet.update('A1', data)
            return

        # Headers
        data = [
            ["UPLOAD SCHEDULE ANALYSIS"],
            [""],
            ["Key Metrics"],
            ["Average Gap Between Uploads", f"{schedule['averageGapDays']} days"],
            ["Consistency Score", f"{schedule['consistencyScore']}/10"],
            ["Uploads Per Week", schedule['uploadsPerWeek']],
            ["Days Since Last Upload", schedule['daysSinceLastUpload']],
            [""],
            ["Best Performing Days"],
            ["Day of Week", "Avg Views", "Upload Count"]
        ]

        # Best days
        for day, avg_views in schedule['bestPerformingDays']:
            upload_count = schedule['uploadDistribution'].get(day, {}).get('count', 0)
            data.append([
                day,
                f"{int(avg_views):,}",
                upload_count
            ])

        # Write data
        worksheet.update('A1', data)

        # Formatting
        fmt_title = CellFormat(
            backgroundColor=Color(0.2, 0.3, 0.5),
            textFormat=TextFormat(bold=True, fontSize=14, foregroundColor=Color(1, 1, 1)),
            horizontalAlignment='CENTER'
        )
        format_cell_range(worksheet, 'A1:D1', fmt_title)
        worksheet.merge_cells('A1:D1')

        worksheet.columns_auto_resize(0, 3)

    def create_action_items_tab(self, sheet, analysis):
        """Tab 7: Action Items (Prioritized Recommendations)"""
        print("   Creating Action Items tab...")

        worksheet = sheet.add_worksheet("Action Items", rows=100, cols=5)

        # Headers
        data = [
            ["ACTION ITEMS - PRIORITIZED RECOMMENDATIONS"],
            [""],
            ["Priority", "Category", "Issue", "Industry Benchmark", "Why This Matters", "Recommendation", "Expected Impact"]
        ]

        # Add all recommendations
        for rec in analysis['allRecommendations']:
            data.append([
                rec['priority'],
                rec['category'],
                rec['issue'],
                rec.get('benchmark', 'N/A'),
                rec.get('why', ''),
                rec['recommendation'],
                rec['impact']
            ])

        # Write data
        worksheet.update('A1', data)

        # Formatting
        fmt_title = CellFormat(
            backgroundColor=Color(0.2, 0.3, 0.5),
            textFormat=TextFormat(bold=True, fontSize=14, foregroundColor=Color(1, 1, 1)),
            horizontalAlignment='CENTER'
        )
        format_cell_range(worksheet, 'A1:G1', fmt_title)
        worksheet.merge_cells('A1:G1')

        # Header row
        fmt_header = CellFormat(
            backgroundColor=Color(0.9, 0.9, 0.9),
            textFormat=TextFormat(bold=True),
            horizontalAlignment='CENTER',
            wrapStrategy='WRAP'
        )
        format_cell_range(worksheet, 'A3:G3', fmt_header)

        worksheet.freeze(rows=3)
        worksheet.columns_auto_resize(0, 6)

    def create_quick_wins_tab(self, sheet, analysis):
        """Tab 8: Quick Wins - Specific Action Items"""
        print("   Creating Quick Wins tab...")

        worksheet = sheet.add_worksheet("Quick Wins", rows=100, cols=8)

        quick_wins = analysis.get('quickWins', [])

        # Headers
        data = [
            ["QUICK WINS - IMMEDIATE ACTION ITEMS"],
            [""],
            ["Priority", "Action Type", "Video URL", "Video Title", "Current State", "Suggested Fix", "Expected Impact", "Effort"]
        ]

        # Add quick wins
        for qw in quick_wins:
            data.append([
                qw['priority'],
                qw['action'],
                qw['video_url'],
                qw['video_title'][:60],
                qw['current_state'],
                qw['suggested_fix'],
                qw['impact'],
                qw['effort']
            ])

        # Write data
        worksheet.update('A1', data)

        # Formatting
        fmt_title = CellFormat(
            backgroundColor=Color(0.2, 0.5, 0.3),  # Green theme for "wins"
            textFormat=TextFormat(bold=True, fontSize=14, foregroundColor=Color(1, 1, 1)),
            horizontalAlignment='CENTER'
        )
        format_cell_range(worksheet, 'A1:H1', fmt_title)
        worksheet.merge_cells('A1:H1')

        # Header row
        fmt_header = CellFormat(
            backgroundColor=Color(0.9, 0.9, 0.9),
            textFormat=TextFormat(bold=True),
            horizontalAlignment='CENTER',
            wrapStrategy='WRAP'
        )
        format_cell_range(worksheet, 'A3:H3', fmt_header)

        worksheet.freeze(rows=3)
        worksheet.columns_auto_resize(0, 7)

    def create_before_after_tab(self, sheet, analysis):
        """Tab 9: Before/After Optimization Examples"""
        print("   Creating Before/After Examples tab...")

        worksheet = sheet.add_worksheet("Before & After Examples", rows=100, cols=6)

        examples = analysis.get('beforeAfterExamples', [])

        # Headers
        data = [
            ["BEFORE/AFTER OPTIMIZATION EXAMPLES"],
            [""],
            ["Type", "Video URL", "Before", "After", "Why It's Better", "Expected Impact"]
        ]

        # Add examples
        for ex in examples:
            data.append([
                ex['type'],
                ex['video_url'],
                ex['before'][:200],  # Truncate if very long
                ex['after'][:200],
                ex['why_better'],
                ex['impact']
            ])

        # Write data
        worksheet.update('A1', data)

        # Formatting
        fmt_title = CellFormat(
            backgroundColor=Color(0.3, 0.4, 0.6),  # Blue theme
            textFormat=TextFormat(bold=True, fontSize=14, foregroundColor=Color(1, 1, 1)),
            horizontalAlignment='CENTER'
        )
        format_cell_range(worksheet, 'A1:F1', fmt_title)
        worksheet.merge_cells('A1:F1')

        # Header row
        fmt_header = CellFormat(
            backgroundColor=Color(0.9, 0.9, 0.9),
            textFormat=TextFormat(bold=True),
            horizontalAlignment='CENTER',
            wrapStrategy='WRAP'
        )
        format_cell_range(worksheet, 'A3:F3', fmt_header)

        worksheet.freeze(rows=3)
        worksheet.columns_auto_resize(0, 5)

    def create_scoring_rubric_tab(self, sheet, analysis):
        """Tab 11: Scoring Methodology & Rubric"""
        print("   Creating Scoring Rubric tab...")

        worksheet = sheet.add_worksheet("Scoring Methodology", rows=150, cols=6)

        health_score = analysis.get('channelHealthScore', 0)
        summary = analysis.get('summary', {})

        # Build comprehensive rubric data
        data = [
            ["SCORING METHODOLOGY & RUBRIC"],
            [""],
            ["How Your Channel Health Score is Calculated"],
            [""],
            ["Formula", "max(10, 100 - (10 × High Priority Issues) - (5 × Medium Priority Issues))"],
            ["Your Score", f"{health_score}/100"],
            ["High Priority Issues", summary.get('highPriority', 0)],
            ["Medium Priority Issues", summary.get('mediumPriority', 0)],
            ["Low Priority Issues", f"{summary.get('lowPriority', 0)} (informational only)"],
            [""],
            ["Score Interpretation"],
            ["Score Range", "Rating", "What It Means", "Action Required"],
            ["80-100", "Excellent", "Channel is well-optimized with minor improvements needed", "Focus on low-priority optimizations"],
            ["60-79", "Good", "Solid foundation with some areas needing attention", "Address medium-priority issues first"],
            ["40-59", "Needs Work", "Significant optimization opportunities exist", "Prioritize high-priority issues immediately"],
            ["20-39", "Critical", "Major optimization required for discoverability", "Urgent action needed on all fronts"],
            ["10-19", "Severe", "Extensive issues affecting all areas of channel", "Complete channel overhaul required"],
            [""],
            ["═" * 80],
            ["PRIORITY LEVEL DEFINITIONS"],
            ["═" * 80],
            [""],
            ["Priority", "Definition", "Examples", "Impact on Score"],
            ["HIGH", "Critical issues affecting video discoverability", "• Missing tags\n• Too short descriptions (<100 chars)\n• Title length issues (<30 or >100 chars)", "-10 points per issue"],
            ["MEDIUM", "Important optimizations that improve performance", "• Inconsistent upload schedule\n• Low engagement compared to benchmarks\n• Missing timestamps or CTAs", "-5 points per issue"],
            ["LOW", "Nice-to-have improvements", "• Opportunity to add more brand tags\n• Could improve description formatting", "0 points (informational)"],
            [""],
            ["═" * 80],
            ["INDUSTRY BENCHMARKS EXPLAINED"],
            ["═" * 80],
            [""],
            ["Metric", "Benchmark", "Why It Matters", "How We Calculate It"],
            ["Title Length", "60-70 characters", "YouTube displays ~60 chars in search results; longer titles get cut off", "Character count of video title"],
            ["Description Length", "200+ characters", "First 150 chars appear in search; longer = more keywords for SEO", "Character count of description"],
            ["Tags Per Video", "5-15 tags", "Too few = missing keywords; too many = diluted relevance", "Count of tags array"],
            ["Engagement Rate", "4-10%", "Measures viewer interaction quality (likes + comments / views)", "((likes + comments) / views) × 100"],
            ["Likes per 1K Views", "40-100", "Industry average; higher = content resonates with audience", "(likes / views) × 1000"],
            ["Comments per 1K", "5-15", "Higher engagement = better algorithmic promotion", "(comments / views) × 1000"],
            ["Upload Frequency", "1-3 videos/week", "Consistency signals active channel to YouTube algorithm", "Average days between uploads"],
            ["Consistency Score", "7/10 or higher", "Regular schedule builds audience expectations", "Based on upload gap standard deviation"],
            [""],
            ["═" * 80],
            ["ANALYSIS CATEGORIES"],
            ["═" * 80],
            [""],
            ["Category", "What We Analyze", "Key Metrics"],
            ["Titles & Descriptions", "• Title length optimization\n• Keyword usage patterns\n• Description quality & CTAs\n• Timestamp presence", "• Avg title length\n• High-performer title patterns\n• Videos with timestamps\n• Description length distribution"],
            ["Tags & Metadata", "• Tag quantity and quality\n• Tag consistency across channel\n• Brand tag usage\n• Category consistency", "• Avg tags per video\n• Videos without tags\n• Most common tags\n• Category consistency %"],
            ["Engagement Analysis", "• Like/comment rates vs benchmarks\n• Top vs bottom performers\n• Engagement patterns\n• Outlier identification", "• Avg engagement rate\n• Likes per 1K views\n• Comments per 1K views\n• Top 5 vs bottom 5 comparison"],
            ["Upload Schedule", "• Upload frequency & consistency\n• Best performing days/times\n• Gap analysis\n• Seasonal patterns", "• Avg days between uploads\n• Consistency score (1-10)\n• Days since last upload\n• Upload distribution by day"],
            [""],
            ["═" * 80],
            ["HOW TO USE THIS AUDIT"],
            ["═" * 80],
            [""],
            ["Step", "Action", "Why"],
            ["1", "Review Summary tab for your overall health score", "Understand your starting point and priority count"],
            ["2", "Check Audit Checklist tab for diagnostic overview", "See exact counts of issues (like Screaming Frog)"],
            ["3", "Read Action Items tab to see all recommendations", "Prioritized list with expected impact"],
            ["4", "Use Quick Wins tab for immediate improvements", "Low-effort, high-impact changes you can make today"],
            ["5", "Review Before/After Examples for inspiration", "See exactly how to optimize titles, descriptions, etc."],
            ["6", "Dive into specific tabs (Titles, Tags, etc.) for details", "Deep-dive into each category"],
            ["7", "Implement High Priority fixes first", "Maximum impact on discoverability"],
            ["8", "Re-audit in 30 days to measure improvement", "Track progress and adjust strategy"],
            [""],
            ["═" * 80],
            ["DATA SOURCES & METHODOLOGY"],
            ["═" * 80],
            [""],
            ["Data Source", "Details"],
            ["YouTube Data API v3", "Official YouTube API for channel/video statistics"],
            ["Analysis Period", "Top 30 videos by view count"],
            ["Benchmarks", "Industry standards from YouTube Creator Academy, VidIQ, TubeBuddy research"],
            ["Engagement Calculations", "Based on public statistics (views, likes, comments)"],
            ["Pattern Detection", "Statistical analysis of top vs bottom performers"],
            ["Upload Analysis", "Temporal analysis of publish dates over video history"],
            [""],
            ["Questions or Need Help?", "This audit follows YouTube SEO best practices as of 2026"],
        ]

        # Write data
        worksheet.update('A1', data)

        # Formatting - Title
        fmt_title = CellFormat(
            backgroundColor=Color(0.1, 0.4, 0.7),  # Professional blue
            textFormat=TextFormat(bold=True, fontSize=16, foregroundColor=Color(1, 1, 1)),
            horizontalAlignment='CENTER'
        )
        format_cell_range(worksheet, 'A1:F1', fmt_title)
        worksheet.merge_cells('A1:F1')

        # Section headers (finding rows with "═" separators or key section titles)
        fmt_section = CellFormat(
            backgroundColor=Color(0.85, 0.85, 0.85),
            textFormat=TextFormat(bold=True, fontSize=12),
            horizontalAlignment='LEFT'
        )

        # Major section headers
        format_cell_range(worksheet, 'A3:F3', fmt_section)  # "How Your Channel Health Score..."
        worksheet.merge_cells('A3:F3')

        format_cell_range(worksheet, 'A11:F11', fmt_section)  # "Score Interpretation"
        worksheet.merge_cells('A11:F11')

        # Table headers
        fmt_table_header = CellFormat(
            backgroundColor=Color(0.4, 0.4, 0.4),
            textFormat=TextFormat(bold=True, foregroundColor=Color(1, 1, 1)),
            horizontalAlignment='CENTER',
            wrapStrategy='WRAP'
        )

        # Apply to all table header rows
        table_header_rows = [12, 22, 31, 40, 52, 62, 70]  # Rows with column headers
        for row in table_header_rows:
            format_cell_range(worksheet, f'A{row}:F{row}', fmt_table_header)

        # Highlight your score
        if health_score >= 80:
            score_color = Color(0.7, 0.9, 0.7)  # Green
        elif health_score >= 60:
            score_color = Color(1, 0.9, 0.6)  # Yellow
        else:
            score_color = Color(1, 0.7, 0.7)  # Red

        fmt_your_score = CellFormat(
            backgroundColor=score_color,
            textFormat=TextFormat(bold=True, fontSize=11)
        )
        format_cell_range(worksheet, 'B6', fmt_your_score)

        # Freeze header
        worksheet.freeze(rows=1)
        worksheet.columns_auto_resize(0, 5)

    def create_audit_checklist_tab(self, sheet, analysis):
        """Tab 10: Comprehensive Diagnostic Audit Checklist"""
        print("   Creating Audit Checklist tab...")

        worksheet = sheet.add_worksheet("Audit Checklist", rows=150, cols=6)

        checklist = analysis.get('auditChecklist', {})
        summary = checklist.get('summary', {})

        # Build data array
        data = [
            ["YOUTUBE CHANNEL AUDIT - DIAGNOSTIC CHECKLIST"],
            [""],
            ["SUMMARY"],
            ["Total Issues Found:", summary.get('total_issues', 0)],
            ["  - Critical Issues:", summary.get('critical_issues', 0)],
            ["  - Warnings:", summary.get('warnings', 0)],
            ["  - Quick Wins Available:", summary.get('quick_wins', 0)],
            ["Estimated Fix Time:", summary.get('estimated_fix_time', 'N/A')],
            ["Potential Impact:", summary.get('potential_impact', 'N/A')],
            [""],
            ["═" * 80],
            ["CRITICAL ISSUES (Must Fix)"],
            ["═" * 80],
            [""],
            ["Issue Type", "Count", "% of Videos", "Impact", "Severity"]
        ]

        # Add critical issues
        for issue in checklist.get('critical_issues', []):
            data.append([
                issue.get('issue', ''),
                issue.get('count', 0),
                issue.get('percentage', ''),
                issue.get('impact', ''),
                issue.get('severity', '')
            ])

        # Engagement warnings section
        data.append([""])
        data.append(["═" * 80])
        data.append(["ENGAGEMENT WARNINGS"])
        data.append(["═" * 80])
        data.append([""])
        data.append(["Metric", "Your Channel", "Benchmark", "Gap", "Status"])

        for warning in checklist.get('engagement_warnings', []):
            data.append([
                warning.get('issue', ''),
                warning.get('current', ''),
                warning.get('benchmark', ''),
                warning.get('gap', ''),
                warning.get('status', '')
            ])

        # Upload schedule section
        data.append([""])
        data.append(["═" * 80])
        data.append(["UPLOAD SCHEDULE ISSUES"])
        data.append(["═" * 80])
        data.append([""])
        data.append(["Issue Type", "Current", "Benchmark", "Status"])

        for schedule in checklist.get('upload_schedule_issues', []):
            data.append([
                schedule.get('issue', ''),
                schedule.get('current', ''),
                schedule.get('benchmark', ''),
                schedule.get('status', '')
            ])

        # Optimization opportunities section
        data.append([""])
        data.append(["═" * 80])
        data.append(["OPTIMIZATION OPPORTUNITIES"])
        data.append(["═" * 80])
        data.append([""])
        data.append(["Issue Type", "Count", "Quick Fix?", "Expected Impact"])

        for opp in checklist.get('optimization_opportunities', []):
            data.append([
                opp.get('issue', ''),
                opp.get('count', 0),
                opp.get('quick_fix', ''),
                opp.get('impact', '')
            ])

        # Write data
        worksheet.update('A1', data)

        # Formatting
        fmt_title = CellFormat(
            backgroundColor=Color(0.8, 0.2, 0.2),  # Red theme for audit
            textFormat=TextFormat(bold=True, fontSize=16, foregroundColor=Color(1, 1, 1)),
            horizontalAlignment='CENTER'
        )
        format_cell_range(worksheet, 'A1:F1', fmt_title)
        worksheet.merge_cells('A1:F1')

        # Summary section formatting
        fmt_summary_header = CellFormat(
            backgroundColor=Color(0.9, 0.9, 0.9),
            textFormat=TextFormat(bold=True, fontSize=12),
            horizontalAlignment='LEFT'
        )
        format_cell_range(worksheet, 'A3:B3', fmt_summary_header)
        worksheet.merge_cells('A3:B3')

        # Section headers (Critical Issues, Engagement, etc.)
        fmt_section = CellFormat(
            backgroundColor=Color(0.95, 0.95, 0.95),
            textFormat=TextFormat(bold=True, fontSize=11),
            horizontalAlignment='LEFT'
        )

        # Find and format section headers
        current_row = 1
        for i, row in enumerate(data, start=1):
            if row and len(row) > 0:
                cell_value = str(row[0])
                # Check if it's a section header (contains "═" or is all caps with multiple words)
                if '═' in cell_value or (cell_value.isupper() and len(cell_value.split()) > 1 and cell_value not in ['YOUR CHANNEL', 'QUICK FIX?']):
                    if '═' not in cell_value:  # Don't format the separator lines
                        format_cell_range(worksheet, f'A{i}:F{i}', fmt_section)
                        worksheet.merge_cells(f'A{i}:F{i}')

        # Column header formatting
        fmt_col_header = CellFormat(
            backgroundColor=Color(0.7, 0.7, 0.7),
            textFormat=TextFormat(bold=True, foregroundColor=Color(1, 1, 1)),
            horizontalAlignment='CENTER',
            wrapStrategy='WRAP'
        )

        # Apply to column headers (look for rows with "Issue Type", "Metric", etc.)
        for i, row in enumerate(data, start=1):
            if row and len(row) > 0:
                if row[0] in ['Issue Type', 'Metric']:
                    format_cell_range(worksheet, f'A{i}:F{i}', fmt_col_header)

        worksheet.freeze(rows=1)
        worksheet.columns_auto_resize(0, 5)

    def export(self, raw_data, analysis):
        """Main export function"""
        # Authenticate
        self.authenticate()

        # Create spreadsheet
        channel_name = raw_data['channel']['title']
        spreadsheet = self.create_spreadsheet(channel_name)

        print(f"📊 Populating {11} tabs (with rate limiting delays)...")
        print("   ⏱️  This will take ~90 seconds to avoid API quotas...")

        # Add videos with engagement rates to analysis for convenience
        analysis['videosAnalyzed'] = raw_data['videos']

        # Create all tabs with delays to avoid API rate limits
        # Google Sheets API limit: 60 write requests per minute
        # With 350 videos, data-heavy tabs need extra breathing room
        # Using 15-second delays (20s for heavy tabs) to stay well under quota
        delay = 15
        heavy_delay = 25  # Extra delay after data-heavy tabs (Performance, Titles, Tags)

        self.create_summary_tab(spreadsheet, raw_data['channel'], analysis)
        time.sleep(delay)

        self.create_scoring_rubric_tab(spreadsheet, analysis)
        time.sleep(delay)

        self.create_audit_checklist_tab(spreadsheet, analysis)
        time.sleep(delay)

        self.create_quick_wins_tab(spreadsheet, analysis)
        time.sleep(delay)

        self.create_before_after_tab(spreadsheet, analysis)
        time.sleep(delay)

        self.create_performance_tab(spreadsheet, raw_data['videos'])
        time.sleep(heavy_delay)

        self.create_titles_tab(spreadsheet, raw_data['videos'], analysis)
        time.sleep(heavy_delay)

        self.create_tags_tab(spreadsheet, raw_data['videos'], analysis)
        time.sleep(heavy_delay)

        self.create_engagement_tab(spreadsheet, analysis)
        time.sleep(delay)

        self.create_schedule_tab(spreadsheet, analysis)
        time.sleep(delay)

        self.create_action_items_tab(spreadsheet, analysis)

        print("   ✅ All tabs created successfully!")

        # Make shareable
        spreadsheet.share('', perm_type='anyone', role='reader')

        return spreadsheet.url


def main():
    """Main execution function"""
    if len(sys.argv) != 3:
        print("❌ Error: Missing required files")
        print("\nUsage:")
        print("  python3 export_to_sheets.py path/to/raw_data.json path/to/analysis.json")
        sys.exit(1)

    raw_data_file = sys.argv[1]
    analysis_file = sys.argv[2]

    # Get credentials paths from environment
    credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
    token_path = os.getenv('GOOGLE_TOKEN_PATH', 'token.json')

    try:
        # Load data
        print("📂 Loading data files...")
        with open(raw_data_file, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        with open(analysis_file, 'r', encoding='utf-8') as f:
            analysis = json.load(f)

        # Initialize exporter
        exporter = SheetsExporter(credentials_path, token_path)

        # Export
        print("\n🚀 Exporting to Google Sheets...")
        print("=" * 50)

        url = exporter.export(raw_data, analysis)

        print("\n" + "=" * 50)
        print("✅ SUCCESS!")
        print(f"\n📊 Google Sheets URL:")
        print(url)
        print("\n💡 Tip: Share this URL with your client or team!")

    except FileNotFoundError as e:
        print(f"❌ Error: File not found: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
