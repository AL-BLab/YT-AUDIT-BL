"""Audit runner wrapper around existing deterministic tool modules."""

from __future__ import annotations

import io
import json
import re
from contextlib import redirect_stdout
from pathlib import Path
from typing import Callable, Dict, Optional

from tools.export_to_excel import ExcelExporter
from tools.generate_markdown_report import MarkdownReportGenerator
from tools.youtube_analyze_videos import YouTubeAnalyzer
from tools.youtube_fetch_channel_data import YouTubeChannelFetcher

YOUTUBE_CHANNEL_PATTERNS = [
    re.compile(r"^https://(www\.)?youtube\.com/@[\w-]+/?$", re.IGNORECASE),
    re.compile(r"^https://(www\.)?youtube\.com/channel/UC[\w-]+/?$", re.IGNORECASE),
    re.compile(r"^https://(www\.)?youtube\.com/c/[\w-]+/?$", re.IGNORECASE),
    re.compile(r"^https://(www\.)?youtube\.com/user/[\w-]+/?$", re.IGNORECASE),
]


def normalize_channel_url(channel_url: str) -> str:
    normalized = channel_url.strip()
    if normalized.startswith("http://"):
        normalized = "https://" + normalized[len("http://") :]
    return normalized.rstrip("/")



def validate_channel_url(channel_url: str) -> bool:
    normalized = normalize_channel_url(channel_url)
    return any(pattern.match(normalized) for pattern in YOUTUBE_CHANNEL_PATTERNS)



def _emit(logger: Optional[Callable[[str], None]], message: str) -> None:
    if logger:
        logger(message)



def _capture_step(logger: Optional[Callable[[str], None]], step_name: str, fn) -> None:
    _emit(logger, f"\n[{step_name}] starting...")
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        fn()
    output = buffer.getvalue().strip()
    if output:
        _emit(logger, output)
    _emit(logger, f"[{step_name}] complete")



def extract_summary_metrics(analysis: Dict) -> Dict[str, int]:
    summary = analysis.get("summary", {})
    return {
        "summary_health_score": int(analysis.get("channelHealthScore", 0)),
        "summary_high_priority": int(summary.get("highPriority", 0)),
        "summary_medium_priority": int(summary.get("mediumPriority", 0)),
        "summary_low_priority": int(summary.get("lowPriority", 0)),
        "videos_analyzed": int(summary.get("videosAnalyzed", summary.get("totalRecommendations", 0))),
    }



def run_audit_pipeline(
    channel_url: str,
    output_folder: str,
    api_key: str,
    max_videos: int = 0,
    logger: Optional[Callable[[str], None]] = None,
) -> Dict:
    """Run full audit and return paths/summary metadata."""
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY is missing")

    normalized_url = normalize_channel_url(channel_url)
    if not validate_channel_url(normalized_url):
        raise ValueError(
            "Invalid channel URL format. Supported: https://youtube.com/@name, /channel/UC..., /c/name, /user/name"
        )

    output_root = Path(output_folder)
    output_root.mkdir(parents=True, exist_ok=True)

    fetcher = YouTubeChannelFetcher(api_key)
    _emit(logger, f"Running audit for: {normalized_url}")

    channel_id = fetcher.extract_channel_id(normalized_url)
    channel_info = fetcher.fetch_channel_info(channel_id)
    videos = fetcher.fetch_channel_videos(channel_id, max_videos)
    raw_data_path = Path(fetcher.save_data(channel_info, videos, output_root / channel_id))

    _emit(logger, f"Raw data saved: {raw_data_path}")

    with raw_data_path.open("r", encoding="utf-8") as raw_file:
        raw_data = json.load(raw_file)

    analyzer = YouTubeAnalyzer(raw_data)

    analysis_holder: Dict = {}

    def do_analysis():
        analysis_holder["data"] = analyzer.generate_analysis()

    _capture_step(logger, "Analyze Videos", do_analysis)
    analysis_data = analysis_holder["data"]

    analysis_path = raw_data_path.parent / "analysis.json"
    with analysis_path.open("w", encoding="utf-8") as analysis_file:
        json.dump(analysis_data, analysis_file, indent=2, ensure_ascii=False)

    _emit(logger, f"Analysis saved: {analysis_path}")

    excel_path = raw_data_path.parent / "audit_report.xlsx"

    def do_excel_export():
        exporter = ExcelExporter(raw_data, analysis_data)
        exporter.export(excel_path)

    _capture_step(logger, "Export Excel", do_excel_export)

    markdown_path = raw_data_path.parent / "report.md"

    def do_markdown():
        generator = MarkdownReportGenerator(raw_data, analysis_data)
        markdown_path.write_text(generator.generate(), encoding="utf-8")

    _capture_step(logger, "Generate Markdown", do_markdown)

    summary_metrics = extract_summary_metrics(analysis_data)
    summary_metrics["videos_analyzed"] = len(raw_data.get("videos", []))

    return {
        "channel_id": channel_id,
        "channel_name": channel_info.get("title", ""),
        "raw_data_path": str(raw_data_path),
        "analysis_path": str(analysis_path),
        "excel_path": str(excel_path),
        "markdown_path": str(markdown_path),
        "summary": summary_metrics,
        "quota_used": int(raw_data.get("metadata", {}).get("quotaUsed", 0)),
    }
