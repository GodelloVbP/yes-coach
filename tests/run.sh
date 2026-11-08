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
# a suite that crashes or prints no result counts as failed: its remaining checks never ran
bad=0
for t in tests/e2e/e2e_*.py; do
  echo "== $t"
  out=$(cd tests/e2e && python3 "$(basename "$t")" 2>&1); code=$?
  echo "$out" | grep -E "^(FAIL|passed|[0-9]+ .*passed)" || true
  if [ $code -ne 0 ] || ! echo "$out" | grep -qE "^(passed|[0-9]+ .*passed)"; then echo "CRASH $t (exit $code)"; echo "$out" | grep -E "Error|Traceback" | head -3; bad=1; fi
done
[ $bad -eq 0 ] || { echo "SOME SUITES FAILED"; exit 1; }
