#!/usr/bin/env python3
# TED tune data: generates song_data.asm for the 6502 player and provides
# a cycle-exact-at-frame-level Python reference model for verification.
CLK = 110840.46875  # PAL: 1.7734475 MHz / 16

SEMI = {'C':0,'C#':1,'D':2,'D#':3,'E':4,'F':5,'F#':6,'G':7,'G#':8,'A':9,'A#':10,'B':11}
def note_idx(s):
    if s == 'OFF': return 0xFE
    base = s[0:2] if s[1] == '#' else s[0]
    octv = int(s[-1])
    return SEMI[base] + 12*octv

def note_to_n(idx):
    f = 440.0 * 2 ** ((idx - 57) / 12)
    n = 1024 - round(CLK / f)
    return max(0, min(1022, n))

NOTE_TABLE = [note_to_n(i) for i in range(96)]

FLG_NOISE, FLG_FIX = 1, 2

# name -> dict(env, sus, rel, arp, vib(delay, table), flags, fixn, slide)
INS_ORDER = ['BASS','BASS2','ARP','ARPM','ARPS','ARPSM','LEAD','LEAD2','PAD',
             'KICK','SNARE','HAT','BASSD']
INS = {
 'BASS' : dict(env=[8,8,7,6,6,5,5,4,4,3,2,0]),
 'BASS2': dict(env=[6,6,6,6,5,5,5,5,5,4,4,4,4,4,4,4,3,3,3,3,3,3,2,2,2,2,1,1,0]),
 'ARP'  : dict(env=[8,6,5,4,3,2,1,0], arp=[0,3,7]),
 'ARPM' : dict(env=[8,6,5,4,3,2,1,0], arp=[0,4,7]),
 'ARPS' : dict(env=[5,6,6,5,5,4,4,3,3,2,2,1,1,0], arp=[0,3,7,12]),
 'ARPSM': dict(env=[5,6,6,5,5,4,4,3,3,2,2,1,1,0], arp=[0,4,7,12]),
 'LEAD' : dict(env=[7,8,8,8,7,7,7,7,6,6,6,6], sus=11,
               vibdel=14, vib=[0,3,3,0,-3,-3], rel=[6,4,2,1,0]),
 'LEAD2': dict(env=[8,8,7,7,6,6,6], sus=6,
               vibdel=10, vib=[0,2,1,-1,-2], rel=[5,3,1,0]),
 'PAD'  : dict(env=[3,4,5,5,6,6], sus=5,
               vibdel=24, vib=[0,1,2,2,1,0,-1,-2,-2,-1], rel=[5,4,3,2,2,1,1,0]),
 'KICK' : dict(env=[8,7,5,2,0], fixn=470, slide=-90),
 'SNARE': dict(env=[8,6,5,3,2,1,0], fixn=1012, noise=True),
 'HAT'  : dict(env=[5,3,0], fixn=1016, noise=True),
 'BASSD': dict(env=[8,7,6,4,2,0]),
}
INS_IDX = {n:i for i,n in enumerate(INS_ORDER)}

# ---------------- patterns ----------------
def pat(cells):
    p = [None]*16
    for r,n,i in cells: p[r] = (n,i)
    return p
def arp_pat(note, ins):
    return pat([(r,note,ins) for r in range(0,16,2)])
def bd(R,R2):
    return pat([(0,'G-3','KICK'),(2,R,'BASS'),(4,'G-3','SNARE'),(6,R,'BASS'),
                (7,R2,'BASS'),(8,'G-3','KICK'),(10,R,'BASS'),(12,'G-3','SNARE'),
                (14,R2,'BASS'),(15,'G-3','HAT')])
def bd3(R,R2):
    return pat([(0,'G-3','KICK'),(1,R,'BASSD'),(2,R2,'BASSD'),(3,R,'BASSD'),
                (4,'G-3','SNARE'),(5,R,'BASSD'),(6,R2,'BASSD'),(7,R,'BASSD'),
                (8,'G-3','KICK'),(9,R,'BASSD'),(10,R2,'BASSD'),(11,R,'BASSD'),
                (12,'G-3','SNARE'),(13,R,'BASSD'),(14,R2,'BASSD'),(15,'G-3','HAT')])
def bp(R,R5):
    return pat([(0,'G-3','KICK'),(2,R,'BASS'),(3,R,'BASS'),(4,'G-3','SNARE'),
                (6,R5,'BASS'),(8,'G-3','KICK'),(10,R,'BASS'),(11,R,'BASS'),
                (12,'G-3','SNARE'),(14,R5,'BASS'),(15,'G-3','HAT')])

