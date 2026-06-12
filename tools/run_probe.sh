#!/bin/bash
# Run a PRG in xplus4 (warp, no sound), grab an exit screenshot.
# Usage: run_probe.sh <prg> <out.png> [limitcycles]
set -e
cd /mnt/d/Toyprojects/10_Plus4VectorStream
PRG="${1:-build/tedtest.prg}"
OUT="${2:-build/tedtest.png}"
CYCLES="${3:-40000000}"
export DISPLAY=:0
rm -f "$OUT"
timeout 180 xplus4 -default -warp +sound -limitcycles "$CYCLES" \
    -autostartprgmode 1 \
    -exitscreenshot "$OUT" -autostart "$PRG" >build/x4run.log 2>&1 || true
if [ -f "$OUT" ]; then
  echo "screenshot: $OUT ($(stat -c%s "$OUT") bytes)"
  grep -iE 'autostart' build/x4run.log | tail -8
else
  echo "NO SCREENSHOT - log tail:"
  tail -15 build/x4run.log
fi
