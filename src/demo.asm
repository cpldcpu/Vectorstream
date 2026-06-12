;------------------------------------------------------------------------
; VECTOR STREAM - a one-file Commodore Plus/4 demo      LATENT 2026
;
;   code + music: sprout        human critic: azure
;
; Rotating solid 3D polyhedra in TED multicolor text mode, 25 fps,
; streamed with the V10CS codec (see v10cs/V10-SPEC.md). PAL only.
;
; Architecture:
;   - 50 Hz raster IRQ (line 204, own vector, ROM banked out):
;     music playtick + tick counter. Nothing else.
;   - main loop sequencer at 25 fps (wait_25). Text entries: fade in/out
;     via TED luminance ramps.
;   - slide scenes are INTRA streams: every frame decodes independently
;     and the decoder's skips write blanks, so one decode rewrites the
;     whole window and erases whatever was there. Movement is therefore
;     just "decode somewhere else": soft-scroll registers carry the
;     fine pixels, the decode base carries the chars - no content
;     shifts, no keyframes. Long-period sine roam x short object loop
;     = the combined pattern repeats only at the lcm.
;   - the video matrix is DOUBLE BUFFERED (A $3800, B $4000): frames
;     decode into the back buffer and the raster IRQ flips $FF14 plus
;     both scroll registers atomically below the visible window, so the
;     coarse (char) and fine (pixel) position always agree and partial
;     decodes are never displayed. The roam decodes straight into the
;     back buffer - no blit.
;   - transitions slide the object fully off any of the four screen
;     edges: the frame decodes into an off-screen canvas and a clipped
;     blit copies it into the back buffer (a clipped decode cannot run
;     in place: above and beside a char matrix sit attributes / the
;     other buffer).
;   - the mega finale is an oversized DELTA stream (intra would rewrite
;     all ~940 cells = over the measured 44k cycle budget): static full
;     window on buffer A, keyframe + plain-skip decode, fade
;     transitions, no flips.
;
; Memory: $1001 shell, $1800 atlas, $2000 decoder+music, $3800/$3C00
; matrix A, $4000/$4400 matrix B, $4800 canvas, $4C00 assets. $F800
; gets the ROM font copied at init (text screens).
;
; Assemble: acme src/demo.asm   (from the project root)
;------------------------------------------------------------------------
!to "build/demo.prg", cbm
!sl "build/demo_sym.txt"

!src "music/player_zp.asm"
!src "src/decoder_zp.asm"

; --- shell zero page ($50-$5F + $F2-$FF; decoder $40-$4F/$CE/$D0-$F1,
;     player $60-$67)
tick    = $50           ; incremented by the IRQ, 50 Hz
tmpc    = $51
seq_ptr = $52
keyp    = $54           ; copy/blit source pointer
fadei   = $56           ; fade step save
frame_t = $57           ; 25 fps pacing: last frame's tick
tickcnt = $58           ; ROAM/RUN countdown (16 bit)
entryi  = $5a           ; sequence index
tmpa    = $5b
txtp    = $5c           ; text record pointer
scrp    = $5e           ; copy/blit destination pointer
mphase  = $f2           ; roam table index
mx      = $f3           ; roam x, pixels, bias 128 = centered
my      = $f4           ; roam y, pixels, bias 64 = centered
dxc     = $f5           ; current char offsets (signed)
dyc     = $f6
xf      = $f7           ; current fine scroll (0-7)
yf      = $f8
mvxp    = $fa           ; roam table pointers
mvyp    = $fc
pxb     = $fe           ; transition pixel counter, biased +512

; double-buffered video matrix: the shell decodes into the back buffer,
; the raster IRQ flips $FF14 + both scroll registers atomically below
; the visible window (coarse chars and fine pixels always agree, and
; partial decodes are never displayed)
ATTRM   = $3800         ; buffer A: attributes ($FF14 = $38)
SCREENM = $3c00         ; buffer A: characters (text/mega always use A)
ATTRB   = $4000         ; buffer B: attributes ($FF14 = $40)
CHARB   = $4400         ; buffer B: characters
CANVAS  = $4800         ; off-screen decode canvas (transitions)
FONTRAM = $f800         ; ROM font copy (text uses codes < 128 only)

        * = $1001
; BASIC stub: 10 SYS4109
        !byte $0b,$10,$0a,$00,$9e
        !text "4109"
        !byte $00,$00,$00

;------------------------------------------------------------------------
; init: runs with kernal ROM banked in, IRQs masked throughout
;------------------------------------------------------------------------
!zone init
start:
        sei
        ; ROM font $D000-$D3FF -> $F800 (reads hit ROM, writes hit RAM).
        ; Only the 128 upper/gfx glyphs: all text uses codes < 128, and
        ; copying a full 2 KB to $F800 would spray the TED registers at
        ; $FF00-$FF3F (writes there always hit I/O).
        lda #$00
        sta keyp
        sta scrp
        lda #$d0
        sta keyp+1
        lda #>FONTRAM
        sta scrp+1
        ldx #4
