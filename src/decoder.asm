;------------------------------------------------------------------------
; decoder.asm - V10CS stream decoder for the 6502        LATENT / sprout
;
; Decodes V10CS streams (codebook classes A/R/U + digram BPE + GOSUB +
; DITTO + fallback + pure-skip). Assembled in TWO flavors from one
; macro body, differing only in what a skip does:
;
;   decode_frame     skips WRITE BLANKS as they advance, and the window
;                    tail after the last op is blank-filled to win_end.
;                    A frame decode rewrites every cell of
;                    [dst_base, win_end) exactly once. For INTRA streams
;                    (header flags bit 2: every frame coded against a
;                    blank screen, class R never emitted) decoded
;                    straight onto the visible screen: stale cells of
;                    the previous frame erase themselves, no clear, no
;                    flash, any payload decodes at any time.
;
;   decode_frame_pl  skips just advance (no writes, O(1) per op).
;                    For intra streams decoded into a CLEARED off-screen
;                    canvas (clearing is cheaper than per-cell blank
;                    writes and invisible off-screen), and for the
;                    delta-coded mega scene (rotated frames + keyframe,
;                    payload i transforms frame i -> i+1).
;
; Interface:
;   scene_ptr ($ED/$EE) -> V10CS blob          jsr scene_setup
;   dst_base = decode destination, win_end = dst_base + window length
;   (win_end is only used by the blank flavor)
;   jsr decode_frame / decode_frame_pl
;       decodes one frame; auto-wraps to payload 0 after the last one.
;
; Tables (copied per scene by scene_setup, page-aligned for abs,X):
;   $0400 cb_skip[N]   $0500 cb_val[N]
;   $0600 dg1, $0700 dg2 - indexed by RAW opcode (entry i at offset N+i)
;
; No self-modifying code, no illegal opcodes (py65-verifiable).
;
; Zero page + table layout: decoder_zp.asm (!src'd by the including
; file BEFORE any code).
;------------------------------------------------------------------------

!macro adv_blank .src {         ; blank-fill .src cells at dstp, then
        ldy .src                ; dstp += .src (preserves X; Y ends 0)
        beq .none
        lda #0
.wr:    dey
        sta (dstp),y
        bne .wr
        lda .src
        clc
        adc dstp
        sta dstp
        bcc .none
        inc dstp+1
.none:
}

!macro adv_plain .src {         ; dstp += .src (no writes)
        lda .src
        clc
        adc dstp
        sta dstp
        bcc .ok
        inc dstp+1
.ok:
}

!macro inc_dst {                ; dstp++
        inc dstp
        bne .incd
        inc dstp+1
.incd:
}

;------------------------------------------------------------------------
; scene_setup: parse header at (scene_ptr), copy tables, arm frame 0
;------------------------------------------------------------------------
!zone scene_setup
scene_setup:
        ldy #9
        lda (scene_ptr),y       ; N
        sta zN
        ldy #10
        lda (scene_ptr),y       ; F
        sta zF
        ldy #13
        lda (scene_ptr),y       ; Na
        sta zNa
        ldy #14
        lda (scene_ptr),y       ; Nr
        clc
        adc zNa
        sta zNanr
        ldy #15
        lda (scene_ptr),y       ; K
        sta cur_s               ; (borrow as K temp)
        clc
        adc zN
        sta zNK
        ldy #7
        lda (scene_ptr),y       ; n_frames (<= 255 by pack-time assert)
        sta frames_total

        clc                     ; srcp = scene_ptr + 24
        lda scene_ptr
        adc #24
        sta srcp
        lda scene_ptr+1
        adc #0
        sta srcp+1

        ldy #0                  ; cb_skip[N] -> $0400
.cps:   cpy zN
        beq .cpsd
        lda (srcp),y
        sta cb_skip,y
        iny
        bne .cps
.cpsd:  lda zN
        jsr add_srcp
        ldy #0                  ; cb_val[N] -> $0500
.cpv:   cpy zN
        beq .cpvd
        lda (srcp),y
        sta cb_val,y
        iny
        bne .cpv
