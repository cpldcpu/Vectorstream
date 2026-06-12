;------------------------------------------------------------------------
; player_core.asm - TED TUNES playback engine          LATENT / sprout 2026
;
; Shared between the standalone player (player.asm) and the VECTOR STREAM
; demo. Provides:
;   select_tune  A = 0..3, call with IRQs masked (resets all voice state)
;   playtick     call once per PAL frame (50 Hz)
;   fxborder     byte: nonzero = border pulses with volume in write_regs
;
; Zero page contract: $60-$67, defined in player_zp.asm (!src'd by the
; including file BEFORE any code, to keep zp addressing in pass 1).
;------------------------------------------------------------------------

;------------------------------------------------------------------------
; select_tune: A = 0..3. Call with IRQs off.
;------------------------------------------------------------------------
select_tune:
        sta curtune
        tay
        lda tdir_len,y
        sta ordlen
        lda tdir_loop,y
        sta ordloop
        lda tdir_speed,y
        sta speedv
        ; copy the four order columns into fixed buffers
        lda tdir_o1lo_lo,y
        sta zp1
        lda tdir_o1lo_hi,y
        sta zp1+1
        ldy ordlen
        dey
cp1:    lda (zp1),y
        sta ordbuf1lo,y
        dey
        bpl cp1
        ldy curtune
        lda tdir_o1hi_lo,y
        sta zp1
        lda tdir_o1hi_hi,y
        sta zp1+1
        ldy ordlen
        dey
cp2:    lda (zp1),y
        sta ordbuf1hi,y
        dey
        bpl cp2
        ldy curtune
        lda tdir_o2lo_lo,y
        sta zp1
        lda tdir_o2lo_hi,y
        sta zp1+1
        ldy ordlen
        dey
cp3:    lda (zp1),y
        sta ordbuf2lo,y
        dey
        bpl cp3
        ldy curtune
        lda tdir_o2hi_lo,y
        sta zp1
        lda tdir_o2hi_hi,y
        sta zp1+1
        ldy ordlen
        dey
cp4:    lda (zp1),y
        sta ordbuf2hi,y
        dey
        bpl cp4
        ; reset player state
        lda #0
        sta framectr
        sta row
        sta orderpos
        sta $ff11
        ldx #1
rstv:   lda #$ff
        sta v_ins,x
        lda #0
        sta v_note,x
        sta v_f,x
        sta v_rel,x
        sta v_relf,x
        sta v_arppos,x
        sta v_vibpos,x
        sta v_curnlo,x
        sta v_curnhi,x
        sta v_nlo,x
        sta v_nhi,x
        sta v_env,x
        sta v_on,x
        sta v_noise,x
        dex
        bpl rstv
        jmp load_order

;------------------------------------------------------------------------
load_order:                     ; fetch pattern pointers for orderpos
        ldy orderpos
        lda ordbuf1lo,y
        sta patp1
        lda ordbuf1hi,y
        sta patp1+1
        lda ordbuf2lo,y
        sta patp2
        lda ordbuf2hi,y
        sta patp2+1
        rts

;------------------------------------------------------------------------
; playtick: call once per PAL frame (50 Hz)
;------------------------------------------------------------------------
playtick:
        lda framectr
        bne noRow
        jsr do_row
noRow:  ldx #0
        jsr voice_frame
        ldx #1
        jsr voice_frame
        jsr write_regs
        inc framectr
        lda framectr
        cmp speedv
        bcc ptdone
        lda #0
        sta framectr
        inc row
        lda row
        cmp #16
        bcc ptdone
        lda #0
        sta row
        inc orderpos
        lda orderpos
        cmp ordlen
        bcc ordok
        lda ordloop
        sta orderpos
ordok:  jsr load_order
ptdone: rts

;------------------------------------------------------------------------
do_row:                         ; read both pattern cells at 'row'
        lda row
        asl
        tay
        ldx #0
        lda (patp1),y
        beq dr2
        sta tnote
        iny
        lda (patp1),y
        sta tins
        jsr trigger
dr2:    lda row
        asl
        tay
        ldx #1
        lda (patp2),y
        beq dr3
        sta tnote
        iny
        lda (patp2),y
        sta tins
        jsr trigger
