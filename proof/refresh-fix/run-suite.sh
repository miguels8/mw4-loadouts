#!/usr/bin/env bash
# Runs the job's tests under a memory cap. usage: run-suite.sh [py|node|all]; run from the repo root.
set -u
cap="systemd-run --user --scope -q -p MemoryMax=3G"
what="${1:-all}"
rc=0
if [ "$what" = py ] || [ "$what" = all ]; then
  for p in test_heartbeat.py test_kick.py test_pc.py; do
    $cap python3 -I -m unittest discover -s tests -p "$p" 2>&1 | tail -"${TAILN:-6}"
    rc=$((rc | ${PIPESTATUS[0]}))
  done
fi
if [ "$what" = node ] || [ "$what" = all ]; then
  $cap node --test --test-reporter=tap tests/engine.test.mjs tests/variants.test.mjs 2>&1 | grep -E "^# (tests|pass|fail)|not ok"
  rc=$((rc | ${PIPESTATUS[0]}))
fi
exit $rc