.fc:    ldy #0
.fc2:   lda (keyp),y
        sta (scrp),y
        iny
        bne .fc2
        inc keyp+1
        inc scrp+1
        dex
        bne .fc

        lda #0                  ; everything black
        sta $ff15
        sta $ff16
        sta $ff17
        sta $ff19
        jsr fill_attr
        lda #0
        jsr fill_screen

        lda #$1b                ; 25 rows, display on, vscroll 3
        sta $ff06
        lda #%10001000          ; reverse off, 40 col, no MCM, hscroll 0
        sta $ff07
        lda #$38                ; video matrix at $3800/$3C00
        sta $ff14
        lda $ff12
        and #%11111011          ; charset fetches from RAM
        sta $ff12

        lda #<irq               ; our world now: vectors in RAM
        sta $fffe
        lda #>irq
        sta $ffff
        lda #<nmi
        sta $fffa
        lda #>nmi
        sta $fffb
        lda #$02                ; raster IRQ only, compare bit 8 = 0
        sta $ff0a
        lda #$cc                ; line 204: just under the visible window
        sta $ff0b
        lda #$ff
        sta $ff09
        lda #0
        sta tick
        sta $ff3f               ; kernal ROM out - RAM to the top
        cli
        jmp demo_main

;------------------------------------------------------------------------
; 50 Hz raster IRQ (direct via $FFFE, ROM banked out)
;------------------------------------------------------------------------
irq:    pha
        txa
        pha
        tya
        pha
        lda #$ff
        sta $ff09               ; ack TED
        lda flip_pend           ; pending buffer flip: matrix base and
        beq irqnf               ; both scroll registers change in one
        lda flip14              ; spot below the visible window
        sta $ff14
        lda flip07
        sta $ff07
        lda flip06
        sta $ff06
        lda #0
        sta flip_pend
irqnf:  lda musmute             ; silent gap during tune changes
        bne irqm
        jsr playtick
irqm:   inc tick
        pla
        tay
        pla
        tax
        pla
nmi:    rti

musmute:   !byte 0
flip_pend: !byte 0
flip14:    !byte $38
flip07:    !byte 0
flip06:    !byte 0

;------------------------------------------------------------------------
; sequencer
;------------------------------------------------------------------------
!zone sequencer
demo_main:
        lda #0
        sta entryi
.show:  jsr load_entry
        lda cur_type
        beq .text
        cmp #2
        beq .mega
        jsr setup_slide         ; slide: enter, roam + decode, exit
        jsr do_enter
        jsr do_roam
        jsr do_exit
        jmp .next
.mega:  jsr setup_mega          ; clipped anim: fade in, decode, fade out
        jsr do_fadein
        jsr do_run_mega
        jsr do_fadeout
        jmp .next
.text:  jsr setup_text          ; text: fade in, hold, fade out
        jsr do_fadein
        ldx entryi              ; the final entry (credits) never fades
        inx                     ; out: hold it forever, music playing
        cpx #seq_count
        beq .hold
        jsr do_run_text
        jsr do_fadeout
.next:  inc entryi
        lda entryi
        cmp #seq_count
        bcc .show
        lda #0
        sta entryi
        beq .show               ; only reached if the last entry is not
.hold:  jsr wait_tick           ; a text screen
        jmp .hold

; copy sequence entry #entryi into cur_entry (52-byte records)
load_entry:
        lda #<seq_table
        sta seq_ptr
        lda #>seq_table
        sta seq_ptr+1
        ldx entryi
        beq .copy
.mul:   clc
        lda seq_ptr
        adc #52
        sta seq_ptr
        bcc .nohi
        inc seq_ptr+1
.nohi:  dex
        bne .mul
.copy:  ldy #51
.cl:    lda (seq_ptr),y
        sta cur_entry,y
        dey
        bpl .cl
        rts

;------------------------------------------------------------------------
; common setup: tune change (with silent gap) + border mode
;------------------------------------------------------------------------
setup_common:
        lda cur_tune
        cmp #$ff
        beq .notune
        lda #1                  ; half a second of silence makes the
        sta musmute             ; tune change a deliberate cut
        lda #0
        sta $ff11
        ldx #25
.pause: jsr wait_tick
        dex
        bne .pause
        sei
        lda cur_tune
        jsr select_tune
        cli
        lda #0
        sta musmute
        sta musatt              ; new tune starts at full volume
.notune:
        lda cur_border
        cmp #$ff
        beq .pulse
        sta $ff19
        lda #0
        sta fxborder
        rts
.pulse: lda #1
        sta fxborder
        rts

;------------------------------------------------------------------------
; slide scene setup: palette on (screen is empty), stream armed, object
; parked off-screen at the enter offset
;------------------------------------------------------------------------
setup_slide:
        jsr setup_common
        lda #>charset           ; corner-diag atlas
        sta $ff13
        lda #0
        jsr fill_screen         ; buffer A chars
        jsr fill_work           ; buffer B chars + canvas
        ldx #7                  ; palette + attr fill (both buffers):
        jsr apply_fade          ; targets, instantly
        lda #%10010000          ; MCM, 38 col, reverse off, hscroll 0
        sta base07_v
        sta $ff07
        lda #$10                ; 24 rows, display on, vscroll 0
        sta base06_v
        sta $ff06
        lda #$38                ; buffer A displayed, B is the back buffer
        sta $ff14
        lda #1
        sta backb_v
        lda #0
        sta flip_pend
        ldy #0                  ; roam state
        sty mphase
        lda cur_mvx
        sta mvxp
        lda cur_mvx+1
        sta mvxp+1
        lda cur_mvy
        sta mvyp
        lda cur_mvy+1
        sta mvyp+1
        lda #128                ; centered (transitions move one axis)
        sta mx
        lda #64
        sta my
        lda #0
        sta dxc
        sta dyc
        sta xf
        sta yf
        sta pdycb
        sta pdycb+1
        lda cur_data            ; parse stream, copy tables
        sta scene_ptr
        lda cur_data+1
        sta scene_ptr+1
        jmp scene_setup

