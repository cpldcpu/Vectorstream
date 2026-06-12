
// =========================================================================
// Constants & palette
// =========================================================================
const SCREEN_CW = 40, SCREEN_CH = 25;     // chars
const CHAR_W = 4, CHAR_H = 8;             // multicolor pixels per char
const FB_W = SCREEN_CW * CHAR_W;          // 160
const FB_H = SCREEN_CH * CHAR_H;          // 200

// We assign:
//  framebuffer value 0 = BG  -> screen color black
//  framebuffer value 1 = MC1 -> blue/purple
//  framebuffer value 2 = MC2 -> yellow
//  framebuffer value 3 = CR  -> red (only valid where the char wants the per-char color)
const COL_BG  = '#0a0a14';
const COL_MC1 = '#6f5dc4';   // blue-violet
const COL_MC2 = '#cfe27c';   // yellow-green
const COL_CR  = '#b04646';   // red
const PALETTE = [COL_BG, COL_MC1, COL_MC2, COL_CR];

// =========================================================================
// Shape registry. Each entry has V (vertices) and F (faces). Faces are
// auto-oriented to CCW from outside (relative to origin) so we can author
// without hand-checking windings.
// =========================================================================
function dist2(a, b) { let s=0; for (let i=0;i<3;i++){const d=a[i]-b[i]; s+=d*d;} return s; }
function orientFace(idx, V) {
  // For a convex polyhedron centered at origin, the outward normal of a face
  // points away from origin. If (v1-v0)×(v2-v0) dotted with the face centroid
  // is negative, the winding is CW from outside; reverse it.
  const v0 = V[idx[0]], v1 = V[idx[1]], v2 = V[idx[2]];
  const a = [v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2]];
  const b = [v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2]];
  const n = [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];
  let cx=0, cy=0, cz=0;
  for (const i of idx) { cx+=V[i][0]; cy+=V[i][1]; cz+=V[i][2]; }
  if (n[0]*cx + n[1]*cy + n[2]*cz < 0) return idx.slice().reverse();
  return idx.slice();
}

// Color faces with up to 3 colors. Uses backtracking to find a proper 3-coloring
// if one exists; otherwise falls back to multi-trial greedy and returns the
// coloring with fewest monochromatic adjacent pairs. Returns {colors, conflicts}.
function colorFaces3(facesArr) {
  const N = facesArr.length;
  // Build face adjacency: two faces are adjacent if they share >= 2 vertices.
  const fAdj = Array.from({length: N}, () => []);
  const sets = facesArr.map(f => new Set(f.idx));
  for (let i = 0; i < N; i++) {
    for (let j = i+1; j < N; j++) {
      let s = 0;
      for (const v of sets[j]) if (sets[i].has(v)) s++;
      if (s >= 2) { fAdj[i].push(j); fAdj[j].push(i); }
    }
  }
  // Order vertices by descending degree (better backtracking)
  const order = Array.from({length: N}, (_, i) => i)
    .sort((a, b) => fAdj[b].length - fAdj[a].length);
  // Try proper 3-coloring
  const cols = new Array(N).fill(-1);
  function tryC(idx) {
    if (idx === N) return true;
    const i = order[idx];
    for (let c = 0; c < 3; c++) {
      let ok = true;
      for (const j of fAdj[i]) if (cols[j] === c) { ok = false; break; }
      if (!ok) continue;
      cols[i] = c;
      if (tryC(idx+1)) return true;
      cols[i] = -1;
    }
    return false;
  }
  if (tryC(0)) return { colors: cols.slice(), conflicts: 0 };
  // Fallback: greedy with many random orderings, take minimum-conflict.
  let best = { colors: null, conflicts: 1e9 };
  for (let trial = 0; trial < 200; trial++) {
    const c = new Array(N).fill(-1);
    const ord = Array.from({length: N}, (_, i) => i);
    for (let i = ord.length-1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i+1));
      [ord[i], ord[j]] = [ord[j], ord[i]];
    }
    for (const i of ord) {
      const used = new Set();
      for (const j of fAdj[i]) if (c[j] >= 0) used.add(c[j]);
      let col = 0;
      while (col < 3 && used.has(col)) col++;
      if (col >= 3) {
        // No conflict-free choice: pick color with fewest collisions.
        const cnt = [0,0,0];
        for (const j of fAdj[i]) if (c[j] >= 0) cnt[c[j]]++;
        let m = cnt[0], mi = 0;
        for (let k = 1; k < 3; k++) if (cnt[k] < m) { m = cnt[k]; mi = k; }
        col = mi;
      }
      c[i] = col;
    }
    let conf = 0;
    for (let i = 0; i < N; i++) for (const j of fAdj[i]) if (j > i && c[j] === c[i]) conf++;
    if (conf < best.conflicts) best = { colors: c, conflicts: conf };
    if (best.conflicts === 0) break;
  }
  return best;
}

