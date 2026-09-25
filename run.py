#!/usr/bin/env python3

import fcntl
import os
import sys

LOCK_FILE = "/tmp/voice-typing.lock"

lock_fd = open(LOCK_FILE, "w")

try:
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print("Voice Typing is already running.")
    sys.exit(1)

from speech_typing.main import main

if __name__ == "__main__":
    main()