;------------------------------------------------------------------------
; clipped (oversized) mega setup: full 40x25 window, static, DELTA
; stream: keyframe placed behind black, palette comes up via the fade
;------------------------------------------------------------------------
setup_mega:
        jsr setup_common
        lda #>charset
        sta $ff13
        lda #%10011000          ; MCM, 40 col, reverse off, hscroll 0
        sta base07_v
        sta $ff07
        lda #$18                ; 25 rows, display on (the vscroll 3
        sta base06_v            ; travels with the buffer flips)
        lda #$1b
        sta $ff06
        lda #0
        sta xf
        lda #3
        sta yf
        lda #$38                ; buffer A fades in, B is the back buffer
        sta $ff14
        lda #1
        sta backb_v
        lda #0
        sta flip_pend
        jsr fill_screen
        lda cur_data
        sta scene_ptr
        lda cur_data+1
        sta scene_ptr+1
        jsr scene_setup
        lda cur_aux             ; keyframe -> buffer A
        sta keyp
        lda cur_aux+1
        sta keyp+1
        lda #<SCREENM
        sta scrp
        lda #>SCREENM
        sta scrp+1
        lda cur_keylen
        sta cplen_v
        lda cur_keylen+1
        sta cplen_v+1
        jsr copy_fwd
        lda #<SCREENM           ; buffer A -> buffer B, all 1000 cells
        sta keyp                ; (B still holds the last slide's frame)
        lda #>SCREENM
        sta keyp+1
        lda #<CHARB
        sta scrp
        lda #>CHARB
        sta scrp+1
        lda #<1000
        sta cplen_v
        lda #>1000
        sta cplen_v+1
        jmp copy_fwd

;------------------------------------------------------------------------
; text screen setup
;------------------------------------------------------------------------
setup_text:
        jsr setup_common
        lda #0
        sta mphase              ; music-fade divider
        lda #>FONTRAM
        sta $ff13
        lda #%10001000          ; 40 col, no MCM, reverse off
        sta $ff07
        lda #$1b                ; 25 rows, vscroll 3
        sta $ff06
        lda #$38                ; static scene: buffer A, no flips
        sta $ff14
        lda #0
        sta flip_pend
        lda #32                 ; spaces
        jsr fill_screen
        jmp plot_text

;------------------------------------------------------------------------
; 25 fps pacing: wait until two 50 Hz ticks have passed since the last
; frame. Overruns self-recover (the next frames run back to back until
; frame_t catches up with tick).
;------------------------------------------------------------------------
!zone pacing
wait_25:
        lda tick                ; diag: ticks burned in the two waits
        sta $0f1c
.f:     lda flip_pend           ; never write a buffer the IRQ has not
        bne .f                  ; flipped away from yet
        lda tick
        sec
        sbc $0f1c
        clc
        adc $0f1a               ; $0F1A += ticks spent on the flip wait
        sta $0f1a
        lda tick
        sta $0f1c
.w:     lda tick
        sec
        sbc frame_t
        bmi .w                  ; early: hold the 25 fps cadence
        pha
        lda tick
        sec
        sbc $0f1c
        clc
        adc $0f1b               ; $0F1B += ticks spent waiting early
        sta $0f1b
        pla
        cmp #6
        bcc .ok                 ; on time (or briefly late: catch up)
        ldx tick                ; far behind: resync, or the 8-bit
        stx frame_t             ; difference wraps and stalls for laps
.ok:    cmp #4                  ; lateness histogram caps at 3
        bcc .hs
        lda #3
.hs:    tax                     ; (diag: $0F10-$0F13)
        inc $0f10,x
        lda frame_t
        clc
        adc pace_v              ; 2 = 25 fps slides, 3 = 16.7 fps mega
        sta frame_t
        rts

sync_25:                        ; resync after setup pauses/fades
        lda #2
        sta pace_v
        lda tick
        sta frame_t
        rts

;------------------------------------------------------------------------
; transitions: ramp one axis (4 px per 25 fps frame) between the center
; and the entry's off-screen offset, decoding + rendering every frame.
; dir 0=bottom (renders direct: the spill region absorbs the overflow),
; 1=top 2=left 3=right (render via canvas + clipped blit).
;------------------------------------------------------------------------
!zone transitions
do_enter:
        jsr sync_25
        lda #0
        sta exitfd_v
        lda cur_flags
        and #3
        sta tdir_v
        jsr set_mode
        lda cur_eoff            ; pxb = 512 + 8*enter_off
        jsr off_to_px
        lda tmpa
        sta pxb
        lda tmpc
        sta pxb+1
        lda #0                  ; tgt = 512 (center)
        sta tgt_v
        lda #2
        sta tgt_v+1
        jmp trans_loop

do_exit:
        jsr sync_25
        lda cur_flags
        and #16                 ; musfade: this exit drives the volume
        sta exitfd_v            ; down to silence (see trans_fade)
        lda cur_flags
        lsr
        lsr
        and #3
        sta tdir_v
        jsr set_mode
        lda cur_xoff            ; tgt = 512 + 8*exit_off
        jsr off_to_px
        lda tmpa
        sta tgt_v
        lda tmpc
        sta tgt_v+1
        lda tdir_v              ; pxb = current axis position
        cmp #2
        bcs .xa
        lda my                  ; vertical: pxb = my + 448
        clc
        adc #$c0
        sta pxb
        lda #1
        adc #0
        sta pxb+1
        jmp trans_loop
.xa:    lda mx                  ; horizontal: pxb = mx + 384
        clc
        adc #$80
        sta pxb
        lda #1
        adc #0
        sta pxb+1
        ; fall through

trans_loop:
.tl:    jsr wait_25
        jsr trans_step
        jsr trans_fade
        jsr trans_apply
        jsr render
        lda pxb                 ; reached the target?
        cmp tgt_v
        bne .tl
        lda pxb+1
        cmp tgt_v+1
        bne .tl
        rts

set_mode:                       ; transitions always render via canvas
        lda #1                  ; (a clipped decode cannot go above or
        sta curmode_v           ; beside a char matrix in place, and
        lda dyc                 ; below sits the other buffer)
        sta pdycb               ; blit row-span continuity, both buffers
        sta pdycb+1
        rts

