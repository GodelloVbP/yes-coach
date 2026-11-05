#!/bin/sh
# Build, then run every test. Fails (exit 1) if any of them fails.
# Needs Node, and for the end-to-end tests Python with playwright and a Chrome at /usr/bin/google-chrome.
cd "$(dirname "$0")/.." || exit 1
failed=""
check() { # check <name> <command...>
  name=$1; shift
  echo "== $name"
  "$@" || failed="$failed $name"
}
check build python3 build.py
check merge node tests/merge.test.mjs
check plates node tests/plates.test.mjs
check progression node tests/progression.test.mjs
check connector node --experimental-strip-types --no-warnings supabase/tests/mcp.test.mjs
for t in tests/e2e/e2e_*.py; do
  check "$(basename "$t")" sh -c 'cd tests/e2e && python3 "$(basename "$1")"' sh "$t"
done
if [ -n "$failed" ]; then echo "FAILED:$failed"; exit 1; fi
echo "all tests passed"
