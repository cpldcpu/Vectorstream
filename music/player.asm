;------------------------------------------------------------------------
; TED TUNES - Commodore Plus/4 music player          LATENT / sprout 2026
;
; Standalone UI wrapper around player_core.asm (the engine shared with
; the VECTOR STREAM demo). 4 tunes, 2 TED voices, 50 Hz player driven by
; our own raster IRQ.
;
; Keys: 1-4 select tune, Q or RUN/STOP exits to BASIC.
; Assemble with: acme player.asm
;------------------------------------------------------------------------
!to "ted_tunes.prg", cbm
!sl "symbols.txt"

CHROUT  = $ffd2

!src "player_zp.asm"

        * = $1001
; BASIC stub: 10 SYS4109
        !byte $0b,$10,$0a,$00,$9e
        !text "4109"
        !byte $00,$00,$00

;------------------------------------------------------------------------
start:
        ldx #7                  ; save the zp bytes we borrow
sv1:    lda zp1,x
        sta zpsave,x
        dex
        bpl sv1
        lda $ff19               ; remember border colour
        sta bordsave

        jsr print_ui
        lda #0
        jsr select_tune
        lda #$ff
        sta prevA               ; key debounce state (all released)
        sta prevB
        lda #0
        sta quitflag

        ; Take over the IRQ completely. The kernal interrupt on the 264
        ; series fires more than once per frame (it maintains its jiffy
        ; from TED timer sources in addition to the raster), so chaining
        ; it would tick the player too fast. Instead: our own raster IRQ
        ; at a fixed line = exactly once per frame, and we scan the
        ; keyboard matrix ourselves.
        sei
        lda $0314
        sta vecsave
        lda $0315
        sta vecsave+1
        lda $ff0a
        sta ff0asave
        lda $ff0b
        sta ff0bsave
        lda #<irq
        sta $0314
        lda #>irq
        sta $0315
        lda #$02                ; enable raster IRQ only, compare bit 8 = 0
        sta $ff0a
        lda #$cc                ; raster line 204 (exists on PAL and NTSC)
        sta $ff0b
        lda #$ff
        sta $ff09               ; ack anything pending
        cli

mainloop:
        lda quitflag            ; keyscan in the IRQ sets this
        beq mainloop

        sei                     ; restore kernal interrupt setup
        lda vecsave
        sta $0314
        lda vecsave+1
        sta $0315
        lda ff0asave
        sta $ff0a
        lda ff0bsave
        sta $ff0b
        lda #$ff
        sta $ff09
        cli
        lda #0
        sta $ff11               ; sound off
        lda bordsave
        sta $ff19
        ldx #7
rs1:    lda zpsave,x
        sta zp1,x
        dex
        bpl rs1
        rts

;------------------------------------------------------------------------
; Raster IRQ, once per frame. The ROM entry stub has pushed A,X,Y and
; vectored through $0314, so we ack, do our work, and unwind ourselves.
;------------------------------------------------------------------------
irq:    lda #$ff
        sta $ff09               ; ack TED interrupts
        jsr playtick
        jsr keyscan
        pla
        tay
        pla
        tax
        pla
        rti

;------------------------------------------------------------------------
; keyscan: direct matrix scan via $FD30 (keyboard latch) / $FF08.
; Selector $7F column: bit0='1', bit3='2', bit6='Q', bit7=RUN/STOP.
; Selector $FD column: bit0='3', bit3='4'.
; Edge-detected against previous frame (active low).
;------------------------------------------------------------------------
keyscan:
        lda #$7f
        sta $fd30
        lda #$ff                ; exclude joystick lines
        sta $ff08               ; (write latches the matrix)
        lda $ff08
        sta tmp
        eor #$ff                ; 1 = pressed now
        and prevA               ; & released last frame = new press
        sta newA
        lda tmp
        sta prevA
        lda #$fd
        sta $fd30
        lda #$ff
        sta $ff08
        lda $ff08
        sta tmp
        eor #$ff
        and prevB
        sta newB
        lda tmp
        sta prevB

        lda newA
        and #$01
        beq ks1
        lda #0
        jsr select_tune
ks1:    lda newA
        and #$08
        beq ks2
        lda #1
        jsr select_tune
ks2:    lda newB
        and #$01
        beq ks3
        lda #2
        jsr select_tune
ks3:    lda newB
        and #$08
        beq ks4
        lda #3
        jsr select_tune
ks4:    lda newA
        and #$c0                ; Q or RUN/STOP
        beq ks5
        lda #1
        sta quitflag
ks5:    rts

;------------------------------------------------------------------------
print_ui:
        ldy #0
pr1:    lda uitext,y
        beq prdone
        jsr CHROUT
        iny
        bne pr1
prdone: rts

uitext: !byte $93,$0d
        !pet "  ted tunes - latent/sprout 2026",$0d,$0d
        !pet "  1 latent pulse   125 bpm",$0d
        !pet "  2 border glow    ambient",$0d
        !pet "  3 night shift    150 bpm",$0d
        !pet "  4 phosphor pop   107 bpm",$0d,$0d
        !pet "  keys: 1-4 tune, q or stop quits",$0d
        !byte 0

;------------------------------------------------------------------------
; the playback engine + song data
;------------------------------------------------------------------------
!src "player_core.asm"
!src "song_data.asm"

;------------------------------------------------------------------------
; wrapper state
;------------------------------------------------------------------------
zpsave:    !fill 8
bordsave:  !byte 0
vecsave:   !fill 2
ff0asave:  !byte 0
ff0bsave:  !byte 0
prevA:     !byte 0
prevB:     !byte 0
newA:      !byte 0
newB:      !byte 0
quitflag:  !byte 0
