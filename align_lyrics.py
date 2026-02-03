#!/usr/bin/env python3
"""
Force-align audio with lyrics and output word timing as JSON.
Uses Whisper transcription matched against provided lyrics.

Usage: python3 align_lyrics.py audio.mp3 lyrics.txt [--output output.json]
"""

import argparse
import json
import sys
import re
import os
from difflib import SequenceMatcher
import whisper


def clean_word(word: str) -> str:
    """Clean a word for comparison."""
    return re.sub(r'[^\w\']', '', word.lower())


def get_lyrics_words(lyrics_path: str) -> list:
    """Extract words from lyrics file."""
    with open(lyrics_path, 'r') as f:
        lines = f.readlines()

    # Split into words, keeping track of original form and line number
    words = []
    for line_num, line in enumerate(lines):
        for match in re.finditer(r'[\w\']+', line):
            words.append({
                'original': match.group(),
                'clean': clean_word(match.group()),
                'line': line_num
            })
    return words


def align_lyrics(audio_path: str, lyrics_path: str, model_name: str = "base") -> list:
    """
    Align audio with lyrics using Whisper transcription matched to lyrics.
    """
    # Load lyrics
    lyrics_words = get_lyrics_words(lyrics_path)
    lyrics_clean = [w['clean'] for w in lyrics_words]

    print(f"Loaded {len(lyrics_words)} words from lyrics", file=sys.stderr)

    # Load Whisper model
    print(f"Loading Whisper model '{model_name}'...", file=sys.stderr)
    model = whisper.load_model(model_name)

    # Read lyrics text for prompt
    with open(lyrics_path, 'r') as f:
        lyrics_text = f.read().strip()

    # Transcribe with word timestamps
    print("Transcribing audio...", file=sys.stderr)
    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        initial_prompt=lyrics_text,  # Guide towards expected words
        condition_on_previous_text=True
    )

    # Extract transcribed words with timestamps
    transcribed = []
    for segment in result.get("segments", []):
        for word_info in segment.get("words", []):
            word = word_info.get("word", "").strip()
            if word:
                transcribed.append({
                    'word': word,
                    'clean': clean_word(word),
                    'start': word_info.get("start", 0),
                    'end': word_info.get("end", 0)
                })

    print(f"Transcribed {len(transcribed)} words", file=sys.stderr)

    # Match transcribed words to lyrics using sequence matching
    print("Matching to lyrics...", file=sys.stderr)

    trans_clean = [w['clean'] for w in transcribed]

    # Use SequenceMatcher to find matching blocks
    matcher = SequenceMatcher(None, lyrics_clean, trans_clean)

    # Build result: for each lyrics word, find its timestamp
    result_timings = []
    lyrics_to_trans = {}  # Map lyrics index to transcribed index

    for block in matcher.get_matching_blocks():
        lyrics_start, trans_start, size = block
        for i in range(size):
            lyrics_idx = lyrics_start + i
            trans_idx = trans_start + i
            if lyrics_idx < len(lyrics_words) and trans_idx < len(transcribed):
                lyrics_to_trans[lyrics_idx] = trans_idx

    # Build output with lyrics words and their timestamps
    for i, lw in enumerate(lyrics_words):
        if i in lyrics_to_trans:
            trans_idx = lyrics_to_trans[i]
            tw = transcribed[trans_idx]
            result_timings.append({
                'word': lw['original'],
                'start': round(tw['start'], 2),
                'end': round(tw['end'], 2),
                'line': lw['line']
            })
        else:
            # Word not matched - interpolate or mark as unknown
            # Try to interpolate from neighbors
            prev_time = 0
            next_time = None

            # Find previous matched word
            for j in range(i - 1, -1, -1):
                if j in lyrics_to_trans:
                    prev_time = transcribed[lyrics_to_trans[j]]['end']
                    break

            # Find next matched word
            for j in range(i + 1, len(lyrics_words)):
                if j in lyrics_to_trans:
                    next_time = transcribed[lyrics_to_trans[j]]['start']
                    break

            if next_time is not None:
                # Interpolate
                est_time = (prev_time + next_time) / 2
            else:
                est_time = prev_time + 0.3  # Estimate 0.3s after previous

            result_timings.append({
                'word': lw['original'],
                'start': round(est_time, 2),
                'end': round(est_time + 0.2, 2),
                'estimated': True,
                'line': lw['line']
            })

    matched = sum(1 for i in range(len(lyrics_words)) if i in lyrics_to_trans)
    print(f"Matched {matched}/{len(lyrics_words)} words ({100*matched//len(lyrics_words)}%)", file=sys.stderr)

    return result_timings


