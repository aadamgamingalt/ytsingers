# ytsingers

Automatically make YouTubers sing any song.

## How it works

1. Fetches subtitles from YouTube channels via yt-dlp
2. Searches subtitles for every word in your target song
3. Downloads the audio segment containing each word
4. Uses Groq Whisper API to get exact word timestamps
5. Extracts melody/timing from the original song audio
6. C++ audio engine pitch-shifts each word clip to the correct note
7. Assembles everything into one MP3

## Setup

```
pip install -r requirements.txt
```

Copy `config.example.json` to `config.json` and fill in your keys.

## Usage

```
python main.py --song song.mp3 --lyrics lyrics.txt --channels channels.txt
```

## Building the audio engine

Push to main — GitHub Actions compiles `audio_engine.exe` automatically.
Download it from the Actions artifacts tab and place it in this folder.

