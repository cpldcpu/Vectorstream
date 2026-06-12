#!/bin/bash
# Fetch Plus/4 ROMs (non-free, not in the Debian VICE package) from the VICE source mirror.
set -e
mkdir -p ~/.local/share/vice/PLUS4
cd ~/.local/share/vice/PLUS4
for f in kernal-318004-05.bin kernal-318005-05.bin basic-318006-01.bin 3plus1-317053-01.bin 3plus1-317054-01.bin; do
  if [ ! -f "$f" ]; then
    curl -sfLO "https://raw.githubusercontent.com/VICE-Team/svn-mirror/main/vice/data/PLUS4/$f" || echo "FAILED: $f"
  fi
  [ -f "$f" ] && echo "$f $(stat -c%s "$f")"
done
