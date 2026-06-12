#!/usr/bin/env python3
"""Crop a region of a screenshot and scale up for inspection.
Usage: crop.py in.png out.png x y w h [scale]"""
import sys
from PIL import Image

inp, out, x, y, w, h = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:7])
scale = int(sys.argv[7]) if len(sys.argv) > 7 else 4
img = Image.open(inp).convert('RGB').crop((x, y, x + w, y + h))
img = img.resize((w * scale, h * scale), Image.NEAREST)
img.save(out)
print(out, img.size)
