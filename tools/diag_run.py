#!/usr/bin/env python3
"""Screenshot + engine state at given wall times.
Usage: python3 tools/diag_run.py t1 t2 t3 ..."""
import os
import re
import socket
import subprocess
import sys
import time

ROOT = '/mnt/d/Toyprojects/10_Plus4VectorStream'
times = [float(a) for a in sys.argv[1:]]


def sym(name):
    """Address from the ACME symbol list (rebuilds shift code labels)."""
    for line in open(os.path.join(ROOT, 'build', 'demo_sym.txt')):
        m = re.match(r'\s*' + name + r'\s*=\s*\$([0-9a-f]+)', line)
        if m:
            return int(m.group(1), 16)
    raise KeyError(name)


MUSATT = sym('musatt')

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
        zp = mem(0x50, 0x5F)            # halts the emu
        zf = mem(0xF2, 0xFF)
        mus = mem(MUSATT, MUSATT + 1)   # musatt, curtune
        ent = zp[0x0A] if len(zp) > 10 else -1
        cmd(f'screenshot "build/diag_{int(t)}.png" 2')
        cmd('g')
        if len(zf) >= 8:
            def s8(v):
                return v - 256 if v >= 128 else v
            print(f't={t:5.1f}s entry={ent} tick={zp[0]:3d} '
                  f'mphase={zf[0]:3d} mx={zf[1]:3d} my={zf[2]:3d} '
                  f'dxc={s8(zf[3]):4d} dyc={s8(zf[4]):4d} '
                  f'xf={zf[5]} yf={zf[6]} '
                  f'tune={mus[1]} att={mus[0]}')
        else:
            print(f't={t:5.1f}s entry={ent} (zp read failed)')
    cmd('x')
finally:
    proc.kill()
