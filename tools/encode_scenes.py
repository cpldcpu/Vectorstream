#!/usr/bin/env python3
"""Encode the rendered demo scenes to V10CS.

Slide scenes (the movable ones) are encoded INTRA (header flags bit 2):
every frame is coded against a blank screen, so any payload reconstructs
its frame independently - the decoder loops by restarting at payload 0,
any play order is legal, and no raw keyframes are shipped. The on-screen
6502 decoder's skips write blank chars as they advance, erasing whatever
was decoded before. Frames are cropped to the decode window (rows above
the object's top margin row stripped - see tools/scenelib.py) so the
blank writes can never land above the char matrix while the object roams.

The mega scene (fx == "fade") stays DELTA-coded: intra would rewrite all
~940 of its cells every frame, measured at 59k cycles against a 44k
budget. It never moves and never needs random access, so it keeps the
rotated-frames trick (payload i transforms frame i -> i+1, the last
payload wraps to frame 0, frame 0 ships as a raw keyframe).

Usage: python3 tools/encode_scenes.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'v10cs'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import v10codec
from scenelib import SCREEN_SIZE, crop_frames


def main():
    cfg = json.load(open(os.path.join(ROOT, 'tools', 'demo.json')))
    build = os.path.join(ROOT, 'build')
    total = 0
    print(f"{'scene':14s} {'mode':>5s} {'frames':>6s} {'K':>3s} "
          f"{'B/frame':>8s} {'stream B':>9s}")
    for s in cfg['scenes']:
        raw = open(os.path.join(build, f"frames_{s['name']}.bin"), 'rb').read()
        n = s['frames']
        assert len(raw) == n * SCREEN_SIZE, s['name']
        out = os.path.join(build, f"scene_{s['name']}.v10cs")
        if s.get('fx') == 'fade':           # mega: delta, rotated loop
            frames = [raw[i*SCREEN_SIZE:(i+1)*SCREEN_SIZE] for i in range(n)]
            enc = frames[1:] + frames[:1]
            st = v10codec.write_file(out, enc, prev0=frames[0])
            mode = 'delta'
        else:                               # slides: intra, cropped window
            frames = crop_frames(raw, n)
            st = v10codec.write_file(out, frames, intra=True)
            mode = 'intra'
        bpf = sum(st['sizes']) / n
        total += st['file_bytes']
        print(f"{s['name']:14s} {mode:>5s} {n:6d} {st['K']:3d} "
              f"{bpf:8.2f} {st['file_bytes']:9d}")
    print(f"{'TOTAL':14s} {'':5s} {'':6s} {'':3s} {'':8s} {total:9d}")


if __name__ == '__main__':
    main()
