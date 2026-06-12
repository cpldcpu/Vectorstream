# V9CS + V10CS reference codecs.
#   make data    -- regenerate the four test animations (needs node + core.js)
#   make         -- build both C decoders
#   make cross   -- Python<->C byte-exact cross-validation (V9 and V10)
#   make clean

.PHONY: all data cross clean

all: v9_decode v10_decode

data:
	node gen_frames.js

v9_decode: v9_decode.c
	cc -O2 -Wall -ansi -pedantic v9_decode.c -o v9_decode

v10_decode: v10_decode.c
	cc -O2 -Wall -ansi -pedantic v10_decode.c -o v10_decode

cross: all
	python3 cross_validate.py
	python3 cross_validate_v10.py

clean:
	rm -f v9_decode v10_decode /tmp/cv.v9cs /tmp/cv.v10cs /tmp/cv_c.bin
