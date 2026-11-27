"""Print the locally verified candidate for private, manual owner enrollment."""

import argparse
import os
import sqlite3

from .google import Settings
from .sessions import enrollment_candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["candidate-pin"])
    parser.parse_args()
    try:
        pin = enrollment_candidate(Settings.from_env(), os.environ["INVITATION_STAGE_STATE_DIR"])
    except (ValueError, KeyError, OSError, sqlite3.Error):
        parser.exit(
            1, "A private verify-only configuration with one current verified candidate is required.\n"
        )
    print(pin)


if __name__ == "__main__":
    main()
