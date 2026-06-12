#!/usr/bin/env python3
"""Run the demo at normal speed, take a monitor screenshot after N real
seconds. Usage: python3 tools/realtime_shot.py <seconds> <out.png>"""
import os
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
secs = float(sys.argv[1])
out = sys.argv[2]

env = dict(os.environ, DISPLAY=':0')
proc = subprocess.Popen(
    ['xplus4', '-default', '+warp', '+sound', '-autostartprgmode', '1',
     '-remotemonitor', '-remotemonitoraddress', 'ip4://127.0.0.1:6510',
     '-autostart', os.path.join(ROOT, 'build', 'demo.prg')],
    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(secs)
    s = None
    for _ in range(20):
        try:
            s = socket.create_connection(('127.0.0.1', 6510), timeout=10)
            break
        except OSError:
            time.sleep(0.5)
    s.settimeout(3)

    def cmd(c):
        s.sendall((c + '\n').encode())
        time.sleep(0.5)
        try:
            while s.recv(65536):
                pass
        except socket.timeout:
            pass

    cmd(f'screenshot "{out}" 2')
    cmd('x')
    s.close()
    time.sleep(1)
    print(out, os.path.getsize(out))
finally:
    proc.kill()
