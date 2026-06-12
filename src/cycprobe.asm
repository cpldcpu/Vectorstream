;------------------------------------------------------------------------
; cycprobe.asm - measure the main-loop cycle budget       LATENT / sprout
;
; Replicates the demo's runtime environment exactly (anim video mode,
; 50 Hz raster IRQ at line 204 running the music playtick, ROM banked
; out) and counts iterations of a 16-cycle loop for 250 ticks (5 s).
;
;   cycles available to the main loop per 50 Hz tick
;       = iters * 16 / 250        (net of IRQ + music overhead)
;
; Result: 24-bit iteration count at $0F00-$0F02, $0F03 = $5E when done.
;------------------------------------------------------------------------
!to "build/cycprobe.prg", cbm
!src "music/player_zp.asm"

tick = $50
cnt0 = $52
cnt1 = $53
cnt2 = $54

        * = $1001
        !byte $0b,$10,$0a,$00,$9e
        !text "4109"
        !byte $00,$00,$00

start:  sei
        lda #0
        sta $ff15
        sta $ff16
        sta $ff17
        sta $ff19
        lda #$10                ; 24 rows, display on (anim scene mode)
        sta $ff06
        lda #%10010000          ; MCM, 38 col, reverse off
        sta $ff07
        lda #$38                ; matrix $3800/$3C00
        sta $ff14
        lda #$18                ; charset $1800 (content irrelevant here)
        sta $ff13
        lda $ff12
        and #%11111011          ; charset from RAM
        sta $ff12
        lda #<irq
        sta $fffe
        lda #>irq
        sta $ffff
        lda #<nmi
        sta $fffa
        lda #>nmi
        sta $fffb
        lda #1                  ; border glow: realistic playtick cost
        jsr select_tune
        lda #$02
        sta $ff0a
        lda #$cc                ; raster line 204
        sta $ff0b
        lda #$ff
        sta $ff09
        lda #0
        sta tick
        sta cnt0
        sta cnt1
        sta cnt2
        sta $ff3f               ; ROM out
        cli

loop:   inc cnt0                ; 5
        bne .t                  ; 3 (overflow path negligible: 1/256)
        inc cnt1
        bne .t
        inc cnt2
.t:     lda tick                ; 3
        cmp #250                ; 2
        bcc loop                ; 3  -> 16 cycles/iteration

        sei
        lda cnt0
        sta $0f00
        lda cnt1
        sta $0f01
        lda cnt2
        sta $0f02
        lda #$5e                ; done marker
        sta $0f03
.hang:  jmp .hang

irq:    pha
        txa
        pha
        tya
        pha
        lda #$ff
        sta $ff09
        jsr playtick
        inc tick
        pla
        tay
        pla
        tax
        pla
nmi:    rti

        * = $2000
!src "music/player_core.asm"
!src "music/song_data.asm"