T1P = {
 'E':pat([]),
 'AAM':arp_pat('A-4','ARP'), 'AF':arp_pat('F-4','ARPM'),
 'AC':arp_pat('C-4','ARPM'), 'AG':arp_pat('G-4','ARPM'),
 'M1':pat([(0,'A-4','LEAD'),(4,'C-5','LEAD'),(6,'B-4','LEAD'),(8,'A-4','LEAD'),(10,'G-4','LEAD'),(12,'A-4','LEAD')]),
 'M2':pat([(0,'C-5','LEAD'),(4,'A-4','LEAD'),(6,'G-4','LEAD'),(8,'F-4','LEAD'),(12,'G-4','LEAD')]),
 'M3':pat([(0,'G-4','LEAD'),(4,'E-4','LEAD'),(8,'G-4','LEAD'),(10,'A-4','LEAD'),(12,'B-4','LEAD')]),
 'M4':pat([(0,'D-5','LEAD'),(4,'B-4','LEAD'),(8,'A-4','LEAD'),(10,'G-4','LEAD'),(12,'B-4','LEAD'),(15,'OFF','LEAD')]),
 'M5':pat([(0,'E-5','LEAD'),(4,'E-5','LEAD'),(6,'D-5','LEAD'),(8,'C-5','LEAD'),(10,'B-4','LEAD'),(12,'C-5','LEAD')]),
 'M6':pat([(0,'A-4','LEAD'),(4,'C-5','LEAD'),(6,'D-5','LEAD'),(8,'C-5','LEAD'),(12,'A-4','LEAD')]),
 'M7':pat([(0,'G-4','LEAD'),(4,'G-4','LEAD'),(6,'A-4','LEAD'),(8,'B-4','LEAD'),(10,'C-5','LEAD'),(12,'D-5','LEAD')]),
 'M8':pat([(0,'B-4','LEAD'),(4,'G-4','LEAD'),(8,'D-5','LEAD'),(12,'B-4','LEAD'),(14,'OFF','LEAD')]),
 'BAM':bd('A-2','A-3'), 'BF':bd('F-3','C-3'), 'BC':bd('C-3','G-3'), 'BG':bd('G-3','D-3'),
}
T2P = {
 'AA':arp_pat('A-4','ARPS'), 'AG':arp_pat('G-4','ARPSM'),
 'AF':arp_pat('F-4','ARPSM'), 'AE':arp_pat('E-4','ARPSM'),
 'SAM':pat([(0,'A-2','BASS2'),(8,'E-3','BASS2')]),
 'SG':pat([(0,'G-3','BASS2'),(8,'D-3','BASS2')]),
 'SF':pat([(0,'F-3','BASS2'),(8,'C-3','BASS2')]),
 'SE':pat([(0,'E-3','BASS2'),(8,'B-2','BASS2')]),
 'LA':pat([(0,'A-4','PAD'),(12,'C-5','PAD')]),
 'LB':pat([(0,'B-4','PAD'),(12,'D-5','PAD')]),
 'LC':pat([(0,'C-5','PAD'),(12,'E-5','PAD')]),
 'LE':pat([(0,'B-4','PAD'),(8,'G#4','PAD'),(14,'OFF','PAD')]),
}
T3P = {
 'E':pat([]),
 'ADM':arp_pat('D-4','ARP'), 'ABB':arp_pat('A#3','ARPM'),
 'AC3':arp_pat('C-4','ARPM'), 'AA3':arp_pat('A-3','ARPM'),
 'N1':pat([(0,'A-4','LEAD'),(3,'D-5','LEAD'),(6,'C-5','LEAD'),(8,'A-4','LEAD'),(11,'F-4','LEAD'),(14,'G-4','LEAD')]),
 'N2':pat([(0,'F-4','LEAD'),(3,'A#4','LEAD'),(6,'A-4','LEAD'),(8,'F-4','LEAD'),(11,'D-4','LEAD'),(14,'F-4','LEAD')]),
 'N3':pat([(0,'E-4','LEAD'),(3,'G-4','LEAD'),(6,'C-5','LEAD'),(8,'G-4','LEAD'),(11,'A-4','LEAD'),(14,'B-4','LEAD')]),
 'N4':pat([(0,'C#5','LEAD'),(4,'E-5','LEAD'),(8,'C#5','LEAD'),(10,'B-4','LEAD'),(12,'A-4','LEAD')]),
 'N5':pat([(0,'D-5','LEAD'),(3,'E-5','LEAD'),(6,'F-5','LEAD'),(8,'E-5','LEAD'),(11,'D-5','LEAD'),(14,'C-5','LEAD')]),
 'N6':pat([(0,'A#4','LEAD'),(3,'D-5','LEAD'),(6,'F-5','LEAD'),(8,'D-5','LEAD'),(11,'C-5','LEAD'),(14,'A#4','LEAD')]),
 'N7':pat([(0,'G-4','LEAD'),(3,'C-5','LEAD'),(6,'E-5','LEAD'),(8,'D-5','LEAD'),(11,'C-5','LEAD'),(14,'B-4','LEAD')]),
 'N8':pat([(0,'A-4','LEAD'),(3,'C#5','LEAD'),(6,'E-5','LEAD'),(10,'D-5','LEAD'),(12,'C#5','LEAD'),(15,'OFF','LEAD')]),
 'BDM':bd3('D-3','D-4'), 'BBB':bd3('A#2','A#3'), 'BC3':bd3('C-3','C-4'), 'BA3':bd3('A-2','A-3'),
}
T4P = {
 'H1':pat([(0,'C-5','LEAD2'),(2,'D-5','LEAD2'),(4,'E-5','LEAD2'),(8,'G-5','LEAD2'),(10,'E-5','LEAD2'),(12,'D-5','LEAD2')]),
 'H2':pat([(0,'B-4','LEAD2'),(2,'C-5','LEAD2'),(4,'D-5','LEAD2'),(8,'G-4','LEAD2'),(12,'B-4','LEAD2')]),
 'H3':pat([(0,'C-5','LEAD2'),(2,'D-5','LEAD2'),(4,'E-5','LEAD2'),(8,'A-5','LEAD2'),(10,'E-5','LEAD2'),(12,'C-5','LEAD2')]),
 'H4':pat([(0,'D-5','LEAD2'),(2,'C-5','LEAD2'),(4,'A-4','LEAD2'),(8,'G-4','LEAD2'),(10,'A-4','LEAD2'),(12,'G-4','LEAD2'),(15,'OFF','LEAD2')]),
 'Q1':pat([(0,'E-5','LEAD2'),(3,'D-5','LEAD2'),(6,'C-5','LEAD2'),(8,'B-4','LEAD2'),(12,'C-5','LEAD2')]),
 'Q2':pat([(0,'F-4','LEAD2'),(3,'A-4','LEAD2'),(6,'C-5','LEAD2'),(8,'D-5','LEAD2'),(12,'C-5','LEAD2')]),
 'Q3':pat([(0,'G-4','LEAD2'),(3,'C-5','LEAD2'),(6,'E-5','LEAD2'),(8,'D-5','LEAD2'),(12,'G-4','LEAD2')]),
 'Q4':pat([(0,'B-4','LEAD2'),(3,'D-5','LEAD2'),(6,'G-5','LEAD2'),(8,'F#5','LEAD2'),(12,'D-5','LEAD2'),(14,'OFF','LEAD2')]),
 'PC':bp('C-3','G-3'), 'PG':bp('G-3','D-3'), 'PAM':bp('A-2','E-3'), 'PF':bp('F-3','C-3'),
}

