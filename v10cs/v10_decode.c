/*
 * v10_decode.c — V10CS reference decoder in ANSI C.
 *
 * Compiles with: cc -O2 -Wall -ansi -pedantic v10_decode.c -o v10_decode
 * Usage: ./v10_decode <file.v10cs> [out.bin]
 *
 * V10CS = V9CS (screen-relative codebook classes) plus:
 *   - digram opcodes [N, N+K): expand to two stream symbols (BPE), decoded
 *     with a small expansion stack; fallback tokens are atomic so char
 *     literals never collide with the digram range;
 *   - GOSUB opcode 0xAE (flags bit 1): `0xAE off_lo off_hi len` re-executes
 *     `len` previously stored stream bytes at absolute offset `off` in the
 *     frame-data region (single return slot, no nesting).
 *
 * Container: V8CS header, version = 3. Bytes 13/14 = Na/Nr, byte 15 = K.
 * Digram table (first[K], second[K]) follows the codebook tables.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SCREEN_W 40
#define SCREEN_H 25
#define SCREEN_SIZE (SCREEN_W * SCREEN_H)

#define GOSUB_OP 0xAE
#define D1_BASE  0xB0
#define D2_BASE  0xB8
#define FB_BASE  0xC0
#define PS_OP    0xFF

#define STACK_MAX 16

typedef struct {
    unsigned char version;
    unsigned short n_frames;
    unsigned char N, F, kmax, flags, na, nr, K;
    unsigned char cb_skip[256], cb_val[256];
    unsigned char dg1[256], dg2[256];
} v10_header_t;

static size_t parse_header(const unsigned char *d, size_t len, v10_header_t *h) {
    size_t off;
    if (len < 24 || memcmp(d, "V8CS", 4) != 0) return 0;
    h->version  = d[4];
    h->n_frames = (unsigned short)(d[7] | (d[8] << 8));
    h->N = d[9]; h->F = d[10]; h->kmax = d[11]; h->flags = d[12];
    h->na = d[13]; h->nr = d[14]; h->K = d[15];
    if (h->version != 3) return 0;
    if ((int)h->N + (int)h->K > GOSUB_OP) return 0;
    if ((int)h->na + (int)h->nr > (int)h->N) return 0;
    off = 24;
    if (off + 2u * h->N + 2u * h->K > len) return 0;
    memcpy(h->cb_skip, d + off, h->N); off += h->N;
    memcpy(h->cb_val,  d + off, h->N); off += h->N;
    memcpy(h->dg1, d + off, h->K); off += h->K;
    memcpy(h->dg2, d + off, h->K); off += h->K;
    return off;
}

/*
 * Decode one frame. `fd` is the whole frame-data region (GOSUB offsets are
 * absolute within it); the payload is fd[start .. start+len).
 * Returns 0 on success.
 */