function buildShape(V, F, normScale) {
  // Apply optional uniform scale so different shapes display at similar size.
  const Vs = V.map(v => [v[0]*normScale, v[1]*normScale, v[2]*normScale]);
  const Fs = F.map(f => ({ idx: orientFace(f.idx, Vs), color: f.color }));
  return { V: Vs, F: Fs };
}

const SHAPES = {
  cube: (() => {
    const V = [
      [-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],
      [-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1],
    ];
    // Opposite faces share a color so any rotation shows ≤ 3 face colors.
    const F = [
      { idx:[0,1,2,3], color:0 }, // back  (z=-1)
      { idx:[4,5,6,7], color:0 }, // front (z=+1)
      { idx:[0,1,5,4], color:1 }, // bottom
      { idx:[3,2,6,7], color:1 }, // top
      { idx:[0,4,7,3], color:2 }, // left
      { idx:[1,2,6,5], color:2 }, // right
    ];
    return buildShape(V, F, 1.0);
  })(),

  octahedron: (() => {
    // 6 vertices on axes, 8 triangular faces (one per octant).
    // Face graph is bipartite (its dual is the cube), so 2 colors give
    // proper coloring — every shared edge is a visible color change. We use
    // colors {0, 1} only; opposite octants alternate.
    const V = [
      [ 1, 0, 0], [-1, 0, 0],   // 0, 1
      [ 0, 1, 0], [ 0,-1, 0],   // 2, 3
      [ 0, 0, 1], [ 0, 0,-1],   // 4, 5
    ];
    // For each octant (sx,sy,sz), color = (sx*sy*sz > 0) ? 0 : 1
    // Vertex indices: +x=0,-x=1,+y=2,-y=3,+z=4,-z=5
    const oct = (sx, sy, sz) => [sx>0?0:1, sy>0?2:3, sz>0?4:5];
    const F = [];
    for (const sx of [+1,-1]) for (const sy of [+1,-1]) for (const sz of [+1,-1]) {
      F.push({ idx: oct(sx,sy,sz), color: (sx*sy*sz > 0) ? 0 : 1 });
    }
    // Scale up to roughly match cube bounding sphere (sqrt(3)).
    return buildShape(V, F, Math.sqrt(3));
  })(),

  hexprism: (() => {
    const V = [];
    for (let i = 0; i < 6; i++) {
      const a = i * Math.PI / 3;
      V.push([Math.cos(a), 1, Math.sin(a)]);  // top ring 0..5
    }
    for (let i = 0; i < 6; i++) {
      const a = i * Math.PI / 3;
      V.push([Math.cos(a), -1, Math.sin(a)]); // bottom ring 6..11
    }
    const F = [
      { idx: [0,1,2,3,4,5],     color: 1 }, // top hex
      { idx: [6,7,8,9,10,11],   color: 1 }, // bottom hex (same color, 'caps')
    ];
    // 6 rectangular sides — alternate two colors so adjacent sides differ.
    for (let i = 0; i < 6; i++) {
      const a = i, b = (i+1)%6;
      F.push({ idx: [a, b, b+6, a+6], color: (i%2===0) ? 0 : 2 });
    }
    return buildShape(V, F, Math.sqrt(3) / Math.sqrt(2)); // ~1.22 — match cube bounding sphere
  })(),

  icosahedron: (() => {
    const phi = (1 + Math.sqrt(5)) / 2;
    const V = [
      [0,  1,  phi], [0,  1, -phi], [0, -1,  phi], [0, -1, -phi],
      [1,  phi, 0 ], [1, -phi, 0 ], [-1, phi, 0 ], [-1,-phi, 0 ],
      [phi, 0,  1 ], [phi, 0, -1 ], [-phi,0,  1 ], [-phi,0, -1 ],
    ];
    // Detect 20 triangular faces by edge-length test (edge² = 4).
    const eps = 0.001, edgeLen2 = 4 + eps;
    const F = [];
    for (let i = 0; i < 12; i++)
      for (let j = i+1; j < 12; j++) {
        if (dist2(V[i], V[j]) > edgeLen2) continue;
        for (let k = j+1; k < 12; k++) {
          if (dist2(V[i], V[k]) > edgeLen2) continue;
          if (dist2(V[j], V[k]) > edgeLen2) continue;
          F.push({ idx: [i, j, k], color: 0 });
        }
      }
    // Proper 3-coloring exists (face graph is dodecahedron, χ = 3).
    const { colors } = colorFaces3(F);
    for (let i = 0; i < F.length; i++) F[i].color = colors[i];
    return buildShape(V, F, Math.sqrt(3) / Math.sqrt(phi + 2));
  })(),

  dodecahedron: (() => {
    const phi = (1 + Math.sqrt(5)) / 2;
    const inv = 1 / phi;
    const V = [
      // 8 cube-corner vertices
      [-1,-1,-1],[ 1,-1,-1],[ 1, 1,-1],[-1, 1,-1],
      [-1,-1, 1],[ 1,-1, 1],[ 1, 1, 1],[-1, 1, 1],
      // 12 "edge-rectangle" vertices on yz/xy/xz planes
      [ 0,-inv,-phi], [ 0, inv,-phi], [ 0,-inv, phi], [ 0, inv, phi],
      [-inv,-phi, 0], [ inv,-phi, 0], [-inv, phi, 0], [ inv, phi, 0],
      [-phi, 0,-inv], [-phi, 0, inv], [ phi, 0,-inv], [ phi, 0, inv],
    ];
    // Edge length² = 4/φ². Build adjacency.
    const eL2 = 4 / (phi * phi);
    const adj = V.map(() => []);
    for (let i = 0; i < 20; i++)
      for (let j = i+1; j < 20; j++) {
        if (Math.abs(dist2(V[i], V[j]) - eL2) < 0.01) {
          adj[i].push(j); adj[j].push(i);
        }
      }
    // Enumerate 5-cycles in the 1-skeleton — these are exactly the 12 pentagonal faces.
    const seen = new Set(), F = [];
    for (let v0 = 0; v0 < 20; v0++) {
      for (const v1 of adj[v0]) if (v1 > v0) {
        for (const v2 of adj[v1]) { if (v2 === v0) continue;
          for (const v3 of adj[v2]) { if (v3 === v1 || v3 === v0) continue;
            for (const v4 of adj[v3]) { if (v4 === v2 || v4 === v1 || v4 === v0) continue;
              if (!adj[v0].includes(v4)) continue;
              const key = [v0,v1,v2,v3,v4].slice().sort((a,b)=>a-b).join(',');
              if (seen.has(key)) continue;
              seen.add(key);
              F.push({ idx: [v0,v1,v2,v3,v4], color: 0 });
            }
          }
        }
      }
    }
    // Dodecahedron's face graph is the icosahedron (χ = 4), so a proper
    // 3-coloring is impossible. colorFaces3 will fall back to greedy and
    // typically finds a 4-4-4 distribution with ~3 monochromatic edges
    // out of 30 — those edges visually merge their faces.
    const { colors } = colorFaces3(F);
    for (let i = 0; i < F.length; i++) F[i].color = colors[i];
    // All 20 vertices are at radius sqrt(3), same as the cube.
    return buildShape(V, F, 1.0);
  })(),
};

