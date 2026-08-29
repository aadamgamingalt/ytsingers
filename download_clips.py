"""
Download audio segments from YouTube for each matched word.
Uses yt-dlp --download-sections to only grab the needed window.
"""

import os
import subprocess
from tqdm import tqdm


def download_clip(video_id, center_time, window_sec, out_dir):
    """Download a short audio window around center_time."""
    start = max(0, center_time - window_sec / 2)
    end = center_time + window_sec / 2

    out_path = os.path.join(out_dir, f"{video_id}_{start:.2f}.mp3")
    if os.path.exists(out_path):
        return out_path

    url = f"https://www.youtube.com/watch?v={video_id}"
    section = f"*{_fmt_time(start)}-{_fmt_time(end)}"

    result = subprocess.run(
        [
            "yt-dlp",
            "--download-sections", section,
            "-x", "--audio-format", "mp3", "--audio-quality", "0",
            "--no-playlist",
            "-o", out_path,
            url
        ],
        capture_output=True, text=True
    )
    return out_path if os.path.exists(out_path) else None


def _fmt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def download_word_clips(word_hits, temp_dir, window_sec=5):
    """
    Download audio clips for all matched words.
    Returns dict: {word: {clip_path, rough_start, rough_end, video_id}}
    """
    clips_dir = os.path.join(temp_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    clips = {}
    for word, hit in tqdm(word_hits.items(), desc="  Downloading clips"):
        center = (hit["start"] + hit["end"]) / 2
        clip_path = download_clip(hit["video_id"], center, window_sec, clips_dir)
        if clip_path:
            clips[word] = {
                "clip_path": clip_path,
                "rough_start": hit["start"],
                "rough_end": hit["end"],
                "video_id": hit["video_id"],
                "window_start": max(0, center - window_sec / 2)
            }
    return clips

