# align_lyrics.py - Usage Guide

Force-aligns audio with lyrics using Whisper and outputs word timing as JSON.

## Requirements

- Python 3
- [openai-whisper](https://github.com/openai/whisper) (`pip install openai-whisper`)

## Basic Command

```bash
python3 align_lyrics.py <audio_file> <lyrics_file>
```

Output is saved to `result.json` by default.

## Arguments

| Argument | Description |
|----------|-------------|
| `audio`  | Path to audio file (mp3, wav, etc.) |
| `lyrics` | Path to lyrics `.txt` file |

## Options

| Flag | Short | Description |
|------|-------|-------------|
| `--output FILE` | `-o` | Output path (default: `result.json`) |
| `--model SIZE` | `-m` | Whisper model: `tiny`, `base`, `small`, `medium`, `large` (default: `base`) |
| `--milliseconds` | `-ms` | Times in milliseconds instead of seconds |
| `--simple` | `-s` | Flat `{word: time}` format instead of `[{word, start, end}]` |
| `--reactive` | `-r` | Grouped by lines with relative word timings (for reactive text rendering) |
| `--font FONT` | | Font string for reactive format (default: `bold 80px Baloo2`) |
| `--color COLOR` | | Color for reactive format (default: `white`) |

## Examples

```bash
# Basic usage
python3 align_lyrics.py song.mp3 lyrics.txt

# Custom output path, larger model
python3 align_lyrics.py song.mp3 lyrics.txt -o timings.json -m medium

# Simple format in milliseconds
python3 align_lyrics.py song.mp3 lyrics.txt -s -ms

# Reactive format with custom font/color
python3 align_lyrics.py song.mp3 lyrics.txt -r --font "bold 60px Arial" --color "yellow"
```

## Resources Folder Structure

For each song, create a folder with these files:

```
resources/my_song/
  song.mp3          # audio file (any format Whisper supports)
  lyrics.txt        # one line per lyric line
  lyrics_s.txt      # (optional) subtitle text, one line per lyric line
```

- **`lyrics.txt`** - The lyrics, with each line on its own line. Words are extracted and matched against the transcription.
- **`lyrics_s.txt`** - Optional subtitle override. If present, each line is attached as a `subtitle` field in reactive output. The filename is derived automatically: for `lyrics.txt` it looks for `lyrics_s.txt`. Must have the same number of lines as `lyrics.txt`.

Then run:

```bash
python3 align_lyrics.py resources/my_song/song.mp3 resources/my_song/lyrics.txt -r
```
