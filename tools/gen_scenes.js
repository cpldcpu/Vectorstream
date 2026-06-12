// Render the demo scenes to raw screen-code frames using the renderer
// extracted from the demo HTML (v10cs/core.js) and the corner-diag atlas.
//
// For periodic scenes, frame i is rendered at angle0 + period*i/n so that
// frame n would exactly equal frame 0 (loop). For 'free' scenes the angle
// advances rate/25 per frame (25 fps timestep), one-shot.
//
// Outputs (in build/): frames_<name>.bin (n x 1000 bytes), charset.bin
// (2048 bytes, corner-diag), and a wrap report on stdout.
//
// Usage: node tools/gen_scenes.js
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
// core.js declares `let currentShape` which stays in the eval's lexical
// scope - a bare `currentShape = x` here would silently create a global
// the eval'd functions never see. Append a setter that closes over it.
eval(fs.readFileSync(path.join(ROOT, 'v10cs', 'core.js'), 'utf8')
     + '\nglobalThis.setShape = (s) => { currentShape = s; };'
     + '\nglobalThis.SHAPES_ = SHAPES;');

// ---------------------------------------------------------------------
// Recolor the icosahedron so the coloring is symmetric under a rotation
// of pi about Y. Geometrically the icosahedron has that symmetry; the
// arbitrary 3-coloring from colorFaces3 breaks it, forcing a 2*pi loop.
// Pairing the faces into pi-orbits and coloring orbits greedily restores
// a pi color period - the encoded loop halves in size.
// ---------------------------------------------------------------------
function symmetrizeIcosa() {
  const sh = SHAPES_.icosahedron;
  const V = sh.V, F = sh.F;
  const perm = V.map(v => {
    const t = [-v[0], v[1], -v[2]];
    let best = -1, bd = 1e9;
    V.forEach((u, j) => {
      const d = (u[0]-t[0])**2 + (u[1]-t[1])**2 + (u[2]-t[2])**2;
      if (d < bd) { bd = d; best = j; }
    });
    return best;
  });
  const keyOf = idx => idx.slice().sort((a, b) => a - b).join(',');
  const byKey = new Map();
  F.forEach((f, i) => byKey.set(keyOf(f.idx), i));
  const mate = F.map(f => byKey.get(keyOf(f.idx.map(i => perm[i]))));
  // face adjacency: share >= 2 vertices
  const sets = F.map(f => new Set(f.idx));
  const adj = F.map(() => []);
  for (let i = 0; i < F.length; i++)
    for (let j = i + 1; j < F.length; j++) {
      let s = 0;
      for (const v of sets[j]) if (sets[i].has(v)) s++;
      if (s >= 2) { adj[i].push(j); adj[j].push(i); }
    }
  // orbits under the pi map
  const orbitOf = new Array(F.length).fill(-1);
  const orbits = [];
  F.forEach((f, i) => {
    if (orbitOf[i] >= 0) return;
    const o = orbits.length;
    orbitOf[i] = o;
    orbitOf[mate[i]] = o;
    orbits.push(i === mate[i] ? [i] : [i, mate[i]]);
  });
  // greedy least-conflict 3-coloring over orbits, high degree first
  const odeg = orbits.map(o => o.reduce((s, f) => s + adj[f].length, 0));
  const order = orbits.map((_, i) => i).sort((a, b) => odeg[b] - odeg[a]);
  const ocol = new Array(orbits.length).fill(-1);
  let conflicts = 0;
  for (const o of order) {
    const cnt = [0, 0, 0];
    for (const f of orbits[o])
      for (const g of adj[f]) {
        if (orbitOf[g] !== o && ocol[orbitOf[g]] >= 0) cnt[ocol[orbitOf[g]]]++;
        if (orbitOf[g] === o && orbits[o].length === 2) cnt.fill(99); // intra-orbit clash unavoidable
      }
    let best = 0;
    for (let c = 1; c < 3; c++) if (cnt[c] < cnt[best]) best = c;
    ocol[o] = best;
    conflicts += Math.min(...cnt) === 99 ? 0 : cnt[best];
  }
  F.forEach((f, i) => { f.color = ocol[orbitOf[i]]; });
  console.log(`icosahedron recolored pi-symmetric (${orbits.length} orbits, `
              + `${conflicts} monochromatic adjacencies)`);
}
symmetrizeIcosa();

