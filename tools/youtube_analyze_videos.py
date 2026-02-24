#!/usr/bin/env python3
"""
YouTube Video Analyzer
Analyzes fetched videos and generates optimization recommendations

Performs 5 analysis modules:
1. Title & Description Optimization
2. Tags & Metadata Effectiveness
3. Engagement Metrics Analysis
4. Upload Schedule & Consistency
5. Shorts Audit (2026 best-practice checks)

Usage:
    python3 youtube_analyze_videos.py path/to/raw_data.json
"""

import re
import sys
import json
import math
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

import numpy as np
from dateutil import parser as dateparser


# Industry Benchmarks and Best Practices
BENCHMARKS = {
    'title_length': {
        'optimal_min': 40,
        'optimal_max': 70,
        'why': 'YouTube displays approximately 60-70 characters in search results. Titles should be long enough to include keywords but short enough to avoid truncation.',
        'source': 'YouTube Creator Academy & TubeBuddy 2024 Research'
    },
    'description_length': {
        'minimum': 100,
        'optimal': 300,
        'why': 'The first 150 characters appear in search results. Longer descriptions provide context for viewers and give YouTube\'s algorithm more data to understand your content.',
        'source': 'YouTube SEO Best Practices 2024'
    },
    'tags': {
        'optimal_min': 8,
        'optimal_max': 12,
        'why': 'Tags help YouTube understand your content context. Too few limits discoverability, too many dilutes relevance. Focus on specific, relevant tags.',
        'source': 'YouTube Metadata Optimization Guidelines'
    },
    'engagement_rate': {
        'poor': 2.0,
        'good': 4.0,
        'excellent': 6.0,
        'why': 'Engagement rate (likes + comments / views) signals content quality to YouTube\'s algorithm. Higher engagement improves search rankings and recommendations.',
        'formula': '(Likes + Comments) / Views × 100',
        'source': 'Social Blade & VidIQ Analytics 2024'
    },
    'comments_per_1k': {
        'minimum': 5,
        'good': 10,
        'excellent': 20,
        'why': 'Comments are heavily weighted by YouTube\'s algorithm. Videos that spark conversation get promoted more in search and suggested videos.',
        'source': 'YouTube Algorithm Research 2024'
    },
    'upload_frequency': {
        'minimum': 1,  # per week
        'optimal': 2,  # per week
        'maximum': 5,  # per week (burnout risk)
        'why': 'Consistent uploading trains your audience and signals to YouTube that your channel is active. 1-3 videos per week is optimal for most creators.',
        'source': 'YouTube Creator Insider 2024'
    },
    'consistency_score': {
        'minimum': 5,
        'good': 7,
        'excellent': 9,
        'why': 'Consistent upload schedules help build audience habits and improve retention. Viewers return when they know when to expect new content.',
        'source': 'Creator Academy - Consistency Guidelines'
    }
}

SHORTS_BENCHMARKS_2026 = {
    "metadata_clarity": {
        "benchmark": "At least 60% of Shorts titles should land in 20-70 characters",
        "why": "Concise but descriptive titles improve relevance and taps in Shorts surfaces.",
        "source": "YouTube Creator Academy (Shorts metadata guidance, official)"
    },
    "description_context": {
        "benchmark": "No more than 50% of Shorts should have sparse descriptions (<40 chars) without hashtags",
        "why": "Basic descriptive context and hashtags help categorization and discovery.",
        "source": "YouTube Help Center + Creator Academy Shorts guidance (official)"
    },
    "posting_freshness": {
        "benchmark": "Publish at least one Short every 21 days for active Shorts channels",
        "why": "Fresh publishing cadence supports momentum for Shorts viewers and distribution.",
        "source": "YouTube Creator Insider cadence best-practice guidance (official)"
    },
    "engagement_relative": {
        "benchmark": "Shorts median engagement should be at least 80% of long-form median engagement",
        "why": "Relative performance normalization avoids false positives on niche channels.",
        "source": "Internal conservative heuristic (official-source-aligned)"
    },
    "comments_depth": {
        "benchmark": "Comments per 1K views should be >= 5",
        "why": "Comment activity indicates depth of resonance beyond passive views.",
        "source": "YouTube community interaction guidance + conservative heuristic"
    },
}

TIMESTAMP_PATTERN = re.compile(r"(?<!\d)(?:\d{1,2}:\d{2}(?::\d{2})?)(?!\d)")
SHORTS_TAG_PATTERN = re.compile(r"(^|\s)#shorts\b", re.IGNORECASE)