off_to_px:                      ; A = signed chars -> tmpc:tmpa = 512+A*8
        ldx #0
        sta tmpa
        ora #0
        bpl .pos
        ldx #$ff
.pos:   stx tmpc
        asl tmpa                ; *8, sign extended
        rol tmpc
        asl tmpa
        rol tmpc
        asl tmpa
        rol tmpc
        lda tmpc
        clc
        adc #2                  ; +512
        sta tmpc
        rts

trans_step:                     ; pxb += or -= 4 toward tgt_v, snapping
        lda pxb                 ; onto it (exits start at the roam's
        cmp tgt_v               ; arbitrary position, so the distance is
        lda pxb+1               ; not always a multiple of 4)
        sbc tgt_v+1
        bcc .up                 ; pxb < tgt: step up
        sec
        lda pxb
        sbc #4
        sta pxb
        bcs .ck
        dec pxb+1
.ck:    lda pxb                 ; undershot the target? snap
        cmp tgt_v
        lda pxb+1
        sbc tgt_v+1
        bcc .snap
        rts
.up:    clc
        lda pxb
        adc #4
        sta pxb
        bcc .ck2
        inc pxb+1
.ck2:   lda tgt_v               ; overshot the target? snap
        cmp pxb
        lda tgt_v+1
        sbc pxb+1
        bcs .done
.snap:  lda tgt_v
        sta pxb
        lda tgt_v+1
        sta pxb+1
.done:  rts

trans_apply:                    ; pxb -> chars+fine on the moving axis
        lda pxb
        and #7
        sta tmpa                ; fine
        lda pxb+1
        sta tmpc
        lda pxb
        lsr tmpc
        ror
        lsr tmpc
        ror
        lsr tmpc
        ror                     ; A = pxb >> 3 (0..127)
        sec
        sbc #64                 ; signed chars
        ldx tdir_v
        cpx #2
        bcs .x
        sta dyc
        lda tmpa
        sta yf
        rts                     ; registers travel with the buffer flip
.x:     sta dxc
        lda tmpa
        sta xf
        rts

trans_fade:                     ; musfade exits: tie the volume to the
        lda exitfd_v            ; remaining travel so the music reaches
        beq .tfr                ; silence exactly as the object leaves
        sec                     ; dist = |pxb - tgt|
        lda pxb
        sbc tgt_v
        sta tmpa
        lda pxb+1
        sbc tgt_v+1
        bcs .tfp
        sec
        lda tgt_v
        sbc pxb
        sta tmpa
        lda tgt_v+1
        sbc pxb+1
.tfp:   bne .tfr                ; >= 256 px away: leave the volume alone
        lda tmpa
        lsr
        lsr
        lsr
        lsr
        sta tmpa
        sec
        lda #15                 ; att = max(att, 15 - dist/16)
        sbc tmpa
        cmp musatt
        bcc .tfr
        beq .tfr
        sta musatt
.tfr:   rts

;------------------------------------------------------------------------
; roam: long-period sine tables, position + pose step on the same frame
;------------------------------------------------------------------------
!zone roam
do_roam:
        jsr sync_25
        lda #0                  ; roam decodes direct into the back
        sta curmode_v           ; buffer - no canvas, no blit
        lda cur_ticks
        sta tickcnt
        lda cur_ticks+1
        sta tickcnt+1
