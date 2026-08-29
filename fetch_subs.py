"""
Download subtitles (auto-generated or manual) for every video
on each channel using yt-dlp. No audio downloaded here.
"""

import os
import subprocess
import glob
import json
from tqdm import tqdm


def fetch_channel_list(channel_url, temp_dir):
    """Get list of all video IDs from a channel."""
    result = subprocess.run(
        ["yt-dlp", "--flat-playlist", "--print", "id", channel_url],
        capture_output=True, text=True
    )
    ids = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    return ids


def fetch_subtitles_for_video(video_id, out_dir):
    """Download subtitles for a single video. Returns path to .vtt file or None."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    result = subprocess.run(
        [
            "yt-dlp",
            "--skip-download",
            "--write-auto-subs",
            "--write-subs",
            "--sub-lang", "en",
            "--sub-format", "vtt",
            "--output", os.path.join(out_dir, "%(id)s.%(ext)s"),
            url
        ],
        capture_output=True, text=True
    )
    # Find the downloaded vtt file
    matches = glob.glob(os.path.join(out_dir, f"{video_id}*.vtt"))
    return matches[0] if matches else None


def fetch_all_subtitles(channel_urls, temp_dir):
    """
    Fetch subtitles for all videos across all channels.
    Returns a dict: {video_id: vtt_file_path}
    """
    subs_dir = os.path.join(temp_dir, "subs")
    os.makedirs(subs_dir, exist_ok=True)

    index_path = os.path.join(temp_dir, "sub_index.json")
    if os.path.exists(index_path):
        print("  Loading cached subtitle index...")
        with open(index_path) as f:
            return json.load(f)

    sub_index = {}

    for channel_url in channel_urls:
        print(f"  Fetching video list: {channel_url}")
        video_ids = fetch_channel_list(channel_url, temp_dir)
        print(f"  Found {len(video_ids)} videos")

        for vid_id in tqdm(video_ids, desc=f"  Subtitles"):
            if vid_id in sub_index:
                continue
            vtt_path = fetch_subtitles_for_video(vid_id, subs_dir)
            if vtt_path:
                sub_index[vid_id] = vtt_path

    with open(index_path, "w") as f:
        json.dump(sub_index, f)

    print(f"  Got subtitles for {len(sub_index)} videos")
    return sub_index

