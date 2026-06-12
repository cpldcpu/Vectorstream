#!/usr/bin/env python3
# Verify the 6502 player against the Python reference model, frame by frame.
import re, sys
from py65.devices.mpu6502 import MPU
from songdata import RefPlayer, TUNES

SENTINEL = 0x8000  # RTS lands here -> subroutine done

def load():
    syms = {}
    for line in open('symbols.txt'):
        m = re.match(r'\s*(\w+)\s*=\s*\$([0-9a-fA-F]+)', line)
        if m: syms[m.group(1)] = int(m.group(2), 16)
    prg = open('ted_tunes.prg', 'rb').read()
    addr = prg[0] | (prg[1] << 8)
    mem = [0] * 65536
    for i, b in enumerate(prg[2:]):
        mem[addr + i] = b
    return mem, syms

def call(mpu, addr, a=None):
    # JSR semantics: push (SENTINEL-1), run until PC == SENTINEL
    mpu.memory[0x01FF] = (SENTINEL - 1) >> 8
    mpu.memory[0x01FE] = (SENTINEL - 1) & 0xFF
    mpu.sp = 0xFD
    mpu.pc = addr
    if a is not None: mpu.a = a
    for _ in range(200000):
        mpu.step()
        if mpu.pc == SENTINEL:
            return
    raise RuntimeError(f'subroutine at ${addr:04x} did not return')

def snapshot(mem):
    return (mem[0xFF0E], mem[0xFF0F], mem[0xFF10] & 3,
            mem[0xFF11], mem[0xFF12] & 3)

def main():
    mem, syms = load()
    nframes = 4000
    allok = True
    for tune in range(4):
        mpu = MPU()
        mpu.memory[:] = mem
        call(mpu, syms['select_tune'], a=tune)
        ref = RefPlayer(tune)
        bad = 0
        for fr in range(nframes):
            call(mpu, syms['playtick'])
            ref.tick()
            got, want = snapshot(mpu.memory), ref.snapshot()
            if got != want:
                if bad < 5:
                    print(f'tune {tune} frame {fr}: asm={got} ref={want}')
                bad += 1
        loops = nframes / (len(TUNES[tune]["order"]) * 16 * TUNES[tune]["speed"])
        status = 'OK' if bad == 0 else f'{bad} MISMATCHES'
        if bad: allok = False
        print(f'tune {tune} ({TUNES[tune]["name"]:13s}): {nframes} frames '
              f'(~{loops:.1f} song loops) ... {status}')
    sys.exit(0 if allok else 1)

if __name__ == '__main__':
    main()