.rl:    jsr wait_25
        inc mphase              ; 25 Hz -> 10.2 s table cycle
        ldy mphase
        lda (mvxp),y
        sta mx
        lda (mvyp),y
        sta my
        lda mx                  ; xf = mx & 7, dxc = (mx>>3) - 16
        and #7
        sta xf
        lda mx
        lsr
        lsr
        lsr
        sec
        sbc #16
        sta dxc
        lda my                  ; yf = my & 7, dyc = (my>>3) - 8
        and #7
        sta yf
        lda my
        lsr
        lsr
        lsr
        sec
        sbc #8
        sta dyc
        jsr render              ; curmode_v = 0: direct
        lda cur_flags           ; musfade: ease down to HALF volume over
        and #16                 ; the scene's last ~10 s; the exit
        beq .nofade             ; transition takes it to silence
        lda tickcnt+1
        cmp #2
        bcs .nofade
        lda tickcnt
        and #63
        bne .nofade
        lda musatt
        cmp #7
        bcs .nofade
        inc musatt
.nofade:
        sec                     ; tickcnt -= 2
        lda tickcnt
        sbc #2
        sta tickcnt
        lda tickcnt+1
        sbc #0
        sta tickcnt+1
        bmi .done
        ora tickcnt
        bne .rl
.done:  rts

