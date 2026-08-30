"""
Analyze the source song:
- Run Groq Whisper on full mix for word timestamps
- Extract melody (F0) with aubio for target notes per word
"""

import os
import math
import numpy as np
import soundfile as sf
import requests


def hz_to_midi(hz):
    if hz <= 0:
        return 60
    return int(round(69 + 12 * math.log2(hz / 440.0)))


def extract_melody(audio_path):
    """Extract F0 over time using aubio if available, else fallback."""
    audio, sr = sf.read(audio_path)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

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
        hop = 512
        times, pitches = [], []
        for i in range(0, len(audio) - 2048, hop):
            frame = audio[i:i+2048]
            zc = np.sum(np.diff(np.sign(frame)) != 0)
            freq = (zc / 2) * (sr / 2048)
            times.append(i / sr)
            pitches.append(float(freq))
        return times, pitches, sr


def get_pitch_at_time(times, pitches, t):
    if not times:
        return 220.0
    idx = min(range(len(times)), key=lambda i: abs(times[i] - t))
    hz = pitches[idx]
    return hz if hz > 50 else 220.0


def transcribe_song(audio_path, groq_api_key):
    """Run Groq Whisper on the song to get word timestamps."""
    print("  Transcribing song with Groq Whisper...")
    with open(audio_path, "rb") as f:
        response = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {groq_api_key}"},
            files={"file": (os.path.basename(audio_path), f, "audio/mpeg")},
            data={
                "model": "whisper-large-v3",
                "response_format": "verbose_json",
                "response_format": "verbose_json",
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
    print("  Extracting melody from song...")
    melody_times, melody_pitches, sr = extract_melody(song_path)

    transcript = transcribe_song(song_path, groq_api_key)

    word_data = []
    for w in transcript.get("words", []):
        t = w["start"]
        dur = w["end"] - w["start"]
        hz = get_pitch_at_time(melody_times, melody_pitches, t + dur / 2)
        midi = hz_to_midi(hz)
        word_data.append({
            "word": w["word"].strip().lower().replace(",", "").replace(".", "").replace("'", ""),
            "time_in_song": t,
            "duration": dur,
            "target_hz": hz,
            "target_midi": midi
        })

    print(f"  Got {len(word_data)} words from song")
    return word_data