let currentShape = 'cube';

// =========================================================================
// 3D transform & projection
// =========================================================================
function rotate(v, rx, ry, rz) {
  let [x,y,z] = v;
  // RY
  let c = Math.cos(ry), s = Math.sin(ry);
  [x,z] = [c*x + s*z, -s*x + c*z];
  // RX
  c = Math.cos(rx); s = Math.sin(rx);
  [y,z] = [c*y - s*z, s*y + c*z];
  // RZ
  c = Math.cos(rz); s = Math.sin(rz);
  [x,y] = [c*x - s*y, s*x + c*y];
  return [x,y,z];
}

function project(v, scale, cx, cy) {
  const d = 4.0;
  const w = d / (d + v[2]);
  // The framebuffer treats cells as square in coordinates, but mc pixels are
  // 2 mono px wide × 1 mono px tall. To draw a visually-square cube, the x
  // projection is halved here so that after the 2:1 display stretch the cube
  // becomes square in visual mono pixels.
  return [cx + v[0]*scale*w*0.5, cy - v[1]*scale*w];
}

// =========================================================================
// Polygon rasterization into framebuffer (value = color index 1..3 or 0)
// =========================================================================
function rasterFace(fb, pts, value) {
  let minY = Math.max(0, Math.floor(Math.min(...pts.map(p=>p[1]))));
  let maxY = Math.min(FB_H-1, Math.ceil (Math.max(...pts.map(p=>p[1]))));
  for (let y = minY; y <= maxY; y++) {
    const xs = [];
    const yy = y + 0.5;
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i], b = pts[(i+1)%pts.length];
      if ((a[1] <= yy && yy < b[1]) || (b[1] <= yy && yy < a[1])) {
        const t = (yy - a[1]) / (b[1] - a[1]);
        xs.push(a[0] + t * (b[0] - a[0]));
      }
    }
    xs.sort((u,v)=>u-v);
    for (let i = 0; i+1 < xs.length; i += 2) {
      const x0 = Math.max(0, Math.ceil (xs[i]   - 0.5));
      const x1 = Math.min(FB_W-1, Math.floor(xs[i+1] - 0.5));
      const rowOff = y * FB_W;
      for (let x = x0; x <= x1; x++) fb[rowOff + x] = value;
    }
  }
}

