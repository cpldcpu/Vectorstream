#!/usr/bin/env python3
"""Generate build/assets.asm for the demo from tools/demo.json.

Emits (org $4C00, after video matrix A, matrix B and the canvas):
  - seq_count + seq_table: one 52-byte record per sequence entry:
      +0  type        0=text 1=slide-anim (intra) 2=mega-anim (delta, fade)
      +1  data lo/hi  (anim: v10cs blob;   text: unused/0)
      +3  aux  lo/hi  (mega: keyframe bin; text: text records)
      +5  ticks lo/hi (ROAM/RUN duration, 50 Hz)
      +7  tune        ($FF = keep current)
      +8  border      ($FF = pulse with music via fxborder)
      +9  mvx lo/hi   movement tables, 256 bytes each (slides)
      +11 mvy lo/hi
      +13 keylen lo/hi   slides: decode window bytes = winrows*40
                         mega:   keyframe copy length = (r1+2)*40
      +15 w0             window top row when centered (= r0-1)
      +16 winrows        window height (= r1-r0+3)
      +17 enter_off      transition start offset, signed chars
      +18 exit_off       transition end offset, signed chars
      +19 flags          bits 0-1 enter dir, bits 2-3 exit dir
                         (0=bottom 1=top 2=left 3=right), bit 4 musfade
                         (fade the music out over the entry's last 5 s),
                         bit 5 text glow-pulse fx
      +20 32 bytes: fade ramps (bg/mc1/mc2/attr)
  - per-scene movement tables: mx bias 128, my bias 64, amplitudes from
    the measured extents (one blank char/row of margin to every border
    the roam can reach - the margins are what erase the movement trail
    under the blank-writing decoder); mx[0]=128, my[0]=64 (transitions
    end centered).
  - mega keyframe, text records, !bin includes for the streams.

Usage: python3 tools/pack_assets.py
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from scenelib import SCREEN_SIZE, extents

DIRS = {'bottom': 0, 'top': 1, 'left': 2, 'right': 3}


def parse_byte(v):
    if isinstance(v, str):
        return int(v, 0)
    return int(v)


def ramp(target, is_attr=False):
    """8 ascending fade steps ending at target."""
    t = parse_byte(target)
    col = t & 0x0F
    lum = (t >> 4) & 0x07
    out = []
    for i in range(8):
        l = lum - (7 - i)
        if col == 0 or l < 0:
            out.append(0x08 if is_attr else 0x00)
        else:
            out.append((l << 4) | col | (0x08 if is_attr else 0x00))
    return out


def screencode(ch):
    c = ord(ch)
    if ch == ' ':
        return 32
    if 'A' <= ch <= 'Z':
        return c - 64
    if ch in '-=':
        return 64            # PETSCII horizontal bar: seamless rule lines
    if '0' <= ch <= '9' or ch in './':
        return c
    raise ValueError(f'no screencode mapping for {ch!r}')


def move_tables(c0, c1, r0, r1, cx, cy):
    """256-entry sine tables. The object keeps 2 chars of blank margin to
    the side borders and 1 row vertically: with double buffering the back
    buffer is TWO frames stale, so the roam trail can span 2 chars
    (<= 8 px/frame), and the margins are what the blank-writing decoder
    rewrites to erase it."""
    ax = 8 * max(0, min(c0 - 2, 37 - c1))
    ay = 8 * max(0, min(r0 - 2, 22 - r1))
    mxs = [max(0, min(255, 128 + round(ax * math.sin(2*math.pi*cx*i/256))))
           for i in range(256)]
    mys = [max(0, min(255, 64 + round(ay * math.sin(2*math.pi*cy*i/256))))
           for i in range(256)]
    assert mxs[0] == 128 and mys[0] == 64
    # max speed 8 px per step: a crossing may never skip a char, or the
    # 1-char margins can no longer erase the trail
    for t in (mxs, mys):
        for a, b in zip(t, t[1:] + t[:1]):
            assert abs(a - b) <= 8
    return mxs, mys, ax, ay


def trans_off(direction, c0, c1, r0, r1):
    """Fully-off-screen offset in chars for a transition direction."""
    return {'bottom': 24 - r0, 'top': -(r1 + 1),
            'left': -(c1 + 1), 'right': 40 - c0}[direction]


def main():
    cfg = json.load(open(os.path.join(ROOT, 'tools', 'demo.json')))
    scenes = {s['name']: s for s in cfg['scenes']}
    used = []
    for e in cfg['sequence']:
        if e['type'] == 'anim' and e['scene'] not in used:
            used.append(e['scene'])

    meta = {}
    for name in used:
        s = scenes[name]
        raw = open(os.path.join(BUILD, f'frames_{name}.bin'), 'rb').read()
        n = s['frames']
        assert n <= 255, f'{name}: frames > 255'
        c0, c1, r0, r1 = extents(raw, n)
        if s.get('fx') == 'fade':
            # oversized/clipped scene: static, delta stream + keyframe
            with open(os.path.join(BUILD, f'key_{name}.bin'), 'wb') as f:
                f.write(raw[:SCREEN_SIZE])
            meta[name] = {
                'type': 2, 'mx': None, 'my': None,
                'keylen': min(SCREEN_SIZE, (r1 + 2) * 40),
                'w0': 0, 'winrows': 0, 'ext': (c0, c1, r0, r1),
            }
            print(f'{name:12s} cols {c0}-{c1} rows {r0}-{r1}  clipped, fade')
            continue
        assert r0 >= 2, f'{name}: object top row {r0} < 2 (shrink/recenter)'
        assert r1 <= 23, f'{name}: object bottom row {r1} > 23'
        assert 1 <= c0 and c1 <= 38, f'{name}: no side margin'
        cx, cy = s.get('move', [1, 2])
        mxs, mys, ax, ay = move_tables(c0, c1, r0, r1, cx, cy)
        w0, winrows = r0 - 1, r1 - r0 + 3
        meta[name] = {
            'type': 1, 'mx': mxs, 'my': mys,
            'keylen': winrows * 40,
            'w0': w0, 'winrows': winrows, 'ext': (c0, c1, r0, r1),
        }
        print(f'{name:12s} cols {c0}-{c1} rows {r0}-{r1}  window {winrows} '
              f'rows @{w0}  move +-{ax}px/{ay}px (cycles {cx}/{cy})')

    lines = ['; generated by pack_assets.py - do not edit',
             '        * = $4c00', '']
    lines.append(f'seq_count = {len(cfg["sequence"])}')
    lines.append('seq_table:')
    texts = []
    for i, e in enumerate(cfg['sequence']):
        ticks = e['ticks']
        tune = e['tune'] & 0xFF if e['tune'] >= 0 else 0xFF
        border = e['border'] & 0xFF if e['border'] >= 0 else 0xFF
        ent = e.get('enter', 'bottom')
        ext = e.get('exit', 'bottom')
        flags = (DIRS[ent] | (DIRS[ext] << 2)
                 | (16 if e.get('musfade') else 0)
                 | (32 if e.get('textfx') else 0))
        if e['type'] == 'anim':
            name = e['scene']
            m = meta[name]
            typ, data = m['type'], f'scene_{name}'
            aux = f'key_{name}' if m['type'] == 2 else '0'
            if m['mx'] is not None:
                mvx, mvy = f'mvx_{name}', f'mvy_{name}'
            else:
                mvx = mvy = '0'
            keylen, w0, winrows = m['keylen'], m['w0'], m['winrows']
            eoff = trans_off(ent, *m['ext']) & 0xFF if m['type'] == 1 else 0
            xoff = trans_off(ext, *m['ext']) & 0xFF if m['type'] == 1 else 0
            ramps = (ramp(e['bg']) + ramp(e['mc1']) + ramp(e['mc2'])
                     + ramp(e['attr'], is_attr=True))
        else:
            typ, data, aux = 0, '0', f'text_{i}'
            mvx = mvy = '0'
            keylen = w0 = winrows = eoff = xoff = 0
            texts.append((i, e['lines']))
            ramps = ramp(e['bg']) + [0] * 8 + [0] * 8 + ramp(e['fg'])
        lines.append(f'        !byte {typ}')
        lines.append(f'        !word {data}')
        lines.append(f'        !word {aux}')
        lines.append(f'        !word {ticks}')
        lines.append(f'        !byte ${tune:02x}, ${border:02x}')
        lines.append(f'        !word {mvx}')
        lines.append(f'        !word {mvy}')
        lines.append(f'        !word {keylen}')
        lines.append(f'        !byte {w0}, {winrows}')
        lines.append(f'        !byte ${eoff:02x}, ${xoff:02x}')
        lines.append(f'        !byte {flags}')
        for o in range(0, 32, 8):
            lines.append('        !byte ' + ', '.join(f'${b:02x}' for b in ramps[o:o+8]))
    lines.append('')

    for name in used:
        m = meta[name]
        if m['mx'] is None:
            continue
        for tab, vals in (('mvx', m['mx']), ('mvy', m['my'])):
            lines.append(f'{tab}_{name}:')
            for o in range(0, 256, 16):
                lines.append('        !byte ' + ', '.join(
                    f'${v:02x}' for v in vals[o:o+16]))
    lines.append('')

    for i, tlines in texts:
        lines.append(f'text_{i}:')
        for txt, row, col, color in tlines:
            codes = [screencode(c) for c in txt]
            assert col + len(codes) <= 40 and row < 25
            lines.append(f'        !byte {row}, {col}, {color}, {len(codes)}'
                         + ''.join(f', ${c:02x}' for c in codes)
                         + f'  ; "{txt}"')
        lines.append('        !byte $ff')
    lines.append('')

    for name in used:
        if meta[name]['type'] == 2:
            lines.append(f'key_{name}:')
            lines.append(f'        !bin "build/key_{name}.bin"')
        lines.append(f'scene_{name}:')
        lines.append(f'        !bin "build/scene_{name}.v10cs"')
    lines.append('assets_end:')
    lines.append('')

    open(os.path.join(BUILD, 'assets.asm'), 'w').write('\n'.join(lines))
    total = sum(os.path.getsize(os.path.join(BUILD, f'scene_{n}.v10cs'))
                + (SCREEN_SIZE if meta[n]['type'] == 2 else 0) + 512
                for n in used)
    print(f'assets.asm: {len(cfg["sequence"])} entries, {len(used)} scenes, '
          f'~{total} bytes of scene data')


if __name__ == '__main__':
    main()
