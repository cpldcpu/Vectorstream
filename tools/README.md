# tools/ — PC-side pipeline + measurement (WSL: node, python3, VICE)

## Build pipeline (run by the Makefile, in this order)

| file | role |
|---|---|
| `demo.json` | the whole demo as data: scenes (shape, tumble turns, frame counts, scale) and the sequence (durations, palettes, tunes, enter/exit directions, flags) |
| `gen_scenes.js` | renders every scene to raw screen-code frames via the renderer in `v10cs/core.js` (corner-diag atlas); rationally periodic rotations so loops are byte-exact |
| `encode_scenes.py` | V10CS-encodes the frames: slides as INTRA streams (cropped to the object window), the mega as a rotated DELTA stream + keyframe; prints the B/frame budget table |
| `scenelib.py` | shared helpers: object extents, decode-window cropping |
| `pack_assets.py` | lays out `build/assets.asm`: 52-byte sequence records, movement sine tables, fade ramps, text records, `!bin` includes; hard-fails the build past `$F7FF` |

## Measurement / design studies

| file | role |
|---|---|
| `probe_budget.py` | runs `src/cycprobe.asm` in VICE → real cycles per 50 Hz tick net of IRQ + music (the 44 k/frame budget) |
| `read_decprobe.py` | runs `src/decprobe.asm` → real decode throughput on target |
| `intra_experiment.py` | intra vs delta coding cost (the +2.8 % result) |
| `intra_bounds.py` | V10CS-intra vs deflate bounds (it matches dictionary-deflate) |
| `analyze_probe.py` | decodes the `tedtest` probe screenshot into TED semantics |

## VICE remote-monitor diagnostics (debugging the running demo)

| file | role |
|---|---|
| `diag_run.py` | screenshots + zp/engine/music state at given wall times |
| `diag_hist.py` | dumps the pacing histograms (`$0F10` lateness, `$0F14` render tick-spans) |
| `catch_entry.py` | polls the sequencer entry index, screenshots a specific scene |
| `realtime_shot.py`, `series_shot.py` | plain timed screenshots |
| `mon_dump.py` | TED register + screen/attr/zp dump |
| `render_ref.py`, `crop.py` | render a raw frame to PNG / crop-zoom a screenshot for inspection |
| `run_probe.sh`, `get_roms.sh` | boot a prg headless for an exit screenshot / fetch VICE ROMs |

Caveats that bite: monitor halts freeze *emulated* time (do cadence math
on emulated counters only); code symbol addresses shift on every
rebuild (scripts that need them parse `build/demo_sym.txt`); the 8-bit
diagnostic counters wrap (zero them via the monitor `f` command before
the window you measure).
