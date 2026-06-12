#!/usr/bin/env python3
"""Run cycprobe.prg in xplus4 and read the measured main-loop budget."""
import os
import socket
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env = dict(os.environ, DISPLAY=':0')
proc = subprocess.Popen(
    ['xplus4', '-default', '-warp', '+sound', '-autostartprgmode', '1',
     '-remotemonitor', '-remotemonitoraddress', 'ip4://127.0.0.1:6510',
     '-autostart', os.path.join(ROOT, 'build', 'cycprobe.prg')],
    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

try:
    time.sleep(8)
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

    cmd('bank cpu')
    for attempt in range(30):
        dump = cmd('m 0f00 0f03')
        # parse ">C:0f00  xx xx xx xx ..."
        for line in dump.splitlines():
            if '0f00' in line.lower() and ':' in line:
                parts = line.split()
                try:
                    idx = next(i for i, p in enumerate(parts)
                               if p.lower().endswith('0f00'))
                    by = [int(x, 16) for x in parts[idx+1:idx+5]]
                except (StopIteration, ValueError):
                    continue
                if len(by) == 4 and by[3] == 0x5E:
                    iters = by[0] | (by[1] << 8) | (by[2] << 16)
                    per_tick = iters * 16 / 250
                    print(f'iterations: {iters}')
                    print(f'main-loop budget: {per_tick:.0f} cycles per '
                          f'50Hz tick = {2*per_tick:.0f} per 25fps frame '
                          f'(net of IRQ+music)')
                    cmd('x')
                    raise SystemExit(0)
        cmd('x')        # resume and wait some more
        time.sleep(2)
    print('probe did not finish; last dump:')
    print(dump)
finally:
    time.sleep(0.5)
    proc.kill()
