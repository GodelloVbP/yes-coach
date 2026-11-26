#!/bin/sh
# Build, then run the tests a change can affect, in parallel. See tests/run.py for the options:
#   sh tests/run.sh            only what changed since origin/main can affect (plus the fast Node tests)
#   sh tests/run.sh --all      everything
#   sh tests/run.sh --list     say which tests that is, and why, without running them
#   sh tests/run.sh --map      run everything with code coverage and rebuild tests/affected-map.json
# Needs Python with playwright, Google Chrome at /usr/bin/google-chrome, and Node.
cd "$(dirname "$0")/.." && exec python3 tests/run.py "$@"
