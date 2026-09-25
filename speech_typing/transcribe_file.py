"""Command-line transcription for an existing audio/video file."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from speech_typing import config
from speech_typing.transcribe import Transcriber


def convert_to_wav(source: Path) -> tuple[Path, bool]:
    """Return a 16 kHz mono WAV path.  The bool says whether it is temporary."""
    if source.suffix.lower() == ".wav":
        return source, False

    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required for non-WAV input files.")

    fd, temp_name = tempfile.mkstemp(prefix="speech_typing_", suffix=".wav")
    # Close the descriptor immediately; ffmpeg will create the file.
    import os
    os.close(fd)
    output = Path(temp_name)
    command = [
        "ffmpeg", "-y", "-i", str(source),
        "-ar", str(config.SAMPLE_RATE), "-ac", str(config.CHANNELS),
        "-c:a", "pcm_s16le", str(output),
    ]
    subprocess.run(command, check=True)
    return output, True


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe an existing audio/video file with whisper.cpp.")
    parser.add_argument("file", type=Path, help="Audio/video file to transcribe")
    parser.add_argument("--model", default=config.MODEL, choices=sorted(config.KNOWN_MODELS))
    parser.add_argument("--language", default=config.LANGUAGE, help="Whisper language code or auto")
    parser.add_argument(
        "--mode",
        default=config.TRANSCRIPTION_MODE,
        choices=("original", "translate_en"),
        help="Keep the spoken language or translate to English",
    )
    parser.add_argument("--output", type=Path, help="Optional output .txt path")
    args = parser.parse_args()

    if not args.file.is_file():
        parser.error(f"Input file not found: {args.file}")

    model_path = config.model_path(args.model)
    if not config.WHISPER_CLI.is_file():
        parser.error(f"whisper-cli not found: {config.WHISPER_CLI}")
    if not model_path.is_file():
        parser.error(f"Model not found: {model_path}")

    wav_path, temporary = convert_to_wav(args.file)
    try:
        transcriber = Transcriber(
            whisper_cli=config.WHISPER_CLI,
            model_path=model_path,
            language=args.language,
            mode=args.mode,
        )
        text = transcriber.transcribe(wav_path)
    finally:
        if temporary:
            wav_path.unlink(missing_ok=True)

    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
        print(args.output)
    else:
        print(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