TUNES = [
 dict(name='LATENT PULSE', speed=6, loop=2, pats=T1P, prefix='T1', order=[
   ('E','BAM'),('E','BAM'),
   ('AAM','BAM'),('AF','BF'),('AC','BC'),('AG','BG'),
   ('M1','BAM'),('M2','BF'),('M3','BC'),('M4','BG'),
   ('M5','BAM'),('M6','BF'),('M7','BC'),('M8','BG'),
   ('AAM','BAM'),('AF','BF'),('AC','BC'),('AG','BG')]),
 dict(name='BORDER GLOW', speed=8, loop=0, pats=T2P, prefix='T2', order=[
   ('AA','SAM'),('AG','SG'),('AF','SF'),('AE','SE'),
   ('LA','SAM'),('LB','SG'),('LC','SF'),('LE','SE')]),
 dict(name='NIGHT SHIFT', speed=5, loop=2, pats=T3P, prefix='T3', order=[
   ('E','BDM'),('E','BDM'),
   ('ADM','BDM'),('ABB','BBB'),('AC3','BC3'),('AA3','BA3'),
   ('N1','BDM'),('N2','BBB'),('N3','BC3'),('N4','BA3'),
   ('N5','BDM'),('N6','BBB'),('N7','BC3'),('N8','BA3'),
   ('ADM','BDM'),('ABB','BBB'),('AC3','BC3'),('AA3','BA3')]),
 dict(name='PHOSPHOR POP', speed=7, loop=0, pats=T4P, prefix='T4', order=[
   ('H1','PC'),('H2','PG'),('H3','PAM'),('H4','PF'),
   ('H1','PC'),('H2','PG'),('H3','PAM'),('H4','PF'),
   ('Q1','PAM'),('Q2','PF'),('Q3','PC'),('Q4','PG')]),
]

