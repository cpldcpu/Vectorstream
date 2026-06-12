; Standalone build of the V10CS decoder for py65 verification.
!to "build/test_decoder.prg", cbm
!sl "build/test_decoder_sym.txt"
!src "src/decoder_zp.asm"
        * = $1001
!src "src/decoder.asm"
