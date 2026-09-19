"""Download a publicly available source document with a checksum manifest.

This intentionally does not scrape or republish textbook content. It records the
source file locally for a later, reviewed extraction step.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    target = Path("data/raw") / args.name
    target.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(Request(args.url, headers={"User-Agent": "LearnCraft content pipeline"}), timeout=30) as response:
        payload = response.read()
    target.write_bytes(payload)
    print(f"{target}: {len(payload)} bytes sha256={hashlib.sha256(payload).hexdigest()}")


if __name__ == "__main__":
    main()