def pat_bytes(p):
    b = []
    for cell in p:
        if cell is None:
            b += [0, 0]
        else:
            n, i = cell
            b += [note_idx(n), INS_IDX[i]]
    return b

# ---------------- ASM emitter ----------------
def s8(v): return v & 0xFF
def emit_asm(path='song_data.asm'):
    L = []
    L.append('; generated by songdata.py - do not edit')
    L.append('FLG_NOISE = 1')
    L.append('FLG_FIX   = 2')
    L.append('note_lo:')
    L.append('\t!byte ' + ','.join(f'${v&0xff:02x}' for v in NOTE_TABLE))
    L.append('note_hi:')
    L.append('\t!byte ' + ','.join(f'${v>>8:02x}' for v in NOTE_TABLE))
    # instrument blobs
    for n in INS_ORDER:
        I = INS[n]
        L.append(f'env_{n}:\t!byte ' + ','.join(str(v) for v in I['env']))
        if 'rel' in I:
            L.append(f'rel_{n}:\t!byte ' + ','.join(str(v) for v in I['rel']))
        if 'arp' in I:
            L.append(f'arp_{n}:\t!byte ' + ','.join(str(v) for v in I['arp']))
        if 'vib' in I:
            L.append(f'vib_{n}:\t!byte ' + ','.join(f'${s8(v):02x}' for v in I['vib']))
    def tab(name, fn):
        L.append(f'{name}:\t!byte ' + ','.join(fn(INS[n], n) for n in INS_ORDER))
    tab('ins_envlo', lambda I,n: f'<env_{n}')
    tab('ins_envhi', lambda I,n: f'>env_{n}')
    tab('ins_envlen', lambda I,n: str(len(I['env'])))
    tab('ins_sus',   lambda I,n: str(I.get('sus', 0xff)))
    tab('ins_rello', lambda I,n: f'<rel_{n}' if 'rel' in I else '0')
    tab('ins_relhi', lambda I,n: f'>rel_{n}' if 'rel' in I else '0')
    tab('ins_rellen',lambda I,n: str(len(I['rel'])) if 'rel' in I else '0')
    tab('ins_arplo', lambda I,n: f'<arp_{n}' if 'arp' in I else '0')
    tab('ins_arphi', lambda I,n: f'>arp_{n}' if 'arp' in I else '0')
    tab('ins_arplen',lambda I,n: str(len(I['arp'])) if 'arp' in I else '0')
    tab('ins_viblo', lambda I,n: f'<vib_{n}' if 'vib' in I else '0')
    tab('ins_vibhi', lambda I,n: f'>vib_{n}' if 'vib' in I else '0')
    tab('ins_viblen',lambda I,n: str(len(I['vib'])) if 'vib' in I else '0')
    tab('ins_vibdel',lambda I,n: str(I.get('vibdel', 0)))
    tab('ins_flags', lambda I,n: str((FLG_NOISE if I.get('noise') else 0) |
                                     (FLG_FIX if 'fixn' in I else 0)))
    tab('ins_fixlo', lambda I,n: f'${I.get("fixn",0)&0xff:02x}')
    tab('ins_fixhi', lambda I,n: f'${I.get("fixn",0)>>8:02x}')
    tab('ins_slide', lambda I,n: f'${s8(I.get("slide",0)):02x}')
    # patterns
    for t in TUNES:
        pre = t['prefix']
        for pn, p in t['pats'].items():
            L.append(f'{pre}_{pn}:')
            L.append('\t!byte ' + ','.join(f'${b:02x}' for b in pat_bytes(p)))
    # orders
    for t in TUNES:
        pre = t['prefix'].lower()
        P = t['prefix']
        for col, sel in (('o1', 0), ('o2', 1)):
            names = [f'{P}_{o[sel]}' for o in t['order']]
            L.append(f'{pre}_{col}lo:\t!byte ' + ','.join(f'<{n}' for n in names))
            L.append(f'{pre}_{col}hi:\t!byte ' + ','.join(f'>{n}' for n in names))
    # tune directory
    pres = [t['prefix'].lower() for t in TUNES]
    for col in ('o1lo','o1hi','o2lo','o2hi'):
        L.append(f'tdir_{col}_lo:\t!byte ' + ','.join(f'<{p}_{col}' for p in pres))
        L.append(f'tdir_{col}_hi:\t!byte ' + ','.join(f'>{p}_{col}' for p in pres))
    L.append('tdir_len:\t!byte ' + ','.join(str(len(t['order'])) for t in TUNES))
    L.append('tdir_loop:\t!byte ' + ','.join(str(t['loop']) for t in TUNES))
    L.append('tdir_speed:\t!byte ' + ','.join(str(t['speed']) for t in TUNES))
    open(path, 'w').write('\n'.join(L) + '\n')
    print(f'wrote {path}')