static int decode_frame(const v10_header_t *h, unsigned char *screen,
                        const unsigned char *fd, size_t fd_len,
                        size_t start, size_t len) {
    unsigned char prev_s = 0, prev_c = 0, prev2_s = 0, prev2_c = 0;
    unsigned short dst = 0;
    size_t src = start, cur_end = start + len;
    size_t ret_src = 0, ret_end = 0;
    int have_ret = 0;
    unsigned char stack[STACK_MAX];
    int sp = 0;
    unsigned char nu_base = (unsigned char)(h->na + h->nr);
    int gosub_on = (h->flags & 0x02) != 0;

    for (;;) {
        unsigned char op;
        /* resolve pending return, then test for more ops */
        while (sp == 0 && src >= cur_end && have_ret) {
            src = ret_src; cur_end = ret_end; have_ret = 0;
        }
        if (sp == 0 && src >= cur_end) break;

        /* fetch op */
        if (sp > 0) op = stack[--sp];
        else        op = fd[src++];

        /* digram expansion (opcode position only) */
        while (op >= h->N && op < (unsigned char)(h->N + h->K)) {
            if (sp >= STACK_MAX) { fprintf(stderr, "stack overflow\n"); return 1; }
            stack[sp++] = h->dg2[op - h->N];
            op = h->dg1[op - h->N];
        }

        if (op < h->N) {
            unsigned char s = h->cb_skip[op];
            unsigned char v = h->cb_val[op];
            unsigned char c;
            dst += s;
            if (op < h->na)          c = v;
            else if (op < nu_base)   c = (unsigned char)(screen[dst] + v);
            else                     c = (unsigned char)(screen[dst - SCREEN_W] + v);
            screen[dst++] = c;
            prev2_s = prev_s; prev2_c = prev_c;
            prev_s = s; prev_c = c;
        } else if (op == GOSUB_OP && gosub_on) {
            unsigned char lo, hi, l;
            if (sp != 0 || have_ret || src + 3 > cur_end) {
                fprintf(stderr, "malformed GOSUB\n"); return 1;
            }
            lo = fd[src++]; hi = fd[src++]; l = fd[src++];
            ret_src = src; ret_end = cur_end; have_ret = 1;
            src = (size_t)(lo | (hi << 8));
            cur_end = src + l;
            if (cur_end > fd_len) { fprintf(stderr, "GOSUB out of range\n"); return 1; }
        } else if (op < D1_BASE) {
            fprintf(stderr, "illegal opcode 0x%02X\n", op);
            return 1;
        } else if (op < D2_BASE) {
            unsigned char Kr = (unsigned char)((op & 7) + 1), k;
            for (k = 0; k < Kr; k++) { dst += prev_s; screen[dst++] = prev_c; }
        } else if (op < FB_BASE) {
            unsigned char Kr = (unsigned char)((op & 7) + 1), k;
            for (k = 0; k < Kr; k++) {
                dst += prev2_s; screen[dst++] = prev2_c;
                dst += prev_s;  screen[dst++] = prev_c;
            }
        } else if (op < PS_OP) {
            unsigned char s = (unsigned char)(op - FB_BASE);
            unsigned char c;
            /* char literal: raw fetch from current source (never a digram,
               never off the stack: fallback tokens are atomic) */
            c = fd[src++];
            dst += s;
            screen[dst++] = c;
            prev2_s = prev_s; prev2_c = prev_c;
            prev_s = s; prev_c = c;
        } else {
            dst += h->F;
        }
    }
    return 0;
}

int main(int argc, char **argv) {
    FILE *f, *out = NULL;
    unsigned char *buf;
    long fsize;
    v10_header_t hdr;
    size_t off, pos, fd_len;
    const unsigned char *fd;
    unsigned char screen[SCREEN_SIZE];
    unsigned long total = 0;
    int i;

    if (argc < 2 || argc > 3) {
        fprintf(stderr, "usage: %s <file.v10cs> [out.bin]\n", argv[0]);
        return 1;
    }
    f = fopen(argv[1], "rb");
    if (!f) { perror(argv[1]); return 1; }
    fseek(f, 0, SEEK_END); fsize = ftell(f); fseek(f, 0, SEEK_SET);
    buf = (unsigned char *)malloc((size_t)fsize);
    if (!buf || fread(buf, 1, (size_t)fsize, f) != (size_t)fsize) {
        fprintf(stderr, "read error\n"); return 1;
    }
    fclose(f);

    off = parse_header(buf, (size_t)fsize, &hdr);
    if (!off) { fprintf(stderr, "bad header\n"); free(buf); return 1; }
    fprintf(stderr,
            "V10CS %d frames, N=%d (a=%d r=%d u=%d), K=%d digrams, gosub=%d\n",
            hdr.n_frames, hdr.N, hdr.na, hdr.nr,
            hdr.N - hdr.na - hdr.nr, hdr.K, (hdr.flags >> 1) & 1);

    if (argc == 3) {
        out = fopen(argv[2], "wb");
        if (!out) { perror(argv[2]); free(buf); return 1; }
    }

    fd = buf + off;
    fd_len = (size_t)fsize - off;
    memset(screen, 0, SCREEN_SIZE);
    pos = 0;
    for (i = 0; i < hdr.n_frames; i++) {
        unsigned short ln;
        if (pos + 2 > fd_len) { fprintf(stderr, "truncated\n"); free(buf); return 1; }
        ln = (unsigned short)(fd[pos] | (fd[pos + 1] << 8));
        pos += 2;
        if (pos + ln > fd_len) { fprintf(stderr, "frame %d truncated\n", i); free(buf); return 1; }
        if (decode_frame(&hdr, screen, fd, fd_len, pos, ln)) { free(buf); return 1; }
        pos += ln;
        total += ln;
        if (out) fwrite(screen, 1, SCREEN_SIZE, out);
    }
    fprintf(stderr, "decoded %d frames, %.2f payload B/frame\n",
            hdr.n_frames, (double)total / hdr.n_frames);
    if (out) fclose(out);
    free(buf);
    return 0;
}
