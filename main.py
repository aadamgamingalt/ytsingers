#!/usr/bin/env python3
"""
ytsingers - Make YouTubers sing any song
"""

import argparse
import json
import os
import sys
from pathlib import Path

from song_analyze import analyze_song
from fetch_subs import fetch_all_subtitles
from find_words import find_words_in_subs
from download_clips import download_word_clips
from transcribe import transcribe_clips
from assemble import assemble_song


def load_config(path="config.json"):
    with open(path) as f:
        return json.load(f)


def load_lyrics(path):
    words = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                for word in line.split():
                    clean = "".join(c for c in word.lower() if c.isalpha())
                    if clean:
                        words.append(clean)
    return words


def main():
    parser = argparse.ArgumentParser(description="Make YouTubers sing any song")
    parser.add_argument("--song", required=True, help="Path to song audio (mp3/wav)")
    parser.add_argument("--lyrics", required=True, help="Path to lyrics txt file")
    parser.add_argument("--channels", required=True, help="Path to channels txt file")
    parser.add_argument("--config", default="config.json", help="Config file path")
    parser.add_argument("--output", default="output/result.mp3", help="Output MP3 path")
    args = parser.parse_args()

    cfg = load_config(args.config)
    os.makedirs(cfg["temp_dir"], exist_ok=True)
    os.makedirs(cfg["output_dir"], exist_ok=True)

    print("[1/6] Analyzing song melody and word timing...")
    song_data = analyze_song(args.song, cfg["groq_api_key"], cfg["temp_dir"])

    print(f"[2/6] Fetching subtitles from channels...")
    channels = [
        l.strip() for l in open(args.channels)
        if l.strip() and not l.startswith("#")
    ]
    sub_index = fetch_all_subtitles(channels, cfg["temp_dir"])

    print("[3/6] Searching subtitles for required words...")
    lyrics_words = load_lyrics(args.lyrics)
    word_hits = find_words_in_subs(lyrics_words, sub_index)

    print("[4/6] Downloading word audio clips...")
    clips = download_word_clips(word_hits, cfg["temp_dir"], cfg["word_window_seconds"])

    print("[5/6] Transcribing clips for exact word timestamps...")
    timed_clips = transcribe_clips(clips, cfg["groq_api_key"])

    print("[6/6] Assembling final track...")
    assemble_song(timed_clips, song_data, args.output)

    print(f"Done! Output: {args.output}")


if __name__ == "__main__":
    main()

