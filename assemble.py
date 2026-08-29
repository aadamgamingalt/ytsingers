"""
Assemble the final track:
- Extract each word slice from its clip
- Call audio_engine.exe to pitch shift to target note
- Place each word at the correct time position from song_data
- Export as MP3
"""

import os
import subprocess
import json
import struct
import wave
import numpy as np
import soundfile as sf


AUDIO_ENGINE = os.path.join(os.path.dirname(__file__), "audio_engine.exe")
SAMPLE_RATE = 44100


def extract_word_audio(clip_path, start, end, out_path):
    """Use ffmpeg to extract the exact word slice."""
    duration = max(0.05, end - start)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", clip_path,
            "-ss", str(start),
            "-t", str(duration),
            "-ar", str(SAMPLE_RATE),
            "-ac", "1",
            out_path
        ],
        capture_output=True
    )
    return os.path.exists(out_path)


def pitch_shift_word(word_wav, target_hz, out_wav):
    """Call the C++ audio engine to pitch shift."""
    if not os.path.exists(AUDIO_ENGINE):
        # Fallback: copy without shifting (for testing without compiled engine)
        import shutil
        shutil.copy(word_wav, out_wav)
        return

    result = subprocess.run(
        [AUDIO_ENGINE, "pitchshift", word_wav, str(target_hz), out_wav],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not os.path.exists(out_wav):
        import shutil
        shutil.copy(word_wav, out_wav)


def assemble_song(timed_clips, song_data, output_path):
    """
    Place each pitched word at its correct time position.
    song_data: [{word, time_in_song, duration, target_hz, target_midi}]
    """
    temp_pieces_dir = os.path.join(os.path.dirname(output_path), "pieces")
    os.makedirs(temp_pieces_dir, exist_ok=True)

    # Find total duration
    if not song_data:
        print("No song data to assemble")
        return
    total_duration = max(w["time_in_song"] + w["duration"] for w in song_data) + 1.0
    total_samples = int(total_duration * SAMPLE_RATE)
    mix = np.zeros(total_samples, dtype=np.float32)

    for song_word in song_data:
        word = song_word["word"]
        if word not in timed_clips:
            continue

        clip_info = timed_clips[word]
        word_wav = os.path.join(temp_pieces_dir, f"{word}_raw.wav")
        shifted_wav = os.path.join(temp_pieces_dir, f"{word}_shifted.wav")

        # Extract word audio
        ok = extract_word_audio(
            clip_info["clip_path"],
            clip_info["exact_start"],
            clip_info["exact_end"],
            word_wav
        )
        if not ok:
            continue

        # Pitch shift to target note
        pitch_shift_word(word_wav, song_word["target_hz"], shifted_wav)

        # Load shifted audio
        if not os.path.exists(shifted_wav):
            continue
        audio, sr = sf.read(shifted_wav)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        # Resample if needed
        if sr != SAMPLE_RATE:
            from scipy.signal import resample
            audio = resample(audio, int(len(audio) * SAMPLE_RATE / sr))

        # Place at correct position
        pos = int(song_word["time_in_song"] * SAMPLE_RATE)
        end_pos = min(pos + len(audio), total_samples)
        mix[pos:end_pos] += audio[:end_pos - pos]

    # Normalize
    peak = np.max(np.abs(mix))
    if peak > 0:
        mix = mix / peak * 0.9

    # Export as WAV first then convert to MP3 with ffmpeg
    tmp_wav = output_path.replace(".mp3", "_tmp.wav")
    sf.write(tmp_wav, mix, SAMPLE_RATE)
    subprocess.run(
        ["ffmpeg", "-y", "-i", tmp_wav, "-b:a", "320k", output_path],
        capture_output=True
    )
    os.remove(tmp_wav)
    print(f"  Mixed {len(song_data)} words into {output_path}")

