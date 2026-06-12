#!/usr/bin/env python3
"""Verify the 6502 V10CS decoder byte-exact against the Python reference.

Slide scenes (intra, cropped window - see tools/scenelib.py):
  1. blank flavor (decode_frame), window prefilled with garbage: two
     sequential loops. Proves the skips + tail fill erase every stale
     cell (the garbage and each previous frame must vanish completely).
  2. blank flavor, random access: payloads decoded in a seeded random
     order by seeking next_pos. Proves decode-order independence
     (ping-pong or any sequence is legal).
  3. plain flavor (decode_frame_pl) on a window cleared before each
     frame - the canvas path the shell uses for top/side transitions.

Mega scene (delta, rotated frames + keyframe): plain flavor, keyframe
preloaded, two sequential loops (proves the seamless wrap), exactly like
the original delta demo.

Also reports max digram stack depth and max cycles per frame.

Usage: python3 verify_decoder.py
"""
import json
import os
import random
import re
import struct
import sys

from py65.devices.mpu6502 import MPU

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'v10cs'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import v10codec
from scenelib import SCREEN_SIZE, window, crop_frames

SENTINEL = 0x8000
BLOB_AT = 0x5000
SCREEN = 0x3C00
DSP = 0xDB


def load():
    syms = {}
    for line in open(os.path.join(ROOT, 'build', 'test_decoder_sym.txt')):
        m = re.match(r'\s*(\w+)\s*=\s*\$([0-9a-fA-F]+)', line)
        if m:
            syms[m.group(1)] = int(m.group(2), 16)
    prg = open(os.path.join(ROOT, 'build', 'test_decoder.prg'), 'rb').read()
    addr = prg[0] | (prg[1] << 8)
    mem = [0] * 65536
    for i, b in enumerate(prg[2:]):
        mem[addr + i] = b
    return mem, syms


def call(mpu, addr, watch_dsp=False):
    mpu.memory[0x01FF] = (SENTINEL - 1) >> 8
    mpu.memory[0x01FE] = (SENTINEL - 1) & 0xFF
    mpu.sp = 0xFD
    mpu.pc = addr
    c0 = mpu.processorCycles
    max_dsp = 0
    for _ in range(2_000_000):
        mpu.step()
        if watch_dsp and mpu.memory[DSP] > max_dsp:
            max_dsp = mpu.memory[DSP]
        if mpu.pc == SENTINEL:
            return mpu.processorCycles - c0, max_dsp
    raise RuntimeError(f'subroutine at ${addr:04x} did not return')


def payload_offsets(blob):
    h, off = v10codec.read_header(blob)
    offs, pos = [], off
    for _ in range(h['n_frames']):
        ln = struct.unpack('<H', blob[pos:pos+2])[0]
        offs.append(pos)
        pos += 2 + ln
    return offs


def fresh_mpu(mem0, syms, blob, win):
    mpu = MPU()
    mpu.memory[:] = mem0
    mpu.memory[BLOB_AT:BLOB_AT + len(blob)] = list(blob)
    mpu.memory[syms['scene_ptr']] = BLOB_AT & 0xFF
    mpu.memory[syms['scene_ptr'] + 1] = BLOB_AT >> 8
    call(mpu, syms['scene_setup'])
    we = SCREEN + win
    mpu.memory[syms['win_end']] = we & 0xFF
    mpu.memory[syms['win_end'] + 1] = we >> 8
    return mpu


class Stat:
    def __init__(self):
        self.bad = 0
        self.cyc = 0
        self.dsp = 0

    def frame(self, mpu, syms, entry, name, fr, want, win):
        cyc, d = call(mpu, syms[entry], watch_dsp=True)
        self.cyc = max(self.cyc, cyc)
        self.dsp = max(self.dsp, d)
        got = bytes(mpu.memory[SCREEN:SCREEN + win])
        if got != want[:win]:
            if self.bad < 3:
                diffs = [i for i in range(win) if got[i] != want[i]]
                print(f'  {name} frame {fr}: {len(diffs)} wrong cells, '
                      f'first at {diffs[0]} got={got[diffs[0]]:02x} '
                      f'want={want[diffs[0]]:02x}')
            self.bad += 1


def main():
    cfg = json.load(open(os.path.join(ROOT, 'tools', 'demo.json')))
    mem0, syms = load()
    allok = True
    for s in cfg['scenes']:
        name = s['name']
        path = os.path.join(ROOT, 'build', f'scene_{name}.v10cs')
        blob = open(path, 'rb').read()
        raw = open(os.path.join(ROOT, 'build', f'frames_{name}.bin'), 'rb').read()
        n = s['frames']
        st = Stat()

        if s.get('fx') == 'fade':
            # ---- mega: delta + keyframe, plain flavor, 2 loops ----
            key = raw[:SCREEN_SIZE]
            expected = v10codec.decode_all(path, prev0=key)
            assert len(expected) == n
            win = SCREEN_SIZE
            mpu = fresh_mpu(mem0, syms, blob, win)
            mpu.memory[SCREEN:SCREEN + win] = list(key)
            for fr in range(2 * n):
                st.frame(mpu, syms, 'decode_frame_pl', name, fr,
                         expected[fr % n], win)
            kind = 'delta 2 loops (pl)'
        else:
            # ---- slides: intra, cropped window ----
            frames = crop_frames(raw, n)
            w0, winrows = window(raw, n)
            win = winrows * 40
            expected = v10codec.decode_all(path)
            assert expected == frames, f'{name}: python ref != cropped frames'
            assert not any(any(f[win:]) for f in frames), name
            offs = payload_offsets(blob)

            # pass 1: blank flavor, garbage prefill, 2 sequential loops
            mpu = fresh_mpu(mem0, syms, blob, win)
            mpu.memory[SCREEN:SCREEN + win] = [0xAA] * win
            for fr in range(2 * n):
                st.frame(mpu, syms, 'decode_frame', name, fr,
                         frames[fr % n], win)

            # pass 2: blank flavor, seeded random access
            mpu = fresh_mpu(mem0, syms, blob, win)
            mpu.memory[SCREEN:SCREEN + win] = [0xAA] * win
            order = list(range(n))
            random.Random(0xC0DE).shuffle(order)
            for fr in order:
                tgt = BLOB_AT + offs[fr]
                mpu.memory[syms['next_pos']] = tgt & 0xFF
                mpu.memory[syms['next_pos'] + 1] = tgt >> 8
                mpu.memory[syms['frames_left']] = 1
                st.frame(mpu, syms, 'decode_frame', name, fr,
                         frames[fr], win)

            # pass 3: plain flavor on a cleared window (canvas path)
            mpu = fresh_mpu(mem0, syms, blob, win)
            for fr in range(n):
                mpu.memory[SCREEN:SCREEN + win] = [0] * win
                st.frame(mpu, syms, 'decode_frame_pl', name, fr,
                         frames[fr], win)
            kind = 'intra seq+rnd+pl   '

        if st.bad:
            allok = False
        status = 'OK' if st.bad == 0 else f'{st.bad} BAD FRAMES'
        print(f'{name:14s} {kind}  max {st.cyc:5d} cyc/f  '
              f'dstack<={st.dsp:2d}  win={win:4d}  ... {status}')
    sys.exit(0 if allok else 1)


if __name__ == '__main__':
    main()
