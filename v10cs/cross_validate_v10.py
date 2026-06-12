"""Cross-validate V10CS: Python encode -> Python & C decode -> compare."""
import subprocess, sys
import v10codec as v10

ANIMS = [("frames_y.bin", "cube/Y"), ("frames_x.bin", "cube/X"),
         ("frames_free.bin", "cube/free"), ("frames_yslow.bin", "slow Y")]
ok_all = True
for path, label in ANIMS:
    raw = open(path, "rb").read()
    frames = [raw[i*1000:(i+1)*1000] for i in range(300)]
    info = v10.write_file("/tmp/cv.v10cs", frames)
    py = v10.decode_all("/tmp/cv.v10cs")
    subprocess.run(["./v10_decode", "/tmp/cv.v10cs", "/tmp/cv_c.bin"],
                   check=True, capture_output=True)
    cd = open("/tmp/cv_c.bin", "rb").read()
    cf = [cd[i*1000:(i+1)*1000] for i in range(300)]
    ok_py = all(a == b for a, b in zip(py, frames))
    ok_c = all(a == b for a, b in zip(cf, frames))
    ok = ok_py and ok_c
    ok_all &= ok
    print(f"{label:10s} K={info['K']:3d} payload={sum(info['sizes'])/300:6.2f} B/f  "
          f"python={'OK' if ok_py else 'FAIL'} c={'OK' if ok_c else 'FAIL'}")
sys.exit(0 if ok_all else 1)
