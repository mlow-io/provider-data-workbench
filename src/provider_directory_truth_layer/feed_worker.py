"""Run explicitly against one local storage root; no scheduler installation."""
import argparse
import signal
import threading
from pathlib import Path

from .intake_store import IntakeStore
from .managed_feed import ManagedFeed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--feed-id')
    args = parser.parse_args()
    root = args.root.resolve()
    # The HTTP workbench initializes/migrates storage; attachment never recovers live attempts.
    service = ManagedFeed(IntakeStore.open_existing(root / 'directory.sqlite3', root))
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        result = service.run_once(args.feed_id)
        print(result, flush=True)
        if args.once:
            break
        stop.wait(1 if result.get('processed') else 5)


if __name__ == '__main__':
    main()
