#!/usr/bin/env python3
"""Render a raw screen-code frame to PNG using charset.bin, for visual
comparison against emulator screenshots.

Usage: python3 tools/render_ref.py <frames.bin> <frame#> <out.png>
"""
import sys
from PIL import Image

PAL = [(0, 0, 0), (0x6F, 0x5D, 0xC4), (0xCF, 0xE2, 0x7C), (0xB0, 0x46, 0x46)]


def main():
    frames_path, fno, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    charset = open('build/charset.bin', 'rb').read()
    raw = open(frames_path, 'rb').read()
    screen = raw[fno * 1000:(fno + 1) * 1000]
    img = Image.new('RGB', (320, 200))
    px = img.load()
    for cy in range(25):
        for cx in range(40):
            code = screen[cy * 40 + cx]
            for py in range(8):
                b = charset[code * 8 + py]
                for pp in range(4):
                    v = (b >> (6 - 2 * pp)) & 3
                    x = cx * 8 + pp * 2
                    y = cy * 8 + py
                    px[x, y] = PAL[v]
                    px[x + 1, y] = PAL[v]
    img = img.resize((384, 240), Image.NEAREST)
    img.save(out)
    print(out)


if __name__ == '__main__':
    main()