.cpvd:  lda zN
        jsr add_srcp

        lda zN                  ; tmpp -> dg1tbl + N
        sta tmpp
        lda #>dg1tbl
        sta tmpp+1
        ldy #0                  ; dg1[K]
.cp1:   cpy cur_s
        beq .cp1d
        lda (srcp),y
        sta (tmpp),y
        iny
        bne .cp1
.cp1d:  lda cur_s
        jsr add_srcp
        lda #>dg2tbl            ; tmpp -> dg2tbl + N
        sta tmpp+1
        ldy #0                  ; dg2[K]
.cp2:   cpy cur_s
        beq .cp2d
        lda (srcp),y
        sta (tmpp),y
        iny
        bne .cp2
.cp2d:  lda cur_s
        jsr add_srcp

        lda srcp                ; fd_base = next_pos = here (frame 0 header)
        sta fd_base
        sta next_pos
        lda srcp+1
        sta fd_base+1
        sta next_pos+1
        lda frames_total
        sta frames_left
        lda #<SCREEN            ; default decode destination + window
        sta dst_base            ; (the shell overrides both per scene)
        lda #>SCREEN
        sta dst_base+1
        lda #<(SCREEN+1000)
        sta win_end
        lda #>(SCREEN+1000)
        sta win_end+1
        rts

add_srcp:                       ; srcp += A
        clc
        adc srcp
        sta srcp
        bcc .ok
        inc srcp+1
.ok:    rts

