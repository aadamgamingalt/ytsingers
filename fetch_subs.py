"""
Download subtitles for the 100 latest non-live videos
from each channel using yt-dlp.
"""

import os
import subprocess
import glob
import json
from tqdm import tqdm


def fetch_channel_list(channel_url, temp_dir, limit=100):
    """Get list of latest video IDs from a channel, skipping lives and shorts."""
    result = subprocess.run(
        [
            "yt-dlp",
            "--flat-playlist",
            "--print", "%(id)s %(live_status)s %(duration)s",
            "--playlist-end", str(limit * 3),  # fetch extra to account for filtered ones
            channel_url
        ],
        capture_output=True, text=True
    )
    ids = []
    for line in result.stdout.splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        vid_id = parts[0]
        live_status = parts[1] if len(parts) > 1 else ""
        duration = parts[2] if len(parts) > 2 else "0"

        # Skip lives
        if live_status in ("is_live", "was_live", "is_upcoming"):
            continue
        # Skip shorts (under 60 seconds)
        try:
            if int(duration) < 60:
                continue
        except ValueError:
            pass

        ids.append(vid_id)
        if len(ids) >= limit:
            break

    return ids


def fetch_subtitles_for_video(video_id, out_dir):
    """Download subtitles for a single video. Returns path to .vtt file or None."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    subprocess.run(
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
    matches = glob.glob(os.path.join(out_dir, f"{video_id}*.vtt"))
    return matches[0] if matches else None


def fetch_all_subtitles(channel_urls, temp_dir, limit=100):
    """
    Fetch subtitles for latest videos across all channels.
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
        video_ids = fetch_channel_list(channel_url, temp_dir, limit)
        print(f"  Found {len(video_ids)} videos (latest {limit}, no lives/shorts)")

        for vid_id in tqdm(video_ids, desc=f"  Subtitles"):
            if vid_id in sub_index:
                continue
            vtt_path = fetch_subtitles_for_video(vid_id, subs_dir)
            if vtt_path:
                sub_index[vid_id] = vtt_path

    with open(index_path, "w") as f:
        json.dump(sub_index, f)

    print(f"  Got subtitles for {len(sub_index)} videos total")
    return sub_index