function rasterIdealFrame(angle, scale, rotMode) {
  rotMode = rotMode || 'free';
  const fb = new Uint8Array(FB_W * FB_H);
  const shape = SHAPES[currentShape];
  let rx, ry, rz;
  if (rotMode === 'y')      { rx = 0;          ry = angle; rz = 0; }
  else if (rotMode === 'x') { rx = angle;      ry = 0;     rz = 0; }
  else if (rotMode === 'z') { rx = 0;          ry = 0;     rz = angle; }
  else                      { rx = angle*0.61; ry = angle; rz = angle*0.27; }
  const verts = shape.V.map(v => rotate(v, rx, ry, rz));
  // project (SC is half-extent in visual mono pixels at scale=1)
  const SC = scale * 60;
  const proj = verts.map(v => project(v, SC, FB_W/2, FB_H/2));
  const faces = [];
  for (const f of shape.F) {
    const p = f.idx.map(i => proj[i]);
    // Signed area: positive => front-facing in our y-flipped screen
    // (faces are oriented CCW-from-outside; under the w=d/(d+z) convention
    // the camera is effectively at -z, so front faces project with A2 > 0).
    let A2 = 0;
    for (let i = 0; i < p.length; i++) {
      const j = (i+1) % p.length;
      A2 += (p[i][0]*p[j][1] - p[j][0]*p[i][1]);
    }
    if (A2 <= 0) continue;
    // depth = average z
    const z = f.idx.reduce((s,i)=>s+verts[i][2], 0) / f.idx.length;
    faces.push({pts: p, value: f.color + 1, z, faceColor: f.color});
  }
  faces.sort((a,b)=> b.z - a.z); // far first (larger z = further from -z camera)
  for (const f of faces) rasterFace(fb, f.pts, f.value);
  // also detect which 3 face colors are present (for stat)
  const colors = new Set();
  for (const f of faces) colors.add(f.faceColor);
  return { fb, faces, faceColorsVisible: [...colors].sort() };
}

// =========================================================================
// Char chunking: framebuffer -> per-char {bytes, colorRam, hasCR}
//   - bytes[8]: each byte = 4 mc pixels (2 bits each, leftmost in high bits)
//   - colorRam: which face color is assigned to '11' bits in this char
// =========================================================================
function chunkChar(fb, cx, cy) {
  const bytes = new Uint8Array(8);
  const ox = cx * CHAR_W, oy = cy * CHAR_H;
  let hasCR = false;
  let colorSet = 0; // bitmask of which values 0..3 appear
  for (let py = 0; py < CHAR_H; py++) {
    let b = 0;
    for (let px = 0; px < CHAR_W; px++) {
      const v = fb[(oy+py)*FB_W + (ox+px)] & 3;
      colorSet |= (1 << v);
      if (v === 3) hasCR = true;
      b = (b << 2) | v;
    }
    bytes[py] = b;
  }
  return { bytes, hasCR, colorSet };
}

// =========================================================================
// Display rendering: given (charset Uint8Array of 256*8, screen char indices,
// per-char color-RAM 0..3 indicating which "logical" face is at '11' bit),
// blit pixels into a Uint8Array of size FB_W*FB_H of color codes 0..3.
// (We treat '11' bits as code 3 directly; ideal & rendered both use codes
// 0..3 -> same palette, so RMS is meaningful.)
// =========================================================================
function renderToFB(charset, screen, fbOut) {
  for (let cy = 0; cy < SCREEN_CH; cy++) {
    for (let cx = 0; cx < SCREEN_CW; cx++) {
      const idx = screen[cy*SCREEN_CW + cx];
      const ox = cx*CHAR_W, oy = cy*CHAR_H;
      const base = idx*8;
      for (let py = 0; py < CHAR_H; py++) {
        const b = charset[base + py];
        fbOut[(oy+py)*FB_W + ox + 0] = (b >> 6) & 3;
        fbOut[(oy+py)*FB_W + ox + 1] = (b >> 4) & 3;
        fbOut[(oy+py)*FB_W + ox + 2] = (b >> 2) & 3;
        fbOut[(oy+py)*FB_W + ox + 3] =  b       & 3;
      }
    }
  }
}

// =========================================================================
// Fixed charset construction
// =========================================================================
const COLOR_PAIRS = [
  [0,1], // bg / MC1
  [0,2], // bg / MC2
  [0,3], // bg / CR
  [1,2], // MC1 / MC2
  [1,3], // MC1 / CR
  [2,3], // MC2 / CR
];

// generate a line-cut 4x8 pattern. (angleRad, signedDist in cells from char center)
// "value A" goes to pixels where (cos t * (x-cx) + sin t * (y-cy)) < signedDist
// "value B" elsewhere. Coordinates use cell centers and treat cells as 1x1
// (matching how the framebuffer rasterizer fills them — visual aspect is
// applied only at display time).
function genLinePattern(angleRad, signedDist, valA, valB) {
  const bytes = new Uint8Array(8);
  let ct = Math.cos(angleRad), st = Math.sin(angleRad);
  // Snap cardinal angles to exact zero — Math.sin(Math.PI) returns 1.22e-16,
  // not 0, which introduces a faint pseudo-tilt at "vertical" gradient angles.
  // The matcher then prefers these almost-vertical-but-not patterns over the
  // true verticals at certain sub-pixel positions, producing comb artifacts
  // along otherwise-vertical edges. Snap fixes it.
  if (Math.abs(ct) < 1e-12) ct = 0;
  if (Math.abs(st) < 1e-12) st = 0;
  const cx = (CHAR_W - 1) / 2;       // 1.5
  const cy = (CHAR_H - 1) / 2;       // 3.5
  for (let py = 0; py < CHAR_H; py++) {
    let b = 0;
    for (let px = 0; px < CHAR_W; px++) {
      const d = ct*(px - cx) + st*(py - cy);
      const v = (d < signedDist) ? valA : valB;
      b = (b << 2) | v;
    }
    bytes[py] = b;
  }
  return bytes;
}