def load_subtitles(lyrics_path: str) -> list:
    """Load subtitle file if it exists (lyrics_s.txt for lyrics.txt)."""
    # Build subtitle path: add _s before extension
    base, ext = os.path.splitext(lyrics_path)
    subtitle_path = f"{base}_s{ext}"

    if not os.path.exists(subtitle_path):
        return None

    print(f"Loading subtitles from {subtitle_path}", file=sys.stderr)
    with open(subtitle_path, 'r') as f:
        return [line.rstrip('\n\r') for line in f.readlines()]


def format_reactive(word_timings: list, font: str = "bold 80px Baloo2", color: str = "white", subtitles: list = None) -> list:
    """Format output as reactive text lines with relative word timings."""
    # Group words by line
    lines = {}
    for word in word_timings:
        line_num = word.get('line', 0)
        if line_num not in lines:
            lines[line_num] = []
        lines[line_num].append(word)

    result = []
    for line_num in sorted(lines.keys()):
        line_words = lines[line_num]
        if not line_words:
            continue

        # Line starts at the first word's start time
        line_start = line_words[0]['start']

        # Build word objects with relative times
        words_array = []
        prev_start = line_start
        for word in line_words:
            # Time is relative to previous word's start (delta)
            relative_time = round(word['start'] - prev_start, 2)
            words_array.append({
                'font': font,
                'color': color,
                'time': relative_time,
                'text': word['word'].upper()
            })
            prev_start = word['start']

        line_obj = {
            'text': json.dumps(words_array, ensure_ascii=False),
            'isJson': True,
            'locked': True,
            'seconds': line_start
        }

        # Add subtitle if available for this line
        if subtitles and line_num < len(subtitles):
            line_obj['subtitle'] = subtitles[line_num].upper()

        result.append(line_obj)

    return result


def format_output(word_timings: list, use_milliseconds: bool = False, simple: bool = False) -> dict:
    """Format output as requested."""
    if simple:
        result = {}
        word_count = {}
        for item in word_timings:
            word = item["word"].lower()
            clean = re.sub(r'[^\w\']', '', word)
            if not clean:
                continue

            if clean in word_count:
                word_count[clean] += 1
                key = f"{clean}_{word_count[clean]}"
            else:
                word_count[clean] = 1
                key = clean

            time_val = item["start"]
            if use_milliseconds:
                time_val = int(time_val * 1000)
            result[key] = time_val
        return result
    else:
        if use_milliseconds:
            return [
                {
                    "word": item["word"],
                    "start": int(item["start"] * 1000),
                    "end": int(item["end"] * 1000)
                }
                for item in word_timings
            ]
        return word_timings


def main():
    parser = argparse.ArgumentParser(
        description="Force-align audio with lyrics and output word timing as JSON"
    )
    parser.add_argument("audio", help="Path to audio file (mp3, wav, etc.)")
    parser.add_argument("lyrics", help="Path to lyrics text file")
    parser.add_argument(
        "--output", "-o",
        help="Output JSON file (default: stdout)"
    )
    parser.add_argument(
        "--model", "-m",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base). Larger = more accurate but slower"
    )
    parser.add_argument(
        "--milliseconds", "-ms",
        action="store_true",
        help="Output times in milliseconds instead of seconds"
    )
    parser.add_argument(
        "--simple", "-s",
        action="store_true",
        help="Simple output format: {word: time} instead of [{word, start, end}]"
    )
    parser.add_argument(
        "--reactive", "-r",
        action="store_true",
        help="Reactive format: grouped by lines with relative word timings"
    )
    parser.add_argument(
        "--font",
        default="bold 80px Baloo2",
        help="Font for reactive format (default: 'bold 80px Baloo2')"
    )
    parser.add_argument(
        "--color",
        default="white",
        help="Color for reactive format (default: 'white')"
    )

    args = parser.parse_args()

    timings = align_lyrics(args.audio, args.lyrics, args.model)

    # Load subtitles if available
    subtitles = load_subtitles(args.lyrics)

    if args.reactive:
        output = format_reactive(timings, args.font, args.color, subtitles)
    else:
        output = format_output(timings, args.milliseconds, args.simple)

    json_output = json.dumps(output, indent=2, ensure_ascii=False)

    # Always write to result.json
    output_path = args.output if args.output else "result.json"
    with open(output_path, 'w') as f:
        f.write(json_output)
    print(f"Saved to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
