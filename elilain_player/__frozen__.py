"""Frozen entry point for the packaged player. No console window, no network."""
import multiprocessing
import sys

from elilain_player.main import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())