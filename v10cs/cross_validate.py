"""Cross-validate: encode each animation with the Python encoder, decode with
both the Python and the C decoder, and compare against the source screens."""
import subprocess, sys
import v9codec as v9

ANIMS = [("frames_y.bin", "cube/Y"), ("frames_x.bin", "cube/X"),
         ("frames_free.bin", "cube/free"), ("frames_yslow.bin", "slow Y")]

ok_all = True
for path, label in ANIMS:
    raw = open(path, "rb").read()
    frames = [raw[i*1000:(i+1)*1000] for i in range(300)]
    v9.write_file("/tmp/cv.v9cs", frames)
    # Python decode
    py = v9.decode_all("/tmp/cv.v9cs")
    # C decode
    subprocess.run(["./v9_decode", "/tmp/cv.v9cs", "/tmp/cv_c.bin"],
                   check=True, capture_output=True)
    cd = open("/tmp/cv_c.bin", "rb").read()
    c_frames = [cd[i*1000:(i+1)*1000] for i in range(300)]
    ok_py = all(a == b for a, b in zip(py, frames))
    ok_c = all(a == b for a, b in zip(c_frames, frames))
    ok_pc = all(a == b for a, b in zip(py, c_frames))
    ok = ok_py and ok_c and ok_pc
    ok_all &= ok
    print(f"{label:10s} python={'OK' if ok_py else 'FAIL'} "
          f"c={'OK' if ok_c else 'FAIL'} py==c={'OK' if ok_pc else 'FAIL'}")
sys.exit(0 if ok_all else 1)
