"""
V10CS — V9CS + digram opcodes + stream subroutines.

Two additions, both pure table/pointer machinery on a 6502 (no bit I/O):

1. DIGRAM opcodes (byte-pair encoding). K codebook slots are reallocated as
   digram codes [N, N+K). A digram expands to two stream symbols, each of
   which may itself be a digram (classic BPE, decoded with a small stack).
   Fallback tokens (op + char literal) are atomic and never merged, so
   digram codes appear only in opcode position and char literals never
   collide with the digram range.

2. GOSUB opcode 0xAE (when enabled): `0xAE off_lo off_hi len` re-executes
   `len` previously stored stream bytes at absolute offset `off` in the
   frame-data region, then returns (single return slot, no nesting).
   Because the re-executed bytes are literally identical to what would
   have been stored inline, all context-dependent semantics (DITTO
   prev-regs, relative codebook classes) are automatically correct.
   This captures the long-range redundancy of near-periodic animations
   (cube/Y repeats with period pi = ~157 frames) that no per-frame
   mechanism can reach.

Opcode map (N codebook + K digram + GOSUB <= 0xAF):

  0x00 .. N-1        codebook (classes A/R/U as in V9CS)
  N    .. N+K-1      digram codes
  0xAE               GOSUB (only if flags bit 1 set; else reserved)
  0xB0 .. 0xBF       DITTO-1/2
  0xC0 .. 0xFE       fallback
  0xFF               pure-skip

Header: V8CS container, version = 3.
  byte 13: Na, byte 14: Nr (V9 class boundaries)
  byte 15: K (digram count)
  flags bit 1: GOSUB enabled
  Digram table (2K bytes: first[i], second[i]) follows the codebook.

The encoder sweeps K over a grid and keeps the smallest total file.
"""
from __future__ import annotations
import struct
from collections import Counter
from typing import List

import v9codec as v9

SCREEN_SIZE = v9.SCREEN_SIZE
F_DEFAULT = v9.F_DEFAULT
D1_BASE = 0xB0
FB_BASE = 0xC0
PS_OP = 0xFF
GOSUB_OP = 0xAE
MAX_CODE = 0xAE          # codebook + digrams must stay below GOSUB
MAGIC = b"V8CS"
VERSION = 3

LZ_MIN_BYTES = 6         # minimum source byte length worth a 4-byte GOSUB
LZ_CAND = 64             # match candidates examined per anchor


# --------------------------------------------------------------------------- #
#  Tokenization                                                                #
# --------------------------------------------------------------------------- #

def tokenize(p: bytes) -> List[bytes]:
    toks = []
    i = 0
    while i < len(p):
        op = p[i]
        if FB_BASE <= op < PS_OP:
            toks.append(p[i:i+2])
            i += 2
        else:
            toks.append(p[i:i+1])
            i += 1
    return toks


# --------------------------------------------------------------------------- #
#  Digram (BPE) training over token sequences                                  #
# --------------------------------------------------------------------------- #

def bpe_train(token_seqs: List[List[bytes]], base: int, K: int):
    """Merge the most frequent adjacent single-byte token pair into a new
    code, repeatedly. Mutates copies; returns (table, seqs)."""
    seqs = [list(s) for s in token_seqs]
    table = []
    while len(table) < K:
        cnt = Counter()
        for s in seqs:
            for a, b in zip(s, s[1:]):
                if len(a) == 1 and len(b) == 1:
                    cnt[(a, b)] += 1
        if not cnt:
            break
        (a, b), f = cnt.most_common(1)[0]
        if f < 4:                      # 2 table bytes + slot not worth less
            break
        code = bytes([base + len(table)])
        table.append((a[0], b[0]))
        for s in seqs:
            i, out = 0, []
            while i < len(s):
                if i + 1 < len(s) and s[i] == a and s[i+1] == b:
                    out.append(code)
                    i += 2
                else:
                    out.append(s[i])
                    i += 1
            s[:] = out
    return table, seqs


# --------------------------------------------------------------------------- #
#  Stream-subroutine (GOSUB) pass                                              #
# --------------------------------------------------------------------------- #

