# v10cs/ — the V10CS codec lab

The character-streaming codec the demo is built on, developed and
validated here on the PC before anything touched the 6502. The demo
itself only consumes `v10codec.py` (encoder), `v9codec.py` (codebook
training) and `core.js` (renderer); the rest is the codec's own test
rig.

| file | role |
|---|---|
| `V10-SPEC.md` | **the format spec**: codebook classes A/R/U, digram BPE, GOSUB stream subroutines, DITTO, fallback, pure-skip, header layout, intra mode |
| `V9-SPEC.md` | the predecessor spec (charset atlas study lives here, §6) |
| `v10codec.py` | encoder + bit-exact Python decoder (`decode_all`); intra mode codes every frame against a blank screen |
| `v9codec.py` | codebook training (singleton keys, K-sweep); intra mode excludes class R |
| `core.js` | the 3D renderer extracted from the original HTML demo (shapes, raster, charset atlases) — eval'd by `tools/gen_scenes.js` |
| `gen_frames.js` | renders the codec-development test frame sets (`frames_*.bin`) |
| `v10_decode.c`, `v9_decode.c` | independent C reference decoders (compiled by the local `Makefile`) |
| `cross_validate_v10.py`, `cross_validate.py` | encode in Python, decode in C, compare byte-exact |

The pipeline trusts this chain end to end: Python encoder ↔ C decoder
here, then Python encoder ↔ 6502 decoder via `verify_decoder.py` at the
repo root.
