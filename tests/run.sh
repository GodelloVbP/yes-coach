#!/bin/sh
# Build, then run every test. Needs Python with playwright, Google Chrome at /usr/bin/google-chrome, and Node.
set -e
cd "$(dirname "$0")/.."
python3 build.py
node tests/merge.test.mjs
node tests/plates.test.mjs
node tests/parity.test.mjs
node tests/starter.test.mjs
[ -f tests/progression.test.mjs ] && node tests/progression.test.mjs
for t in tests/e2e/e2e_*.py; do echo "== $t"; (cd tests/e2e && python3 "$(basename "$t")" 2>&1 | grep -E "^(FAIL|passed|[0-9]+ .*passed)" || true); done
