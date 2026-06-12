# V10CS Format Specification (v1)

V10CS = V9CS + two opcode classes that close most of the remaining gap to
general-purpose compressors while staying pure table/pointer machinery on a
6502 — no bit-serial I/O. On the cube/Y reference animation it reaches
**23.4 B/frame** (V8CS: 41.2, −43%; V9CS: 31.7) at ~1836 decode
cycles/frame (9.3% of a PAL frame).

## 1. Where the gap to deflate was

Deflate applied to the V9CS stream itself still gained 28–44%, splitting
into two mechanisms:

1. **Symbol entropy.** V9 ops carry 5.7–7.3 bits but occupy a byte.
   Adjacent ops also correlate (run grammar: starter→ditto, cb→cb).
2. **Long-range repetition.** cube/Y is near-periodic (period π ≈ 157
   frames at 1 rad/s · 50 Hz); whole op sequences recur thousands of bytes
   back. No per-frame mechanism can see this.

Bit-serial Huffman costs ~20–25 cycles/bit (≈5000 cycles/frame — over
budget). The two classes below capture the same redundancy byte-aligned.

## 2. Digram opcodes (byte-pair encoding)

K codebook slots are reallocated as digram codes `[N, N+K)`. A digram
expands to two stream symbols, each of which may itself be a digram
(classic BPE; expansion uses a small stack, max observed depth 5, decoder
reserves 16). This jointly captures sub-byte symbol entropy and short-range
op-sequence repetition — the dominant gap component on cube/X and slow-Y.

**Alphabet discipline:** fallback tokens (op + char literal) are atomic and
never merged, so digram codes appear only in opcode position; char literals
never collide with the digram range. On a 6502 the literal is always
fetched raw from the current source pointer.

K is a per-file parameter; the encoder sweeps a grid and keeps the smallest
file (deltas-heavy content prefers a large codebook, repetitive content
prefers digram slots).

## 3. GOSUB — stream subroutines

Opcode `0xAE off_lo off_hi len` (flags bit 1) re-executes `len` previously
stored stream bytes at absolute offset `off` in the frame-data region, then
returns. Single return slot, no nesting; source regions are token-aligned,
contain no GOSUB, lie within one payload, and are ≤255 bytes.

Correctness is contextual for free: the re-executed bytes are **literally
identical** to what would have been stored inline, so DITTO prev-registers,
relative codebook classes, and screen state all behave exactly as if the
bytes were in place. The decoder needs the file in memory (it is, in a
demo) and one saved pointer pair — ~55 cycles per call, ~0.6 calls/frame.

This is the mechanism that finally captures the π-periodicity of axial
rotations: frame f's payload largely matches frame f−157's. The earlier
V8-report conclusion that back-references are net-negative was an artifact
of (a) measuring only cube/Y at V8's redundancy level and (b) within-frame
references; the periodic cross-frame matches are worth ~5 B/frame on Y and
X, and the encoder simply emits no GOSUBs where there are no matches
(cube/free: 0.03/frame).

## 4. Opcode map

```
0x00 .. N-1        codebook (classes A/R/U, V9CS semantics)
N    .. N+K-1      digram codes                  (N + K <= 0xAE)
0xAE               GOSUB (flags bit 1; else reserved)
0xAF               reserved
0xB0 .. 0xBF       DITTO-1 / DITTO-2
0xC0 .. 0xFE       fallback (skip in op, char literal follows)
0xFF               pure-skip F
```

Header: V8CS container, `version = 3`; byte 13 = Na, 14 = Nr, 15 = K;
flags bit 0 = DITTO, bit 1 = GOSUB. Digram tables `first[K]`, `second[K]`
follow the codebook tables.

## 5. Results (300 frames, payload B/frame)

| animation  | V8CS  | V9CS  | V10CS | zlib(raw) | zlib(xor-Δ) | lzma(raw) |
|------------|-------|-------|-------|-----------|-------------|-----------|
| cube/Y     | 41.16 | 31.71 | **23.43** | 46.15 | 38.87 | 20.16 |
| cube/X     | 32.94 | 27.88 | **16.49** | 25.68 | 26.50 | 13.19 |
| cube/free  | 98.26 | 84.61 | **80.66** | 96.33 | 88.28 | 70.72 |
| slow Y     | 19.04 | 16.09 | **10.95** | 21.87 | 15.90 | 13.72 |

V10CS beats deflate on every animation regardless of whether deflate sees
raw screens or XOR deltas, and beats LZMA on slow-Y. The remaining LZMA gap
on Y/X/free is range-coded entropy — not reachable byte-aligned within the
cycle budget. Optimal K chosen per file: 48/48/32/48.

Round-trip verified byte-exact on all four animations in Python and ANSI C;
both decoders agree (`cross_validate_v10.py`).

## 6. Decoder cycle budget (PAL 6502, executed ops/frame)

| | cube/Y | cube/X |
|---|---|---|
| codebook A/R/U      | 2.05 / 10.43 / 5.33 | 2.11 / 6.02 / 0.91 |
| fallback / pure-skip | 5.93 / 1.23 | 4.90 / 5.54 |
| DITTO-1 / DITTO-2   | 1.21 / 0.86 | 5.31 / 0.04 |
| digram expansions (~18 cyc) | 3.92 | 8.47 |
| GOSUB calls (~55 cyc)       | 0.63 | 0.56 |
| **total cycles**    | **~1836 (9.3%)** | **~1944 (9.9%)** |

Both within the <10%-of-PAL-frame design budget. The digram expander is an
8-cell ZP stack with `LDA tbl1,X / PHA`-style fetch; GOSUB saves/restores
one pointer pair.

## 7. Reference implementation

- `v10codec.py`            — encoder (K sweep) / decoder
- `v10_decode.c`           — ANSI C decoder
- `cross_validate_v10.py`  — Python↔C byte-exact cross-check
- requires `v9codec.py` (delta extraction, codebook training, V9 encode)
