#!/usr/bin/env python3
"""Playlist Bridge CLI compatibility entry point for 2.0."""

from playlist_bridge.legacy import main


if __name__ == "__main__":
    raise SystemExit(main())