;------------------------------------------------------------------------
; render + blit live in the $2000 segment (the shell segment is full);
; see below the decoder include.
;------------------------------------------------------------------------
!macro render_blit_code {
!zone render
render:
        lda tick                ; diag: render tick-span -> $0F14-$0F17
        sta $0f18
        lda curmode_v
        beq render_direct
        jmp render_canvas

render_direct:
        lda #0                  ; tmpa = sign extension of dxc
        sta tmpa
        lda dxc
        bpl .pp
        dec tmpa
.pp:    ldx cur_w0              ; row = w0 + dyc (always inside the
        txa                     ; matrix: roam margins guarantee it)
        clc
        adc dyc
        tax
        lda dxc                 ; dst_base = back + woff[row] + sext(dxc)
        clc
        adc woff_lo,x
        sta dst_base
        lda woff_hi,x
        adc tmpa
        sta dst_base+1
        ldy backb_v
        clc
        lda dst_base
        adc bchar_lo,y
        sta dst_base
        lda dst_base+1
        adc bchar_hi,y
        sta dst_base+1
        clc                     ; win_end = dst_base + keylen
        lda dst_base
        adc cur_keylen
        sta win_end
        lda dst_base+1
        adc cur_keylen+1
        sta win_end+1
        jsr decode_frame
        jmp req_flip

render_canvas:
        lda #<CANVAS
        sta dst_base
        lda #>CANVAS
        sta dst_base+1
        clc
        lda #<CANVAS
        adc cur_keylen
        sta win_end
        lda #>CANVAS
        adc cur_keylen+1
        sta win_end+1
        jsr decode_frame        ; rewrites the whole canvas window
        ; fall through to the blit

;------------------------------------------------------------------------
; blit: copy the canvas window to the matrix at (dxc, dyc), clipped to
; the screen, blank-filling everything in the affected row span that the
; window does not cover (erases the movement trail). Row span = window
; rows at the current AND previous dyc, clamped to rows 0..24.
;------------------------------------------------------------------------
blit:
        ldx backb_v             ; the back buffer last showed the frame
        lda dyc                 ; TWO ticks ago: trail span from its own
        sec                     ; dyc history. tmpa = min, tmpc = max
        sbc pdycb,x
        bvc .nv
        eor #$80
.nv:    bmi .dless
        lda pdycb,x
        sta tmpa
        lda dyc
        sta tmpc
        jmp .mm
.dless: lda dyc
        sta tmpa
        lda pdycb,x
        sta tmpc
.mm:    lda cur_w0              ; first row: w0 + min, clamp >= 0
        clc
        adc tmpa
        bpl .lo0
        lda #0
.lo0:   cmp #25
        bcs .tnone              ; entirely below the screen
        sta brow_v
        lda cur_w0              ; last row: w0 + max + winrows - 1
        clc
        adc tmpc                ; (range -25..27: no signed overflow)
        clc
        adc cur_winrows
        sec
        sbc #1
        bmi .tnone              ; entirely above the screen
        cmp #25                 ; clamp <= 24
        bcc .hi0
        lda #24
.hi0:   sta bhi_v
        cmp brow_v
        bcs .span
.tnone: jmp .none               ; empty span
.span:  lda dxc                 ; lf = max(0, dxc): first copied column
        bpl .lf0
        lda #0
.lf0:   sta blf_v
        cmp #40                 ; fully off to the right: blank rows only
        bcc .rows
        lda #40
        sta blf_v

.rows:  ldx brow_v              ; ---- per destination row ----
        ldy backb_v             ; scrp = back buffer + woff[row]
        clc
        lda woff_lo,x
        adc bchar_lo,y
        sta scrp
        lda woff_hi,x
        adc bchar_hi,y
        sta scrp+1
        txa                     ; sr = row - w0 - dyc
        sec
        sbc cur_w0
        sec
        sbc dyc
        bpl .insp
        jmp .blank              ; above the window: blank row
.insp:  cmp cur_winrows
        bcc .insr
        jmp .blank              ; below the window: blank row
.insr:  tax                     ; keyp = CANVAS + woff[sr] - sext(dxc)
        ldy #0
        lda dxc
        bpl .p2
        dey
.p2:    sty tmpa
        clc
        lda woff_lo,x
        adc #<CANVAS
        sta keyp
        lda woff_hi,x
        adc #>CANVAS
        sta keyp+1
        sec
        lda keyp
        sbc dxc
        sta keyp
        lda keyp+1
        sbc tmpa
        sta keyp+1
        ldy blf_v               ; left fill: columns 0..lf-1
        beq .cp
        lda #0
.lfl:   dey
        sta (scrp),y
        bne .lfl
        lda blf_v
        cmp #40
        bcc .cp
        jmp .next               ; nothing to copy
.cp:    ldy blf_v               ; copy columns lf..39 (unrolled chain;
        jsr copy_clip           ; right-edge overreads fixed by the fill)
        lda dxc                 ; right fill if dxc < 0: cols 40+dxc..39
        bpl .next
        clc
        adc #40
        tay
        lda #0
.rfl:   sta (scrp),y
        iny
        cpy #40
        bne .rfl
        jmp .next
.blank: lda #0                  ; row entirely outside the window
        ldy #39
.bfl:   sta (scrp),y
        dey
        bpl .bfl
.next:  ldx brow_v
        inx
        stx brow_v
        cpx bhi_v
        beq .agn
        bcs .none
.agn:   jmp .rows
.none:  ldx backb_v
        lda dyc
        sta pdycb,x
        ; fall through: request the flip to the buffer just written

req_flip:                       ; arm the IRQ flip: matrix base + both
        ldx backb_v             ; scroll fine values change atomically
        lda b14tab,x
        sta flip14
        lda base07_v
        ora xf
        sta flip07
        lda base06_v
        ora yf
        sta flip06
        lda #1
        sta flip_pend
        lda backb_v             ; the written buffer becomes the front
        eor #1
        sta backb_v
        lda tick                ; diag: render tick-span histogram
        sec
        sbc $0f18
        cmp #4
        bcc .h
        lda #3
.h:     tax
        inc $0f14,x
        rts

bchar_lo: !byte <SCREENM, <CHARB
bchar_hi: !byte >SCREENM, >CHARB
b14tab:   !byte $38, $40

; r*40 offsets, rows 0..46
woff_lo: !for r, 0, 46 { !byte <(r*40) }
woff_hi: !for r, 0, 46 { !byte >(r*40) }

; jump into the unrolled copy chain at pair Y (= first column): copies
; columns Y..39 from (keyp) to (scrp) at 13 cycles/cell
copy_clip:
        lda centry_hi,y
        pha
        lda centry_lo,y
        pha
        rts                     ; -> chain + 5*Y
copychain:
!for i, 0, 39 {
        lda (keyp),y
        sta (scrp),y
        iny
}
        rts

centry_lo: !for i, 0, 39 { !byte <(copychain + i*5 - 1) }
centry_hi: !for i, 0, 39 { !byte >(copychain + i*5 - 1) }

;------------------------------------------------------------------------
; mega frame: tear-free double buffering for the DELTA-coded finale.
; The back buffer is two frames stale, so first bring it up to date by
; copying the front window over it (copy-forward), then the regular
; delta payload applies. ~16 k copy + ~34 k decode = 3 ticks per frame.
;------------------------------------------------------------------------
!zone mega
mega_frame:
        lda tick                ; diag: render tick-span
        sta $0f18
        lda backb_v
        eor #1
        tay                     ; front chars -> copy source
        ldx backb_v             ; back chars  -> copy dest + decode dst
        lda bchar_lo,y
        sta keyp
        lda bchar_hi,y
        sta keyp+1
        lda bchar_lo,x
        sta scrp
        sta dst_base
        lda bchar_hi,x
        sta scrp+1
        sta dst_base+1
        lda cur_keylen          ; the keyframe rows cover every cell any
        sta cplen_v             ; payload ever touches
        lda cur_keylen+1
        sta cplen_v+1
        jsr copy_fwd
        jsr decode_frame_pl
        jsr mega_fx
        jmp req_flip

;------------------------------------------------------------------------
; mega color program: 8 hue phases of 64 frames (~3.8 s) each - out of
; dark blue, through purple and red, an orange/yellow blaze, then back
; into the dark. mc1/mc2 luminance breathes with a 64-frame period
; aligned to the phases, so every hue cut lands on a dim frame. The %11
; face color follows via the attribute matrices (refilled per phase).
; The last phase holds the entry palette so the fade-out ramps from
; exactly where the effect stopped.
;------------------------------------------------------------------------
mega_fx:
        inc fxfrm_v
        lda fxfrm_v
        and #63
        bne .nph
        ldx fxphs_v             ; next phase (sticks at 7)
        cpx #7
        bcs .nph
        inx
        stx fxphs_v
        lda hue3_t,x
        jsr fill_attr2
.nph:   ldx fxphs_v
        cpx #7
        bcs .frz
        lda fxfrm_v             ; breath index: 16 steps x 4 frames
        lsr
        lsr
        and #15
        tay
        lda breath1_t,y
        ora hue1_t,x
        sta $ff16
        lda breath2_t,y
        ora hue2_t,x
        sta $ff17
        rts
.frz:   lda #$3e                ; hold the entry palette (= fade target)
        sta $ff16
        lda #$56
        sta $ff17
        rts

hue1_t:    !byte 14,  6,  4,  2,  2,  8,  4, 14   ; mc1 (dark face)
hue2_t:    !byte  6, 13, 11,  4,  8,  7, 11,  6   ; mc2 (light face)
hue3_t:    !byte $4e,$4b,$4c,$4a,$4a,$4f,$4c,$4e  ; %11 face attr (MC bit)
breath1_t: !byte $20,$20,$30,$30,$40,$40,$50,$50  ; mc1 lum 2-5
           !byte $50,$50,$40,$40,$30,$30,$20,$20
breath2_t: !byte $40,$40,$50,$50,$60,$60,$70,$70  ; mc2 lum 4-7
           !byte $70,$70,$60,$60,$50,$50,$40,$40
}

