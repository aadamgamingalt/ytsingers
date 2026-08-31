"""
Download audio segments from YouTube for each matched word.
Uses yt-dlp --download-sections to only grab the needed window.
Parallel downloads with timeout per clip.
"""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm


def _fmt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def download_clip(video_id, center_time, window_sec, out_dir, timeout=30):
    start = max(0, center_time - window_sec / 2)
    end = center_time + window_sec / 2
    out_path = os.path.join(out_dir, f"{video_id}_{start:.2f}.mp3")

    if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
        return out_path

    url = f"https://www.youtube.com/watch?v={video_id}"
    section = f"*{_fmt_time(start)}-{_fmt_time(end)}"

    try:
        subprocess.run(
            [
                "yt-dlp",
                "--download-sections", section,
                "-x", "--audio-format", "mp3", "--audio-quality", "0",
                "--no-playlist",
                "--quiet",
                "-o", out_path,
                url
            ],
            capture_output=True, text=True,
            timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return None

    return out_path if os.path.exists(out_path) and os.path.getsize(out_path) > 1000 else None


def download_word_clips(word_hits, temp_dir, window_sec=5, workers=6):
    clips_dir = os.path.join(temp_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    clips = {}

    def _download(word, hit):
        center = (hit["start"] + hit["end"]) / 2
        clip_path = download_clip(hit["video_id"], center, window_sec, clips_dir)
        return word, clip_path, hit

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_download, word, hit): word
            for word, hit in word_hits.items()
        }
        for future in tqdm(as_completed(futures), total=len(futures), desc="  Downloading clips"):
            word, clip_path, hit = future.result()
            if clip_path:
                center = (hit["start"] + hit["end"]) / 2
                clips[word] = {
                    "clip_path": clip_path,
                    "rough_start": hit["start"],
                    "rough_end": hit["end"],
                    "video_id": hit["video_id"],
                    "window_start": max(0, center - window_sec / 2)
                }

    print(f"  Downloaded {len(clips)}/{len(word_hits)} clips")
    return clips