function buildFixedCharset(layout) {
  // returns { charset: Uint8Array(256*8), meta: array of 256 entries {kind, valA, valB, angle, offset} }
  const charset = new Uint8Array(256*8);
  const meta = new Array(256);

  // 0..3: solid chars (all 00, 01, 10, 11)
  for (let v = 0; v < 4; v++) {
    const byte = (v<<6)|(v<<4)|(v<<2)|v;
    for (let py = 0; py < 8; py++) charset[v*8 + py] = byte;
    meta[v] = { kind:'solid', val:v };
  }

  let slot = 4;

  // Each layout produces a "plan": an array of
  //   { angle, offsetCount, offsetRange }
  // entries, repeated once per color pair. This factors out the previously
  // uniform grid so axial-rotation layouts can vary offset count per angle.
  let pairs = COLOR_PAIRS;
  let plan;
  const D = Math.PI / 180; // deg -> rad helper

  if (layout === '6x7') {
    plan = [];
    for (let i = 0; i < 6; i++) plan.push({ angle: (i/6)*2*Math.PI, offsetCount: 7, offsetRange: 3.5 });
  }
  else if (layout === 'y-opt-6x7') {
    // 6 gradient angles = 3 line orientations × 2 polarities, clustered at the
    // axial directions. Critically, every line orientation MUST appear with both
    // polarities (θ and θ+180°) because a tile may have e.g. red-above-blue OR
    // blue-above-red and the matcher needs both. Single-polarity coverage was
    // an early mistake — see the angle histogram in the analysis text below.
    //   { 0°, 180°} → vertical line, 2 polarities
    //   {90°, 270°} → horizontal line, 2 polarities
    //   {75°, 255°} → line tilted ~+15°, 2 polarities
    const angDeg = [0, 180, 90, 270, 75, 255];
    plan = angDeg.map(d => ({ angle: d*D, offsetCount: 7, offsetRange: 3.5 }));
  }
  else if (layout === 'axial-h8v6') {
    // 6 line orientations × 2 polarities = 12 gradient angles.
    // FIXED from the earlier 4-line version which had two structural problems:
    //   (1) vertical line offsets {−1.5, ±0.5, 1.5} included a degenerate
    //       all-B duplicate of the solid char at sd=−1.5, wasting 12 slots
    //       across pairs;
    //   (2) tilts were ONLY ±15° from horizontal — leaving no representation
    //       for near-vertical edges (the common case for cube edges originally
    //       parallel to Y under modest free rotation).
    //
    // Per-pair: 6+6 + 3+3 + 3+3+3+3 + 3+3+3+3 = 42 → 42×6 + 4 = 256.
    plan = [
      // horizontal line (gradient ±y): 6 offsets per polarity, on row boundaries
      { angle:  90*D, offsetCount: 6, offsetRange: 2.5 },
      { angle: 270*D, offsetCount: 6, offsetRange: 2.5 },
      // vertical line (gradient ±x): 3 offsets per polarity, on column boundaries
      // sd ∈ {−1, 0, +1} = exact transitions between cols (0,1), (1,2), (2,3)
      { angle:   0*D, offsetCount: 3, offsetRange: 1.0 },
      { angle: 180*D, offsetCount: 3, offsetRange: 1.0 },
      // ±15° from VERTICAL — line orientations 75° and 105°
      // (gradient angles 165°/345° give line 75° = +15° from vert,
      //  gradient angles  15°/195° give line 105° = −15° from vert)
      // 3 offsets each, range 2.0 covers the diagonal cell-span
      { angle:  15*D, offsetCount: 3, offsetRange: 2.0 },
      { angle: 195*D, offsetCount: 3, offsetRange: 2.0 },
      { angle: 165*D, offsetCount: 3, offsetRange: 2.0 },
      { angle: 345*D, offsetCount: 3, offsetRange: 2.0 },
      // ±15° from HORIZONTAL — line orientations 15° and 165°
      // (gradient 75°/255° = line 165°, gradient 105°/285° = line 15°)
      { angle:  75*D, offsetCount: 3, offsetRange: 3.0 },
      { angle: 255*D, offsetCount: 3, offsetRange: 3.0 },
      { angle: 105*D, offsetCount: 3, offsetRange: 3.0 },
      { angle: 285*D, offsetCount: 3, offsetRange: 3.0 },
    ];
  }
  else if (layout === 'pure-axial') {
    // Cardinals only, no tilted chars at all. Demonstrates the lower bound of
    // an axial-only atlas: zero coverage for any tilted edge.
    // {90°,270°} ×16 + {0°,180°} ×5 = 32+10 = 42 per pair × 6 = 252 + 4 = 256.
    plan = [
      { angle:  90*D, offsetCount: 16, offsetRange: 3.5 }, // horiz pol A
      { angle: 270*D, offsetCount: 16, offsetRange: 3.5 }, // horiz pol B
      { angle:   0*D, offsetCount:  5, offsetRange: 1.5 }, // vert pol A (4 cols)
      { angle: 180*D, offsetCount:  5, offsetRange: 1.5 }, // vert pol B
    ];
  }
  else if (layout === 'corner-diag') {
    // 4 line orientations × 2 polarities = 8 gradient angles.
    // Designed in response to the question "can a Y-only-specialized atlas
    // beat axial-h8v6?" The answer turned out to apply more broadly.
    //
    // Key insight: under any axial rotation, the residual matching error is
    // not dominated by line-orientation mismatch — it's dominated by CORNER
    // TILES at face vertices, where two edges meet in an L-shape. The best
    // straight-line approximation of an L is a 45° diagonal through the
    // corner. The ±15° tilts in axial-h8v6 are too close to cardinal to help.
    //
    // This layout drops the ±15° tilts entirely and spends those slots on
    // dense 45°/135° diagonal coverage for corner tiles. Empirically beats
    // axial-h8v6 on essentially every shape × rotation-mode combination by
    // 10-30%, sometimes more on the highly-corner-heavy octahedron.
    //
    // Per pair: 7+7 + 3+3 + 6+6+5+5 = 42 → 42×6 + 4 = 256.
    plan = [
      // horizontal line: 7 offsets per polarity at row boundaries
      { angle:  90*D, offsetCount: 7, offsetRange: 3.0 },
      { angle: 270*D, offsetCount: 7, offsetRange: 3.0 },
      // vertical line: 3 offsets per polarity at column boundaries
      { angle:   0*D, offsetCount: 3, offsetRange: 1.0 },
      { angle: 180*D, offsetCount: 3, offsetRange: 1.0 },
      // +45° diagonal line (gradients 135°, 315°): 6 offsets each polarity
      { angle: 135*D, offsetCount: 6, offsetRange: 3.5 },
      { angle: 315*D, offsetCount: 6, offsetRange: 3.5 },
      // −45° diagonal line (gradients 45°, 225°): 5 offsets each polarity
      { angle:  45*D, offsetCount: 5, offsetRange: 3.0 },
      { angle: 225*D, offsetCount: 5, offsetRange: 3.0 },
    ];
  }
  else if (layout === '8x5') {
    plan = []; for (let i = 0; i < 8; i++) plan.push({ angle: (i/8)*2*Math.PI, offsetCount: 5, offsetRange: 3.0 });
  }
  else if (layout === '4x10') {
    plan = []; for (let i = 0; i < 4; i++) plan.push({ angle: (i/4)*2*Math.PI, offsetCount: 10, offsetRange: 3.5 });
  }
  else if (layout === '10x4') {
    plan = []; for (let i = 0; i < 10; i++) plan.push({ angle: (i/10)*2*Math.PI, offsetCount: 4, offsetRange: 3.0 });
  }
  else if (layout === '14x3') {
    plan = []; for (let i = 0; i < 14; i++) plan.push({ angle: (i/14)*2*Math.PI, offsetCount: 3, offsetRange: 3.2 });
  }
  else if (layout === '20x2') {
    plan = []; for (let i = 0; i < 20; i++) plan.push({ angle: (i/20)*2*Math.PI, offsetCount: 2, offsetRange: 2.0 });
  }
  else if (layout === 'all2color') {
    pairs = [ [0,1], [0,2], [1,2] ];
    plan = []; for (let i = 0; i < 14; i++) plan.push({ angle: (i/14)*2*Math.PI, offsetCount: 6, offsetRange: 3.2 });
  } else {
    plan = []; for (let i = 0; i < 6; i++) plan.push({ angle: (i/6)*2*Math.PI, offsetCount: 7, offsetRange: 3.5 });
  }

  for (const [vA, vB] of pairs) {
    for (const { angle, offsetCount, offsetRange } of plan) {
      for (let oi = 0; oi < offsetCount; oi++) {
        const off = (offsetCount === 1) ? 0 :
          (-offsetRange + 2*offsetRange * oi / (offsetCount - 1));
        if (slot >= 256) break;
        const bytes = genLinePattern(angle, off, vA, vB);
        for (let py = 0; py < 8; py++) charset[slot*8 + py] = bytes[py];
        meta[slot] = { kind:'edge', valA:vA, valB:vB, angle, offset:off };
        slot++;
      }
    }
  }
  // fill remaining with bg solid
  while (slot < 256) {
    for (let py = 0; py < 8; py++) charset[slot*8 + py] = 0;
    meta[slot] = { kind:'unused' };
    slot++;
  }
  return { charset, meta };
}

