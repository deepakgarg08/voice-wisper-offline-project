"""Application entry point."""

import logging

from .app import Application


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    app = Application()
    app.run()