;------------------------------------------------------------------------
; decode_frame body, shared by both flavors (.blank = 1: skips write
; blank chars + window tail fill; .blank = 0: skips just advance)
;------------------------------------------------------------------------
!macro decode_body .blank {
        lda frames_left         ; wrap to first payload after the last
        bne .golen
        lda fd_base
        sta next_pos
        lda fd_base+1
        sta next_pos+1
        lda frames_total
        sta frames_left
.golen: ldy #0                  ; endp = len (temp)
        lda (next_pos),y
        sta endp
        iny
        lda (next_pos),y
        sta endp+1
        clc                     ; srcp = next_pos + 2
        lda next_pos
        adc #2
        sta srcp
        lda next_pos+1
        adc #0
        sta srcp+1
        clc                     ; endp = srcp + len; next_pos = endp
        lda endp
        adc srcp
        sta endp
        sta next_pos
        lda endp+1
        adc srcp+1
        sta endp+1
        sta next_pos+1
        lda dst_base
        sta dstp
        lda dst_base+1
        sta dstp+1
        lda #0
        sta prev_s
        sta prev_c
        sta prev2_s
        sta prev2_c
        sta dsp
        sta have_ret

.mainloop:
        ldy dsp                 ; pending digram expansion?
        beq .from_src
        dey
        sty dsp
        lda dstack,y
        jmp .dispatch
.from_src:
        lda srcp                ; stream exhausted? (token-aligned: == only)
        cmp endp
        bne .fetch
        lda srcp+1
        cmp endp+1
        bne .fetch
        lda have_ret            ; pending GOSUB return?
        bne .doret
        jmp .frame_done
.doret: lda retp
        sta srcp
        lda retp+1
        sta srcp+1
        lda retend
        sta endp
        lda retend+1
        sta endp+1
        lda #0
        sta have_ret
        jmp .from_src
.fetch: ldy #0
        lda (srcp),y
        inc srcp
        bne .dispatch
        inc srcp+1

.dispatch:                      ; A = opcode
        cmp zN
        bcc .cb_op              ; most frequent: codebook, falls close
        jmp .not_cb

.cb_op: tax                     ; codebook classes A/R/U
        lda cb_skip,x
        sta cur_s
        !if .blank { +adv_blank cur_s } else { +adv_plain cur_s }
        cpx zNa
        bcc .classA
        cpx zNanr
        bcc .classR
        sec                     ; class U: c = screen[dst-40] + val
        lda dstp
        sbc #40
        sta tmpp
        lda dstp+1
        sbc #0
        sta tmpp+1
        ldy #0
        lda (tmpp),y
        clc
        adc cb_val,x
        jmp .store_rot
.classR:
        ldy #0                  ; class R: c = screen[dst] + val
        lda (dstp),y
        clc
        adc cb_val,x
        jmp .store_rot
.classA:
        lda cb_val,x            ; class A: c = val

.store_rot:                     ; A = char, cur_s = skip: write + rotate prevs
        ldy #0
        sta (dstp),y
        tax
        lda prev_s
        sta prev2_s
        lda prev_c
        sta prev2_c
        lda cur_s
        sta prev_s
        stx prev_c
        +inc_dst
        jmp .mainloop

.not_cb:
        cmp zNK
        bcs .hi_ops
        tax                     ; digram: push second, continue with first
        ldy dsp
        lda dg2tbl,x
        sta dstack,y
        inc dsp
        lda dg1tbl,x
        jmp .dispatch

.hi_ops:
        cmp #$ff
        beq .pure_skip
        cmp #$c0
        bcs .fallback
        cmp #$b8
        bcs .ditto2
        cmp #$b0
        bcs .ditto1
        jmp .gosub              ; $AE (rare: ~0.6 calls/frame)

.pure_skip:
        !if .blank { +adv_blank zF } else { +adv_plain zF }
        jmp .mainloop

.fallback:                      ; $C0..$FE: skip = op-$C0, raw literal char
        sec
        sbc #$c0
        sta cur_s
        !if .blank { +adv_blank cur_s } else { +adv_plain cur_s }
        jsr fetch_raw
        jmp .store_rot

.ditto1:
        and #7                  ; repeat (prev_s, prev_c) K times
        tax
        inx
.d1:    !if .blank { +adv_blank prev_s } else { +adv_plain prev_s }
        lda prev_c
        ldy #0
        sta (dstp),y
        +inc_dst
        dex
        bne .d1
        jmp .mainloop

.ditto2:
        and #7                  ; repeat (prev2 pair, prev pair) K times
        tax
        inx
.d2:    !if .blank { +adv_blank prev2_s } else { +adv_plain prev2_s }
        lda prev2_c
        ldy #0
        sta (dstp),y
        +inc_dst
        !if .blank { +adv_blank prev_s } else { +adv_plain prev_s }
        lda prev_c
        ldy #0
        sta (dstp),y
        +inc_dst
        dex
        bne .d2
        jmp .mainloop

.gosub: jsr fetch_raw
        sta tmpp                ; off_lo
        jsr fetch_raw
        sta tmpp+1              ; off_hi
        jsr fetch_raw
        tax                     ; len
        lda srcp
        sta retp
        lda srcp+1
        sta retp+1
        lda endp
        sta retend
        lda endp+1
        sta retend+1
        lda #1
        sta have_ret
        clc                     ; srcp = fd_base + off
        lda tmpp
        adc fd_base
        sta srcp
        lda tmpp+1
        adc fd_base+1
        sta srcp+1
        clc                     ; endp = srcp + len
        txa
        adc srcp
        sta endp
        lda srcp+1
        adc #0
        sta endp+1
        jmp .mainloop

.frame_done:
        !if .blank {            ; blank-fill the window tail: the stream
        lda #0                  ; ends at the last nonblank cell, but the
        tay                     ; cells up to win_end may hold stale chars
.tf:    ldx dstp+1              ; from the previously decoded frame
        cpx win_end+1
        bne .wr
        ldx dstp
        cpx win_end
        beq .tfd
.wr:    sta (dstp),y
        inc dstp
        bne .tf
        inc dstp+1
        jmp .tf
.tfd:
        }
        dec frames_left
        rts
}

!zone decode_frame
decode_frame:                   ; on-screen flavor: skips write blanks
        +decode_body 1

!zone decode_frame_pl
decode_frame_pl:                ; canvas/delta flavor: plain skips
        +decode_body 0

;------------------------------------------------------------------------
fetch_raw:                      ; A = next stream byte (no end check:
        ldy #0                  ; literals/GOSUB args never cross endp)
        lda (srcp),y
        inc srcp
        bne .fr
        inc srcp+1
.fr:    rts