// =========================================================================
// Approach 1: match ideal char-tile against fixed charset
// =========================================================================
// We compute per-pixel mismatch (count of differing 2-bit cells), considering
// that the per-char color (3) can be remapped to any face color the char wants.
// Strategy: for each candidate fixed char, score it against the ideal tile
// under the bit interpretation defined by its meta. We restrict candidates by
// the ideal tile's value-set to keep the search practical.
function matchFixedCharForTile(tile, fixed) {
  // tile.bytes already encodes ideal in 2-bit codes (0..3 directly).
  // We pick the fixed char with minimum Hamming distance.
  // Group filter: only consider candidates whose {valA,valB} ⊆ tile.colorSet,
  // OR solid chars whose val ∈ tile.colorSet.
  let bestIdx = 0, bestDist = 1e9;
  const tColorSet = tile.colorSet;
  for (let i = 0; i < 256; i++) {
    const m = fixed.meta[i];
    if (m.kind === 'solid') {
      if (((tColorSet >> m.val) & 1) === 0 && tColorSet !== 0) continue;
    } else if (m.kind === 'edge') {
      // candidate makes use of valA, valB
      // accept candidate if those colors are present (or at least one is)
      const fA = (tColorSet >> m.valA) & 1;
      const fB = (tColorSet >> m.valB) & 1;
      if (!(fA && fB)) continue;
    } else continue;
    // Hamming over 32 cells
    let d = 0;
    const base = i*8;
    for (let py = 0; py < 8 && d < bestDist; py++) {
      const fb = fixed.charset[base+py];
      const tb = tile.bytes[py];
      // unroll 4 cells
      d += ((fb >> 6) & 3) !== ((tb >> 6) & 3) ? 1 : 0;
      d += ((fb >> 4) & 3) !== ((tb >> 4) & 3) ? 1 : 0;
      d += ((fb >> 2) & 3) !== ((tb >> 2) & 3) ? 1 : 0;
      d += ( fb       & 3) !== ( tb       & 3) ? 1 : 0;
    }
    if (d < bestDist) { bestDist = d; bestIdx = i; }
    if (bestDist === 0) break;
  }
  return { idx: bestIdx, dist: bestDist };
}

