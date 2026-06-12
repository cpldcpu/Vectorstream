/*
 * v9_decode.c — V9CS reference decoder in ANSI C.
 *
 * Compiles with: cc -O2 -Wall -ansi -pedantic v9_decode.c -o v9_decode
 *
 * Usage: ./v9_decode <file.v9cs> [out.bin]
 *   Decodes all frames; if out.bin is given, writes the concatenated
 *   1000-byte screens for cross-validation against the Python codec.
 *
 * V9CS is the V8CS container with version = 2. The codebook gains two
 * screen-relative reference classes; reserved header bytes 13/14 carry the
 * class boundaries Na (absolute) and Nr (relative-to-old). Class layout:
 *
 *   op in [0, Na)        char = cb_val[op]
 *   op in [Na, Na+Nr)    char = screen[dst] + cb_val[op]        (mod 256)
 *   op in [Na+Nr, N)     char = screen[dst - width] + cb_val[op] (mod 256)
 *
 * All other opcode classes (DITTO, fallback, pure-skip) are unchanged.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SCREEN_W 40
#define SCREEN_H 25
#define SCREEN_SIZE (SCREEN_W * SCREEN_H)

#define D1_BASE 0xB0
#define D2_BASE 0xB8
#define FB_BASE 0xC0
#define PS_OP   0xFF

typedef struct {
    unsigned char version, width, height;
    unsigned short n_frames;
    unsigned char n_codebook, f_fallback, kmax, flags;
    unsigned char na, nr;
    unsigned char cb_skip[256];
    unsigned char cb_val[256];
} v9_header_t;

static size_t v9_parse_header(const unsigned char *data, size_t len,
                              v9_header_t *hdr) {
    size_t off;
    if (len < 24) return 0;
    if (memcmp(data, "V8CS", 4) != 0) return 0;
    hdr->version    = data[4];
    hdr->width      = data[5];
    hdr->height     = data[6];
    hdr->n_frames   = (unsigned short)(data[7] | (data[8] << 8));
    hdr->n_codebook = data[9];
    hdr->f_fallback = data[10];
    hdr->kmax       = data[11];
    hdr->flags      = data[12];
    hdr->na         = data[13];
    hdr->nr         = data[14];
    if (hdr->version != 2) return 0;
    if (hdr->width * hdr->height > SCREEN_SIZE) return 0;
    if ((int)hdr->na + (int)hdr->nr > (int)hdr->n_codebook) return 0;
    if (hdr->n_codebook > D1_BASE) return 0;
    off = 24;
    if (off + 2u * hdr->n_codebook > len) return 0;
    memcpy(hdr->cb_skip, data + off, hdr->n_codebook);
    off += hdr->n_codebook;
    memcpy(hdr->cb_val, data + off, hdr->n_codebook);
    off += hdr->n_codebook;
    return off;
}

static void v9_decode_frame(const v9_header_t *hdr,
                            unsigned char *screen,
                            const unsigned char *payload, size_t len) {
    unsigned char prev_s = 0, prev_c = 0;
    unsigned char prev2_s = 0, prev2_c = 0;
    unsigned short dst = 0;
    size_t src = 0;
    unsigned char F = hdr->f_fallback;
    unsigned char N = hdr->n_codebook;
    unsigned char na = hdr->na;
    unsigned char nu_base = (unsigned char)(hdr->na + hdr->nr);

    while (src < len) {
        unsigned char op = payload[src++];
        if (op < N) {
            unsigned char s = hdr->cb_skip[op];
            unsigned char v = hdr->cb_val[op];
            unsigned char c;
            dst += s;
            if (op < na)            c = v;
            else if (op < nu_base)  c = (unsigned char)(screen[dst] + v);
            else                    c = (unsigned char)(screen[dst - SCREEN_W] + v);
            screen[dst++] = c;
            prev2_s = prev_s; prev2_c = prev_c;
            prev_s = s; prev_c = c;
        } else if (op < D1_BASE) {
            /* unused codebook range: must not appear */
            fprintf(stderr, "illegal opcode 0x%02X\n", op);
            return;
        } else if (op < D2_BASE) {
            unsigned char K = (unsigned char)((op & 7) + 1);
            unsigned char k;
            for (k = 0; k < K; k++) {
                dst += prev_s;
                screen[dst++] = prev_c;
            }
        } else if (op < FB_BASE) {
            unsigned char K = (unsigned char)((op & 7) + 1);
            unsigned char k;
            for (k = 0; k < K; k++) {
                dst += prev2_s;
                screen[dst++] = prev2_c;
                dst += prev_s;
                screen[dst++] = prev_c;
            }
        } else if (op < PS_OP) {
            unsigned char s = (unsigned char)(op - FB_BASE);
            unsigned char c = payload[src++];
            dst += s;
            screen[dst++] = c;
            prev2_s = prev_s; prev2_c = prev_c;
            prev_s = s; prev_c = c;
        } else {
            dst += F;
        }
    }
}

int main(int argc, char **argv) {
    FILE *f, *out = NULL;
    unsigned char *buf;
    long fsize;
    v9_header_t hdr;
    size_t off;
    unsigned char screen[SCREEN_SIZE];
    unsigned long total = 0;
    int i;

    if (argc < 2 || argc > 3) {
        fprintf(stderr, "usage: %s <file.v9cs> [out.bin]\n", argv[0]);
        return 1;
    }
    f = fopen(argv[1], "rb");
    if (!f) { perror(argv[1]); return 1; }
    fseek(f, 0, SEEK_END);
    fsize = ftell(f);
    fseek(f, 0, SEEK_SET);
    buf = (unsigned char *)malloc((size_t)fsize);
    if (!buf) { fprintf(stderr, "OOM\n"); fclose(f); return 1; }
    if (fread(buf, 1, (size_t)fsize, f) != (size_t)fsize) {
        fprintf(stderr, "short read\n"); free(buf); fclose(f); return 1;
    }
    fclose(f);

    off = v9_parse_header(buf, (size_t)fsize, &hdr);
    if (!off) { fprintf(stderr, "bad header\n"); free(buf); return 1; }
    fprintf(stderr,
            "V9CS (V8CS v%d) %dx%d, %d frames, N=%d (a=%d r=%d u=%d), F=%d\n",
            hdr.version, hdr.width, hdr.height, hdr.n_frames,
            hdr.n_codebook, hdr.na, hdr.nr,
            hdr.n_codebook - hdr.na - hdr.nr, hdr.f_fallback);

    if (argc == 3) {
        out = fopen(argv[2], "wb");
        if (!out) { perror(argv[2]); free(buf); return 1; }
    }

    memset(screen, 0, SCREEN_SIZE);
    for (i = 0; i < hdr.n_frames; i++) {
        unsigned short ln;
        if (off + 2 > (size_t)fsize) {
            fprintf(stderr, "truncated at frame %d\n", i);
            free(buf); return 1;
        }
        ln = (unsigned short)(buf[off] | (buf[off + 1] << 8));
        off += 2;
        if (off + ln > (size_t)fsize) {
            fprintf(stderr, "frame %d truncated\n", i);
            free(buf); return 1;
        }
        v9_decode_frame(&hdr, screen, buf + off, ln);
        off += ln;
        total += ln;
        if (out) fwrite(screen, 1, SCREEN_SIZE, out);
    }
    fprintf(stderr, "decoded %d frames, %.2f payload B/frame\n",
            hdr.n_frames, (double)total / hdr.n_frames);
    if (out) fclose(out);
    free(buf);
    return 0;
}
