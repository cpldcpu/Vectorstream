// Regenerate the four test datasets. Requires core.js (renderer functions
// extracted from c64_cube_demo HTML). Usage: node gen_frames.js
const fs = require('fs');
eval(fs.readFileSync('core.js','utf8'));
currentShape = 'cube';
const fixed = buildFixedCharset('corner-diag');
function gen(mode, rate, out) {
  const FRAMES = 300, dt = 1/50, scale = 0.95;
  let angle = 0.31;
  const buf = Buffer.alloc(FRAMES*1000);
  for (let f = 0; f < FRAMES; f++) {
    angle += rate*dt;
    const ideal = rasterIdealFrame(angle, scale, mode);
    Buffer.from(renderFixedFrame(ideal.fb, fixed).screen).copy(buf, f*1000);
  }
  fs.writeFileSync(out, buf);
  console.log(out);
}
gen('y',    1.0,  'frames_y.bin');
gen('x',    1.0,  'frames_x.bin');
gen('free', 1.0,  'frames_free.bin');
gen('y',    0.25, 'frames_yslow.bin');
