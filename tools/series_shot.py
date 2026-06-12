#!/usr/bin/env python3
"""One xplus4 session, periodic monitor screenshots + entry index.
Usage: python3 tools/series_shot.py <start_s> <end_s> <step_s>"""
import os
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
t0, t1, dt = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])

env = dict(os.environ, DISPLAY=':0')
proc = subprocess.Popen(
    ['xplus4', '-default', '+warp', '+sound', '-autostartprgmode', '1',
     '-remotemonitor', '-remotemonitoraddress', 'ip4://127.0.0.1:6510',
     '-autostart', os.path.join(ROOT, 'build', 'demo.prg')],
    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    start = time.time()
    s = None
    for _ in range(40):
        try:
            s = socket.create_connection(('127.0.0.1', 6510), timeout=10)
            break
        except OSError:
            time.sleep(0.5)
    s.settimeout(2)

    def cmd(c, wait=0.3):
        s.sendall((c + '\n').encode())
        time.sleep(wait)
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

    cmd('g')   # ensure running (connect may have halted it)
    t = t0
    while t <= t1:
        now = time.time() - start
        if now < t:
            time.sleep(t - now)
        ent = cmd('m 005a 005a')        # halts; entryi
        cmd(f'screenshot "build/ser_{int(t)}.png" 2')
        cmd('g')
        e = ent.split()[1] if '>' in ent else '?'
        print(f't={t:.0f}s entryi={ent.strip().splitlines()[-1][:30]}')
        t += dt
    cmd('x')
finally:
    proc.kill()
