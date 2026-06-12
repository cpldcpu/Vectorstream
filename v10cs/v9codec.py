"""
V9CS — screen-relative codebook codec for C64 pre-rendered animations.

Strict extension of V8CS. The single structural change: codebook entries
carry a *reference mode*. An entry is (mode, skip, val) with

  mode A (absolute):  char = val                       (V8 semantics)
  mode R (relative):  char = (screen[dst] + val) & 0xFF    -- old char at cell
  mode U (up):        char = (screen[dst-40] + val) & 0xFF -- already-decoded
                                                              char above

Rationale: the fixed-atlas matcher assigns consecutive charset slots to
consecutive sub-cell edge offsets, so when an edge crosses a sub-cell
boundary the new char at a cell is a small, *structural* delta from what
was there (+-1 within an offset family, +-18..35 across families/polarity).
These deltas generalize across absolute char values, so a relative entry
covers what would otherwise be many absolute pairs.

Opcode map (M = 176 codebook slots, same envelope as V8CS):

  0x00 .. Na-1            class-A codebook hit (absolute)
  Na   .. Na+Nr-1         class-R codebook hit (relative to old char)
  Na+Nr .. M-1            class-U codebook hit (relative to char above)
  0xB0 .. 0xB7            DITTO-1, K = (op&7)+1
  0xB8 .. 0xBF            DITTO-2, K = (op&7)+1
  0xC0 .. 0xFE            fallback: skip = op-0xC0, char literal in next byte
  0xFF                    pure-skip F (=63)

Na, Nr, Nu are file parameters (Na+Nr+Nu = M <= 176). All codebook classes
resolve to a concrete (skip, written-char) pair and update (prev, prev2)
exactly like a V8 codebook hit, so DITTO semantics are unchanged.

Header is the V8CS header with version = 2 and two of the reserved bytes
used for Na and Nr (Nu = N - Na - Nr).

6502 note: class R costs one extra `lda (dst),y / adc tbl,x` over class A.
Class U needs screen[dst-40]; computed lazily per op via a second ZP
pointer (sec/sbc #40 on a copy), ~+20 cycles, only on class-U ops.
Encoder never emits class U for dst < 40.
"""
from __future__ import annotations
import struct
import heapq
from collections import Counter
from typing import List, Tuple

SCREEN_W, SCREEN_H = 40, 25
SCREEN_SIZE = SCREEN_W * SCREEN_H

M_DEFAULT = 176
F_DEFAULT = 63
KMAX_DEFAULT = 8

D1_BASE = 0xB0
D2_BASE = 0xB8
FB_BASE = 0xC0
PS_OP = 0xFF

MAGIC = b"V8CS"          # same container, version bump
VERSION = 2


# --------------------------------------------------------------------------- #
#  Delta extraction (identical to V8)                                          #
# --------------------------------------------------------------------------- #

def frame_deltas(prev: bytes, cur: bytes) -> List[Tuple[int, int]]:
    d = []
    last = -1
    for i in range(SCREEN_SIZE):
        if prev[i] != cur[i]:
            d.append((i - last - 1, cur[i]))
            last = i
    return d


# --------------------------------------------------------------------------- #
#  Training: greedy max-coverage over (class, skip, val) keys                  #
# --------------------------------------------------------------------------- #

