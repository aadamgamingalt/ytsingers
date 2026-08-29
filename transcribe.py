"""
Send word clips to Groq Whisper for exact word-level timestamps.
Batches clips smartly to respect rate limits (20 RPM, 2000/day).
Clips under 10s count as 10s on Groq, so we send one per request.
"""

import os
import time
import requests
from tqdm import tqdm


GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
RATE_LIMIT_RPM = 18  # stay under 20 with buffer
MIN_INTERVAL = 60.0 / RATE_LIMIT_RPM


def transcribe_clip(clip_path, groq_api_key, target_word):
    """
    Transcribe one clip and find the exact timestamp of target_word.
    Returns (word_start, word_end) relative to clip start, or None.
    """
    with open(clip_path, "rb") as f:
        response = requests.post(
            GROQ_TRANSCRIBE_URL,
            headers={"Authorization": f"Bearer {groq_api_key}"},
            files={"file": (os.path.basename(clip_path), f, "audio/mpeg")},
            data={
                "model": "whisper-large-v3",
                "response_format": "verbose_json",
                "timestamp_granularities": "word",
                "language": "en"
            }
        )

    if response.status_code != 200:
        return None

    data = response.json()
    words = data.get("words", [])

    # Find the target word in the transcription
    for w in words:
        cleaned = w["word"].strip().lower()
        cleaned = "".join(c for c in cleaned if c.isalpha())
        if cleaned == target_word:
            return w["start"], w["end"]

    # Fallback: return middle of clip
    return None


def transcribe_clips(clips, groq_api_key):
    """
    Transcribe all clips and get exact word timestamps.
    Returns updated clips dict with exact_start, exact_end added.
    """
    timed_clips = {}
    last_request = 0

    for word, clip_info in tqdm(clips.items(), desc="  Transcribing"):
        # Rate limiting
        elapsed = time.time() - last_request
        if elapsed < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - elapsed)

        result = transcribe_clip(clip_info["clip_path"], groq_api_key, word)
        last_request = time.time()

        if result:
            exact_start, exact_end = result
            clip_info["exact_start"] = exact_start
            clip_info["exact_end"] = exact_end
        else:
            # Fallback to subtitle rough timing offset into clip
            window_start = clip_info.get("window_start", 0)
            rough_offset = clip_info["rough_start"] - window_start
            clip_info["exact_start"] = max(0, rough_offset)
            clip_info["exact_end"] = clip_info["exact_start"] + 0.3

        timed_clips[word] = clip_info

    return timed_clips

