;------------------------------------------------------------------------
; decprobe.asm - measure real decode_frame throughput      LATENT / sprout
;
; Demo-identical environment (anim video mode, 50 Hz IRQ with playtick,
; ROM out). Decodes the cube_t intra stream into the buffer-A char
; matrix in a tight loop for 500 ticks (10 s) and counts frames.
;
;   ticks per decode = 500 / count
;
; Result: 16-bit decode count at $0F20/21, $0F22 = $5E when done.
;------------------------------------------------------------------------
!to "build/decprobe.prg", cbm
!src "music/player_zp.asm"
!src "src/decoder_zp.asm"

tick = $50
cnt  = $52

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
        lda #$10                ; 24 rows, display on
        sta $ff06
        lda #%10010000          ; MCM, 38 col
        sta $ff07
        lda #$38
        sta $ff14
        lda #$18
        sta $ff13
        lda $ff12
        and #%11111011
        sta $ff12
        lda #<irq
        sta $fffe
        lda #>irq
        sta $ffff
        lda #<nmi
        sta $fffa
        lda #>nmi
        sta $fffb
        lda #0                  ; latent pulse: demo-realistic IRQ cost
        jsr select_tune
        lda #$02
        sta $ff0a
        lda #$cc
        sta $ff0b
        lda #$ff
        sta $ff09
        lda #0
        sta tick
        sta cnt
        sta cnt+1
        sta $ff3f
        cli

        lda #<blob
        sta scene_ptr
        lda #>blob
        sta scene_ptr+1
        jsr scene_setup
        lda #<(SCREEN+920)      ; cube window
        sta win_end
        lda #>(SCREEN+920)
        sta win_end+1

loop:   jsr decode_frame
        inc cnt
        bne .nc
        inc cnt+1
.nc:    lda tick
        cmp #250
        bcc loop
        sei
        lda cnt
        sta $0f20
        lda cnt+1
        sta $0f21
        lda #$5e
        sta $0f22
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
!src "src/decoder.asm"
!src "music/player_core.asm"
!src "music/song_data.asm"

blob:
        !bin "build/scene_cube_t.v10cs"