;------------------------------------------------------------------------
; run loops: text (50 Hz, optional music fade-out), mega (25 fps decode)
;------------------------------------------------------------------------
!zone run_text
do_run_text:
        lda cur_ticks
        sta tickcnt
        lda cur_ticks+1
        sta tickcnt+1
.rl:    jsr wait_tick
        lda cur_flags           ; glow pulse: breathe the text luminance
        and #32                 ; (2.5 s sine via the tick counter)
        beq .nofx
        lda tick
        lsr
        lsr
        lsr
        and #15
        tax
        lda pulse_tab,x
        jsr text_lum
.nofx:  lda cur_flags           ; optionally fade the music out
        and #16                 ; (one volume step every 8 ticks)
        beq .tdown
        inc mphase
        lda mphase
        and #7
        bne .tdown
        lda musatt
        cmp #15
        bcs .tdown
        inc musatt
.tdown: sec                     ; tickcnt--
        lda tickcnt
        sbc #1
        sta tickcnt
        lda tickcnt+1
        sbc #0
        sta tickcnt+1
        ora tickcnt
        bne .rl
        rts

!zone run_mega
do_run_mega:
        jsr sync_25
        lda #3                  ; copy-forward + decode + flip is ~51 k
        sta pace_v              ; cycles: a tear-free mega frame needs 3
        lda #0                  ; ticks (16.7 fps)
        sta fxfrm_v
        sta fxphs_v
        lda cur_ticks
        sta tickcnt
        lda cur_ticks+1
        sta tickcnt+1
.rl:    jsr wait_25
        jsr mega_frame          ; delta payload into the back buffer
        sec                     ; tickcnt -= 3
        lda tickcnt
        sbc #3
        sta tickcnt
        lda tickcnt+1
        sbc #0
        sta tickcnt+1
        bmi .done
        ora tickcnt
        bne .rl
.done:  rts

;------------------------------------------------------------------------
; fades (text + mega screens)
;------------------------------------------------------------------------
!zone fades
do_fadein:
        ldx #0
.fi:    stx fadei
        jsr apply_fade
        jsr wait2
        ldx fadei
        inx
        cpx #8
        bne .fi
        rts

do_fadeout:
        ldx #6
.fo:    stx fadei
        jsr apply_fade
        jsr wait2
        ldx fadei
        dex
        bpl .fo
        lda #0                  ; final step: true black
        sta $ff15
        sta $ff16
        sta $ff17
        jsr fill_attr2          ; the mega may end on either buffer
        jmp wait2

apply_fade:                     ; X = step 0..7 of the entry's ramps
        lda cur_ramps,x
        sta $ff15
        lda cur_ramps+8,x
        sta $ff16
        lda cur_ramps+16,x
        sta $ff17
        lda cur_ramps+24,x
        ldy cur_type
        bne .anim
        and #$70                ; text: ramp only the luminance, keep the
        jmp text_lum            ; per-cell colors plot_text wrote
.anim:  jmp fill_attr2          ; slides AND the mega flip buffers: fill
                                ; both attr matrices; text stays on A

text_lum:                       ; A = luminance bits ($00-$70) -> every
        sta tmpa                ; attr cell of buffer A, colors kept
        ldx #0
.tf:    lda ATTRM,x
        and #$0f
        ora tmpa
        sta ATTRM,x
        lda ATTRM+$100,x
        and #$0f
        ora tmpa
        sta ATTRM+$100,x
        lda ATTRM+$200,x
        and #$0f
        ora tmpa
        sta ATTRM+$200,x
        lda ATTRM+$300,x
        and #$0f
        ora tmpa
        sta ATTRM+$300,x
        inx
        bne .tf
        rts

; glow-pulse luminance table (16 steps, sine between lum 2 and 7)
pulse_tab:
        !byte $40,$50,$60,$60,$70,$70,$70,$60
        !byte $50,$40,$30,$20,$20,$20,$30,$30

;------------------------------------------------------------------------
; helpers
;------------------------------------------------------------------------
!zone helpers
wait2:  jsr wait_tick
wait_tick:
        lda tick
.w:     cmp tick
        beq .w
        rts

fill_attr:                      ; A -> buffer A attribute matrix
        ldx #0
.fa:    sta ATTRM,x
        sta ATTRM+$100,x
        sta ATTRM+$200,x
        sta ATTRM+$300,x
        inx
        bne .fa
        rts

fill_attr2:                     ; A -> both attribute matrices
        ldx #0
.f2:    sta ATTRM,x
        sta ATTRM+$100,x
        sta ATTRM+$200,x
        sta ATTRM+$300,x
        sta ATTRB,x
        sta ATTRB+$100,x
        sta ATTRB+$200,x
        sta ATTRB+$300,x
        inx
        bne .f2
        rts

fill_screen:                    ; A -> buffer A char matrix
        ldx #0
