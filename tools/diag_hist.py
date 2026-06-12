#!/usr/bin/env python3
"""Dump the wait_25 lateness histogram at given wall times.
Usage: python3 tools/diag_hist.py t1 t2 ..."""
import os
import re
import socket
import subprocess
import sys
import time

ROOT = '/mnt/d/Toyprojects/10_Plus4VectorStream'
times = [float(a) for a in sys.argv[1:]]

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
        o = b''
        try:
            while True:
                b = s.recv(65536)
                if not b:
                    break
                o += b
        except socket.timeout:
            pass
        return o.decode(errors='replace')

    def mem(lo, hi):
        d = cmd(f'm {lo:04x} {hi:04x}')
        by = []
        for line in d.splitlines():
            m = re.search(r'>C:[0-9a-f]{4}\s+((?:[0-9a-f]{2}\s+)+)', line)
            if m:
                by += [int(x, 16) for x in m.group(1).split()]
        return by

    cmd('g')
    for t in times:
        now = time.time() - start
        if now < t:
            time.sleep(t - now)
        h = mem(0x0F10, 0x0F1B)
        e = mem(0x005A, 0x005A)
        zp = mem(0x50, 0x50)
        cmd('g')
        print(f't={t:5.1f}s entry={e[0] if e else "?"} tick={zp[0]:3d} '
              f'late={h[:4]} render-ticks={h[4:8]} '
              f'flipwait={h[10]} earlywait={h[11]}')
    cmd('x')
finally:
    proc.kill()
