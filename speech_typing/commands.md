I also created transcribe_file.py.

Examples:

python3 -m speech_typing.transcribe_file recording.wav

English translation:

python3 -m speech_typing.transcribe_file recording.wav --mode translate_en

Original language:

python3 -m speech_typing.transcribe_file recording.wav --mode original

Use Medium:

python3 -m speech_typing.transcribe_file recording.wav --model medium

Video:

python3 -m speech_typing.transcribe_file lecture.mp4 --model medium --mode translate_en

and:

python3 -m speech_typing.transcribe_file lecture.mp4 \
    --model medium \
    --mode translate_en \
    --output lecture.txt

For non-WAV files, the helper uses ffmpeg to convert the input to 16-kHz mono WAV before passing it to whisper.cpp. That's consistent with whisper.cpp's current CLI requirements/documentation