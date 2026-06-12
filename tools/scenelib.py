"""Shared scene geometry for encode_scenes / pack_assets / verify_decoder.

A slide scene's decode WINDOW is the object's bounding rows plus one blank
margin row above and below, cropped from the full 40x25 canvas:

    w0      = r0 - 1            first window row (in object space)
    winrows = r1 - r0 + 3       window height
    window  = winrows * 40      bytes rewritten per decoded frame

Frames are encoded intra with the rows above w0 stripped (the on-screen
decoder blank-writes every window cell, and rows above the window would
land in the attribute matrix when the object roams upward).
"""
SCREEN_SIZE = 1000
SCREEN_W = 40


def extents(raw, n):
    """Bounding box of nonblank cells over all frames."""
    c0, c1, r0, r1 = 40, -1, 25, -1
    for f in range(n):
        fr = raw[f*SCREEN_SIZE:(f+1)*SCREEN_SIZE]
        for i, b in enumerate(fr):
            if b:
                r, c = divmod(i, SCREEN_W)
                c0, c1 = min(c0, c), max(c1, c)
                r0, r1 = min(r0, r), max(r1, r)
    return c0, c1, r0, r1


def window(raw, n):
    """(w0, winrows) of the cropped decode window."""
    c0, c1, r0, r1 = extents(raw, n)
    return r0 - 1, r1 - r0 + 3


def crop_frames(raw, n):
    """Frames with rows above w0 stripped (zero-padded back to 1000)."""
    w0, winrows = window(raw, n)
    out = []
    for f in range(n):
        fr = raw[f*SCREEN_SIZE:(f+1)*SCREEN_SIZE]
        cut = fr[w0*SCREEN_W:]
        out.append(cut + bytes(SCREEN_SIZE - len(cut)))
    return out