const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, 'demo.json'), 'utf8'));
const BUILD = path.join(ROOT, 'build');
fs.mkdirSync(BUILD, { recursive: true });

const fixed = buildFixedCharset('corner-diag');
fs.writeFileSync(path.join(BUILD, 'charset.bin'), Buffer.from(fixed.charset));
console.log('charset.bin (corner-diag, 2048 bytes)');

function renderAt(shape, mode, angle, scale) {
  setShape(shape);
  const ideal = rasterIdealFrame(angle, scale, mode);
  return renderFixedFrame(ideal.fb, fixed).screen;
}

// Like rasterIdealFrame, but with explicit per-axis angles and a movable
// projection center (for drifting tumble scenes). Mirrors the face
// culling / depth sort / raster steps from core.js.
const FBW = 160, FBH = 200;
function renderTumble(shapeName, rx, ry, rz, cx, cy, scale) {
  const shape = SHAPES_[shapeName];
  const fb = new Uint8Array(FBW * FBH);
  const verts = shape.V.map(v => rotate(v, rx, ry, rz));
  const SC = scale * 60;
  const proj = verts.map(v => project(v, SC, cx, cy));
  const faces = [];
  for (const f of shape.F) {
    const p = f.idx.map(i => proj[i]);
    let A2 = 0;
    for (let i = 0; i < p.length; i++) {
      const j = (i + 1) % p.length;
      A2 += (p[i][0] * p[j][1] - p[j][0] * p[i][1]);
    }
    if (A2 <= 0) continue;
    const z = f.idx.reduce((s, i) => s + verts[i][2], 0) / f.idx.length;
    faces.push({ pts: p, value: f.color + 1, z });
  }
  faces.sort((a, b) => b.z - a.z);
  for (const f of faces) rasterFace(fb, f.pts, f.value);
  return renderFixedFrame(fb, fixed).screen;
}

function periodOf(s) {
  if (s.period === 'pi') return Math.PI;
  if (s.period === '2pi') return 2 * Math.PI;
  if (s.period === '2pi/3') return 2 * Math.PI / 3;
  if (typeof s.period === 'number') return s.period;
  return null; // free
}

// Tumble scenes: rationally periodic free rotation + Lissajous drift,
// both with period = the loop length, so the whole thing loops exactly.
//   tumble: [p, q, r]  integer axis turns per loop
//   drift:  [ax, ay, qx, qy]  amplitudes (mc px) and integer cycle counts
function tumbleFrame(s, i, n, scale, a0) {
  const ph = 2 * Math.PI * i / n;
  const [p, q, r] = s.tumble;
  const d = s.drift || [0, 0, 1, 2];
  const cx = FBW / 2 + d[0] * Math.sin(d[2] * ph);
  const cy = FBH / 2 + d[1] * Math.sin(d[3] * ph + 1.1);
  return renderTumble(s.shape, p * ph + a0 * 0.61, q * ph + a0,
                      r * ph + a0 * 0.27, cx, cy, scale);
}

for (const s of cfg.scenes) {
  const n = s.frames;
  const scale = s.scale || cfg.scale;
  const a0 = (s.angle0 !== undefined) ? s.angle0 : cfg.angle0;
  const period = s.tumble ? null : periodOf(s);
  const buf = Buffer.alloc(n * 1000);
  for (let i = 0; i < n; i++) {
    let screen;
    if (s.tumble)            screen = tumbleFrame(s, i, n, scale, a0);
    else if (period !== null) screen = renderAt(s.shape, s.mode, a0 + period * i / n, scale);
    else                      screen = renderAt(s.shape, s.mode, a0 + s.rate * i / 25, scale);
    Buffer.from(screen).copy(buf, i * 1000);
  }
  fs.writeFileSync(path.join(BUILD, `frames_${s.name}.bin`), buf);

  // wrap check: frame n vs frame 0
  let report;
  let wrap = null;
  if (s.tumble)             wrap = Buffer.from(tumbleFrame(s, n, n, scale, a0));
  else if (period !== null) wrap = Buffer.from(renderAt(s.shape, s.mode, a0 + period, scale));
  if (wrap) {
    let diff = 0;
    for (let i = 0; i < 1000; i++) if (wrap[i] !== buf[i]) diff++;
    report = `loop wrap diff ${diff}/1000 cells`;
  } else {
    report = 'one-shot (free)';
  }
  console.log(`frames_${s.name}.bin  ${n} frames  ${report}`);
}
