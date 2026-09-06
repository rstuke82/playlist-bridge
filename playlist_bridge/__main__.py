"""Playlist Bridge 2.0 command dispatcher."""

import sys

from . import __version__


def main() -> int:
    command = sys.argv[1].lower() if len(sys.argv) > 1 else "help"

    if command in {"web", "serve", "ui"}:
        from .api import run
        run()
        return 0

    if command in {"version", "--version", "-v"}:
        print(__version__)
        return 0

    print(f"Playlist Bridge {__version__}")
    print("Usage:")
    print("  python sync.py                 # existing CLI")
    print("  python sync.py --sync-all      # automated CLI sync")
    print("  python -m playlist_bridge web  # web UI/API on port 8787")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
