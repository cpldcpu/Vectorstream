#!/usr/bin/env python3
"""Run decprobe.prg, read the decode count."""
import os
import re
import socket
import subprocess
import time

ROOT = '/mnt/d/Toyprojects/10_Plus4VectorStream'
env = dict(os.environ, DISPLAY=':0')
proc = subprocess.Popen(
    ['xplus4', '-default', '-warp', '+sound', '-autostartprgmode', '1',
     '-remotemonitor', '-remotemonitoraddress', 'ip4://127.0.0.1:6510',
     '-autostart', os.path.join(ROOT, 'build', 'decprobe.prg')],
    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(8)
    s = socket.create_connection(('127.0.0.1', 6510), timeout=10)
    s.settimeout(3)

    def cmd(c):
        s.sendall((c + '\n').encode())
        time.sleep(0.4)
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

    for _ in range(30):
        d = cmd('m 0f20 0f22')
        m = re.search(r'>C:0f20\s+([0-9a-f]{2})\s+([0-9a-f]{2})\s+([0-9a-f]{2})',
                      d)
        if m and int(m.group(3), 16) == 0x5E:
            n = int(m.group(1), 16) | (int(m.group(2), 16) << 8)
            print(f'decodes in 250 ticks: {n}  -> {250/n:.2f} ticks/decode '
                  f'= {250/n*22074:.0f} VICE-budget cycles')
            break
        cmd('x')
        time.sleep(2)
finally:
    proc.kill()
