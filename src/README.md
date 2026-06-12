# src/ — 6502 sources (ACME)

The Plus/4-side code. `demo.asm` is the top-level file the Makefile
assembles; everything else is `!src`'d into it or is a standalone
measurement/test program.

| file | role |
|---|---|
| `demo.asm` | the demo shell: BASIC stub, init (ROM bank-out, RAM IRQ vectors, font copy), 50 Hz raster IRQ (music + tick + atomic buffer flip), sequencer (text → slides → mega → held credits), 25/16.7 fps pacing (`wait_25` with per-scene stride `pace_v`), transitions, roam movement, render/blit, mega copy-forward double buffering + color program, fades, music fade logic |
| `decoder.asm` | the V10CS stream decoder, one macro body assembled in two flavors: `decode_frame` (skips write blanks — on-screen intra streams) and `decode_frame_pl` (plain O(1) skips — canvas decodes and the delta mega). See `v10cs/V10-SPEC.md` |
| `decoder_zp.asm` | decoder zero-page layout + table addresses, `!src`'d before any code |
| `test_decoder.asm` | minimal decoder harness assembled for the py65 byte-exactness check (`verify_decoder.py`) |
| `cycprobe.asm` | measures the real main-loop cycle budget per 50 Hz tick (net of IRQ + music) in VICE — result at `$0F00`, read by `tools/probe_budget.py` |
| `decprobe.asm` | measures real decode throughput (decodes the cube stream in a loop for 250 ticks) — count at `$0F20`, read by `tools/read_decprobe.py` |
| `tedtest.asm` | milestone-0 TED hardware probe (multicolor attribute semantics, RAM charset) — `make probe` |

Conventions: no self-modifying code and no illegal opcodes in anything
py65-verified; zone-local labels (`.x`) everywhere; the shell segment
must stay below `$1800` and the `$2000` code segment below `$3800`
(guard `!if`s enforce both).