dr3:    rts

;------------------------------------------------------------------------
; trigger: X = voice, tnote/tins = pattern cell ($FE = key off)
;------------------------------------------------------------------------
trigger:
        lda tnote
        cmp #$fe
        bne trnote
        lda #1                  ; key off: enter release
        sta v_rel,x
        lda #0
        sta v_relf,x
        rts
trnote:
        sta v_note,x
        lda tins
        sta v_ins,x
        tay
        lda #0
        sta v_f,x
        sta v_rel,x
        sta v_relf,x
        sta v_arppos,x
        sta v_vibpos,x
        lda ins_flags,y
        and #FLG_FIX
        beq trdone
        lda ins_fixlo,y         ; drums: start N from fixed value
        sta v_curnlo,x
        lda ins_fixhi,y
        sta v_curnhi,x
trdone: rts

;------------------------------------------------------------------------
; voice_frame: X = voice. Envelope, arpeggio, slide, vibrato.
;------------------------------------------------------------------------
voice_frame:
        lda v_ins,x
        cmp #$ff
        bne vf1
        lda #0
        sta v_env,x
        sta v_on,x
        rts
vf1:    sta cins

; ---- envelope ----
        ldy cins
        lda v_rel,x
        beq vf_norel
        lda ins_rellen,y        ; release phase
        beq vf_relz
        lda v_relf,x
        cmp ins_rellen,y
        bcs vf_relz
        lda ins_rello,y
        sta zp1
        lda ins_relhi,y
        sta zp1+1
        ldy v_relf,x
        lda (zp1),y
        jmp vf_relset
vf_relz:
        lda #0
vf_relset:
        sta v_env,x
        lda v_relf,x
        cmp #$ff
        beq vf_pitch
        inc v_relf,x
        jmp vf_pitch
vf_norel:
        lda v_f,x               ; attack/decay or sustain
        cmp ins_envlen,y
        bcs vf_sus
        lda ins_envlo,y
        sta zp1
        lda ins_envhi,y
        sta zp1+1
        ldy v_f,x
        lda (zp1),y
        jmp vf_envset
vf_sus: lda ins_sus,y
        cmp #$ff
        beq vf_envz
        sta tmp
        lda ins_envlo,y
        sta zp1
        lda ins_envhi,y
        sta zp1+1
        ldy tmp
        lda (zp1),y
        jmp vf_envset
vf_envz:
        lda #0
vf_envset:
        sta v_env,x

; ---- pitch ----
vf_pitch:
        ldy cins
        lda ins_flags,y
        and #FLG_FIX
        beq vf_melodic
        lda ins_slide,y         ; drums: curN += slide (signed)
        pha
        bmi vf_negs
        lda #0
        beq vf_sext
vf_negs:
        lda #$ff
vf_sext:
        sta tmp
        pla
        clc
        adc v_curnlo,x
        sta v_curnlo,x
        lda v_curnhi,x
        adc tmp
        sta v_curnhi,x
        bmi vf_clamp            ; clamp at N=2
        bne vf_fixdone
        lda v_curnlo,x
        cmp #2
        bcs vf_fixdone
vf_clamp:
        lda #2
        sta v_curnlo,x
        lda #0
        sta v_curnhi,x
vf_fixdone:
        lda v_curnlo,x
        sta v_nlo,x
        lda v_curnhi,x
        sta v_nhi,x
        jmp vf_flags

vf_melodic:
        lda v_note,x
        sta tmp                 ; tmp = note (+ arp offset)
        lda ins_arplen,y
        beq vf_noarp
        lda ins_arplo,y
        sta zp1
        lda ins_arphi,y
        sta zp1+1
        ldy v_arppos,x
        lda (zp1),y
        clc
        adc tmp
        sta tmp
        ldy cins
        inc v_arppos,x
        lda v_arppos,x
        cmp ins_arplen,y
        bcc vf_noarp
        lda #0
        sta v_arppos,x
