"""Entry point. All actual wiring lives in app.py -- this just configures
logging, builds the Application, and reports startup failures clearly.
"""

from __future__ import annotations

import sys

from . import config
from .app import Application
from .exceptions import ConfigError, KeyboardAccessError, MicrophoneNotFoundError
from .logging_setup import setup_logging


def main() -> None:
    logger = setup_logging(
        config.LOG_LEVEL, config.LOG_FILE, config.LOG_MAX_BYTES, config.LOG_BACKUP_COUNT
    )

    try:
        app = Application()
    except ConfigError as exc:
        logger.error("Configuration error:\n%s", exc)
        sys.exit(1)
    except (KeyboardAccessError, MicrophoneNotFoundError) as exc:
        logger.error(str(exc))
        sys.exit(1)
    except Exception as exc:
        logger.error("Startup failed: %s", exc)
        sys.exit(1)

    app.run()


if __name__ == "__main__":
    main()
