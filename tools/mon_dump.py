#!/usr/bin/env python3
"""Launch the demo in xplus4 (warp), then use the VICE remote monitor to
dump TED registers, screen, attrs and zp state for debugging.

Usage: python3 tools/mon_dump.py [seconds_emulated]
"""
import os
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
secs = float(sys.argv[1]) if len(sys.argv) > 1 else 12.0

env = dict(os.environ, DISPLAY=':0')
proc = subprocess.Popen(
    ['xplus4', '-default', '-warp', '+sound', '-autostartprgmode', '1',
     '-remotemonitor', '-remotemonitoraddress', 'ip4://127.0.0.1:6510',
     '-autostart', os.path.join(ROOT, 'build', 'demo.prg')],
    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

try:
    # warp factor is large; poll the monitor port, then wait for emulated time
    time.sleep(6 + secs / 8)   # rough warp-time guess; refined by reg dump

    s = socket.create_connection(('127.0.0.1', 6510), timeout=10)
    s.settimeout(3)

    def cmd(c):
        s.sendall((c + '\n').encode())
        time.sleep(0.4)
        out = b''
        try:
            while True:
                b = s.recv(65536)
                if not b:
                    break
                out += b
        except socket.timeout:
            pass
        return out.decode(errors='replace')

    print(cmd('bank io'))
    print('--- TED regs (io bank) ---')
    print(cmd('m ff06 ff1f'))
    print(cmd('screenshot "build/mon_shot.png" 2'))
    print(cmd('bank cpu'))
    print('--- shell zp (tick, entryi=5a, phase=57) ---')
    print(cmd('m 0050 005f'))
    print('--- decoder zp ---')
    print(cmd('m 00d0 00ef'))
    print('--- screen row 12 ---')
    print(cmd('m 0de0 0e07'))
    print('--- attr row 12 ---')
    print(cmd('m 09e0 0a07'))
    print('--- charset slot 1 (solid mc1) ---')
    print(cmd('m 1808 180f'))
    print('--- cur_entry ---')
    print(cmd('m 12f6 131e'))
    cmd('x')
    s.close()
finally:
    time.sleep(1)
    proc.kill()
