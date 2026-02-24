#!/usr/bin/env python3
"""
YouTube Channel Data Fetcher
Fetches channel metadata and videos from YouTube Data API v3

Usage:
    python3 youtube_fetch_channel_data.py "https://youtube.com/@channelname"
"""

import sys
import os
import json
import re
import time
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class YouTubeChannelFetcher:
    def __init__(self, api_key):
        """Initialize YouTube API client"""
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.quota_used = 0

    def extract_channel_id(self, url):
        """
        Extract channel ID from various YouTube URL formats

        Supported formats:
        - https://youtube.com/@username
        - https://youtube.com/channel/UCxxxxxxxx
        - https://youtube.com/c/channelname
        - https://youtube.com/user/username
        """
        # Remove trailing slashes and whitespace
        url = url.strip().rstrip('/')

        # Pattern 1: @username
        match = re.search(r'youtube\.com/@([\w-]+)', url)
        if match:
            return self.get_channel_id_from_username(match.group(1))

        # Pattern 2: /channel/UCxxxxx (direct channel ID)
        match = re.search(r'youtube\.com/channel/(UC[\w-]+)', url)
        if match:
            return match.group(1)

        # Pattern 3: /c/channelname (custom URL)
        match = re.search(r'youtube\.com/c/([\w-]+)', url)
        if match:
            return self.get_channel_id_from_custom_url(match.group(1))

        # Pattern 4: /user/username (legacy)
        match = re.search(r'youtube\.com/user/([\w-]+)', url)
        if match:
            return self.get_channel_id_from_username(match.group(1))

        raise ValueError(
            f"Invalid YouTube channel URL format: {url}\n"
            "Supported formats:\n"
            "  - https://youtube.com/@username\n"
            "  - https://youtube.com/channel/UCxxxxxxxx\n"
            "  - https://youtube.com/c/channelname\n"
            "  - https://youtube.com/user/username"
        )

    def get_channel_id_from_username(self, username):
        """Get channel ID from @username or legacy username"""
        try:
            # Try with @ prefix first (modern format)
            if not username.startswith('@'):
                username = f'@{username}'

            request = self.youtube.channels().list(
                part='id',
                forHandle=username.lstrip('@')
            )
            response = request.execute()
            self.quota_used += 1

            if response['items']:
                return response['items'][0]['id']

            # Fallback: Try forUsername (legacy)
            request = self.youtube.channels().list(
                part='id',
                forUsername=username.lstrip('@')
            )
            response = request.execute()
            self.quota_used += 1

            if response['items']:
                return response['items'][0]['id']

            raise ValueError(f"Channel not found: {username}")

        except HttpError as e:
            if e.resp.status == 404:
                raise ValueError(f"Channel not found: {username}")
            raise

    def get_channel_id_from_custom_url(self, custom_url):
        """Get channel ID from custom URL (/c/channelname)"""
        # For custom URLs, we need to search
        try:
            request = self.youtube.search().list(
                part='snippet',
                q=custom_url,
                type='channel',
                maxResults=1
            )
            response = request.execute()
            self.quota_used += 100  # Search is expensive

            if response['items']:
                return response['items'][0]['snippet']['channelId']

            raise ValueError(f"Channel not found with custom URL: {custom_url}")

        except HttpError as e:
            if e.resp.status == 404:
                raise ValueError(f"Channel not found: {custom_url}")
            raise

    def fetch_channel_info(self, channel_id):
        """Fetch channel metadata"""
        try:
            request = self.youtube.channels().list(
                part='snippet,statistics,contentDetails',
                id=channel_id
            )
            response = request.execute()
            self.quota_used += 1

            if not response['items']:
                raise ValueError(f"Channel not found: {channel_id}")

            channel = response['items'][0]

            return {
                'id': channel['id'],
                'title': channel['snippet']['title'],
                'description': channel['snippet'].get('description', ''),
                'customUrl': channel['snippet'].get('customUrl', ''),
                'publishedAt': channel['snippet']['publishedAt'],
                'thumbnails': channel['snippet'].get('thumbnails', {}),
                'subscriberCount': int(channel['statistics'].get('subscriberCount', 0)),
                'videoCount': int(channel['statistics'].get('videoCount', 0)),
                'viewCount': int(channel['statistics'].get('viewCount', 0)),
                'uploadsPlaylistId': channel['contentDetails']['relatedPlaylists'].get('uploads', '')
            }

        except HttpError as e:
            if e.resp.status == 403:
                raise Exception("YouTube API quota exceeded. Wait until midnight PT or use a different API key.")
            elif e.resp.status == 404:
                raise ValueError(f"Channel not found: {channel_id}")
            else:
                raise Exception(f"YouTube API error: {e}")

    def fetch_channel_videos(self, channel_id, max_videos=0):
        """
        Fetch videos from a channel uploads playlist.

        Strategy:
        1. Get uploads playlist ID from channel info
        2. Fetch all videos from uploads playlist
        3. Get full video details including statistics
        4. Sort by view count and optionally limit to top N

        max_videos behavior:
        - max_videos <= 0: return all channel videos
        - max_videos > 0: return top N by view count
        """
        print(f"📹 Fetching videos from channel...")

        # Get all video IDs from uploads playlist
        video_ids = []
        next_page_token = None

        try:
            # Get uploads playlist ID
            channel_info = self.fetch_channel_info(channel_id)
            uploads_playlist_id = channel_info['uploadsPlaylistId']

            if not uploads_playlist_id:
                raise Exception("Could not find uploads playlist for this channel")

            # Fetch all video IDs from uploads playlist (50 per page)
            while True:
                request = self.youtube.playlistItems().list(
                    part='contentDetails',
                    playlistId=uploads_playlist_id,
                    maxResults=50,
                    pageToken=next_page_token
                )
                response = request.execute()
                self.quota_used += 1

                video_ids.extend([
                    item['contentDetails']['videoId']
                    for item in response.get('items', [])
                ])

                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break

            print(f"   Found {len(video_ids)} videos")

            if not video_ids:
                raise Exception("No videos found in channel")

            # Fetch full video details in batches (API allows max 50 per request)
            videos = []
            batch_size = 50

            for i in range(0, len(video_ids), batch_size):
                batch_ids = video_ids[i:i + batch_size]

                request = self.youtube.videos().list(
                    part='snippet,statistics,contentDetails',
                    id=','.join(batch_ids)
                )
                response = request.execute()
                self.quota_used += 1

                for video in response.get('items', []):
                    # Parse video data
                    videos.append({
                        'id': video['id'],
                        'title': video['snippet']['title'],
                        'description': video['snippet'].get('description', ''),
                        'publishedAt': video['snippet']['publishedAt'],
                        'channelId': video['snippet']['channelId'],
                        'channelTitle': video['snippet']['channelTitle'],
                        'tags': video['snippet'].get('tags', []),
                        'categoryId': video['snippet'].get('categoryId', ''),
                        'thumbnails': video['snippet'].get('thumbnails', {}),
                        'duration': video['contentDetails'].get('duration', ''),
                        'statistics': {
                            'viewCount': int(video['statistics'].get('viewCount', 0)),
                            'likeCount': int(video['statistics'].get('likeCount', 0)),
                            'commentCount': int(video['statistics'].get('commentCount', 0))
                        }
                    })

            # Sort by view count (descending)
            videos.sort(key=lambda x: x['statistics']['viewCount'], reverse=True)

            if max_videos > 0:
                selected_videos = videos[:max_videos]
                print(f"✅ Selected top {len(selected_videos)} videos by view count")
            else:
                selected_videos = videos
                print(f"✅ Selected all {len(selected_videos)} videos")

            return selected_videos

        except HttpError as e:
            if e.resp.status == 403:
                raise Exception("YouTube API quota exceeded. Wait until midnight PT or use a different API key.")
            else:
                raise Exception(f"YouTube API error: {e}")

    def save_data(self, channel_info, videos, output_dir):
        """Save fetched data to JSON file"""
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Prepare data structure
        data = {
            'channel': channel_info,
            'videos': videos,
            'metadata': {
                'fetchedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'videoCount': len(videos),
                'quotaUsed': self.quota_used
            }
        }

        # Save to file
        output_file = output_path / 'raw_data.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return str(output_file)