def _singleton_keys(frames: List[bytes], kmax: int = KMAX_DEFAULT,
                    prev0: bytes = None, intra: bool = False):
    """For each transition, walk the deltas in decode order and collect the
    candidate keys of every delta the encoder would emit as a singleton
    (i.e. not a DITTO continuation). Returns list of key-tuples.

    intra: every frame is coded against a BLANK screen (random-access
    streams). Class R is excluded: under a blank reference it is
    byte-identical to class A at encode time, but an intra decoder whose
    skips write blanks reads a stale cell there, so R must never be
    emitted. Class U stays valid (the cell above is always rewritten
    earlier in the same frame)."""
    keysets = []
    blank = bytes(SCREEN_SIZE)
    prev = bytes(prev0) if prev0 is not None else blank
    if intra:
        prev = blank
    for cur in frames:
        d = frame_deltas(prev, cur)
        scr = bytearray(prev)
        pos = -1
        items = []
        for s, c in d:
            pos += s + 1
            ks = []
            for j in range(s // F_DEFAULT + 1):
                rem = s - j * F_DEFAULT
                if rem > 0xFF:
                    continue
                ks.append((('a', rem, c), j))
                if not intra:
                    ks.append((('r', rem, (c - scr[pos]) & 0xFF), j))
                if pos >= SCREEN_W:
                    ks.append((('u', rem, (c - scr[pos - SCREEN_W]) & 0xFF), j))
            items.append(((s, c), ks))
            scr[pos] = c
        # DITTO gating (table-independent, matches encoder)
        i, n = 0, len(items)
        while i < n:
            sc = items[i][0]
            if i + 2 < n and items[i+1][0] == sc and items[i+2][0] == sc:
                R = 3
                while i + R < n and items[i+R][0] == sc:
                    R += 1
                keysets.append((items[i][0][0], items[i][1]))
                i += R
                continue
            sc2 = items[i+1][0] if i + 1 < n else None
            if (i + 3 < n and sc2 != sc and items[i+2][0] == sc
                    and items[i+3][0] == sc2):
                R = 2
                while (i + 2*R + 1 < n and items[i+2*R][0] == sc
                       and items[i+2*R+1][0] == sc2):
                    R += 1
                keysets.append((items[i][0][0], items[i][1]))
                keysets.append((items[i+1][0][0], items[i+1][1]))
                i += 2 * R
                continue
            keysets.append((items[i][0][0], items[i][1]))
            i += 1
        if not intra:
            prev = cur
    return keysets


def _greedy_assign(keysets, fb_cost, where, candidates, M):
    """Lazy greedy over keys with per-(delta,key) costs. cur[idx] tracks the
    cheapest emit cost found so far for that singleton (init = fallback)."""
    cur = list(fb_cost)
    gain0 = Counter()
    for idx, (s, ks) in enumerate(keysets):
        for key, j in ks:
            if key in candidates:
                g = cur[idx] - (j + 1)
                if g > 0:
                    gain0[key] += g
    heap = [(-v, k) for k, v in gain0.items()]
    heapq.heapify(heap)
    chosen = []
    while len(chosen) < M and heap:
        negv, key = heapq.heappop(heap)
        g = 0
        for idx, j in where[key]:
            d = cur[idx] - (j + 1)
            if d > 0:
                g += d
        if g == 0:
            continue
        if -negv > g:
            heapq.heappush(heap, (-g, key))
            continue
        chosen.append(key)
        for idx, j in where[key]:
            if j + 1 < cur[idx]:
                cur[idx] = j + 1
    return set(chosen)


def _encoded_cost(keysets, fb_cost, chosen):
    tot = 0
    for idx, (s, ks) in enumerate(keysets):
        c = fb_cost[idx]
        for key, j in ks:
            if key in chosen and j + 1 < c:
                c = j + 1
        tot += c
    return tot


def train_codebook(frames: List[bytes], M: int = M_DEFAULT,
                   F: int = F_DEFAULT, prev0: bytes = None,
                   intra: bool = False):
    """Select M (class, skip, val) entries minimizing encoded bytes.

    Candidate keys for a singleton delta (s, c) include chain-reduced forms:
    for every j with rem = s - j*F in [0, 255], the keys
    ('a', rem, c), ('r', rem, dc), ('u', rem, dc_up) emit as j pure-skips
    plus one codebook hit (cost j+1, vs fallback cost 2 + s//F).

    Greedy max coverage over overlapping key classes has no guarantee against
    the abs-only family, so we run multiple starts and keep the best by
    realized cost. The V8-equivalent abs selection makes V9 >= V8."""
    keysets = _singleton_keys(frames, prev0=prev0, intra=intra)
    fb_cost = [2 + s // F for s, ks in keysets]
    candidates = set()
    where = {}
    for idx, (s, ks) in enumerate(keysets):
        for key, j in ks:
            candidates.add(key)
            where.setdefault(key, []).append((idx, j))

    starts = []
    # 1: greedy over all classes with chain reduction
    starts.append(_greedy_assign(keysets, fb_cost, where, candidates, M))
    # 2: greedy over absolute keys only
    abs_cand = set(k for k in candidates if k[0] == 'a')
    starts.append(_greedy_assign(keysets, fb_cost, where, abs_cand, M))
    # 3: V8-equivalent — top-M (s,c) pairs by raw frequency over all deltas,
    #    exact-skip only (this is what a legal V8CS file would ship)
    raw = Counter()
    blank = bytes(SCREEN_SIZE)
    prev = blank if intra else (
        bytes(prev0) if prev0 is not None else blank)
    for cur_f in frames:
        for s, c in frame_deltas(prev, cur_f):
            if s <= 0xFF:
                raw[('a', s, c)] += 1
        if not intra:
            prev = cur_f
    starts.append(set(k for k, _ in raw.most_common(M)))

    best = None
    for st in starts:
        cost = _encoded_cost(keysets, fb_cost, st)
        if best is None or cost < best[0]:
            best = (cost, st)
    chosen = list(best[1])

    # order: class a, then r, then u (contiguous opcode ranges)
    order = {'a': 0, 'r': 1, 'u': 2}
    chosen.sort(key=lambda k: (order[k[0]], k[1], k[2]))
    na = sum(1 for k in chosen if k[0] == 'a')
    nr = sum(1 for k in chosen if k[0] == 'r')
    skip_tbl = [k[1] for k in chosen]
    val_tbl = [k[2] for k in chosen]
    index = {k: i for i, k in enumerate(chosen)}
    return skip_tbl, val_tbl, na, nr, index


# --------------------------------------------------------------------------- #
#  Encoder                                                                     #
# --------------------------------------------------------------------------- #

def encode_frame(prev_screen: bytes, deltas: List[Tuple[int, int]],
                 index: dict, F: int = F_DEFAULT,
                 kmax: int = KMAX_DEFAULT) -> bytes:
    scr = bytearray(prev_screen)
    pos = -1
    items = []
    for s, c in deltas:
        pos += s + 1
        ks = []
        for j in range(s // F + 1):
            rem = s - j * F
            if rem > 0xFF:
                continue
            ks.append((('a', rem, c), j))
            ks.append((('r', rem, (c - scr[pos]) & 0xFF), j))
            if pos >= SCREEN_W:
                ks.append((('u', rem, (c - scr[pos - SCREEN_W]) & 0xFF), j))
        items.append(((s, c), ks))
        scr[pos] = c

    out: list[int] = []

    def emit_single(idx: int) -> None:
        (s, c), ks = items[idx]
        best = None
        for key, j in ks:
            if key in index and (best is None or j < best[1]):
                best = (key, j)
        if best is not None:
            for _ in range(best[1]):
                out.append(PS_OP)
            out.append(index[best[0]])
            return
        rem = s
        while rem >= F:
            out.append(PS_OP)
            rem -= F
        out.append(FB_BASE + rem)
        out.append(c)

    def starter_ok(idx: int) -> bool:
        """A DITTO starter must leave prev_s equal to the delta's full skip:
        either an exact-skip (j == 0) codebook key, or a fallback with s < F.
        (V8's encoder lacked this gate; a run of identical deltas with
        s >= F would decode incorrectly.)"""
        (s, c), ks = items[idx]
        if any(key in index and j == 0 for key, j in ks):
            return True
        return s < F

    i, n = 0, len(items)
    while i < n:
        sc = items[i][0]
        if (i + 2 < n and items[i+1][0] == sc and items[i+2][0] == sc
                and starter_ok(i)):
            R = 3
            while i + R < n and items[i+R][0] == sc:
                R += 1
            emit_single(i)
            rem = R - 1
            while rem > 0:
                k = min(rem, kmax)
                out.append(D1_BASE + (k - 1))
                rem -= k
            i += R
            continue
        sc2 = items[i+1][0] if i + 1 < n else None
        if (i + 3 < n and sc2 != sc and items[i+2][0] == sc
                and items[i+3][0] == sc2 and starter_ok(i)
                and starter_ok(i + 1)):
            R = 2
            while (i + 2*R + 1 < n and items[i+2*R][0] == sc
                   and items[i+2*R+1][0] == sc2):
                R += 1
            emit_single(i)
            emit_single(i + 1)
            rem = R - 1
            while rem > 0:
                k = min(rem, kmax)
                out.append(D2_BASE + (k - 1))
                rem -= k
            i += 2 * R
            continue
        emit_single(i)
        i += 1
    return bytes(out)


# --------------------------------------------------------------------------- #
#  Decoder                                                                     #
# --------------------------------------------------------------------------- #

def decode_frame(prev_screen: bytes, payload: bytes,
                 skip_tbl: list, val_tbl: list, na: int, nr: int,
                 F: int = F_DEFAULT) -> bytes:
    screen = bytearray(prev_screen)
    dst = 0
    src = 0
    prev_s = prev_c = prev2_s = prev2_c = 0
    n = len(payload)
    nu_base = na + nr
    M = len(skip_tbl)
    while src < n:
        op = payload[src]
        src += 1
        if op < M:
            s = skip_tbl[op]
            v = val_tbl[op]
            dst += s
            if op < na:
                c = v
            elif op < nu_base:
                c = (screen[dst] + v) & 0xFF
            else:
                c = (screen[dst - SCREEN_W] + v) & 0xFF
            screen[dst] = c
            dst += 1
            prev2_s, prev2_c = prev_s, prev_c
            prev_s, prev_c = s, c
        elif op < D2_BASE:
            if op < D1_BASE:
                raise ValueError(f"opcode 0x{op:02X} in unused codebook range")
            K = (op & 7) + 1
            for _ in range(K):
                dst += prev_s
                screen[dst] = prev_c
                dst += 1
        elif op < FB_BASE:
            K = (op & 7) + 1
            for _ in range(K):
                dst += prev2_s
                screen[dst] = prev2_c
                dst += 1
                dst += prev_s
                screen[dst] = prev_c
                dst += 1
        elif op < PS_OP:
            s = op - FB_BASE
            c = payload[src]
            src += 1
            dst += s
            screen[dst] = c
            dst += 1
            prev2_s, prev2_c = prev_s, prev_c
            prev_s, prev_c = s, c
        else:
            dst += F
    return bytes(screen)


# --------------------------------------------------------------------------- #
#  File I/O                                                                    #
# --------------------------------------------------------------------------- #

def write_file(path: str, frames: List[bytes], M: int = M_DEFAULT,
               F: int = F_DEFAULT, kmax: int = KMAX_DEFAULT) -> dict:
    skip_tbl, val_tbl, na, nr, index = train_codebook(frames, M)
    N = len(skip_tbl)
    header = bytearray(24)
    header[0:4] = MAGIC
    header[4] = VERSION
    header[5] = SCREEN_W
    header[6] = SCREEN_H
    header[7:9] = struct.pack("<H", len(frames))
    header[9] = N
    header[10] = F
    header[11] = kmax
    header[12] = 0x01           # ditto enabled
    header[13] = na             # reserved bytes 13/14 -> class boundaries
    header[14] = nr

    body = bytearray()
    body.extend(bytes(skip_tbl))
    body.extend(bytes(val_tbl))

    prev = bytes(SCREEN_SIZE)
    sizes = []
    for cur in frames:
        d = frame_deltas(prev, cur)
        payload = encode_frame(prev, d, index, F, kmax)
        body.extend(struct.pack("<H", len(payload)))
        body.extend(payload)
        sizes.append(len(payload))
        prev = cur
    with open(path, "wb") as f:
        f.write(header)
        f.write(body)
    return {"na": na, "nr": nr, "nu": N - na - nr, "sizes": sizes,
            "file_bytes": 24 + len(body)}


def read_file(path: str):
    data = open(path, "rb").read()
    if data[0:4] != MAGIC or data[4] != VERSION:
        raise ValueError("not a V9CS (V8CS v2) file")
    n_frames = struct.unpack("<H", data[7:9])[0]
    N, F, kmax = data[9], data[10], data[11]
    na, nr = data[13], data[14]
    off = 24
    skip_tbl = list(data[off:off + N]); off += N
    val_tbl = list(data[off:off + N]); off += N
    payloads = []
    for _ in range(n_frames):
        ln = struct.unpack("<H", data[off:off + 2])[0]; off += 2
        payloads.append(data[off:off + ln]); off += ln
    return (skip_tbl, val_tbl, na, nr, F), payloads


def decode_all(path: str) -> List[bytes]:
    (skip_tbl, val_tbl, na, nr, F), payloads = read_file(path)
    screens = []
    prev = bytes(SCREEN_SIZE)
    for p in payloads:
        cur = decode_frame(prev, p, skip_tbl, val_tbl, na, nr, F)
        screens.append(cur)
        prev = cur
    return screens