// =========================================================================
// Approach 2: build dynamic charset by storing each unique tile pattern
// =========================================================================
function buildDynamicFrame(fb) {
  // tile-bytes -> slot. cap at 256.
  const charset = new Uint8Array(256*8);
  const slotMap = new Map(); // key=pattern hex, val=slot index
  const screen = new Uint8Array(SCREEN_CW * SCREEN_CH);
  // pre-allocate solid chars for the 4 simple values to mirror "real" engine
  for (let v = 0; v < 4; v++) {
    const byte = (v<<6)|(v<<4)|(v<<2)|v;
    for (let py = 0; py < 8; py++) charset[v*8 + py] = byte;
    const k = byte.toString(16).padStart(2,'0').repeat(8);
    slotMap.set(k, v);
  }
  let nextSlot = 4;
  let overflow = 0;
  let edgeCharCount = 0;

  for (let cy = 0; cy < SCREEN_CH; cy++) {
    for (let cx = 0; cx < SCREEN_CW; cx++) {
      const t = chunkChar(fb, cx, cy);
      // key
      let key = '';
      for (let py = 0; py < 8; py++) key += t.bytes[py].toString(16).padStart(2,'0');
      let slot = slotMap.get(key);
      if (slot === undefined) {
        if (nextSlot < 256) {
          slot = nextSlot++;
          slotMap.set(key, slot);
          for (let py = 0; py < 8; py++) charset[slot*8 + py] = t.bytes[py];
        } else {
          overflow++;
          slot = 0; // fallback to bg
        }
      }
      screen[cy*SCREEN_CW + cx] = slot;
      // count an "edge" char as one with >1 distinct color in it
      const c = t.colorSet;
      let nColors = 0;
      for (let v = 0; v < 4; v++) if ((c>>v)&1) nColors++;
      if (nColors >= 2) edgeCharCount++;
    }
  }
  return { charset, screen, uniqueChars: nextSlot, edgeChars: edgeCharCount, overflow };
}

