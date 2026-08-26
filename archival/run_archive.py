"""
Demo/CLI entry point: archive a single URL via the Wayback Machine and
print the resulting snapshot URL.

Usage (with IA_ACCESS_KEY / IA_SECRET_KEY set in the environment):
    python -m archival.run_archive "https://bpsc.bihar.gov.in/..."
"""

from __future__ import annotations

import argparse
import logging
import sys

from archival.wayback_client import archive_url

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    args = parser.parse_args()

    snapshot = archive_url(args.url)
    if snapshot:
        print(f"Archived: {snapshot}")
    else:
        print("Archival failed -- see the WARNING log above for why.")


if __name__ == "__main__":
    sys.exit(main())
