#!/usr/bin/env python3
"""
Markdown Report Generator
Generates executive summary report in markdown format

Usage:
    python3 generate_markdown_report.py path/to/raw_data.json path/to/analysis.json
"""

import sys
import json
from pathlib import Path
from datetime import datetime


class MarkdownReportGenerator:
    def __init__(self, raw_data, analysis):
        """Initialize generator with data"""
        self.channel = raw_data['channel']
        self.videos = raw_data['videos']
        self.metadata = raw_data.get('metadata', {})
        self.analysis = analysis

    def generate_header(self):
        """Generate report header"""
        date_str = datetime.now().strftime('%B %d, %Y')

        return f"""# YouTube Channel Audit Report
**Channel:** {self.channel['title']}
**Date:** {date_str}
**Videos Analyzed:** {len(self.videos)}

---

"""

    def generate_executive_summary(self):
        """Generate executive summary section"""
        health_score = self.analysis.get("channelHealthScore", 0)
        shorts_health_score = self.analysis.get("shortsHealthScore")
        summary = self.analysis.get("summary", {})

        # Determine health rating
        if health_score >= 80:
            rating = "Excellent 🟢"
        elif health_score >= 60:
            rating = "Good 🟡"
        else:
            rating = "Needs Improvement 🔴"

        text = f"""## Executive Summary

### Channel Health Score: {health_score}/100 ({rating})

**Quick Stats:**
- Total Subscribers: {self.channel['subscriberCount']:,}
- Total Videos: {self.channel['videoCount']:,}
- Total Views: {self.channel['viewCount']:,}
- Videos Analyzed: {len(self.videos)}
- Shorts Videos: {summary.get('shortsVideos', 0)}
- Long-form Videos: {summary.get('longFormVideos', 0)}

**Audit Findings:**
- ✅ {summary.get('lowPriority', 0)} Low Priority Items
- ⚠️  {summary.get('mediumPriority', 0)} Medium Priority Items
- 🚨 {summary.get('highPriority', 0)} High Priority Items
- 🎬 Shorts Health Score: {f"{shorts_health_score}/100" if shorts_health_score is not None else "N/A"}
- ⏱️ Timestamp Coverage: {summary.get('timestampCoveragePercent', 0)}%

---

"""
        return text

    def generate_top_recommendations(self):
        """Generate top 5 recommendations"""
        top_recs = self.analysis.get("allRecommendations", [])[:5]

        text = "## Top 5 Recommendations\n\n"

        for i, rec in enumerate(top_recs, 1):
            icon = "🚨" if rec.get("priority") == "High" else "⚠️" if rec.get("priority") == "Medium" else "✅"

            text += f"""### {i}. {icon} [{rec.get('priority', 'Low')}] {rec.get('category', 'General')}: {rec.get('issue', 'N/A')}

**Recommendation:**
{rec.get('recommendation', 'N/A')}

**Expected Impact:**
{rec.get('impact', 'N/A')}

---

"""

        return text

    def generate_detailed_analysis(self):
        """Generate detailed analysis by module"""
        text = "## Detailed Analysis\n\n"

        # Titles & Descriptions
        modules = self.analysis.get("analysisModules", {})
        titles = modules.get("titlesAndDescriptions", {})
        text += f"""### 📝 Titles & Descriptions

**Key Metrics:**
- Average title length: {titles.get('titleLengthAverage', 0)} characters
- High performers avg: {titles.get('titleLengthHighPerformers', 0)} characters
- Average description length: {titles.get('descriptionLengthAverage', 0)} characters
- Videos with timestamps: {titles.get('videosWithTimestamps', 0)}/{len(self.videos)}

**Common Keywords in Top Performers:**
"""

        for keyword, count in titles.get("commonKeywords", [])[:8]:
            text += f"- `{keyword}` ({count} occurrences)\n"

        text += "\n---\n\n"

        # Tags & Metadata
        tags = modules.get("tagsAndMetadata", {})
        text += f"""### 🏷️  Tags & Metadata

**Key Metrics:**
- Average tags per video: {tags.get('averageTagCount', 0)}
- Videos without tags: {tags.get('videosWithoutTags', 0)}/{len(self.videos)}
- Category consistency: {tags.get('categoryConsistency', 0)}%
- Most common category: {tags.get('mostCommonCategory', 'N/A')}

**Most Common Tags:**
"""

        for tag, count in tags.get("commonTags", [])[:10]:
            percentage = (count / len(self.videos)) * 100
            text += f"- `{tag}` ({count} videos, {percentage:.1f}%)\n"

        if tags.get('brandTags'):
            text += "\n**Brand Tags Identified:**\n"
            for tag, count in tags['brandTags']:
                text += f"- `{tag}` (used in {count} videos)\n"

        text += "\n---\n\n"

        # Engagement
        engagement = modules.get("engagement", {})
        text += f"""### 📈 Engagement Metrics

**Key Metrics:**
- Average engagement rate: {engagement.get('averageEngagementRate', 0)}%
- Likes per 1000 views: {engagement.get('likesPerThousandViews', 0)}
- Comments per 1000 views: {engagement.get('commentsPerThousandViews', 0)}

**Industry Benchmarks:**
- Good engagement rate: 4-6%
- Excellent engagement rate: >6%

**Performance Distribution:**
- High engagement outliers: {engagement.get('outliers', {}).get('high', 0)} videos
- Low engagement outliers: {engagement.get('outliers', {}).get('low', 0)} videos

---

"""

        # Upload Schedule
        schedule = modules.get("uploadSchedule", {})

        if 'error' not in schedule:
            text += f"""### 📅 Upload Schedule & Consistency

**Key Metrics:**
- Average gap between uploads: {schedule.get('averageGapDays', 0)} days
- Consistency score: {schedule.get('consistencyScore', 0)}/10
- Uploads per week: {schedule.get('uploadsPerWeek', 0)}
- Days since last upload: {schedule.get('daysSinceLastUpload', 'N/A')}

**Best Performing Days:**
"""

            for day, avg_views in schedule.get("bestPerformingDays", []):
                upload_count = schedule.get("uploadDistribution", {}).get(day, {}).get('count', 0)
                text += f"- {day}: {int(avg_views):,} avg views ({upload_count} uploads)\n"

            text += "\n---\n\n"

        timestamp = self.analysis.get("timestampAudit", {})
        missing_videos = timestamp.get("missingVideos", [])
        text += f"""### ⏱️ Timestamp Coverage Audit

**Key Metrics:**
- Eligible long-form videos (>2 min): {timestamp.get('eligibleCount', 0)}
- Videos with timestamps: {timestamp.get('withTimestampsCount', 0)}
- Videos missing timestamps: {timestamp.get('missingCount', 0)}
- Coverage: {timestamp.get('coveragePercent', 0)}%

"""
        if not missing_videos:
            if timestamp.get("eligibleCount", 0) == 0:
                text += "No eligible videos over 2 minutes were found for timestamp auditing.\n\n"
            else:
                text += "All eligible videos currently include timestamps.\n\n"
        else:
            text += "**Top Videos Missing Timestamps (by views):**\n\n"
            text += "| Priority | Title | Views | Duration (min) | URL |\n"
            text += "|----------|-------|-------|----------------|-----|\n"
            for item in missing_videos[:10]:
                url = item.get("video_url", "")
                title = item.get("title", "").replace("|", " ")
                text += (
                    f"| {item.get('priority', 'Medium')} | {title[:70]} | "
                    f"{int(item.get('views', 0)):,} | {item.get('duration_minutes', 0)} | "
                    f"[Link]({url}) |\n"
                )
            text += "\n"

        text += "\n---\n\n"

        shorts = modules.get("shorts2026", {})
        shorts_score = self.analysis.get("shortsHealthScore")
        text += f"""### 🎬 Shorts Audit (2026)

**Key Metrics:**
- Shorts health score: {f"{shorts_score}/100" if shorts_score is not None else "N/A"}
- Shorts count: {shorts.get('shortsCount', 0)}
- Shorts % of channel: {shorts.get('shortsPercentOfChannel', 0)}%
- Avg views: {shorts.get('avgViews', 0)}
- Median views: {shorts.get('medianViews', 0)}
- Avg engagement: {shorts.get('avgEngagementRate', 0)}%
- Comments per 1K views: {shorts.get('commentsPer1k', 0)}
- Last 30 days Shorts: {shorts.get('postedLast30Days', 0)}
- Days since last Short: {shorts.get('daysSinceLastShort', 'N/A')}
- Metadata coverage: {shorts.get('metadataCoverage', 0)}%

"""

        shorts_recs = self.analysis.get("shortsRecommendations", shorts.get("recommendations", []))
        if not shorts_recs:
            if shorts.get("shortsCount", 0) == 0:
                text += "No Shorts identified by configured detection rule.\n\n"
            else:
                text += "No Shorts-specific issues were triggered by configured checks.\n\n"
        else:
            text += "**Top Shorts Recommendations:**\n"
            for idx, rec in enumerate(shorts_recs[:5], 1):
                text += f"{idx}. **[{rec.get('priority', 'Low')}]** {rec.get('recommendation', 'N/A')}\n"
            text += "\n"

        shorts_video_audits = shorts.get("videoAudits", [])
        text += "**Shorts Video Optimization Opportunities:**\n\n"
        if not shorts_video_audits:
            text += "No Shorts video-level opportunities available.\n\n"
        else:
            text += "| Video URL | Title | Views | Engagement % | Opportunity Count | Optimization Opportunities |\n"
            text += "|-----------|-------|-------|--------------|-------------------|----------------------------|\n"
            for item in shorts_video_audits:
                title = item.get("title", "").replace("|", " ")
                url = item.get("video_url", "")
                opportunities = item.get("optimizationSummary", "").replace("|", ";")
                text += (
                    f"| [Link]({url}) | {title[:65]} | {int(item.get('views', 0)):,} | "
                    f"{item.get('engagementRate', 0)}% | {item.get('opportunityCount', 0)} | "
                    f"{opportunities} |\n"
                )
            text += "\n"

        text += "\n---\n\n"

        return text

    def generate_top_performers(self):
        """Generate top and bottom performers analysis"""
        engagement = self.analysis.get("analysisModules", {}).get("engagement", {})

        text = "## Performance Insights\n\n"

        text += "### 🌟 Top 5 Most Engaging Videos\n\n"
        text += "| Title | Engagement Rate | Views |\n"
        text += "|-------|----------------|-------|\n"

        for video in engagement.get("topPerformers", []):
            title = video.get("title", "")
            title = title[:60] + "..." if len(title) > 60 else title
            text += f"| {title} | {video.get('engagementRate', 0)}% | {int(video.get('views', 0)):,} |\n"

        text += "\n### 📉 Bottom 5 Least Engaging Videos\n\n"
        text += "| Title | Engagement Rate | Views |\n"
        text += "|-------|----------------|-------|\n"

        for video in engagement.get("bottomPerformers", []):
            title = video.get("title", "")
            title = title[:60] + "..." if len(title) > 60 else title
            text += f"| {title} | {video.get('engagementRate', 0)}% | {int(video.get('views', 0)):,} |\n"

        text += "\n---\n\n"

        return text

    def generate_action_items(self):
        """Generate prioritized action items"""
        text = "## Action Items (Prioritized)\n\n"

        combined = list(self.analysis.get("allRecommendations", []))
        combined.extend(self.analysis.get("shortsRecommendations", []))

        high_priority = [r for r in combined if r.get("priority") == "High"]
        medium_priority = [r for r in combined if r.get("priority") == "Medium"]
        low_priority = [r for r in combined if r.get("priority") == "Low"]

        def _category_label(rec):
            category = rec.get("category", "General")
            if category.lower() == "shorts":
                return "Shorts"
            return category

        if high_priority:
            text += "### 🚨 High Priority (Action Required)\n\n"
            for i, rec in enumerate(high_priority, 1):
                text += f"{i}. **[{_category_label(rec)}]** {rec.get('recommendation', 'N/A')}\n"
            text += "\n"

        if medium_priority:
            text += "### ⚠️  Medium Priority (Recommended)\n\n"
            for i, rec in enumerate(medium_priority, 1):
                text += f"{i}. **[{_category_label(rec)}]** {rec.get('recommendation', 'N/A')}\n"
            text += "\n"

        if low_priority:
            text += "### ✅ Low Priority (Nice to Have)\n\n"
            for i, rec in enumerate(low_priority, 1):
                text += f"{i}. **[{_category_label(rec)}]** {rec.get('recommendation', 'N/A')}\n"
            text += "\n"

        text += "---\n\n"

        return text

    def generate_methodology(self):
        """Generate methodology appendix"""
        text = """## Methodology

This audit was conducted using the following analysis modules:

1. **Title & Description Optimization**
   - Analyzed title length patterns (optimal: 60-70 characters)
   - Identified keyword patterns in high-performing videos
   - Evaluated description quality and structure
   - Checked for SEO best practices

2. **Tags & Metadata Effectiveness**
   - Assessed tag quantity and quality (optimal: 8-12 tags)
   - Analyzed tag consistency across channel
   - Identified brand tags and category usage
   - Evaluated metadata completeness

3. **Engagement Metrics Analysis**
   - Calculated engagement rate: (likes + comments) / views × 100
   - Compared against industry benchmarks
   - Identified top and bottom performers
   - Detected patterns in successful content

4. **Upload Schedule & Consistency**
   - Analyzed upload frequency and consistency
   - Identified best-performing days and times
   - Calculated consistency score (1-10)
   - Flagged scheduling issues

5. **Timestamp Coverage Audit**
   - Audited long-form videos only (non-Shorts, duration > 2 minutes)
   - Detected chapter patterns using `mm:ss` and `hh:mm:ss`
   - Prioritized missing timestamp findings by views

6. **Shorts Audit (2026)**
   - Classified Shorts using hybrid rule:
     `<=60s`, or `61-180s` with `#shorts` in title/description
   - Evaluated Shorts metadata quality, freshness, and engagement depth
   - Produced separate Shorts health score and recommendations

**Data Source:** YouTube Data API v3
**Benchmark Policy:** Official YouTube guidance first; conservative heuristics used where official numeric thresholds are unavailable.
**Analysis Date:** """ + datetime.now().strftime('%B %d, %Y') + """

---

"""

        return text

    def generate_footer(self):
        """Generate report footer"""
        return f"""## Next Steps

1. **Review this report** with your team or stakeholders
2. **Prioritize action items** based on impact and effort
3. **Implement high-priority changes** first
4. **Track progress** on recommendations
5. **Re-audit in 30 days** to measure improvement

---

**Report Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
**Quota Used:** {self.metadata.get('quotaUsed', 'N/A')} YouTube API units

*This report was generated using the WAT Framework YouTube Audit System.*
"""

    def generate(self):
        """Generate complete markdown report"""
        print("📝 Generating markdown report...")

        report = ""
        report += self.generate_header()
        report += self.generate_executive_summary()
        report += self.generate_top_recommendations()
        report += self.generate_detailed_analysis()
        report += self.generate_top_performers()
        report += self.generate_action_items()
        report += self.generate_methodology()
        report += self.generate_footer()

        print("✅ Report generated successfully!")

        return report


def main():
    """Main execution function"""
    if len(sys.argv) != 3:
        print("❌ Error: Missing required files")
        print("\nUsage:")
        print("  python3 generate_markdown_report.py path/to/raw_data.json path/to/analysis.json")
        sys.exit(1)

    raw_data_file = sys.argv[1]
    analysis_file = sys.argv[2]

    try:
        # Load data
        print("📂 Loading data files...")
        with open(raw_data_file, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        with open(analysis_file, 'r', encoding='utf-8') as f:
            analysis = json.load(f)

        # Generate report
        print("\n🚀 Generating Markdown Report")
        print("=" * 50)

        generator = MarkdownReportGenerator(raw_data, analysis)
        report = generator.generate()

        # Save to file
        output_path = Path(raw_data_file).parent / 'report.md'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)

        # Also print to console for immediate review
        print("\n" + "=" * 50)
        print("✅ SUCCESS!")
        print(f"📁 Report saved to: {output_path}")
        print("\n📄 Report Preview:")
        print("=" * 50)
        print(report[:1000] + "\n\n... (truncated for display)\n")

        print(f"\nView full report at: {output_path}")

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