.fs:    sta SCREENM,x
        sta SCREENM+$100,x
        sta SCREENM+$200,x
        sta SCREENM+$300,x
        inx
        bne .fs
        rts

fill_work:                      ; 0 -> buffer B chars + canvas
        lda #0
        ldx #0
.fw:    sta CHARB,x
        sta CHARB+$100,x
        sta CHARB+$200,x
        sta CHARB+$300,x
        sta CANVAS,x
        sta CANVAS+$100,x
        sta CANVAS+$200,x
        sta CANVAS+$300,x
        inx
        bne .fw
        rts

!zone copy_fwd
copy_fwd:                       ; (keyp) -> (scrp), cplen_v bytes, ascending
        ldy #0
.pg:    lda cplen_v+1
        beq .rem
.pgl:   lda (keyp),y
        sta (scrp),y
        iny
        bne .pgl
        inc keyp+1
        inc scrp+1
        dec cplen_v+1
        jmp .pg
.rem:   ldy cplen_v
        beq .done
        ldy #0
.rl:    lda (keyp),y
        sta (scrp),y
        iny
        cpy cplen_v
        bne .rl
.done:  rts

!zone plot_text
plot_text:                      ; records at cur_aux: row,col,color,len,codes...,$FF
        lda cur_aux
        sta txtp
        lda cur_aux+1
        sta txtp+1
.rec:   ldy #0
        lda (txtp),y            ; row
        cmp #$ff
        beq .done
        tax
        iny
        lda (txtp),y            ; col
        clc
        adc row_lo,x
        sta scrp
        lda row_hi,x
        adc #0
        sta scrp+1
        sec                     ; keyp -> attr cell (attrs sit $400 below)
        lda scrp
        sta keyp
        lda scrp+1
        sbc #4
        sta keyp+1
        iny
        lda (txtp),y            ; color
        sta tmpc
        iny
        lda (txtp),y            ; len
        sta tmpa
        clc                     ; txtp += 4
        lda txtp
        adc #4
        sta txtp
        bcc .nc1
        inc txtp+1
.nc1:   ldy #0
.cp:    lda (txtp),y
        sta (scrp),y
        lda tmpc
        sta (keyp),y
        iny
        cpy tmpa
        bne .cp
        clc                     ; txtp += len
        lda txtp
        adc tmpa
        sta txtp
        bcc .rec
        inc txtp+1
        jmp .rec
.done:  rts

; buffer A char rows (text plotting)
row_lo:  !for r, 0, 24 { !byte <(SCREENM + r*40) }
row_hi:  !for r, 0, 24 { !byte >(SCREENM + r*40) }

; current sequence entry (copied from seq_table, 52 bytes)
cur_entry:
cur_type:     !byte 0
cur_data:     !word 0
cur_aux:      !word 0
cur_ticks:    !word 0
cur_tune:     !byte 0
cur_border:   !byte 0
cur_mvx:      !word 0
cur_mvy:      !word 0
cur_keylen:   !word 0          ; slide: window bytes; mega: keyframe bytes
cur_w0:       !byte 0          ; window top row when centered
cur_winrows:  !byte 0          ; window height in rows
cur_eoff:     !byte 0          ; enter offset, signed chars
cur_xoff:     !byte 0          ; exit offset, signed chars
cur_flags:    !byte 0          ; b0-1 enter dir, b2-3 exit dir, b4 musfade
cur_ramps:    !fill 32

; engine state
tdir_v:       !byte 0          ; transition direction (0 b, 1 t, 2 l, 3 r)
tgt_v:        !word 0          ; transition target (biased pixels)
curmode_v:    !byte 0          ; 0 = direct, 1 = canvas + blit
backb_v:      !byte 1          ; back buffer index (0 = A, 1 = B)
pdycb:        !byte 0, 0       ; per-buffer dyc of the last frame in it
base07_v:     !byte 0          ; scene's $FF07/$FF06 base bits (fine
base06_v:     !byte 0          ; scroll ORed in at the flip)
brow_v:       !byte 0          ; blit: current/last row
bhi_v:        !byte 0
blf_v:        !byte 0          ; blit: first copied column
cplen_v:      !word 0          ; copy_fwd length
pace_v:       !byte 2          ; wait_25 frame stride in ticks (2 or 3)
exitfd_v:     !byte 0          ; nonzero: exit transition drives musatt
fxfrm_v:      !byte 0          ; mega: effect frame counter
fxphs_v:      !byte 0          ; mega: hue phase 0-7

!if * > $1800 { !error "shell overflows into the charset" }

;------------------------------------------------------------------------
; corner-diag charset atlas (2 KB aligned)
;------------------------------------------------------------------------
        * = $1800
charset:
        !bin "build/charset.bin"

;------------------------------------------------------------------------
; V10CS decoder (both flavors), music engine, song data
;------------------------------------------------------------------------
        * = $2000
!src "src/decoder.asm"
        +render_blit_code
!src "music/player_core.asm"
!src "music/song_data.asm"

!if * > $3800 { !error "code/music overflows into the video matrix" }

;------------------------------------------------------------------------
; scene table, movement tables, mega keyframe, V10CS streams (org $4C00,
; after video matrix A $3800, matrix B $4000 and the canvas $4800)
;------------------------------------------------------------------------
!src "build/assets.asm"
