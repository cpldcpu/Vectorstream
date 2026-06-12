# V9CS Format Specification (v1)

V9CS extends V8CS with **screen-relative codebook classes**. It reaches
**31.7 B/frame** on the cube/Y reference animation (V8CS: 41.2), a 23%
reduction, at ~1704 decode cycles/frame (8.7% of a PAL frame, vs 8.1% for
V8CS). Gains hold across all four test animations (11–23%). The container
is the V8CS container with `version = 2`; DITTO, fallback and pure-skip are
unchanged.

## 1. The structural observation

V8's bytes are dominated by 2-byte fallbacks: (skip, char) pairs too rare
for a 176-entry absolute codebook. But the chars are not arbitrary. The
fixed-atlas matcher assigns **consecutive charset slots to consecutive
sub-cell edge offsets**, so when an edge crosses one offset quantum, the new
char at a cell is a small structural delta from screen content the decoder
already has:

| predictor of written char            | fraction of all deltas (cube/Y) |
|---------------------------------------|--------------------------------|
| `old ± 1` (same cell, offset step)     | 46.8%                          |
| `old ± {18..20, 30..35}` (family hop)  | ~15%                           |
| `above + d` (vertical coherence)       | large share of the remainder   |

These deltas generalize across absolute char values: one relative entry
covers what would otherwise be dozens of absolute pairs. This is also why
the report's LZ investigation (§"back-reference") came up negative — the
redundancy is not in the byte-stream history, it is in the screen itself,
where the decoder can read it for free.

## 2. File layout

Identical to V8CS except `version = 2` and reserved header bytes 13/14:

```
| 0      | magic "V8CS"                       |
| 4      | version = 2                        |
| 5,6    | width = 40, height = 25            |
| 7      | n_frames (2 B LE)                  |
| 9      | N = codebook size, <= 176          |
| 10     | F = fallback range, default 63     |
| 11     | KMAX, default 8                    |
| 12     | flags (bit 0: DITTO enabled)       |
| 13     | Na  (absolute entries)             |
| 14     | Nr  (relative entries)             |
| 15..23 | reserved, zero                     |
| 24     | cb_skip[0..N-1]                    |
| 24+N   | cb_val [0..N-1]                    |
| 24+2N  | frames as in V8CS                  |
```

Nu = N − Na − Nr "up" entries occupy the top of the codebook range.

## 3. Codebook classes

The codebook range `0x00..N-1` is split into three contiguous classes:

| opcode range      | class | written char                          |
|-------------------|-------|---------------------------------------|
| `0    .. Na-1`    | A     | `c = cb_val[op]`            (V8 semantics) |
| `Na   .. Na+Nr-1` | R     | `c = (screen[dst] + cb_val[op]) & 0xFF`    |
| `Na+Nr .. N-1`    | U     | `c = (screen[dst-40] + cb_val[op]) & 0xFF` |

All classes perform `dst += cb_skip[op]; screen[dst++] = c` and update
`(prev, prev2)` with the **resolved** `(skip, c)`, so DITTO semantics are
unchanged. Class R reads the old char at the destination *before* the
write; class U reads the already-decoded char one row up (the encoder never
emits class U for `dst < 40`).

Opcodes `N..0xAF` are reserved and must not appear.

## 4. Chain-reduced codebook hits

A pure-skip chain followed by a codebook hit is a valid stream, so a delta
with skip `s` can be emitted as `j` pure-skips plus a codebook entry whose
table skip is `rem = s − j·F` (cost `j+1` bytes vs `2 + s/F` for chained
fallback). The encoder searches `j = 0, 1, ...` and takes the smallest
covered `j`. This makes table entries reusable across skip residues and is
what rescues sparse animations (slow rotation), whose dominant cost is
recurring large-skip deltas.

Note this also exposes a **latent V8CS encoder bug**: a chained emit leaves
`prev_s = rem`, not `s`, so it must never seed a DITTO run. The V9 encoder
gates DITTO starters on `s < F` or coverage by an exact-skip (`j = 0`)
entry. (V8's encoder lacks this gate; a run of ≥3 identical deltas with
skip ≥ F decodes incorrectly. None of the four test animations triggers
it, but it is reachable.)

## 5. Codebook training

Each singleton-emitted delta contributes candidate keys
`('a', rem, c)`, `('r', rem, c−old)`, `('u', rem, c−above)` for every
chain-reduced `rem ≤ 255`, with per-key cost `j+1`. Selection minimizes
realized bytes via lazy greedy over a current-best-assignment objective.
Because greedy max-coverage over overlapping key classes carries no
guarantee against the disjoint absolute family, three starts are evaluated
by realized cost and the best kept:

1. greedy over all classes (chain-reduced),
2. greedy over absolute keys only,
3. the V8-equivalent selection (top-N raw-frequency exact pairs).

Start 3 makes V9CS ≥ V8CS by construction on any input.

## 6. Results (300 frames each, corner-diag atlas, scale 0.95)

| animation       | V8CS B/f | V9CS B/f | gain  | Na/Nr/Nu  |
|-----------------|----------|----------|-------|-----------|
| cube/Y 1 rad/s  | 41.16    | **31.71**| 23.0% | 36/91/49  |
| cube/X 1 rad/s  | 32.94    | 27.88    | 15.4% | 50/99/27  |
| cube/free       | 98.26    | 84.61    | 13.9% | 27/110/39 |
| cube/Y 0.25     | 19.04    | 16.09    | 15.5% | 78/77/21  |

The V8 baselines restrict codebook skips to ≤255 — i.e. what a legal V8CS
file can ship. (Frequency-sorting over raw deltas can otherwise select
unserializable pairs on sparse inputs; the slow-Y figure previously quoted
from such a codebook is not achievable on-format.)

Round-trip is verified byte-exact for all four animations in both the
Python and the ANSI C decoder, and the two decoders agree byte-exact
(`cross_validate.py`).

## 7. Decoder cycle budget (PAL 6502, 1 MHz, cube/Y)

| op class      | cycles/op | ops/frame | cycles/frame |
|---------------|-----------|-----------|--------------|
| A (absolute)  | ~38       | 3.07      | 117          |
| R (relative)  | ~46       | 10.75     | 494          |
| U (up)        | ~60       | 5.08      | 305          |
| fallback      | ~55       | 4.84      | 266          |
| pure-skip     | ~30       | 1.05      | 32           |
| DITTO-1       | 14+25K    | 1.21      | 212          |
| DITTO-2       | 14+50K    | 0.86      | 278          |
| **total**     |           |           | **~1704 (8.7%)** |

Class R adds `LDA (dst),Y / CLC / ADC cb_val,X` over class A (~+8 cycles).
Class U lazily derives a second ZP pointer (`dst − 40`, 16-bit SBC) per op
(~+22 cycles); it is not maintained in the hot pointer-advance path.

## 8. Reference implementation

- `v9codec.py`         — encoder/decoder/trainer
- `v9_decode.c`        — ANSI C decoder (also dumps screens for validation)
- `cross_validate.py`  — Python↔C byte-exact cross-check on all animations
- `gen_frames.js`      — regenerates the four test datasets from the
                          renderer extracted from the demo HTML (`core.js`)
