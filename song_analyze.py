"""
Analyze the source song:
- Separate vocals with Demucs
- Run Groq Whisper on vocals for word timestamps
- Extract melody (F0) with aubio/numpy for target notes per word
"""

import os
import subprocess
import json
import math
import tempfile
import numpy as np
import soundfile as sf
import requests


def hz_to_midi(hz):
    if hz <= 0:
        return 60  # default to middle C
    return int(round(69 + 12 * math.log2(hz / 440.0)))


def separate_vocals(song_path, temp_dir):
    """Use Demucs to isolate vocals from the song."""
    print("  Separating vocals with Demucs (this takes a few minutes)...")
    result = subprocess.run(
        ["python", "-m", "demucs", "--two-stems=vocals", "-o", temp_dir, song_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("  Demucs failed, using full mix for melody extraction")
        return song_path

    # Demucs outputs to temp_dir/htdemucs/<song_name>/vocals.wav
    song_name = os.path.splitext(os.path.basename(song_path))[0]
    vocals_path = os.path.join(temp_dir, "htdemucs", song_name, "vocals.wav")
    if os.path.exists(vocals_path):
        print("  Vocals separated successfully")
        return vocals_path
    return song_path


def extract_melody(audio_path):
    """Extract F0 (fundamental frequency) over time using numpy zero-crossing."""
    audio, sr = sf.read(audio_path)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)  # mono

    # Use aubio if available, otherwise fallback to simple autocorrelation
    try:
        import aubio
        hop_size = 512
        buf_size = 2048
        pitch_o = aubio.pitch("yin", buf_size, hop_size, sr)
        pitch_o.set_unit("Hz")
        pitch_o.set_silence(-40)

        pitches = []
        times = []
        pos = 0
        while pos + buf_size <= len(audio):
            frame = audio[pos:pos + buf_size].astype(np.float32)
            pitch = pitch_o(frame)[0]
            pitches.append(float(pitch))
            times.append(pos / sr)
            pos += hop_size

        return times, pitches, sr

    except ImportError:
        # Simple fallback: fixed hop autocorrelation
        hop = 512
        times, pitches = [], []
        for i in range(0, len(audio) - 2048, hop):
            frame = audio[i:i+2048]
            # Zero crossing rate as rough pitch proxy
            zc = np.sum(np.diff(np.sign(frame)) != 0)
            freq = (zc / 2) * (sr / 2048)
            times.append(i / sr)
            pitches.append(float(freq))
        return times, pitches, sr


def get_pitch_at_time(times, pitches, t):
    """Get the pitch in Hz closest to time t."""
    if not times:
        return 220.0
    idx = min(range(len(times)), key=lambda i: abs(times[i] - t))
    return pitches[idx]


def transcribe_song(vocals_path, groq_api_key):
    """Run Groq Whisper on the vocal track to get word timestamps."""
    print("  Transcribing song with Groq Whisper...")
    with open(vocals_path, "rb") as f:
        response = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {groq_api_key}"},
            files={"file": (os.path.basename(vocals_path), f, "audio/wav")},
            data={
                "model": "whisper-large-v3",
                "response_format": "verbose_json",
                "timestamp_granularities": "word",
                "language": "en"
            }
        )
    if response.status_code != 200:
        raise RuntimeError(f"Groq transcription failed: {response.text}")
    return response.json()


def analyze_song(song_path, groq_api_key, temp_dir):
    """
    Returns a list of dicts:
    {word, time_in_song, duration, target_hz, target_midi}
    """
    vocals_path = separate_vocals(song_path, temp_dir)
    transcript = transcribe_song(vocals_path, groq_api_key)
    melody_times, melody_pitches, sr = extract_melody(vocals_path)

    word_data = []
    words = transcript.get("words", [])
    for i, w in enumerate(words):
        t = w["start"]
        dur = w["end"] - w["start"]
        hz = get_pitch_at_time(melody_times, melody_pitches, t + dur / 2)
        midi = hz_to_midi(hz)
        word_data.append({
            "word": w["word"].strip().lower().replace(",", "").replace(".", ""),
            "time_in_song": t,
            "duration": dur,
            "target_hz": hz,
            "target_midi": midi
        })

    return word_data

