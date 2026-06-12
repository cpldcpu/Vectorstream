# VECTOR STREAM - LATENT Plus/4 demo. Run from WSL.
#   make            full asset + demo build + size check
#   make verify     py65 decoder + music verification
#   make run        boot the demo in xplus4 (WSLg)
#   make probe      milestone-0 TED hardware probe
#   make clean

CEILING := 63487   # $F7FF: highest allowed loaded byte ($F800+ = font copy)

.PHONY: all assets encode pack demo size verify run probe release clean

all: demo

build/charset.bin: tools/gen_scenes.js tools/demo.json v10cs/core.js
	node tools/gen_scenes.js

assets: build/charset.bin

encode: assets tools/encode_scenes.py v10cs/v10codec.py v10cs/v9codec.py
	python3 tools/encode_scenes.py

pack: encode tools/pack_assets.py
	python3 tools/pack_assets.py

demo: pack src/demo.asm src/decoder.asm music/player_core.asm music/player_zp.asm music/song_data.asm
	acme src/demo.asm
	$(MAKE) --no-print-directory size

size:
	@python3 -c "import sys; d=open('build/demo.prg','rb').read(); \
	start=d[0]|d[1]<<8; end=start+len(d)-3; \
	print(f'demo.prg: {len(d)} bytes, \$${start:04x}-\$${end:04x}'); \
	sys.exit(1 if end > $(CEILING) else 0)" \
	|| (echo 'SIZE BUDGET EXCEEDED (> $$F7FF)'; false)

verify: demo
	acme src/test_decoder.asm
	python3 verify_decoder.py
	cd music && acme player.asm && python3 verify.py

run: demo
	DISPLAY=:0 xplus4 -default -autostartprgmode 1 -autostart build/demo.prg

probe:
	acme src/tedtest.asm
	bash tools/run_probe.sh build/tedtest.prg build/tedtest.png

release: demo
	cp build/demo.prg vectorstream.prg

clean:
	rm -rf build music/ted_tunes.prg music/symbols.txt
