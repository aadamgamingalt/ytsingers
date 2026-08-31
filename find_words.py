"""
Search subtitle files for target words.
Streams files one at a time to avoid memory issues.
"""

import re
import os


def clean_word(w):
    """Lowercase, strip punctuation and apostrophes."""
    return re.sub(r"[^a-z]", "", w.lower())


def parse_vtt_words(vtt_path):
    entries = []
    time_pattern = re.compile(
        r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})"
    )

    def to_sec(h, m, s, ms):
        return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000

    current_start = None
    current_end = None
    in_cue = False

    with open(vtt_path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            m = time_pattern.match(line)
            if m:
                g = m.groups()
                current_start = to_sec(*g[:4])
                current_end = to_sec(*g[4:])
                in_cue = True
                continue
            if in_cue and line and not line.isdigit():
                clean_line = re.sub(r"<[^>]+>", "", line).strip()
                raw_words = re.findall(r"[a-zA-Z']+", clean_line)
                words = [clean_word(w) for w in raw_words if clean_word(w)]
                if words:
                    dur = (current_end - current_start) / len(words)
                    for i, word in enumerate(words):
                        entries.append((
                            word,
                            current_start + i * dur,
                            current_start + (i+1) * dur
                        ))
                in_cue = False
            elif not line:
                in_cue = False

    return entries


def find_words_in_subs(target_words, sub_index):
    # Clean target words the same way
    target_set = set(clean_word(w) for w in target_words if clean_word(w))
    hits = {}

    print(f"  Searching {len(sub_index)} subtitle files...")
    for i, (video_id, vtt_path) in enumerate(sub_index.items()):
        if i % 50 == 0:
            print(f"  [{i}/{len(sub_index)}] matched {len(hits)}/{len(target_set)} words so far...")
        try:
            for word, start, end in parse_vtt_words(vtt_path):
                if word in target_set:
                    dur = end - start
                    if word not in hits or dur > (hits[word]["end"] - hits[word]["start"]):
                        hits[word] = {
                            "video_id": video_id,
                            "start": start,
                            "end": end,
                            "vtt_path": vtt_path
                        }
        except Exception:
            pass

    missing = [w for w in target_set if w not in hits]
    if missing:
        print(f"  WARNING: Could not find: {sorted(missing)}")
    print(f"  Matched {len(hits)}/{len(target_set)} unique words")
    return hits
