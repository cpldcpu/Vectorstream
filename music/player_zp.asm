; Zero-page contract of the TED TUNES engine (player_core.asm).
; !src this BEFORE any code that calls the player, so the assembler
; knows these are zero-page operands in pass 1.
zp1     = $60           ; work pointer (env/rel/arp/vib tables)
patp1   = $64           ; current pattern, voice 1
patp2   = $66           ; current pattern, voice 2
