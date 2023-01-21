; mm2mmc3regs.inc
; Copyright 2022 Justin Olbrantz (Quantam)

; Common definitions for both Mega Man 2 and Rockman 2 for the ca65 assembler.
; Do not include this file directly. Use mm2mmc3.inc or rm2mmc3.inc.

; This work is licensed under the Creative Commons Attribution-ShareAlike 4.0 International License. To view a copy of this license, visit http://creativecommons.org/licenses/by-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

BankCtrlReg := $9ffc
BankReg := $9ffd
MirrorReg := $bffc
PrgRamProtectReg := $bffd
IrqCounterReg := $dffc
IrqReloadReg := $dffd
IrqDisableReg := $fffc
IrqEnableReg := $fffd

SWITCH_BANK_8 = 6
SWITCH_BANK_A = 7

MIRROR_VERTICAL = 0
MIRROR_HORIZONTAL = 1

Cur16kBank := $29
CurBankA := $67
CurBankCtrl := $68
SetBankTemp := $69

; IRQ handler API
; If a hack uses bank-switching in all 3 of the game loop, IRQ handler, and NMI handler, these macros must be executed in the IRQ handler before (save_irq_bank_regs) and after (restore_irq_bank_regs) all bank-switching occurs, and the safe bank-switching API must be used.

.macro save_irq_bank_regs
	lda CurBankCtrl
	pha
	
	lda SetBankTemp
	pha
	
	lda Cur16kBank
	pha
	
	lda CurBankA
	pha
.endmacro

.macro restore_irq_bank_regs
	pla
	jsr SwitchBankA
	
	pla
	asl A
	jsr SwitchBank8
	
	pla
	jsr SetBankTemp
	
	pla
	sta CurBankCtrl
	sta BankCtrlReg
.endmacro