class YouTubeAnalyzer:
    def __init__(self, data):
        """Initialize analyzer with fetched data"""
        self.channel = data['channel']
        self.videos = data['videos']
        self.metadata = data.get('metadata', {})

        # Calculate engagement rates upfront
        for video in self.videos:
            stats = video['statistics']
            views = stats['viewCount']
            if views > 0:
                engagement = ((stats['likeCount'] + stats['commentCount']) / views) * 100
                video['engagementRate'] = round(engagement, 2)
            else:
                video['engagementRate'] = 0.0

    def is_timestamp_present(self, description):
        """Detect chapter-style timestamps (mm:ss or hh:mm:ss)."""
        return bool(TIMESTAMP_PATTERN.search(description or ""))

    def duration_seconds(self, duration_iso):
        """
        Parse ISO 8601 duration to seconds.
        Example: PT2M30S = 150 seconds
        """
        match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_iso or "")
        if not match:
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds

    def parse_duration_to_seconds(self, duration_str):
        """Backward-compatible alias for legacy calls."""
        return self.duration_seconds(duration_str)

    def is_short_video(self, video):
        """
        Hybrid Shorts rule:
        - duration <= 60s => Shorts
        - duration 61-180s => Shorts only with #shorts in title/description
        - otherwise => not Shorts
        """
        duration = self.duration_seconds(video.get("duration", "PT0S"))
        if duration <= 60:
            return True
        if duration <= 180:
            title = video.get("title", "")
            description = video.get("description", "")
            haystack = f"{title} {description}"
            return bool(SHORTS_TAG_PATTERN.search(haystack))
        return False

    def split_videos_by_format(self):
        shorts_videos = []
        long_form_videos = []
        for video in self.videos:
            if self.is_short_video(video):
                shorts_videos.append(video)
            else:
                long_form_videos.append(video)
        return shorts_videos, long_form_videos

    def _parse_published_datetime(self, raw_value):
        try:
            parsed = dateparser.parse(raw_value)
        except Exception:
            return None
        if parsed is None:
            return None
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed

    def generate_timestamp_audit(self, long_form_videos):
        """
        Build dedicated timestamp findings for long-form videos > 2 minutes.
        """
        eligible_videos = [
            video for video in long_form_videos
            if self.duration_seconds(video.get("duration", "PT0S")) > 120
        ]

        with_timestamps_count = sum(
            1 for video in eligible_videos
            if self.is_timestamp_present(video.get("description", ""))
        )

        missing_videos = [
            video for video in eligible_videos
            if not self.is_timestamp_present(video.get("description", ""))
        ]
        missing_videos.sort(key=lambda item: item["statistics"]["viewCount"], reverse=True)

        high_priority_cutoff = max(1, math.ceil(len(missing_videos) / 4)) if missing_videos else 0
        missing_rows = []
        for idx, video in enumerate(missing_videos):
            seconds = self.duration_seconds(video.get("duration", "PT0S"))
            missing_rows.append({
                "video_id": video.get("id", ""),
                "video_url": f"https://youtube.com/watch?v={video.get('id', '')}",
                "title": video.get("title", ""),
                "duration_seconds": seconds,
                "duration_minutes": round(seconds / 60, 2),
                "publishedAt": video.get("publishedAt", ""),
                "views": int(video.get("statistics", {}).get("viewCount", 0)),
                "description_length": len(video.get("description", "")),
                "priority": "High" if idx < high_priority_cutoff else "Medium",
                "has_timestamps": "No",
            })

        eligible_count = len(eligible_videos)
        missing_count = len(missing_rows)
        coverage = (with_timestamps_count / eligible_count * 100) if eligible_count > 0 else 0.0

        return {
            "eligibleCount": eligible_count,
            "withTimestampsCount": with_timestamps_count,
            "missingCount": missing_count,
            "coveragePercent": round(coverage, 1),
            "missingVideos": missing_rows,
        }

    def analyze_shorts_2026(self, shorts_videos, long_form_videos):
        """
        Shorts-specific audit module aligned to official guidance and conservative heuristics.
        """
        recommendations = []
        shorts_count = len(shorts_videos)
        total_count = len(self.videos)
        shorts_percent = (shorts_count / total_count * 100) if total_count else 0.0

        durations = [self.duration_seconds(video.get("duration", "PT0S")) for video in shorts_videos]
        avg_duration = float(np.mean(durations)) if durations else 0.0

        shorts_views = [video["statistics"]["viewCount"] for video in shorts_videos]
        avg_views = float(np.mean(shorts_views)) if shorts_views else 0.0
        median_views = float(np.median(shorts_views)) if shorts_views else 0.0

        shorts_engagement = [video.get("engagementRate", 0.0) for video in shorts_videos]
        avg_engagement = float(np.mean(shorts_engagement)) if shorts_engagement else 0.0
        median_engagement = float(np.median(shorts_engagement)) if shorts_engagement else 0.0

        total_short_views = sum(video["statistics"]["viewCount"] for video in shorts_videos)
        total_short_comments = sum(video["statistics"]["commentCount"] for video in shorts_videos)
        comments_per_1k = (total_short_comments / total_short_views * 1000) if total_short_views else 0.0

        metadata_optimized = 0
        for video in shorts_videos:
            title_len = len(video.get("title", ""))
            desc = video.get("description", "")
            if 20 <= title_len <= 70 and (len(desc) >= 40 or "#" in desc):
                metadata_optimized += 1
        metadata_coverage = (metadata_optimized / shorts_count * 100) if shorts_count else 0.0

        published_dates = [
            self._parse_published_datetime(video.get("publishedAt", ""))
            for video in shorts_videos
        ]
        published_dates = [dt for dt in published_dates if dt is not None]
        now = datetime.utcnow()
        posted_last_30_days = sum(1 for dt in published_dates if dt >= now - timedelta(days=30))
        days_since_last_short = (now - max(published_dates)).days if published_dates else None
        sorted_shorts = sorted(shorts_videos, key=lambda item: item["statistics"]["viewCount"], reverse=True)

        if shorts_count == 0:
            recommendations.append({
                "priority": "Informational",
                "category": "Shorts",
                "issue": "No Shorts identified by configured rule",
                "benchmark": "Shorts rule: <=60s, or 61-180s with #shorts in title/description",
                "why": "Shorts should be evaluated separately due to different discovery mechanics.",
                "recommendation": "If Shorts are part of strategy, publish an initial pilot batch and re-audit.",
                "impact": "Enables a measurable Shorts baseline and iterative optimization.",
                "source": "YouTube Help + Creator Academy Shorts fundamentals (official)",
            })
            return {
                "shortsCount": 0,
                "shortsPercentOfChannel": 0.0,
                "avgDurationSeconds": 0.0,
                "avgViews": 0.0,
                "medianViews": 0.0,
                "avgEngagementRate": 0.0,
                "medianEngagementRate": 0.0,
                "commentsPer1k": 0.0,
                "postedLast30Days": 0,
                "daysSinceLastShort": None,
                "metadataCoverage": 0.0,
                "videosWithOpportunities": 0,
                "totalVideoOpportunities": 0,
                "videoAudits": [],
                "recommendations": recommendations,
            }

        title_outside_optimal = [
            video for video in shorts_videos
            if len(video.get("title", "")) < 20 or len(video.get("title", "")) > 70
        ]
        if len(title_outside_optimal) / shorts_count > 0.4:
            benchmark = SHORTS_BENCHMARKS_2026["metadata_clarity"]
            recommendations.append({
                "priority": "Medium",
                "category": "Shorts",
                "issue": f"{len(title_outside_optimal)} Shorts have titles outside 20-70 characters",
                "benchmark": benchmark["benchmark"],
                "why": benchmark["why"],
                "recommendation": "Normalize Shorts titles to concise, intent-led phrasing in the 20-70 range.",
                "impact": "Improves tap propensity and relevance interpretation.",
                "source": benchmark["source"],
            })

        sparse_descriptions = [
            video for video in shorts_videos
            if len(video.get("description", "")) < 40 and "#" not in video.get("description", "")
        ]
        if len(sparse_descriptions) / shorts_count > 0.5:
            benchmark = SHORTS_BENCHMARKS_2026["description_context"]
            recommendations.append({
                "priority": "Medium",
                "category": "Shorts",
                "issue": f"{len(sparse_descriptions)} Shorts have sparse descriptions without hashtags",
                "benchmark": benchmark["benchmark"],
                "why": benchmark["why"],
                "recommendation": "Add one-line context and 1-3 relevant hashtags for each Short.",
                "impact": "Improves catalog clarity and potential discoverability.",
                "source": benchmark["source"],
            })

        if shorts_count >= 5 and days_since_last_short is not None and days_since_last_short > 21:
            benchmark = SHORTS_BENCHMARKS_2026["posting_freshness"]
            recommendations.append({
                "priority": "High",
                "category": "Shorts",
                "issue": f"No new Shorts in {days_since_last_short} days",
                "benchmark": benchmark["benchmark"],
                "why": benchmark["why"],
                "recommendation": "Re-start a consistent Shorts cadence with a minimum monthly publishing floor.",
                "impact": "Restores freshness signals and audience recency.",
                "source": benchmark["source"],
            })

        long_form_engagement = [video.get("engagementRate", 0.0) for video in long_form_videos]
        long_form_median_engagement = float(np.median(long_form_engagement)) if long_form_engagement else 0.0
        if shorts_count >= 10 and long_form_median_engagement > 0:
            if median_engagement < (0.8 * long_form_median_engagement):
                benchmark = SHORTS_BENCHMARKS_2026["engagement_relative"]
                recommendations.append({
                    "priority": "High",
                    "category": "Shorts",
                    "issue": "Shorts median engagement materially underperforms long-form median",
                    "benchmark": benchmark["benchmark"],
                    "why": benchmark["why"],
                    "recommendation": "Rework hooks, pacing, and payoff structure in first 2-3 seconds of Shorts.",
                    "impact": "Raises retention and completion probability in Shorts feed.",
                    "source": benchmark["source"],
                })

        if comments_per_1k < 5:
            benchmark = SHORTS_BENCHMARKS_2026["comments_depth"]
            recommendations.append({
                "priority": "Medium",
                "category": "Shorts",
                "issue": f"Shorts comments depth is low ({comments_per_1k:.1f} comments per 1K views)",
                "benchmark": benchmark["benchmark"],
                "why": benchmark["why"],
                "recommendation": "Use prompt-led CTAs in caption and pinned comment to spark responses.",
                "impact": "Improves signal depth beyond passive views.",
                "source": benchmark["source"],
            })

        video_audits = []
        videos_with_opportunities = 0
        total_video_opportunities = 0

        for video in sorted_shorts:
            title = video.get("title", "")
            description = video.get("description", "")
            duration = self.duration_seconds(video.get("duration", "PT0S"))
            views = int(video["statistics"]["viewCount"])
            comments = int(video["statistics"]["commentCount"])
            engagement_rate = float(video.get("engagementRate", 0.0))
            comments_per_1k_video = (comments / views * 1000) if views > 0 else 0.0

            opportunities = []
            if len(title) < 20 or len(title) > 70:
                opportunities.append("Adjust title length into 20-70 character range.")
            if len(description) < 40 and "#" not in description:
                opportunities.append("Add one-line context and 1-3 relevant hashtags.")
            if comments_per_1k_video < 5:
                opportunities.append("Increase comment prompts (question CTA + pinned comment).")
            if engagement_rate < median_engagement and shorts_count >= 5:
                opportunities.append("Strengthen first 2-second hook and pacing.")

            opportunity_count = len(opportunities)
            if opportunity_count > 0:
                videos_with_opportunities += 1
                total_video_opportunities += opportunity_count
            else:
                opportunities = ["No immediate opportunities flagged by configured checks."]

            video_audits.append({
                "video_id": video.get("id", ""),
                "video_url": f"https://youtube.com/watch?v={video.get('id', '')}",
                "title": title,
                "publishedAt": video.get("publishedAt", ""),
                "durationSeconds": duration,
                "durationMinutes": round(duration / 60, 2),
                "views": views,
                "engagementRate": round(engagement_rate, 2),
                "commentsPer1k": round(comments_per_1k_video, 1),
                "opportunityCount": opportunity_count,
                "optimizationOpportunities": opportunities,
                "optimizationSummary": " | ".join(opportunities),
            })

        return {
            "shortsCount": shorts_count,
            "shortsPercentOfChannel": round(shorts_percent, 1),
            "avgDurationSeconds": round(avg_duration, 1),
            "avgViews": round(avg_views, 1),
            "medianViews": round(median_views, 1),
            "avgEngagementRate": round(avg_engagement, 2),
            "medianEngagementRate": round(median_engagement, 2),
            "commentsPer1k": round(comments_per_1k, 1),
            "postedLast30Days": posted_last_30_days,
            "daysSinceLastShort": days_since_last_short,
            "metadataCoverage": round(metadata_coverage, 1),
            "videosWithOpportunities": videos_with_opportunities,
            "totalVideoOpportunities": total_video_opportunities,
            "videoAudits": video_audits,
            "recommendations": recommendations,
        }

    def analyze_titles_descriptions(self):
        """
        Module 1: Title & Description Optimization

        Analyzes:
        - Title length patterns
        - Keyword density in high performers
        - Description quality and structure
        - SEO optimization opportunities
        """
        print("📝 Analyzing titles and descriptions...")

        # Title length analysis
        title_lengths = [len(video['title']) for video in self.videos]
        avg_title_length = np.mean(title_lengths)

        # Identify high performers (top 33%)
        sorted_by_views = sorted(self.videos, key=lambda x: x['statistics']['viewCount'], reverse=True)
        high_performers = sorted_by_views[:len(sorted_by_views)//3]
        low_performers = sorted_by_views[-len(sorted_by_views)//3:]

        # Analyze title patterns in high performers
        high_perf_titles = [v['title'] for v in high_performers]
        high_perf_title_lengths = [len(t) for t in high_perf_titles]

        # Extract keywords from high performers
        all_words = []
        for title in high_perf_titles:
            # Remove special characters and split
            words = re.findall(r'\b[a-zA-Z]{3,}\b', title.lower())
            all_words.extend(words)

        # Common words (excluding stop words)
        stop_words = {'the', 'and', 'for', 'with', 'you', 'how', 'this', 'that', 'from', 'are', 'was', 'but'}
        filtered_words = [w for w in all_words if w not in stop_words]
        keyword_frequency = Counter(filtered_words).most_common(10)

        # Description analysis
        desc_lengths = [len(video['description']) for video in self.videos]
        avg_desc_length = np.mean(desc_lengths)
        videos_with_long_desc = sum(1 for d in desc_lengths if d > 500)
        videos_with_short_desc = sum(1 for d in desc_lengths if d < 100)

        # Check for timestamps in descriptions
        videos_with_timestamps = sum(
            1 for video in self.videos
            if self.is_timestamp_present(video.get("description", ""))
        )

        # Recommendations
        recommendations = []

        if avg_title_length > 70:
            recommendations.append({
                'priority': 'Medium',
                'category': 'Titles',
                'issue': f'Average title length is {int(avg_title_length)} characters',
                'recommendation': 'Shorten titles to 60-70 characters for better visibility in search results',
                'impact': 'Better click-through rates in search and suggested videos'
            })

        if avg_title_length < 40:
            recommendations.append({
                'priority': 'Medium',
                'category': 'Titles',
                'issue': f'Average title length is {int(avg_title_length)} characters',
                'recommendation': 'Expand titles to 50-70 characters to include more relevant keywords',
                'impact': 'Improved SEO and discoverability'
            })

        if keyword_frequency:
            top_keywords = ', '.join([f'"{word}"' for word, count in keyword_frequency[:5]])
            recommendations.append({
                'priority': 'High',
                'category': 'Titles',
                'issue': 'High-performing videos use specific keyword patterns',
                'recommendation': f'Incorporate these high-impact keywords more frequently: {top_keywords}',
                'impact': 'Align with proven successful content patterns'
            })

        if videos_with_short_desc > len(self.videos) * 0.3:
            recommendations.append({
                'priority': 'High',
                'category': 'Descriptions',
                'issue': f'{videos_with_short_desc} videos have descriptions under 100 characters',
                'recommendation': 'Write detailed descriptions (300-500 chars) with keywords in the first 150 characters',
                'impact': 'Better SEO, more context for viewers and algorithm'
            })

        if videos_with_timestamps < len(self.videos) * 0.5:
            recommendations.append({
                'priority': 'Medium',
                'category': 'Descriptions',
                'issue': f'Only {videos_with_timestamps} videos have timestamps',
                'recommendation': 'Add timestamps to video descriptions for better viewer experience',
                'impact': 'Improved watch time, viewer satisfaction, and YouTube features like key moments'
            })

        return {
            'titleLengthAverage': round(avg_title_length, 1),
            'titleLengthHighPerformers': round(np.mean(high_perf_title_lengths), 1),
            'commonKeywords': keyword_frequency[:10],
            'descriptionLengthAverage': round(avg_desc_length, 1),
            'videosWithTimestamps': videos_with_timestamps,
            'recommendations': recommendations
        }

    def analyze_tags_metadata(self):
        """
        Module 2: Tags & Metadata Effectiveness

        Analyzes:
        - Tag quantity and quality
        - Tag consistency across channel
        - Category usage
        """
        print("🏷️  Analyzing tags and metadata...")

        # Tag analysis
        tag_counts = [len(video.get('tags', [])) for video in self.videos]
        avg_tag_count = np.mean(tag_counts) if tag_counts else 0

        # Videos with no tags
        videos_without_tags = sum(1 for count in tag_counts if count == 0)

        # Collect all tags
        all_tags = []
        for video in self.videos:
            all_tags.extend([tag.lower() for tag in video.get('tags', [])])

        # Most common tags (potential brand tags)
        tag_frequency = Counter(all_tags).most_common(20)

        # Identify potential brand/channel tags (appear in >30% of videos)
        total_videos = len(self.videos)
        brand_tags = [
            (tag, count) for tag, count in tag_frequency
            if count > total_videos * 0.3
        ]

        # Category consistency
        categories = [video.get('categoryId', '') for video in self.videos if video.get('categoryId')]
        category_distribution = Counter(categories)
        most_common_category = category_distribution.most_common(1)[0] if category_distribution else ('Unknown', 0)
        category_consistency = (most_common_category[1] / len(self.videos)) * 100 if self.videos else 0

        # Recommendations
        recommendations = []

        if avg_tag_count < 5:
            recommendations.append({
                'priority': 'High',
                'category': 'Tags',
                'issue': f'Average tag count is only {int(avg_tag_count)} per video',
                'recommendation': 'Use 8-12 relevant tags per video, mixing broad and specific keywords',
                'impact': 'Significantly improved discoverability and search ranking'
            })

        if avg_tag_count > 15:
            recommendations.append({
                'priority': 'Medium',
                'category': 'Tags',
                'issue': f'Average tag count is {int(avg_tag_count)} per video',
                'recommendation': 'Reduce to 8-12 most relevant tags. Quality over quantity.',
                'impact': 'More focused targeting and better algorithm understanding'
            })

        if videos_without_tags > 0:
            recommendations.append({
                'priority': 'High',
                'category': 'Tags',
                'issue': f'{videos_without_tags} videos have no tags',
                'recommendation': 'Add relevant tags to all videos immediately',
                'impact': 'Critical for basic discoverability'
            })

        if not brand_tags:
            recommendations.append({
                'priority': 'High',
                'category': 'Tags',
                'issue': 'No consistent brand tags across videos',
                'recommendation': f'Create 2-3 brand tags (e.g., channel name, niche) and use them in every video',
                'impact': 'Stronger channel identity and easier content grouping'
            })
        else:
            brand_tag_names = ', '.join([f'"{tag}"' for tag, count in brand_tags[:3]])
            recommendations.append({
                'priority': 'Low',
                'category': 'Tags',
                'issue': f'Good use of brand tags: {brand_tag_names}',
                'recommendation': 'Continue using these brand tags consistently',
                'impact': 'Maintain strong channel identity'
            })

        if category_consistency < 80:
            recommendations.append({
                'priority': 'Medium',
                'category': 'Metadata',
                'issue': f'Category consistency is only {int(category_consistency)}%',
                'recommendation': 'Use consistent category selection to help YouTube understand your niche',
                'impact': 'Better content classification and recommendations'
            })

        return {
            'averageTagCount': round(avg_tag_count, 1),
            'videosWithoutTags': videos_without_tags,
            'commonTags': tag_frequency[:15],
            'brandTags': brand_tags,
            'categoryConsistency': round(category_consistency, 1),
            'mostCommonCategory': most_common_category[0],
            'recommendations': recommendations
        }

    def analyze_engagement(self):
        """
        Module 3: Engagement Metrics Analysis

        Analyzes:
        - Engagement rate patterns
        - Likes-to-views ratio
        - Comments-to-views ratio
        - Top vs. bottom performers
        """
        print("📈 Analyzing engagement metrics...")

        # Calculate channel-wide metrics
        total_views = sum(v['statistics']['viewCount'] for v in self.videos)
        total_likes = sum(v['statistics']['likeCount'] for v in self.videos)
        total_comments = sum(v['statistics']['commentCount'] for v in self.videos)

        avg_engagement_rate = np.mean([v['engagementRate'] for v in self.videos])

        # Likes and comments per 1000 views
        likes_per_1k = (total_likes / total_views * 1000) if total_views > 0 else 0
        comments_per_1k = (total_comments / total_views * 1000) if total_views > 0 else 0

        # Identify top and bottom performers by engagement
        sorted_by_engagement = sorted(self.videos, key=lambda x: x['engagementRate'], reverse=True)
        top_engaged = sorted_by_engagement[:5]
        bottom_engaged = sorted_by_engagement[-5:]

        # Analyze patterns in top performers
        top_title_lengths = [len(v['title']) for v in top_engaged]
        top_tag_counts = [len(v.get('tags', [])) for v in top_engaged]
        top_desc_lengths = [len(v['description']) for v in top_engaged]

        # Analyze patterns in bottom performers
        bottom_title_lengths = [len(v['title']) for v in bottom_engaged]
        bottom_tag_counts = [len(v.get('tags', [])) for v in bottom_engaged]
        bottom_desc_lengths = [len(v['description']) for v in bottom_engaged]

        # Identify outliers (unusually high/low engagement)
        median_engagement = np.median([v['engagementRate'] for v in self.videos])
        std_engagement = np.std([v['engagementRate'] for v in self.videos])

        outliers_high = [
            v for v in self.videos
            if v['engagementRate'] > median_engagement + 2 * std_engagement
        ]
        outliers_low = [
            v for v in self.videos
            if v['engagementRate'] < median_engagement - 2 * std_engagement
        ]

        # Recommendations
        recommendations = []

        if avg_engagement_rate < 2.0:
            benchmark = BENCHMARKS['engagement_rate']
            recommendations.append({
                'priority': 'High',
                'category': 'Engagement',
                'issue': f'Low average engagement rate: {avg_engagement_rate:.2f}%',
                'benchmark': f"Industry Standard: Good = {benchmark['good']}%, Excellent = {benchmark['excellent']}%",
                'why': benchmark['why'],
                'formula': benchmark['formula'],
                'recommendation': 'Add clear calls-to-action (CTAs) in videos asking viewers to like and comment',
                'impact': 'Engagement rate below 2% indicates passive audience; CTAs can double engagement',
                'source': benchmark['source']
            })

        if avg_engagement_rate > 5.0:
            recommendations.append({
                'priority': 'Low',
                'category': 'Engagement',
                'issue': f'Excellent engagement rate: {avg_engagement_rate:.2f}%',
                'recommendation': 'Maintain current engagement strategies and analyze top performers for patterns',
                'impact': 'Above 5% is exceptional; preserve what works'
            })

        if comments_per_1k < 5:
            benchmark = BENCHMARKS['comments_per_1k']
            recommendations.append({
                'priority': 'High',
                'category': 'Engagement',
                'issue': f'Low comment rate: {comments_per_1k:.1f} comments per 1000 views',
                'benchmark': f"Industry Standard: Minimum = {benchmark['minimum']}, Good = {benchmark['good']}, Excellent = {benchmark['excellent']}",
                'why': benchmark['why'],
                'recommendation': 'Ask questions in videos and pin engaging comments to encourage discussion',
                'impact': 'Comments are heavily weighted by algorithm; increasing them improves visibility',
                'source': benchmark['source']
            })

        # Pattern analysis
        if np.mean(top_title_lengths) < np.mean(bottom_title_lengths) - 10:
            recommendations.append({
                'priority': 'Medium',
                'category': 'Engagement',
                'issue': 'Top performing videos have shorter titles',
                'recommendation': f'Consider shorter titles (avg {int(np.mean(top_title_lengths))} chars) like your best performers',
                'impact': 'Align with proven engagement patterns'
            })

        if np.mean(top_tag_counts) > np.mean(bottom_tag_counts) + 3:
            recommendations.append({
                'priority': 'Medium',
                'category': 'Engagement',
                'issue': 'Top performing videos have more tags',
                'recommendation': f'Use {int(np.mean(top_tag_counts))} tags like your highest engagement videos',
                'impact': 'Match metadata strategy of successful content'
            })

        if outliers_high:
            titles = [v['title'][:50] for v in outliers_high[:3]]
            recommendations.append({
                'priority': 'High',
                'category': 'Engagement',
                'issue': f'{len(outliers_high)} videos have exceptionally high engagement',
                'recommendation': f'Analyze these outliers for replicable patterns: {", ".join(titles)}...',
                'impact': 'Replicate successful formulas to increase overall engagement'
            })

        return {
            'averageEngagementRate': round(avg_engagement_rate, 2),
            'likesPerThousandViews': round(likes_per_1k, 1),
            'commentsPerThousandViews': round(comments_per_1k, 1),
            'topPerformers': [
                {
                    'title': v['title'],
                    'engagementRate': v['engagementRate'],
                    'views': v['statistics']['viewCount']
                }
                for v in top_engaged
            ],
            'bottomPerformers': [
                {
                    'title': v['title'],
                    'engagementRate': v['engagementRate'],
                    'views': v['statistics']['viewCount']
                }
                for v in bottom_engaged
            ],
            'outliers': {
                'high': len(outliers_high),
                'low': len(outliers_low)
            },
            'recommendations': recommendations
        }

    def analyze_upload_schedule(self):
        """
        Module 4: Upload Schedule & Consistency

        Analyzes:
        - Upload frequency
        - Consistency scoring
        - Best performing days/times
        - Gaps in upload schedule
        """
        print("📅 Analyzing upload schedule...")

        # Parse dates
        video_dates = []
        for video in self.videos:
            try:
                date = dateparser.parse(video['publishedAt'])
                video_dates.append({
                    'date': date,
                    'title': video['title'],
                    'views': video['statistics']['viewCount'],
                    'dayOfWeek': date.strftime('%A'),
                    'hour': date.hour
                })
            except Exception as e:
                print(f"   Warning: Could not parse date for video: {video['title']}")

        if not video_dates:
            return {
                'error': 'Could not parse video dates',
                'recommendations': []
            }

        # Sort by date
        video_dates.sort(key=lambda x: x['date'])

        # Calculate gaps between uploads
        gaps = []
        for i in range(1, len(video_dates)):
            gap_days = (video_dates[i]['date'] - video_dates[i-1]['date']).days
            gaps.append(gap_days)

        avg_gap = np.mean(gaps) if gaps else 0
        std_gap = np.std(gaps) if gaps else 0
        consistency_score = max(0, 10 - (std_gap / avg_gap * 10)) if avg_gap > 0 else 0

        # Find best performing days
        day_performance = {}
        for vd in video_dates:
            day = vd['dayOfWeek']
            if day not in day_performance:
                day_performance[day] = {'views': 0, 'count': 0}
            day_performance[day]['views'] += vd['views']
            day_performance[day]['count'] += 1

        # Calculate average views per day
        day_avg_views = {
            day: data['views'] / data['count']
            for day, data in day_performance.items()
        }
        best_days = sorted(day_avg_views.items(), key=lambda x: x[1], reverse=True)

        # Upload frequency (uploads per week)
        if len(video_dates) > 1:
            date_range = (video_dates[-1]['date'] - video_dates[0]['date']).days
            weeks = date_range / 7
            uploads_per_week = len(video_dates) / weeks if weeks > 0 else 0
        else:
            uploads_per_week = 0

        # Check recency
        most_recent = video_dates[-1]['date']
        days_since_last = (datetime.now(most_recent.tzinfo) - most_recent).days

        # Recommendations
        recommendations = []

        if consistency_score < 5:
            recommendations.append({
                'priority': 'High',
                'category': 'Schedule',
                'issue': f'Inconsistent upload schedule (score: {consistency_score:.1f}/10)',
                'recommendation': f'Establish consistent upload frequency. Current avg: every {int(avg_gap)} days with high variation.',
                'impact': 'Consistency helps build audience habits and improves algorithm favorability'
            })

        if uploads_per_week < 1:
            recommendations.append({
                'priority': 'High',
                'category': 'Schedule',
                'issue': f'Low upload frequency: {uploads_per_week:.1f} videos per week',
                'recommendation': 'Increase to at least 1 video per week for sustained growth',
                'impact': 'Regular content is essential for channel growth and audience retention'
            })

        if uploads_per_week > 5:
            recommendations.append({
                'priority': 'Medium',
                'category': 'Schedule',
                'issue': f'High upload frequency: {uploads_per_week:.1f} videos per week',
                'recommendation': 'Consider if quality is maintained at this pace. Sometimes less frequent, higher quality wins.',
                'impact': 'Balance quantity with quality; burnout risk is high'
            })

        if days_since_last > 30:
            recommendations.append({
                'priority': 'High',
                'category': 'Schedule',
                'issue': f'{days_since_last} days since last upload',
                'recommendation': 'Upload new content soon. Long gaps hurt algorithm performance and audience retention.',
                'impact': 'Critical: Extended silence can significantly damage channel momentum'
            })

        if best_days:
            top_day = best_days[0][0]
            top_day_views = best_days[0][1]
            recommendations.append({
                'priority': 'Medium',
                'category': 'Schedule',
                'issue': f'Best performing day: {top_day} (avg {int(top_day_views):,} views)',
                'recommendation': f'Consider uploading more content on {top_day} when possible',
                'impact': 'Align uploads with proven high-performance days'
            })

        return {
            'averageGapDays': round(avg_gap, 1),
            'consistencyScore': round(consistency_score, 1),
            'uploadsPerWeek': round(uploads_per_week, 2),
            'daysSinceLastUpload': days_since_last,
            'bestPerformingDays': best_days[:3],
            'uploadDistribution': day_performance,
            'recommendations': recommendations
        }

    def generate_quick_wins(self):
        """
        Generate specific, actionable quick wins
        Identifies exact videos that need immediate fixes
        """
        print("🎯 Identifying quick wins...")

        quick_wins = []

        # Quick Win 1: Videos with no tags
        no_tags_videos = [v for v in self.videos if len(v.get('tags', [])) == 0]
        for video in no_tags_videos[:5]:  # Top 5 by views
            # Generate suggested tags based on title
            title_words = re.findall(r'\b[a-zA-Z]{3,}\b', video['title'].lower())
            suggested_tags = [word for word in title_words if word not in {'the', 'and', 'for', 'with'}][:8]

            quick_wins.append({
                'priority': 'High',
                'action': 'Add Tags',
                'video_id': video['id'],
                'video_title': video['title'],
                'video_url': f"https://youtube.com/watch?v={video['id']}",
                'views': video['statistics']['viewCount'],
                'current_state': '0 tags',
                'suggested_fix': f"Add these tags: {', '.join(suggested_tags[:5])}",
                'impact': 'Immediate discoverability improvement',
                'effort': 'Low (2 minutes)'
            })

        # Quick Win 2: Short descriptions on high-performing videos
        short_desc_videos = [
            v for v in self.videos
            if len(v.get('description', '')) < 100
            and v['statistics']['viewCount'] > np.median([x['statistics']['viewCount'] for x in self.videos])
        ]
        for video in short_desc_videos[:3]:
            quick_wins.append({
                'priority': 'High',
                'action': 'Expand Description',
                'video_id': video['id'],
                'video_title': video['title'],
                'video_url': f"https://youtube.com/watch?v={video['id']}",
                'views': video['statistics']['viewCount'],
                'current_state': f"{len(video.get('description', ''))} characters",
                'suggested_fix': 'Write 300-500 char description with keywords in first 150 chars',
                'impact': 'Better search ranking and context',
                'effort': 'Medium (5-10 minutes)'
            })

        # Quick Win 3: Missing timestamps on top performers (only videos > 2 minutes)
        top_10_videos = sorted(self.videos, key=lambda x: x['statistics']['viewCount'], reverse=True)[:10]
        no_timestamps = [
            v for v in top_10_videos
            if not self.is_short_video(v)
            and not self.is_timestamp_present(v.get("description", ""))
            and self.duration_seconds(v.get("duration", "PT0S")) > 120
        ]
        for video in no_timestamps[:3]:
            duration_seconds = self.duration_seconds(video.get("duration", "PT0S"))
            duration_mins = duration_seconds // 60
            quick_wins.append({
                'priority': 'Medium',
                'action': 'Add Timestamps',
                'video_id': video['id'],
                'video_title': video['title'],
                'video_url': f"https://youtube.com/watch?v={video['id']}",
                'views': video['statistics']['viewCount'],
                'current_state': f'No timestamps ({duration_mins}min video)',
                'suggested_fix': 'Add chapter timestamps (e.g., 0:00 Intro, 1:23 Main Content)',
                'impact': 'Improved viewer experience, better retention',
                'effort': 'Low (3-5 minutes)'
            })

        # Quick Win 4: Title optimization opportunities
        long_titles = [v for v in self.videos if len(v['title']) > 70]
        for video in long_titles[:2]:
            # Suggest shortened version
            shortened = video['title'][:67] + '...'
            quick_wins.append({
                'priority': 'Medium',
                'action': 'Shorten Title',
                'video_id': video['id'],
                'video_title': video['title'],
                'video_url': f"https://youtube.com/watch?v={video['id']}",
                'views': video['statistics']['viewCount'],
                'current_state': f"{len(video['title'])} characters (truncated in search)",
                'suggested_fix': f'Shorten to ~60 chars: "{shortened}"',
                'impact': 'Full title visible in search results',
                'effort': 'Low (2 minutes)'
            })

        # Sort by priority and views
        priority_order = {'High': 0, 'Medium': 1, 'Low': 2}
        quick_wins.sort(key=lambda x: (priority_order[x['priority']], -x['views']))

        return quick_wins[:10]  # Top 10 quick wins

    def generate_before_after_examples(self):
        """
        Generate before/after examples for optimization
        Shows what good metadata looks like
        """
        print("📋 Generating before/after examples...")

        examples = []

        # Example 1: Title optimization
        # Find a video with suboptimal title
        for video in self.videos:
            title = video['title']
            title_len = len(title)

            # If title is too short or too long, create optimized version
            if title_len < 40 or title_len > 70:
                # Create optimized title
                if title_len < 40:
                    # Add descriptive context
                    optimized = f"{title} | {self.channel['title']} Exclusive"
                else:
                    # Shorten while keeping key info
                    optimized = title[:60] + "..."

                examples.append({
                    'type': 'Title Optimization',
                    'video_id': video['id'],
                    'video_url': f"https://youtube.com/watch?v={video['id']}",
                    'before': title,
                    'after': optimized,
                    'why_better': f"Optimal length (60-70 chars), includes brand, avoids truncation. Before: {title_len} chars, After: {len(optimized)} chars",
                    'impact': 'Better click-through rate in search results'
                })
                break

        # Example 2: Description optimization
        short_desc = [v for v in self.videos if len(v.get('description', '')) < 100]
        if short_desc:
            video = short_desc[0]
            before_desc = video.get('description', '(empty)')

            # Create optimized description
            after_desc = f"""{video['title']}

Watch the full video to see [main topic]. In this video, we cover:
- Key point 1
- Key point 2
- Key point 3

Subscribe to {self.channel['title']} for more content!

Video URL: https://youtube.com/watch?v={video['id']}
#hashtag1 #hashtag2"""

            examples.append({
                'type': 'Description Optimization',
                'video_id': video['id'],
                'video_url': f"https://youtube.com/watch?v={video['id']}",
                'before': before_desc[:100],
                'after': after_desc,
                'why_better': 'Includes keywords in first 150 chars, bullet points for scannability, CTA, hashtags',
                'impact': 'Better SEO and viewer engagement'
            })

        # Example 3: Tags optimization
        no_tags = [v for v in self.videos if len(v.get('tags', [])) == 0]
        if no_tags:
            video = no_tags[0]
            # Extract keywords from title
            title_words = re.findall(r'\b[a-zA-Z]{3,}\b', video['title'].lower())
            suggested_tags = [word for word in title_words if word not in {'the', 'and', 'for', 'with', 'this', 'that', 'from'}][:10]

            examples.append({
                'type': 'Tags Optimization',
                'video_id': video['id'],
                'video_url': f"https://youtube.com/watch?v={video['id']}",
                'before': '(no tags)',
                'after': ', '.join(suggested_tags + [self.channel['title'].lower(), 'brand name', 'category']),
                'why_better': 'Mix of specific keywords + brand tags. 8-12 tags is optimal.',
                'impact': 'Helps YouTube understand content and recommend to right audience'
            })

        return examples

    def generate_audit_checklist(self):
        """
        Generate comprehensive diagnostic audit checklist
        Similar to Screaming Frog's issue-count format
        """
        print("📋 Generating audit checklist...")

        checklist = {
            'critical_issues': [],
            'engagement_warnings': [],
            'upload_schedule_issues': [],
            'optimization_opportunities': [],
            'summary': {}
        }

        # ===== CRITICAL ISSUES =====

        # 1. Videos with 0 tags
        no_tags = [v for v in self.videos if len(v.get('tags', [])) == 0]
        if no_tags:
            # Calculate impact vs tagged videos
            tagged_videos = [v for v in self.videos if len(v.get('tags', [])) > 0]
            if tagged_videos:
                tagged_avg_views = np.mean([v['statistics']['viewCount'] for v in tagged_videos])
                no_tags_avg_views = np.mean([v['statistics']['viewCount'] for v in no_tags])
                impact = ((no_tags_avg_views - tagged_avg_views) / tagged_avg_views * 100) if tagged_avg_views > 0 else 0
                impact_str = f"{impact:+.0f}% vs tagged"
            else:
                impact_str = "All videos affected"

            checklist['critical_issues'].append({
                'issue': 'Videos with 0 tags',
                'count': len(no_tags),
                'percentage': f"{len(no_tags)/len(self.videos)*100:.0f}%",
                'impact': impact_str,
                'severity': 'High'
            })

        # 2. Short descriptions (<100 chars)
        short_desc = [v for v in self.videos if len(v.get('description', '')) < 100]
        if short_desc:
            optimal_desc = [v for v in self.videos if len(v.get('description', '')) >= 300]
            if optimal_desc:
                short_avg_views = np.mean([v['statistics']['viewCount'] for v in short_desc])
                optimal_avg_views = np.mean([v['statistics']['viewCount'] for v in optimal_desc])
                impact = ((short_avg_views - optimal_avg_views) / optimal_avg_views * 100) if optimal_avg_views > 0 else 0
                impact_str = f"{impact:+.0f}% vs optimal"
            else:
                impact_str = "All videos affected"

            checklist['critical_issues'].append({
                'issue': 'Videos with short descriptions (<100 chars)',
                'count': len(short_desc),
                'percentage': f"{len(short_desc)/len(self.videos)*100:.0f}%",
                'impact': impact_str,
                'severity': 'High'
            })

        # 3. Missing timestamps on videos > 2 minutes
        videos_over_2min = [
            v for v in self.videos
            if not self.is_short_video(v)
            and self.duration_seconds(v.get("duration", "PT0S")) > 120
        ]
        no_timestamps = [
            v for v in videos_over_2min
            if not self.is_timestamp_present(v.get("description", ""))
        ]
        if no_timestamps:
            checklist['critical_issues'].append({
                'issue': 'Videos missing timestamps (>2min duration)',
                'count': len(no_timestamps),
                'percentage': f"{len(no_timestamps)/len(videos_over_2min)*100:.0f}%" if videos_over_2min else "N/A",
                'impact': "-12% retention (est.)",
                'severity': 'Medium'
            })

        # 4. Titles too long (>70 chars)
        long_titles = [v for v in self.videos if len(v['title']) > 70]
        if long_titles:
            checklist['critical_issues'].append({
                'issue': 'Titles too long (>70 chars, truncated in search)',
                'count': len(long_titles),
                'percentage': f"{len(long_titles)/len(self.videos)*100:.0f}%",
                'impact': "-8% CTR (est.)",
                'severity': 'Medium'
            })

        # 5. Titles too short (<40 chars)
        short_titles = [v for v in self.videos if len(v['title']) < 40]
        if short_titles:
            checklist['critical_issues'].append({
                'issue': 'Titles too short (<40 chars)',
                'count': len(short_titles),
                'percentage': f"{len(short_titles)/len(self.videos)*100:.0f}%",
                'impact': "-5% CTR (est.)",
                'severity': 'Low'
            })

        # 6. Insufficient tags (<8 tags)
        insufficient_tags = [v for v in self.videos if len(v.get('tags', [])) > 0 and len(v.get('tags', [])) < 8]
        if insufficient_tags:
            checklist['critical_issues'].append({
                'issue': 'Videos with insufficient tags (<8)',
                'count': len(insufficient_tags),
                'percentage': f"{len(insufficient_tags)/len(self.videos)*100:.0f}%",
                'impact': "-10% discovery (est.)",
                'severity': 'Medium'
            })

        # ===== ENGAGEMENT WARNINGS =====

        avg_engagement = np.mean([v['engagementRate'] for v in self.videos])
        benchmark_engagement = BENCHMARKS['engagement_rate']['good']

        checklist['engagement_warnings'].append({
            'issue': 'Average engagement rate',
            'current': f"{avg_engagement:.2f}%",
            'benchmark': f"{benchmark_engagement:.1f}%",
            'gap': f"{((avg_engagement - benchmark_engagement) / benchmark_engagement * 100):+.0f}%",
            'status': '✓ Good' if avg_engagement >= benchmark_engagement else '⚠️ Below'
        })

        # Low engagement videos
        low_engagement_videos = [v for v in self.videos if v['engagementRate'] < 2.0]
        checklist['engagement_warnings'].append({
            'issue': 'Videos below 2% engagement',
            'current': str(len(low_engagement_videos)),
            'benchmark': '0',
            'gap': f"{len(low_engagement_videos)} affected",
            'status': '✓ Good' if len(low_engagement_videos) == 0 else '⚠️ Poor'
        })

        # Comments per 1k views
        total_comments = sum(v['statistics']['commentCount'] for v in self.videos)
        total_views = sum(v['statistics']['viewCount'] for v in self.videos)
        comments_per_1k = (total_comments / total_views * 1000) if total_views > 0 else 0
        benchmark_comments = BENCHMARKS['comments_per_1k']['good']

        checklist['engagement_warnings'].append({
            'issue': 'Comments per 1000 views',
            'current': f"{comments_per_1k:.1f}",
            'benchmark': str(benchmark_comments),
            'gap': f"{((comments_per_1k - benchmark_comments) / benchmark_comments * 100):+.0f}%",
            'status': '✓ Good' if comments_per_1k >= benchmark_comments else '⚠️ Low'
        })

        # ===== UPLOAD SCHEDULE ISSUES =====

        dates = [dateparser.parse(v['publishedAt']) for v in self.videos]
        dates_sorted = sorted(dates)

        if len(dates_sorted) > 1:
            days_span = (dates_sorted[-1] - dates_sorted[0]).days
            uploads_per_week = (len(self.videos) / days_span * 7) if days_span > 0 else 0

            checklist['upload_schedule_issues'].append({
                'issue': 'Uploads per week',
                'current': f"{uploads_per_week:.1f}",
                'benchmark': '1-2',
                'status': '✓ Good' if 1 <= uploads_per_week <= 3 else '⚠️ Low' if uploads_per_week < 1 else '⚠️ High'
            })

            # Days since last upload
            # Remove timezone info for comparison
            now = datetime.now()
            last_upload = dates_sorted[-1].replace(tzinfo=None) if dates_sorted[-1].tzinfo else dates_sorted[-1]
            days_since_last = (now - last_upload).days
            checklist['upload_schedule_issues'].append({
                'issue': 'Days since last upload',
                'current': f"{days_since_last}d",
                'benchmark': '<7d',
                'status': '✓ Good' if days_since_last < 7 else '⚠️ Stale' if days_since_last < 30 else '⚠️ Very Stale'
            })

            # Upload consistency (std deviation of gaps)
            gaps = [(dates_sorted[i+1] - dates_sorted[i]).days for i in range(len(dates_sorted)-1)]
            if gaps:
                avg_gap = np.mean(gaps)
                std_gap = np.std(gaps)
                consistency_score = max(0, 10 - (std_gap / avg_gap * 10)) if avg_gap > 0 else 0

                checklist['upload_schedule_issues'].append({
                    'issue': 'Upload consistency score',
                    'current': f"{consistency_score:.1f}/10",
                    'benchmark': '7+',
                    'status': '✓ Good' if consistency_score >= 7 else '⚠️ Inconsistent'
                })

                # Longest gap
                longest_gap = max(gaps)
                checklist['upload_schedule_issues'].append({
                    'issue': 'Longest gap between uploads',
                    'current': f"{longest_gap}d",
                    'benchmark': '<30d',
                    'status': '✓ Good' if longest_gap < 30 else '⚠️ Problematic'
                })

        # ===== OPTIMIZATION OPPORTUNITIES =====

        # Missing brand tags
        brand_name_lower = self.channel['title'].lower()
        videos_without_brand = [
            v for v in self.videos
            if not any(brand_name_lower in tag.lower() for tag in v.get('tags', []))
        ]
        if videos_without_brand:
            checklist['optimization_opportunities'].append({
                'issue': 'Missing brand tags',
                'count': len(videos_without_brand),
                'quick_fix': '✓ Yes',
                'impact': '+15% discovery (est.)'
            })

        # No CTA in description
        cta_keywords = ['subscribe', 'like', 'comment', 'follow', 'click', 'watch']
        no_cta = [
            v for v in self.videos
            if not any(kw in v.get('description', '').lower() for kw in cta_keywords)
        ]
        if no_cta:
            checklist['optimization_opportunities'].append({
                'issue': 'No CTA in description',
                'count': len(no_cta),
                'quick_fix': '✓ Yes',
                'impact': '+10% engagement (est.)'
            })

        # No hashtags
        no_hashtags = [
            v for v in self.videos
            if '#' not in v.get('description', '')
        ]
        if no_hashtags:
            checklist['optimization_opportunities'].append({
                'issue': 'No hashtags used',
                'count': len(no_hashtags),
                'quick_fix': '✓ Yes',
                'impact': '+8% search (est.)'
            })

        # Descriptions missing video URL
        no_video_link = [
            v for v in self.videos
            if 'youtube.com' not in v.get('description', '').lower() and 'youtu.be' not in v.get('description', '').lower()
        ]
        if no_video_link:
            checklist['optimization_opportunities'].append({
                'issue': 'No video link in description',
                'count': len(no_video_link),
                'quick_fix': '✓ Yes',
                'impact': '+5% shareability (est.)'
            })

        # ===== SUMMARY =====
        high_priority_count = len([i for i in checklist['critical_issues'] if i.get('severity') == 'High'])
        medium_priority_count = len([i for i in checklist['critical_issues'] if i.get('severity') == 'Medium'])
        low_priority_count = len([i for i in checklist['critical_issues'] if i.get('severity') == 'Low'])

        warning_count = len([w for w in checklist['engagement_warnings'] if '⚠️' in w.get('status', '')])
        warning_count += len([s for s in checklist['upload_schedule_issues'] if '⚠️' in s.get('status', '')])

        total_issues = len(checklist['critical_issues']) + warning_count
        quick_wins = len(checklist['optimization_opportunities'])

        checklist['summary'] = {
            'total_issues': total_issues,
            'critical_issues': len(checklist['critical_issues']),
            'warnings': warning_count,
            'quick_wins': quick_wins,
            'high_priority': high_priority_count,
            'medium_priority': medium_priority_count,
            'low_priority': low_priority_count,
            'estimated_fix_time': f"{quick_wins * 3} minutes",
            'potential_impact': '+20-30% channel performance (est.)'
        }

        return checklist

    def calculate_channel_health_score(self, all_recommendations):
        """
        Calculate overall channel health score (10-100)
        Based on number and severity of issues

        Formula: max(10, 100 - (10 × High Priority) - (5 × Medium Priority))

        Updated 2026-02-11: Reduced penalty values for more realistic scoring
        - High Priority: -10 points (was -15)
        - Medium Priority: -5 points (was -8)
        - Minimum score: 10 (was 0)
        """
        high_priority_issues = sum(
            1 for r in all_recommendations
            if r.get('priority') == 'High'
        )
        medium_priority_issues = sum(
            1 for r in all_recommendations
            if r.get('priority') == 'Medium'
        )

        # Start at 100, deduct points for issues
        score = 100
        score -= high_priority_issues * 10  # Reduced from 15
        score -= medium_priority_issues * 5  # Reduced from 8

        # Minimum score is 10 instead of 0 for better differentiation
        return max(10, min(100, score))

    def calculate_shorts_health_score(self, shorts_recommendations):
        """
        Calculate Shorts-only health score (separate from long-form score).
        Formula: max(10, 100 - (12 × High) - (6 × Medium) - (2 × Low))
        """
        high_priority_issues = sum(
            1 for rec in shorts_recommendations
            if rec.get("priority") == "High"
        )
        medium_priority_issues = sum(
            1 for rec in shorts_recommendations
            if rec.get("priority") == "Medium"
        )
        low_priority_issues = sum(
            1 for rec in shorts_recommendations
            if rec.get("priority") == "Low"
        )

        score = 100
        score -= high_priority_issues * 12
        score -= medium_priority_issues * 6
        score -= low_priority_issues * 2
        return max(10, min(100, score))

    def generate_analysis(self):
        """Generate complete analysis with all modules"""
        print("\n🔬 YouTube Channel Analysis")
        print("=" * 50)

        # Run all analysis modules
        titles_analysis = self.analyze_titles_descriptions()
        tags_analysis = self.analyze_tags_metadata()
        engagement_analysis = self.analyze_engagement()
        schedule_analysis = self.analyze_upload_schedule()
        shorts_videos, long_form_videos = self.split_videos_by_format()
        shorts_analysis = self.analyze_shorts_2026(shorts_videos, long_form_videos)
        timestamp_audit = self.generate_timestamp_audit(long_form_videos)

        # Collect all recommendations
        all_recommendations = []
        all_recommendations.extend(titles_analysis.get('recommendations', []))
        all_recommendations.extend(tags_analysis.get('recommendations', []))
        all_recommendations.extend(engagement_analysis.get('recommendations', []))
        all_recommendations.extend(schedule_analysis.get('recommendations', []))

        # Sort by priority
        priority_order = {'High': 0, 'Medium': 1, 'Low': 2}
        all_recommendations.sort(key=lambda x: priority_order.get(x.get('priority', 'Low'), 3))

        # Calculate health score
        health_score = self.calculate_channel_health_score(all_recommendations)
        shorts_recommendations = shorts_analysis.get("recommendations", [])
        shorts_health_score = self.calculate_shorts_health_score(shorts_recommendations)

        # Generate quick wins, before/after examples, and audit checklist
        quick_wins = self.generate_quick_wins()
        before_after_examples = self.generate_before_after_examples()
        audit_checklist = self.generate_audit_checklist()

        shorts_high_priority = sum(1 for rec in shorts_recommendations if rec.get("priority") == "High")
        shorts_medium_priority = sum(1 for rec in shorts_recommendations if rec.get("priority") == "Medium")
        shorts_low_priority = sum(1 for rec in shorts_recommendations if rec.get("priority") == "Low")

        print("\n✅ Analysis complete!")
        print(f"📊 Channel Health Score: {health_score}/100")
        print(f"🎬 Shorts Health Score: {shorts_health_score}/100")
        print(f"📋 Total Recommendations: {len(all_recommendations)}")
        print(f"   - High Priority: {sum(1 for r in all_recommendations if r.get('priority') == 'High')}")
        print(f"   - Medium Priority: {sum(1 for r in all_recommendations if r.get('priority') == 'Medium')}")
        print(f"   - Low Priority: {sum(1 for r in all_recommendations if r.get('priority') == 'Low')}")
        print(f"🎬 Shorts Recommendations: {len(shorts_recommendations)}")
        print(f"   - High Priority: {shorts_high_priority}")
        print(f"   - Medium Priority: {shorts_medium_priority}")
        print(f"   - Low Priority: {shorts_low_priority}")
        print(
            "⏱️ Timestamp Coverage: "
            f"{timestamp_audit.get('coveragePercent', 0):.1f}% "
            f"({timestamp_audit.get('withTimestampsCount', 0)}/{timestamp_audit.get('eligibleCount', 0)})"
        )
        print(f"🎯 Quick Wins Identified: {len(quick_wins)}")
        print(f"📋 Before/After Examples: {len(before_after_examples)}")
        print(f"🔍 Audit Issues Found: {audit_checklist['summary']['total_issues']}")

        return {
            'channelHealthScore': health_score,
            'shortsHealthScore': shorts_health_score,
            'analysisModules': {
                'titlesAndDescriptions': titles_analysis,
                'tagsAndMetadata': tags_analysis,
                'engagement': engagement_analysis,
                'uploadSchedule': schedule_analysis,
                'shorts2026': shorts_analysis,
            },
            'allRecommendations': all_recommendations,
            'shortsRecommendations': shorts_recommendations,
            'timestampAudit': timestamp_audit,
            'quickWins': quick_wins,
            'beforeAfterExamples': before_after_examples,
            'auditChecklist': audit_checklist,
            'summary': {
                'totalRecommendations': len(all_recommendations),
                'highPriority': sum(1 for r in all_recommendations if r.get('priority') == 'High'),
                'mediumPriority': sum(1 for r in all_recommendations if r.get('priority') == 'Medium'),
                'lowPriority': sum(1 for r in all_recommendations if r.get('priority') == 'Low'),
                'quickWins': len(quick_wins),
                'beforeAfterExamples': len(before_after_examples),
                'auditIssues': audit_checklist['summary']['total_issues'],
                'shortsVideos': len(shorts_videos),
                'longFormVideos': len(long_form_videos),
                'shortsHighPriority': shorts_high_priority,
                'shortsMediumPriority': shorts_medium_priority,
                'shortsLowPriority': shorts_low_priority,
                'timestampEligibleVideos': timestamp_audit.get('eligibleCount', 0),
                'timestampMissingVideos': timestamp_audit.get('missingCount', 0),
                'timestampCoveragePercent': timestamp_audit.get('coveragePercent', 0.0),
            }
        }


def main():
    """Main execution function"""
    if len(sys.argv) != 2:
        print("❌ Error: Missing data file path")
        print("\nUsage:")
        print("  python3 youtube_analyze_videos.py path/to/raw_data.json")
        sys.exit(1)

    data_file = sys.argv[1]
    data_path = Path(data_file)

    # Check if file exists
    if not data_path.exists():
        print(f"❌ Error: File not found: {data_file}")
        sys.exit(1)

    try:
        # Load data
        print(f"📂 Loading data from: {data_file}")
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Initialize analyzer
        analyzer = YouTubeAnalyzer(data)

        # Run analysis
        analysis_results = analyzer.generate_analysis()

        # Save results
        output_file = data_path.parent / 'analysis.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_results, f, indent=2, ensure_ascii=False)

        print(f"\n📁 Analysis saved to: {output_file}")
        print("\nNext step:")
        print(f"  python3 tools/export_to_excel.py {data_file} {output_file}")

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
