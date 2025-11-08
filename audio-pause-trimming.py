#!/usr/bin/env python3
"""
Trim pauses longer than N seconds in a video's audio track.

Dependencies:
  pip install pydub moviepy ffmpeg-python

Requires ffmpeg executable in PATH.
"""
import argparse
import subprocess
from pathlib import Path
from pydub import AudioSegment, silence

def extract_audio(video_path: Path, audio_path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000", str(audio_path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

def trim_pauses(
    audio_path: Path,
    output_path: Path,
    min_pause_ms: int = 2000,
    keep_silence_ms: int = 250,
    silence_threshold_db: float | None = None,
) -> None:
    audio = AudioSegment.from_file(audio_path)
    thresh = silence_threshold_db or audio.dBFS - 18

    silent_spans = silence.detect_silence(
        audio,
        min_silence_len=min_pause_ms,
        silence_thresh=thresh,
    )

    if not silent_spans:
        audio.export(output_path, format=output_path.suffix.lstrip("."))
        return

    trimmed = AudioSegment.silent(duration=0)
    cursor = 0

    for start, end in silent_spans:
        trimmed += audio[cursor:start]
        span_len = end - start

        if span_len > min_pause_ms:
            tail_start = max(start, end - keep_silence_ms)
            trimmed += audio[tail_start:end]
        else:
            trimmed += audio[start:end]

        cursor = end

    trimmed += audio[cursor:]
    trimmed.export(output_path, format=output_path.suffix.lstrip("."))

def mux_video_with_audio(video_path: Path, audio_path: Path, output_path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-c:v",
            "copy",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-shortest",
            str(output_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

def main():
    parser = argparse.ArgumentParser(description="Trim silences longer than a threshold in video audio.")
    parser.add_argument("video", type=Path, help="Input video file")
    parser.add_argument("--min-pause", type=float, default=2.0, help="Minimum pause (seconds) to trim")
    parser.add_argument("--keep", type=float, default=0.25, help="Silence to leave after trimming (seconds)")
    parser.add_argument("--silence-thresh", type=float, default=None, help="Silence threshold in dBFS (override auto)")
    parser.add_argument("--tmp-dir", type=Path, default=Path("tmp"), help="Temporary directory")
    parser.add_argument("--output", type=Path, help="Output video file (default: input_basename_trimmed.mp4)")
    args = parser.parse_args()

    tmp_dir = args.tmp_dir
    tmp_dir.mkdir(parents=True, exist_ok=True)

    audio_raw = tmp_dir / "audio_raw.wav"
    audio_trimmed = tmp_dir / "audio_trimmed.wav"
    output_video = args.output or args.video.with_name(f"{args.video.stem}_trimmed{args.video.suffix}")

    extract_audio(args.video, audio_raw)
    trim_pauses(
        audio_raw,
        audio_trimmed,
        min_pause_ms=int(args.min_pause * 1000),
        keep_silence_ms=int(args.keep * 1000),
        silence_threshold_db=args.silence_thresh,
    )
    mux_video_with_audio(args.video, audio_trimmed, output_video)

    print(f"✅ Done: {output_video}")

if __name__ == "__main__":
    main()