vf_noarp:
        ldy tmp                 ; N = note table lookup
        lda note_lo,y
        sta v_nlo,x
        lda note_hi,y
        sta v_nhi,x
        ldy cins                ; vibrato (table, signed deltas)
        lda ins_viblen,y
        beq vf_flags
        lda v_f,x
        cmp ins_vibdel,y
        bcc vf_flags
        lda ins_viblo,y
        sta zp1
        lda ins_vibhi,y
        sta zp1+1
        ldy v_vibpos,x
        lda (zp1),y
        pha
        bmi vf_vneg
        lda #0
        beq vf_vsext
vf_vneg:
        lda #$ff
vf_vsext:
        sta tmp
        pla
        clc
        adc v_nlo,x
        sta v_nlo,x
        lda v_nhi,x
        adc tmp
        sta v_nhi,x
        ldy cins
        inc v_vibpos,x
        lda v_vibpos,x
        cmp ins_viblen,y
        bcc vf_flags
        lda #0
        sta v_vibpos,x

; ---- flags & frame advance ----
vf_flags:
        ldy cins
        lda ins_flags,y
        and #FLG_NOISE
        sta v_noise,x
        lda v_env,x
        beq vf_onset
        lda #1
vf_onset:
        sta v_on,x
        lda v_f,x
        cmp #$ff
        beq vf_done
        inc v_f,x
vf_done:
        rts

;------------------------------------------------------------------------
; write_regs: push the frame's state into the TED
;------------------------------------------------------------------------
write_regs:
        lda v_nlo
        sta $ff0e               ; voice 1 freq low
        lda $ff12
        and #$fc
        ora v_nhi
        sta $ff12               ; voice 1 freq high (preserve bitmap bits)
        lda v_nlo+1
        sta $ff0f               ; voice 2 freq low
        lda v_nhi+1
        sta $ff10               ; voice 2 freq high
        lda v_env               ; volume = max(env1, env2)
        cmp v_env+1
        bcs wr1
        lda v_env+1
wr1:    sta wvol
        lda v_on
        beq wr2
        lda wvol
        ora #$10                ; voice 1 square on
        sta wvol
wr2:    lda v_on+1
        beq wr4
        lda v_noise+1
        beq wr3
        lda wvol
        ora #$40                ; voice 2 noise on
        sta wvol
        bne wr4
wr3:    lda wvol
        ora #$20                ; voice 2 square on
        sta wvol
wr4:    lda musatt              ; master fade: volume -= musatt, floor 0
        beq wr4n
        lda wvol
        and #$0f
        sec
        sbc musatt
        bpl wr4c
        lda #0
wr4c:   sta tmp
        lda wvol
        and #$f0
        ora tmp
        sta wvol
wr4n:   lda wvol
        sta $ff11
        lda fxborder            ; border pulses with volume (optional)
        beq wr5
        lda wvol
        and #$0f
        tay
        lda bordertab,y
        sta $ff19
wr5:    rts

bordertab:
        !byte $00,$11,$21,$21,$31,$31,$41,$51,$61

fxborder:  !byte 1
musatt:    !byte 0

;------------------------------------------------------------------------
; NOTE: song_data.asm is !src'd by the including file (acme resolves
; include paths relative to the working directory, not this file).
;------------------------------------------------------------------------
; player engine state
;------------------------------------------------------------------------
curtune:   !byte 0
framectr:  !byte 0
row:       !byte 0
orderpos:  !byte 0
ordlen:    !byte 0
ordloop:   !byte 0
speedv:    !byte 0
cins:      !byte 0
tmp:       !byte 0
tnote:     !byte 0
tins:      !byte 0
wvol:      !byte 0
ordbuf1lo: !fill 24
ordbuf1hi: !fill 24
ordbuf2lo: !fill 24
ordbuf2hi: !fill 24
v_ins:     !fill 2
v_note:    !fill 2
v_f:       !fill 2
v_rel:     !fill 2
v_relf:    !fill 2
v_arppos:  !fill 2
v_vibpos:  !fill 2
v_curnlo:  !fill 2
v_curnhi:  !fill 2
v_nlo:     !fill 2
v_nhi:     !fill 2
v_env:     !fill 2
v_on:      !fill 2
v_noise:   !fill 2
