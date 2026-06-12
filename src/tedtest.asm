;------------------------------------------------------------------------
; tedtest.asm - Milestone 0 probe for the VECTOR STREAM demo
;
; Answers, by visual inspection of one screen:
;   Q1  does multicolor text mode work with a RAM charset at $2000
;       ($FF12 bit 2 = 0, $FF13 = $20)?
;   Q2  what does the %11 bitpair use from the attribute byte -
;       full color+luminance, or a restricted subset?
;   Q3  does attribute bit 3 gate per-char multicolor like the C64
;       (bit3=0 -> hires char), or is MCM global on TED?
;
; Screen layout (rows counted from 0):
;   row  2: 16 cells of char 3 (all %11), attr = color 0..15, lum 7
;   row  4: 16 cells of char 3 (all %11), attr = color 2 (red), lum 0..7 (x2)
;   row  6: 16 cells of char 4 (striped), attr = $0A (lum0 col10, bit3=1)
;   row  8: 16 cells of char 4 (striped), attr = $02 (lum0 col2,  bit3=0)
;   row 10: chars 0,1,2,3 repeated (solid 00/01/10/11 reference)
; If bit3 gating exists, rows 6 and 8 will render visibly differently
; (row 8 falling back to hires: 8 thin pixels instead of 4 wide ones).
;
; Assemble: acme src/tedtest.asm   ->  build/tedtest.prg
;------------------------------------------------------------------------
!to "build/tedtest.prg", cbm

SCREEN = $0c00
COLRAM = $0800

        * = $1001
        !byte $0b,$10,$0a,$00,$9e       ; 10 SYS4109
        !text "4109"
        !byte $00,$00,$00

CSET = $1800            ; charset base under test

start:
        sei
        ; --- build the test charset at CSET ---
        ; char 0: all %00, char 1: all %01, char 2: all %10, char 3: all %11
        ldx #0
cs0:    lda #%00000000
        sta CSET,x
        lda #%01010101
        sta CSET+$08,x
        lda #%10101010
        sta CSET+$10,x
        lda #%11111111
        sta CSET+$18,x
        inx
        cpx #8
        bne cs0
        ; char 4: rows 00,01,10,11,00,01,10,11 (horizontal stripes)
        ; char 200 ($C8): same stripes (tests the upper half of a 2KB set
        ; with hardware reverse disabled via $FF07 bit 7)
        ldx #0
cs4:    lda stripes,x
        sta CSET+$20,x
        sta CSET+200*8,x
        inx
        cpx #8
        bne cs4

        ; --- clear screen to char 0, colram to $71 (white lum7) ---
        ldx #0
clr:    lda #0
        sta SCREEN,x
        sta SCREEN+$100,x
        sta SCREEN+$200,x
        sta SCREEN+$2e8,x
        lda #$71
        sta COLRAM,x
        sta COLRAM+$100,x
        sta COLRAM+$200,x
        sta COLRAM+$2e8,x
        inx
        bne clr

        ; --- row 2: char 3, attr = lum7 | color 0..15 ---
        ldx #0
r2:     lda #3
        sta SCREEN+2*40+12,x
        txa
        ora #$70
        sta COLRAM+2*40+12,x
        inx
        cpx #16
        bne r2

        ; --- row 4: char 3, attr = color 2, lum 0..7 twice ---
        ldx #0
r4:     lda #3
        sta SCREEN+4*40+12,x
        txa
        and #$07
        asl
        asl
        asl
        asl
        ora #$02
        sta COLRAM+4*40+12,x
        inx
        cpx #16
        bne r4

        ; --- row 6: char 4 (stripes), attr $0A (bit3=1) ---
        ; --- row 8: char 4 (stripes), attr $02 (bit3=0) ---
        ldx #0
r68:    lda #4
        sta SCREEN+6*40+12,x
        sta SCREEN+8*40+12,x
        lda #$0a
        sta COLRAM+6*40+12,x
        lda #$02
        sta COLRAM+8*40+12,x
        inx
        cpx #16
        bne r68

        ; --- row 10: solid reference chars 0,1,2,3 ---
        ldx #0
r10:    txa
        and #3
        sta SCREEN+10*40+12,x
        inx
        cpx #16
        bne r10

        ; --- row 12: char 200 (high-code stripes), attr $3A ---
        ldx #0
r12:    lda #200
        sta SCREEN+12*40+12,x
        lda #$3a
        sta COLRAM+12*40+12,x
        inx
        cpx #16
        bne r12

        ; --- TED setup ---
        lda #$08                ; screen at $0c00 (bits 7-3 of FF14)
        sta $ff14
        lda #>CSET              ; charset base
        sta $ff13
        lda $ff12
        and #%11111011          ; bit 2 = 0 -> charset from RAM
        sta $ff12
        lda $ff07
        ora #%10010000          ; MCM on, hardware reverse off
        sta $ff07
        lda #$00                ; bg = black
        sta $ff15
        lda #$36                ; MC1 ($FF16): lum 3, color 6 (bluish)
        sta $ff16
        lda #$6e                ; MC2 ($FF17): lum 6, color 14? (yellowish area)
        sta $ff17
        lda #$00
        sta $ff19               ; border black

        cli
forever:
        jmp forever

stripes:
        !byte %00000000
        !byte %01010101
        !byte %10101010
        !byte %11111111
        !byte %00000000
        !byte %01010101
        !byte %10101010
        !byte %11111111
