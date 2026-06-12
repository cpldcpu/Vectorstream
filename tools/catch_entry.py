#!/usr/bin/env python3
"""Poll until entryi == target, then wait extra seconds and screenshot.
Usage: python3 tools/catch_entry.py <entry> <extra_s> <out.png>"""
import os
import re
import socket
import subprocess
import sys
import time

ROOT = '/mnt/d/Toyprojects/10_Plus4VectorStream'
target = int(sys.argv[1])
extra = float(sys.argv[2])
out = sys.argv[3]


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
    s = None
    for _ in range(40):
        try:
            s = socket.create_connection(('127.0.0.1', 6510), timeout=10)
            break
        except OSError:
            time.sleep(0.5)
    s.settimeout(2)

    def cmd(c, wait=0.25):
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

    cmd('g')
    for _ in range(120):
        time.sleep(1.5)
        d = cmd('m 005a 005a')
        m = re.search(r'>C:005a\s+([0-9a-f]{2})', d)
        cmd('g')
        if m and int(m.group(1), 16) == target:
            time.sleep(extra)
            mus = cmd(f'm {MUSATT:04x} {MUSATT + 1:04x}')
            mm = re.search(r'>C:[0-9a-f]{4}\s+([0-9a-f]{2})\s+([0-9a-f]{2})',
                           mus)
            cmd(f'screenshot "{out}" 2')
            cmd('g')
            att, tune = ((int(mm.group(1), 16), int(mm.group(2), 16))
                         if mm else ('?', '?'))
            print(f'caught entry {target}+{extra}s: tune={tune} att={att} '
                  f'shot {out}')
            break
    else:
        print('never caught entry', target)
    cmd('x')
finally:
    proc.kill()
