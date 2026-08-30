"""
Search subtitle files for target words.
Returns best match (video_id, timestamp) for each word.
"""

import re
import os
from collections import defaultdict


def parse_vtt_words(vtt_path):
    """
    Parse a .vtt file and return list of (word, start_seconds, end_seconds).
    """
    entries = []
    with open(vtt_path, encoding="utf-8", errors="ignore") as f:
        content = f.read()

    blocks = re.split(r"\n\n+", content)
    time_pattern = re.compile(
        r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})"
    )

    for block in blocks:
        lines = block.strip().splitlines()
        ts_line = None
        for line in lines:
            m = time_pattern.match(line)
            if m:
                ts_line = m
                break
        if not ts_line:
            continue

        def to_sec(h, m, s, ms):
            return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000

        start = to_sec(*ts_line.groups()[:4])
        end = to_sec(*ts_line.groups()[4:])

        text_lines = []
        past_ts = False
        for line in lines:
            if time_pattern.match(line):
                past_ts = True
                continue
            if past_ts:
                clean = re.sub(r"<[^>]+>", "", line).strip()
                if clean:
                    text_lines.append(clean)

        text = " ".join(text_lines)
        words = re.findall(r"[a-zA-Z]+", text)
        if not words:
            continue

        dur = (end - start) / len(words)
        for i, word in enumerate(words):
            entries.append((word.lower(), start + i * dur, start + (i+1) * dur))

    return entries


def find_words_in_subs(target_words, sub_index):
    """
    For each target word, find the best occurrence across all subtitle files.
    Returns dict: {word: {video_id, start, end, vtt_path}}
    """
    print("  Building word index from subtitles...")
    word_index = defaultdict(list)

    for video_id, vtt_path in sub_index.items():
        try:
            entries = parse_vtt_words(vtt_path)
            for word, start, end in entries:
                word_index[word].append({
                    "video_id": video_id,
                    "start": start,
                    "end": end,
                    "vtt_path": vtt_path
                })
        except Exception:
            pass

    hits = {}
    missing = []
    for word in target_words:
        if word in word_index and word_index[word]:
            best = max(word_index[word], key=lambda x: x["end"] - x["start"])
            hits[word] = best
        else:
            missing.append(word)

    if missing:
        print(f"  WARNING: Could not find these words: {missing}")

    print(f"  Matched {len(hits)}/{len(target_words)} words")
    return hits