# ---------------- reference player model ----------------
class RefVoice:
    def __init__(self):
        self.ins=0xff; self.note=0; self.f=0; self.rel=0; self.relf=0
        self.arppos=0; self.vibpos=0; self.curn=0; self.n=0
        self.env=0; self.on=0; self.noise=0

class RefPlayer:
    def __init__(self, tune):
        t = TUNES[tune]
        self.t = t
        self.frame=0; self.row=0; self.orderpos=0
        self.v = [RefVoice(), RefVoice()]
        self.reg = {0x0e:0, 0x0f:0, 0x10:0, 0x11:0, 0x12:0}
    def trigger(self, v, nb, ib):
        if nb == 0xFE:
            v.rel = 1; v.relf = 0; return
        v.note = nb; v.ins = ib
        v.f=0; v.rel=0; v.relf=0; v.arppos=0; v.vibpos=0
        I = INS[INS_ORDER[ib]]
        if 'fixn' in I:
            v.curn = I['fixn']
    def voice_frame(self, v):
        if v.ins == 0xff:
            v.env = 0; v.on = 0; return
        I = INS[INS_ORDER[v.ins]]
        env=I['env']; rel=I.get('rel',[]); arp=I.get('arp',[]); vib=I.get('vib',[])
        sus=I.get('sus',0xff)
        if v.rel:
            e = rel[v.relf] if v.relf < len(rel) else 0
            v.env = e
            if v.relf < 255: v.relf += 1
        else:
            if v.f < len(env): e = env[v.f]
            elif sus != 0xff:  e = env[sus]
            else:              e = 0
            v.env = e
        if 'fixn' in I:
            v.curn += I.get('slide', 0)
            if v.curn < 2: v.curn = 2
            v.n = v.curn
        else:
            note = v.note
            if arp:
                note = (note + arp[v.arppos]) & 0xff
                v.arppos += 1
                if v.arppos >= len(arp): v.arppos = 0
            n = NOTE_TABLE[note]
            if vib and v.f >= I['vibdel']:
                n += vib[v.vibpos]
                v.vibpos += 1
                if v.vibpos >= len(vib): v.vibpos = 0
            v.n = n
        v.noise = 1 if I.get('noise') else 0
        v.on = 1 if v.env > 0 else 0
        if v.f < 255: v.f += 1
    def tick(self):
        t = self.t
        if self.frame == 0:
            p1, p2 = t['order'][self.orderpos]
            for v, pname in ((self.v[0], p1), (self.v[1], p2)):
                b = pat_bytes(t['pats'][pname])
                nb, ib = b[self.row*2], b[self.row*2+1]
                if nb: self.trigger(v, nb, ib)
        self.voice_frame(self.v[0]); self.voice_frame(self.v[1])
        v0, v1 = self.v
        self.reg[0x0e] = v0.n & 0xff
        self.reg[0x12] = (self.reg[0x12] & 0xfc) | ((v0.n >> 8) & 3)
        self.reg[0x0f] = v1.n & 0xff
        self.reg[0x10] = (v1.n >> 8) & 3
        ctrl = max(v0.env, v1.env)
        if v0.on: ctrl |= 0x10
        if v1.on: ctrl |= 0x40 if v1.noise else 0x20
        self.reg[0x11] = ctrl
        self.frame += 1
        if self.frame >= t['speed']:
            self.frame = 0; self.row += 1
            if self.row >= 16:
                self.row = 0; self.orderpos += 1
                if self.orderpos >= len(t['order']):
                    self.orderpos = t['loop']
    def snapshot(self):
        r = self.reg
        return (r[0x0e], r[0x0f], r[0x10] & 3, r[0x11], r[0x12] & 3)

if __name__ == '__main__':
    emit_asm()
    # sanity: run each tune a few thousand frames
    for ti, t in enumerate(TUNES):
        rp = RefPlayer(ti)
        nz = 0
        for _ in range(3000):
            rp.tick()
            if rp.reg[0x11] & 0x0f: nz += 1
        print(f"tune {ti} ({t['name']}): {nz/3000:.0%} frames audible")
