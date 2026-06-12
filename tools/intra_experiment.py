#!/usr/bin/env python3
"""Experiment: what does V10CS cost if every frame is coded independently
(delta against a BLANK screen) instead of against the previous frame?

Intra coding would allow random access / ping-pong playback: any payload
reconstructs its frame from a cleared screen. GOSUB stays legal (it reads
emitted stream bytes from the blob, not decoded screen state), so cross-
frame redundancy is still partially captured.

Method: monkeypatch the three places v9codec chains prev=cur so training
and encoding always see prev=BLANK, then run the normal v10 build + K
sweep. Compare against the shipped delta-coded .v10cs files.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')
sys.path.insert(0, os.path.join(ROOT, 'v10cs'))
import v9codec as v9          # noqa: E402
import v10codec as v10        # noqa: E402

BLANK = bytes(v9.SCREEN_SIZE)

_orig_sk = v9._singleton_keys
_orig_fd = v9.frame_deltas
_orig_ef = v9.encode_frame


def _intra_sk(frames, kmax=v9.KMAX_DEFAULT, prev0=None):
    out = []
    for f in frames:
        out.extend(_orig_sk([f], prev0=BLANK))
    return out


def _intra_fd(prev, cur):
    return _orig_fd(BLANK, cur)


def _intra_ef(prev_screen, deltas, index, F=v9.F_DEFAULT,
              kmax=v9.KMAX_DEFAULT):
    return _orig_ef(BLANK, deltas, index, F, kmax)


def set_intra(on):
    v9._singleton_keys = _intra_sk if on else _orig_sk
    v9.frame_deltas = _intra_fd if on else _orig_fd
    v9.encode_frame = _intra_ef if on else _orig_ef


def build_best(frames, use_gosub):
    best = None
    for K in (0, 16, 32, 48, 64, 80):
        N = min(176, v10.MAX_CODE) - K
        blob, payloads = v10._build(frames, N, K, use_gosub)
        if best is None or len(blob) < len(best[0]):
            best = (blob, payloads, K)
    return best


def verify_intra(frames):
    """Sanity: with GOSUB off every payload is self-contained; decode each
    one as a standalone 1-frame file from a blank screen and compare."""
    blob, payloads, K = build_best(frames, use_gosub=False)
    import struct
    h, off = v10.read_header(blob)
    tables = blob[24:off]
    tmp = os.path.join(BUILD, '_intra_check.v10cs')
    for i, (p, want) in enumerate(zip(payloads, frames)):
        head = bytearray(blob[:24])
        head[7:9] = struct.pack('<H', 1)
        open(tmp, 'wb').write(bytes(head) + tables
                              + struct.pack('<H', len(p)) + p)
        got = v10.decode_all(tmp)[0]
        assert got == want, f'frame {i} mismatch'
    os.remove(tmp)
    return len(blob)


def main():
    cfg = json.load(open(os.path.join(ROOT, 'tools', 'demo.json')))
    scenes = {s['name']: s for s in cfg['scenes']}
    used = []
    for e in cfg['sequence']:
        if e['type'] == 'anim' and e['scene'] not in used:
            used.append(e['scene'])

    print(f'{"scene":12s} {"frames":>6s} {"cells":>6s} '
          f'{"delta file":>10s} {"d B/f":>6s} {"d max":>6s} '
          f'{"intra file":>10s} {"i B/f":>6s} {"i max":>6s} {"ratio":>6s}')
    tot_d = tot_i = 0
    for name in used:
        raw = open(os.path.join(BUILD, f'frames_{name}.bin'), 'rb').read()
        n = scenes[name]['frames']
        frames = [raw[i*1000:(i+1)*1000] for i in range(n)]
        cells = sum(sum(1 for b in f if b) for f in frames) // n

        cur = os.path.getsize(os.path.join(BUILD, f'scene_{name}.v10cs'))
        # reconstruct delta payload stats from the shipped file
        d = open(os.path.join(BUILD, f'scene_{name}.v10cs'), 'rb').read()
        h, off = v10.read_header(d)
        import struct
        sizes_d, pos = [], off
        for _ in range(h['n_frames']):
            ln = struct.unpack('<H', d[pos:pos+2])[0]
            sizes_d.append(ln)
            pos += 2 + ln

        set_intra(True)
        blob, payloads, K = build_best(frames, use_gosub=True)
        set_intra(False)
        sizes_i = [len(p) for p in payloads]

        tot_d += cur
        tot_i += len(blob)
        print(f'{name:12s} {n:6d} {cells:6d} {cur:10d} '
              f'{sum(sizes_d)/len(sizes_d):6.0f} {max(sizes_d):6d} '
              f'{len(blob):10d} {sum(sizes_i)/len(sizes_i):6.0f} '
              f'{max(sizes_i):6d} {len(blob)/cur:5.1f}x')

    print(f'{"TOTAL":12s} {"":6s} {"":6s} {tot_d:10d} {"":6s} {"":6s} '
          f'{tot_i:10d} {"":6s} {"":6s} {tot_i/tot_d:5.1f}x')

    # correctness sanity on the smallest scene
    set_intra(True)
    name = used[0]
    raw = open(os.path.join(BUILD, f'frames_{name}.bin'), 'rb').read()
    n = scenes[name]['frames']
    frames = [raw[i*1000:(i+1)*1000] for i in range(n)]
    verify_intra(frames)
    set_intra(False)
    print(f'intra round-trip verified on {name} (gosub-off variant)')


if __name__ == '__main__':
    main()