def lz_pass(token_seqs: List[List[bytes]], data_start: int):
    """Greedy token-aligned LZ over the emitted stream. Sources are
    physically emitted byte regions (single payload, no GOSUB inside,
    <= 255 bytes). Offsets are absolute within the frame-data region
    (headers included), so each emitted token's final offset is known
    when later frames reference it."""
    out_seqs = []
    index = {}                  # token-trigram -> list of (hist_idx)
    hist_tok = []               # emitted source-eligible tokens
    hist_off = []               # absolute offset of each
    hist_frame = []             # payload index (sources must not span frames)
    off = data_start

    for fno, s in enumerate(token_seqs):
        off += 2                # frame length header
        out = []
        i, n = 0, len(s)
        # token byte offsets if emitted literally from current position are
        # assigned as we go (GOSUB replacements shift later tokens, so we
        # emit-and-account token by token)
        while i < n:
            best_len, best_pos = 0, -1
            key = (s[i], s[i+1], s[i+2]) if i + 2 < n else None
            if key is not None:
                for h in index.get(key, ())[-LZ_CAND:]:
                    l = 0
                    while (i + l < n and h + l < len(hist_tok)
                           and hist_frame[h + l] == hist_frame[h]
                           and hist_tok[h + l] == s[i + l]):
                        # source must be contiguous bytes
                        if l and hist_off[h + l] != hist_off[h + l - 1] + len(hist_tok[h + l - 1]):
                            break
                        l += 1
                    if l > best_len:
                        best_len, best_pos = l, h
            if best_len:
                # trim to byte-length cap
                while best_len and sum(len(t) for t in hist_tok[best_pos:best_pos + best_len]) > 0xFF:
                    best_len -= 1
                blen = sum(len(t) for t in hist_tok[best_pos:best_pos + best_len])
            if best_len and blen >= LZ_MIN_BYTES and blen > 4:
                src_off = hist_off[best_pos]
                out.append(bytes([GOSUB_OP, src_off & 0xFF,
                                  (src_off >> 8) & 0xFF, blen]))
                # the matched tokens are NOT source-eligible (they are not
                # physically emitted here), so they don't enter the history
                i += best_len
                off += 4
            else:
                t = s[i]
                if i + 2 < n:
                    pass
                # register trigram anchored at this token using the *source*
                # token stream values (we index by upcoming emitted tokens)
                hist_tok.append(t)
                hist_off.append(off)
                hist_frame.append(fno)
                h = len(hist_tok) - 1
                if h >= 2 and hist_frame[h-2] == fno:
                    k = (hist_tok[h-2], hist_tok[h-1], hist_tok[h])
                    index.setdefault(k, []).append(h - 2)
                off += len(t)
                out.append(t)
                i += 1
        out_seqs.append(out)
    return out_seqs


# --------------------------------------------------------------------------- #
#  File writer                                                                 #
# --------------------------------------------------------------------------- #

def _build(frames, N, K, use_gosub, F=F_DEFAULT, prev0=None, intra=False):
    """intra=True: every frame is coded against a BLANK screen, class R
    excluded (see v9._singleton_keys). Payloads become random-access: any
    frame decodes independently when skips write the blank char. Header
    flags bit 2 marks such files."""
    skip_tbl, val_tbl, na, nr, index = v9.train_codebook(
        frames, N, prev0=prev0, intra=intra)
    if intra:
        assert nr == 0, "intra training must not select class R"
    payloads = []
    blank = bytes(SCREEN_SIZE)
    prev = blank if intra else (
        bytes(prev0) if prev0 is not None else blank)
    for cur in frames:
        d = v9.frame_deltas(prev, cur)
        payloads.append(v9.encode_frame(prev, d, index, F))
        if not intra:
            prev = cur
    token_seqs = [tokenize(p) for p in payloads]
    table, token_seqs = bpe_train(token_seqs, N, K) if K else ([], token_seqs)
    if use_gosub:
        data_start = 0
        token_seqs = lz_pass(token_seqs, data_start)
    out_payloads = [b''.join(s) for s in token_seqs]

    header = bytearray(24)
    header[0:4] = MAGIC
    header[4] = VERSION
    header[5] = v9.SCREEN_W
    header[6] = v9.SCREEN_H
    header[7:9] = struct.pack("<H", len(frames))
    header[9] = N
    header[10] = F
    header[11] = v9.KMAX_DEFAULT
    header[12] = 0x01 | (0x02 if use_gosub else 0x00) | (0x04 if intra else 0x00)
    header[13] = na
    header[14] = nr
    header[15] = len(table)

    body = bytearray()
    body.extend(bytes(skip_tbl))
    body.extend(bytes(val_tbl))
    body.extend(bytes(a for a, _ in table))
    body.extend(bytes(b for _, b in table))
    for p in out_payloads:
        body.extend(struct.pack("<H", len(p)))
        body.extend(p)
    return bytes(header) + bytes(body), out_payloads


def write_file(path: str, frames: List[bytes],
               k_grid=(0, 16, 32, 48, 64, 80), use_gosub=True,
               prev0=None, intra=False) -> dict:
    if intra:
        # class R is excluded under intra: its candidate space folds into
        # A/U, so re-sweep K a little wider against the intra statistics
        k_grid = tuple(sorted(set(k_grid) | {96, 112}))
    best = None
    for K in k_grid:
        N = min(176, MAX_CODE) - K
        blob, payloads = _build(frames, N, K, use_gosub, prev0=prev0,
                                intra=intra)
        if best is None or len(blob) < len(best[0]):
            best = (blob, payloads, K, N)
    blob, payloads, K, N = best
    open(path, "wb").write(blob)
    return {"K": K, "N": N, "file_bytes": len(blob),
            "sizes": [len(p) for p in payloads]}