def main():
    """Main execution function"""
    # Check arguments
    if len(sys.argv) != 2:
        print("❌ Error: Missing channel URL")
        print("\nUsage:")
        print("  python3 youtube_fetch_channel_data.py \"CHANNEL_URL\"")
        print("\nExample:")
        print("  python3 youtube_fetch_channel_data.py \"https://youtube.com/@mkbhd\"")
        sys.exit(1)

    channel_url = sys.argv[1]

    # Get configuration from environment
    api_key = os.getenv('YOUTUBE_API_KEY')
    max_videos = int(os.getenv('MAX_VIDEOS', 0))
    output_folder = os.getenv('OUTPUT_FOLDER', '.tmp/youtube_audits')

    if not api_key:
        print("❌ Error: YOUTUBE_API_KEY not found in .env file")
        sys.exit(1)

    try:
        print("🚀 YouTube Channel Data Fetcher")
        print("=" * 50)
        print(f"Channel URL: {channel_url}")
        if max_videos > 0:
            print(f"Max videos: {max_videos}")
        else:
            print("Max videos: ALL")
        print()

        # Initialize fetcher
        fetcher = YouTubeChannelFetcher(api_key)

        # Step 1: Extract channel ID
        print("🔍 Extracting channel ID...")
        channel_id = fetcher.extract_channel_id(channel_url)
        print(f"   Channel ID: {channel_id}")
        print()

        # Step 2: Fetch channel info
        print("📊 Fetching channel information...")
        channel_info = fetcher.fetch_channel_info(channel_id)
        print(f"   Channel: {channel_info['title']}")
        print(f"   Subscribers: {channel_info['subscriberCount']:,}")
        print(f"   Total Videos: {channel_info['videoCount']:,}")
        print(f"   Total Views: {channel_info['viewCount']:,}")
        print()

        # Step 3: Fetch videos
        videos = fetcher.fetch_channel_videos(channel_id, max_videos)
        print()

        # Step 4: Save data
        output_dir = f"{output_folder}/{channel_id}"
        output_file = fetcher.save_data(channel_info, videos, output_dir)

        print("=" * 50)
        print("✅ SUCCESS!")
        print(f"📁 Data saved to: {output_file}")
        print(f"📊 Videos fetched: {len(videos)}")
        print(f"💰 API quota used: ~{fetcher.quota_used} units")
        print()
        print("Next step:")
        print(f"  python3 tools/youtube_analyze_videos.py {output_file}")

    except ValueError as e:
        print(f"❌ Validation Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
