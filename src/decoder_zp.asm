; Zero-page + table layout of the V10CS decoder (decoder.asm).
; !src this BEFORE any code that references the decoder, so the
; assembler emits zero-page addressing in pass 1.

dstack   = $40          ; digram expansion stack, 16 bytes ($40-$4F)
win_end  = $ce          ; dst_base + window length: decode_frame blank-
                        ; fills up to here after the last op (intra tail)
srcp     = $d0          ; stream read pointer
endp     = $d2          ; end of current stream region
dstp     = $d4          ; screen write pointer (absolute)
retp     = $d6          ; GOSUB return: saved srcp
retend   = $d8          ; GOSUB return: saved endp
have_ret = $da
dsp      = $db          ; digram stack pointer
prev_s   = $dc
prev_c   = $dd
prev2_s  = $de
prev2_c  = $df
tmpp     = $e0          ; class-U pointer / GOSUB offset temp
zN       = $e2          ; codebook size
zNK      = $e3          ; N + K (first non-digram opcode)
zNa      = $e4          ; class A size
zNanr    = $e5          ; Na + Nr (start of class U)
zF       = $e6          ; pure-skip distance
fd_base  = $e7          ; frame-data region base (GOSUB offsets relative)
next_pos = $e9          ; start of next frame (its length header)
frames_left  = $eb
cur_s    = $ec          ; skip of the op in flight
scene_ptr    = $ed
frames_total = $ef
dst_base     = $f0      ; decode destination: the off-screen canvas for
                        ; movable scenes, the char matrix for the mega
                        ; finale. Constant per scene (intra streams are
                        ; position-independent); scene_setup resets it
                        ; to SCREEN, the shell overrides it after.

cb_skip  = $0400
cb_val   = $0500
dg1tbl   = $0600
dg2tbl   = $0700
SCREEN   = $3c00        ; char matrix (attrs at $3800)