// =========================================================================
// Approach 2 with frame coherence: persistent slot pool, LRU eviction.
// Patterns that survive across frames reuse the same slot — no regen needed.
// =========================================================================
class SlotPool {
  constructor(size, reservedSolids) {
    this.size = size;
    this.reservedSolids = reservedSolids;
    this.charset = new Uint8Array(size * 8);
    this.patternToSlot = new Map();
    this.slotToPattern = new Array(size).fill(null);
    this.slotAge = new Uint16Array(size);
    this.regensThisFrame = 0;
    this.evictionsThisFrame = 0;
    this.totalRegens = 0;
    this.framesElapsed = 0;
    this._initSolids();
  }
  _initSolids() {
    for (let v = 0; v < this.reservedSolids; v++) {
      const byte = (v<<6)|(v<<4)|(v<<2)|v;
      for (let py = 0; py < 8; py++) this.charset[v*8 + py] = byte;
      const k = byte.toString(16).padStart(2,'0').repeat(8);
      this.patternToSlot.set(k, v);
      this.slotToPattern[v] = k;
      this.slotAge[v] = 0;
    }
  }
  reset() {
    this.patternToSlot.clear();
    for (let i = 0; i < this.size; i++) {
      this.slotToPattern[i] = null;
      this.slotAge[i] = 0;
    }
    this._initSolids();
    this.regensThisFrame = 0;
    this.totalRegens = 0;
    this.framesElapsed = 0;
  }
  beginFrame() {
    this.regensThisFrame = 0;
    this.evictionsThisFrame = 0;
    // age all non-reserved slots
    for (let i = this.reservedSolids; i < this.size; i++) this.slotAge[i]++;
    this.framesElapsed++;
  }
  lookupOrAlloc(patternBytes, key) {
    const existing = this.patternToSlot.get(key);
    if (existing !== undefined) {
      this.slotAge[existing] = 0;
      return existing;
    }
    // Miss: pick LRU non-reserved slot
    let victim = this.reservedSolids, victimAge = -1;
    for (let i = this.reservedSolids; i < this.size; i++) {
      if (this.slotAge[i] > victimAge) { victimAge = this.slotAge[i]; victim = i; }
    }
    const oldKey = this.slotToPattern[victim];
    if (oldKey !== null) {
      this.patternToSlot.delete(oldKey);
      this.evictionsThisFrame++;
    }
    this.slotToPattern[victim] = key;
    this.patternToSlot.set(key, victim);
    this.slotAge[victim] = 0;
    for (let py = 0; py < 8; py++) this.charset[victim*8 + py] = patternBytes[py];
    this.regensThisFrame++;
    this.totalRegens++;
    return victim;
  }
  activeCount() {
    let n = 0;
    for (let i = 0; i < this.size; i++) if (this.slotAge[i] === 0) n++;
    return n;
  }
}

function buildDynamicFrameCoherent(fb, pool) {
  pool.beginFrame();
  const screen = new Uint8Array(SCREEN_CW * SCREEN_CH);
  let edgeChars = 0;
  for (let cy = 0; cy < SCREEN_CH; cy++) {
    for (let cx = 0; cx < SCREEN_CW; cx++) {
      const t = chunkChar(fb, cx, cy);
      let key = '';
      for (let py = 0; py < 8; py++) key += t.bytes[py].toString(16).padStart(2,'0');
      const slot = pool.lookupOrAlloc(t.bytes, key);
      screen[cy*SCREEN_CW + cx] = slot;
      let nc = 0;
      for (let v = 0; v < 4; v++) if ((t.colorSet>>v)&1) nc++;
      if (nc >= 2) edgeChars++;
    }
  }
  return {
    charset: pool.charset,
    screen,
    active: pool.activeCount(),
    regens: pool.regensThisFrame,
    evictions: pool.evictionsThisFrame,
    totalRegens: pool.totalRegens,
    edgeChars
  };
}

// =========================================================================
// Approach 1: render screen by matching each tile to fixed atlas
// =========================================================================
function renderFixedFrame(fb, fixed) {
  const screen = new Uint8Array(SCREEN_CW * SCREEN_CH);
  let totalHam = 0, edgeChars = 0;
  const usedSlots = new Set();
  for (let cy = 0; cy < SCREEN_CH; cy++) {
    for (let cx = 0; cx < SCREEN_CW; cx++) {
      const t = chunkChar(fb, cx, cy);
      const r = matchFixedCharForTile(t, fixed);
      screen[cy*SCREEN_CW + cx] = r.idx;
      usedSlots.add(r.idx);
      let nColors = 0;
      for (let v = 0; v < 4; v++) if ((t.colorSet>>v)&1) nColors++;
      if (nColors >= 2) { totalHam += r.dist; edgeChars++; }
    }
  }
  return { screen, uniqueChars: usedSlots.size, edgeChars, avgHam: edgeChars ? totalHam/edgeChars : 0 };
}

// =========================================================================
// Canvas helpers
// =========================================================================




// =========================================================================
// Stats
// =========================================================================
function rmsAndWrong(a, b) {
  let sum = 0, wrong = 0;
  const N = a.length;
  for (let i = 0; i < N; i++) {
    const d = a[i] - b[i];
    if (d !== 0) { sum += d*d; wrong++; }
  }
  return { rms: Math.sqrt(sum / N), wrongPct: 100 * wrong / N };
}