# --------------------------------------------------------------------------- #
#  Decoder                                                                     #
# --------------------------------------------------------------------------- #

def read_header(data: bytes):
    if data[0:4] != MAGIC or data[4] != VERSION:
        raise ValueError("not a V10CS file")
    h = {
        "n_frames": struct.unpack("<H", data[7:9])[0],
        "N": data[9], "F": data[10], "kmax": data[11],
        "flags": data[12], "na": data[13], "nr": data[14], "K": data[15],
    }
    off = 24
    N, K = h["N"], h["K"]
    h["skip"] = list(data[off:off+N]); off += N
    h["val"] = list(data[off:off+N]); off += N
    h["dg1"] = list(data[off:off+K]); off += K
    h["dg2"] = list(data[off:off+K]); off += K
    return h, off


def decode_all(path: str, prev0=None) -> List[bytes]:
    """Intra files (flags bit 2) mirror the 6502 skip-writes-blank decoder
    exactly: the screen persists across frames (stale cells must be erased
    by the skips themselves), every skip writes blanks as it advances, and
    the tail after the last op is blank-filled."""
    data = open(path, "rb").read()
    h, off = read_header(data)
    N, K, F = h["N"], h["K"], h["F"]
    na, nu_base = h["na"], h["na"] + h["nr"]
    gosub = bool(h["flags"] & 0x02)
    intra = bool(h["flags"] & 0x04)
    frame_data = data[off:]
    screens = []
    screen = bytearray(prev0) if prev0 is not None else bytearray(SCREEN_SIZE)
    pos = 0

    for _ in range(h["n_frames"]):
        ln = struct.unpack("<H", frame_data[pos:pos+2])[0]
        pos += 2
        end = pos + ln
        src = pos
        ret = None              # (return_src, return_end) single slot
        cur_end = end
        dst = 0
        prev_s = prev_c = prev2_s = prev2_c = 0
        stack = []              # digram expansion stack

        def adv(n):             # skip: intra decoders write blanks
            nonlocal dst
            if intra:
                screen[dst:dst+n] = bytes(n)
            dst += n

        def fetch():
            nonlocal src, ret, cur_end
            while True:
                if stack:
                    return stack.pop()
                if src < cur_end:
                    b = frame_data[src]
                    src += 1
                    return b
                if ret is not None:
                    src, cur_end = ret
                    ret = None
                    continue
                raise ValueError("stream exhausted mid-op")

        while True:
            # resolve pending returns before testing for more ops
            while src >= cur_end and ret is not None and not stack:
                src, cur_end = ret
                ret = None
            if not stack and src >= cur_end:
                break
            op = fetch()
            # digram expansion (only in opcode position)
            while N <= op < N + K:
                stack.append(h["dg2"][op - N])
                op = h["dg1"][op - N]
            if op < N:
                s = h["skip"][op]
                v = h["val"][op]
                adv(s)
                if op < na:
                    c = v
                elif op < nu_base:
                    c = (screen[dst] + v) & 0xFF
                else:
                    c = (screen[dst - v9.SCREEN_W] + v) & 0xFF
                screen[dst] = c
                dst += 1
                prev2_s, prev2_c = prev_s, prev_c
                prev_s, prev_c = s, c
            elif op == GOSUB_OP and gosub:
                lo = fetch(); hi = fetch(); l = fetch()
                assert not stack and ret is None
                ret = (src, cur_end)
                src = lo | (hi << 8)
                cur_end = src + l
            elif op < D1_BASE:
                raise ValueError(f"illegal opcode 0x{op:02X}")
            elif op < 0xB8:
                Kr = (op & 7) + 1
                for _ in range(Kr):
                    adv(prev_s)
                    screen[dst] = prev_c
                    dst += 1
            elif op < FB_BASE:
                Kr = (op & 7) + 1
                for _ in range(Kr):
                    adv(prev2_s)
                    screen[dst] = prev2_c
                    dst += 1
                    adv(prev_s)
                    screen[dst] = prev_c
                    dst += 1
            elif op < PS_OP:
                s = op - FB_BASE
                c = fetch()
                adv(s)
                screen[dst] = c
                dst += 1
                prev2_s, prev2_c = prev_s, prev_c
                prev_s, prev_c = s, c
            else:
                adv(F)
        pos = end
        if intra:
            screen[dst:] = bytes(SCREEN_SIZE - dst)
        screens.append(bytes(screen))
    return screens
