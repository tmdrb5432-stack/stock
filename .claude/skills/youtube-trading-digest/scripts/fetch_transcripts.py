#!/usr/bin/env python3
"""Fetch recent video metadata + transcripts from YouTube channels/playlists.

Requires (install locally, not in this repo):
    pip install yt-dlp youtube-transcript-api

Usage:
    python3 fetch_transcripts.py <channel_or_playlist_url> [<url2> ...] [--limit N]

Prints a JSON array to stdout, one entry per video:
    {
        "source": "<input url>",
        "video_id": "...",
        "title": "...",
        "upload_date": "YYYYMMDD",
        "url": "https://www.youtube.com/watch?v=...",
        "transcript": "<full transcript text>" | null,
        "transcript_error": "<reason>" | null
    }

Does not download video/audio — only lists metadata (yt-dlp --flat-playlist)
and pulls caption text (youtube-transcript-api), so it is fast and light.
"""
import argparse
import json
import subprocess
import sys


def normalize_source(url: str) -> str:
    """Point channel handle URLs at their /videos tab so flat-playlist lists videos."""
    if "playlist" in url or "/videos" in url:
        return url
    return url.rstrip("/") + "/videos"


def list_videos(source_url: str, limit: int):
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--playlist-end", str(limit),
        "--print", "%(id)s\t%(title)s\t%(upload_date)s",
        normalize_source(source_url),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"[warn] yt-dlp failed for {source_url}: {result.stderr.strip()}", file=sys.stderr)
        return []
    videos = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            videos.append({"id": parts[0], "title": parts[1], "upload_date": parts[2]})
    return videos


def get_transcript(video_id: str, languages=("ko", "en")):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            TranscriptsDisabled,
            NoTranscriptFound,
            VideoUnavailable,
        )
    except ImportError:
        return None, "youtube-transcript-api not installed"

    try:
        segments = YouTubeTranscriptApi.get_transcript(video_id, languages=list(languages))
        return " ".join(s["text"] for s in segments), None
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
        return None, type(e).__name__
    except Exception as e:  # noqa: BLE001 - surface any other transcript failure as data
        return None, str(e)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", help="Channel or playlist URLs")
    parser.add_argument("--limit", type=int, default=5, help="Videos per source (default 5)")
    args = parser.parse_args()

    output = []
    for source in args.sources:
        for v in list_videos(source, args.limit):
            transcript, error = get_transcript(v["id"])
            output.append({
                "source": source,
                "video_id": v["id"],
                "title": v["title"],
                "upload_date": v.get("upload_date"),
                "url": f"https://www.youtube.com/watch?v={v['id']}",
                "transcript": transcript,
                "transcript_error": error,
            })

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
