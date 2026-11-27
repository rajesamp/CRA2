"""Print the locally verified candidate for private, manual owner enrollment."""

import argparse
import os
import sqlite3

from .google import Settings, Unavailable
from .sessions import enrollment_candidate, session_store_from_env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["candidate-pin"])
    parser.parse_args()
    try:
        settings = Settings.from_env()
        firestore_settings = ("INVITATION_STAGE_FIRESTORE_PROJECT", "INVITATION_STAGE_FIRESTORE_DATABASE")
        if any(os.environ.get(name) for name in firestore_settings):
            pin = session_store_from_env().candidate(settings)
        else:
            pin = enrollment_candidate(settings, os.environ["INVITATION_STAGE_STATE_DIR"])
    except (ValueError, KeyError, OSError, sqlite3.Error, Unavailable):
        parser.exit(
            1, "A private verify-only configuration with one current verified candidate is required.\n"
        )
    print(pin)


if __name__ == "__main__":
    main()
