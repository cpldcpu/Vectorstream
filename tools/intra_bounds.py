#!/usr/bin/env python3
"""How close is V10CS-intra to what ANY codec could do on these frames?

Reference points per scene (per-frame bytes, avg/max):
  1. v10cs intra        — delta-vs-blank + shared codebook + digrams + GOSUB
  2. zlib standalone    — deflate -15 L9 per frame, no cross-frame context
                          (upper bound for any single-frame-only codec,
                          already generous: bit-oriented Huffman, 6502-hostile)
  3. zlib + dict        — deflate per frame with all PREVIOUS raw frames as
                          dictionary (information bound for cross-frame LZ
                          with random access; not directly realizable —
                          the 6502 has no raw frames to point into)
  4. zlib sequential    — whole scene concatenated / n (bound for sequential
                          delta-style coding, no random access)
"""
import json
import os
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')
sys.path.insert(0, os.path.join(ROOT, 'v10cs'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from intra_experiment import set_intra, build_best  # noqa: E402


def zl(data, dictionary=None):
    c = zlib.compressobj(9, zlib.DEFLATED, -15, 9, zlib.Z_DEFAULT_STRATEGY,
                         zdict=dictionary) if dictionary else \
        zlib.compressobj(9, zlib.DEFLATED, -15)
    return len(c.compress(data) + c.flush())


def main():
    cfg = json.load(open(os.path.join(ROOT, 'tools', 'demo.json')))
    scenes = {s['name']: s for s in cfg['scenes']}
    used = []
    for e in cfg['sequence']:
        if e['type'] == 'anim' and e['scene'] not in used:
            used.append(e['scene'])

    print(f'{"scene":12s} {"v10 intra":>12s} {"zlib alone":>12s} '
          f'{"zlib+dict":>12s} {"zlib seq":>9s}')
    for name in used:
        raw = open(os.path.join(BUILD, f'frames_{name}.bin'), 'rb').read()
        n = scenes[name]['frames']
        frames = [raw[i*1000:(i+1)*1000] for i in range(n)]

        set_intra(True)
        blob, payloads, K = build_best(frames, use_gosub=True)
        set_intra(False)
        v10s = [len(p) for p in payloads]

        alone = [zl(f) for f in frames]
        wdict = []
        for i, f in enumerate(frames):
            d = b''.join(frames[:i])[-32768:]
            wdict.append(zl(f, d) if d else zl(f))
        seq = zl(b''.join(frames)) / n

        print(f'{name:12s} {sum(v10s)/n:6.0f}/{max(v10s):4d} '
              f'{sum(alone)/n:6.0f}/{max(alone):4d} '
              f'{sum(wdict)/n:6.0f}/{max(wdict):4d} {seq:9.0f}')


if __name__ == '__main__':
    main()
