; WBDEC.ASM - word list decoder for WORDBREAKER
;
; Lives inside line 1 of the BASIC program ("1 REM" + these bytes),
; which always starts at 201AH, so the code sits at a fixed address.
; The packed word list lives in the program's LAST line (32767 REM ...),
; found at run time from TXTUNF, so BASIC lines can be edited freely.
;
; No byte of this code may be 0DH (CR) or BASIC would think the line ends.
; The build script checks this.
;
; BASIC entry points:
;   USR(8226)     returns the number of secret (answer) words
;   USR(8229,R)   unpacks secret word number R (1..N) to SCR (15936)
;   USR(8232,G)   G = address of a 5 letter guess; returns 1 if known word
;   USR(8235)     returns the total number of words (answers + guesses)
;   USR(8238,G)   marks guess G against the secret in @(1)-@(5), updates the
;                 letter status in @(21)-@(46), writes the display line
;                 (tiles + alphabet) to G+8 for PUT$, returns greens (0-5)
;                 uses BASIC variable C: 1 = ANSI colors, 0 = text marks
;
; Constants supplied by the build script:
;   KEY   XOR key for the table area      PLEN  payload length
;   OFFL/OFFD/OFFP  Huffman table offsets  STRM  bit stream offset
;
TXTUNF	EQU	2018H
SCR	EQU	3E40H		; scratch inside the BASIC line buffer (free during USR)
W	EQU	SCR		; current word, 5 ASCII letters
BPTR	EQU	SCR+5		; bit stream pointer
BYTE	EQU	SCR+7		; current stream byte (shifted)
BCNT	EQU	SCR+8		; bits left in BYTE
BASE	EQU	SCR+9		; address of payload
CNT	EQU	SCR+11		; words left in this group
RV	EQU	SCR+13		; R for PICK
GP	EQU	SCR+15		; guess pointer for CHECK
FST	EQU	SCR+17		; 1 = next word is first of its group
GL	EQU	SCR+20		; guess letters (5)
SL	EQU	SCR+25		; secret letters (5)
MK	EQU	SCR+30		; marks 0 grey 1 yellow 2 green (5)
US	EQU	SCR+35		; secret letter used (5)
GRN	EQU	SCR+40		; green count
OUTP	EQU	SCR+41		; output pointer (2)
CVAR	EQU	3E06H		; BASIC variable C
SEC	EQU	3DFEH		; @(1)
KEYS	EQU	3DD6H		; @(21)
;
	ORG	2022H		; 201AH + line number(2) + 'REM' + three 0 bytes
	JMP	NANS
	JMP	PICK
	JMP	CHECK
	JMP	NWRD
	JMP	MARK
;
; BASE = TXTUNF - 1 - PLEN
INIT:	PUSH	H
	LHLD	TXTUNF
	LXI	D,0-(PLEN+1)
	DAD	D
	SHLD	BASE
	POP	H
	RET
;
NANS:	CALL	INIT
	LHLD	BASE
	INX	H
	INX	H
	JMP	LD16
NWRD:	CALL	INIT
	LHLD	BASE
; HL -> 16 bit table value; returns it in HL (DE clobbered)
LD16:	MOV	A,M
	XRI	KEY
	MOV	E,A
	INX	H
	MOV	A,M
	XRI	KEY
	MOV	D,A
	XCHG
	RET
;
; A = group (0..25) -> HL = BASE+4+6*A
GRPENT:	MOV	L,A
	ADD	A
	ADD	L
	ADD	A
	ADI	4
	MOV	E,A
	MVI	D,0
	LHLD	BASE
	DAD	D
	RET
;
; start decoding group A
STARTG:	PUSH	PSW
	ADI	'A'
	STA	W
	MVI	A,1
	STA	FST
	XRA	A
	STA	BCNT
	POP	PSW
	CALL	GRPENT
	PUSH	H
	CALL	LD16		; HL = group offset in stream
	XCHG
	LHLD	BASE
	DAD	D
	LXI	D,STRM
	DAD	D
	SHLD	BPTR
	POP	H
	INX	H
	INX	H
	CALL	LD16		; HL = words in group
	SHLD	CNT
	RET
;
; get next bit into carry, keeps BC DE HL
GETBIT:	PUSH	H
	LXI	H,BCNT
	DCR	M
	JP	GB2
	MVI	M,7
	LHLD	BPTR
	MOV	A,M
	INX	H
	CPI	10H		; escape byte?
	JNZ	GB1
	MOV	A,M
	INX	H
	XRI	80H
GB1:	SHLD	BPTR
	STA	BYTE
GB2:	LXI	H,BYTE
	MOV	A,M
	ADD	A
	MOV	M,A
	POP	H
	RET
;
; HUFFT: DE = table offset from BASE. Returns symbol in A. Keeps BC.
HUFFT:	LHLD	BASE
	DAD	D
	XCHG
; HUFF: DE -> 8 code length counts, then the symbols (all XOR KEY)
HUFF:	PUSH	B
	PUSH	H
	PUSH	D
	MVI	B,0		; code
	MVI	C,0		; first code of this length
	MVI	L,0		; symbol index
HF1:	CALL	GETBIT
	MOV	A,B
	ACI	0
	MOV	B,A
	LDAX	D
	XRI	KEY
	MOV	H,A		; count of codes this length
	MOV	A,B
	SUB	C
	CMP	H
	JC	HF2
	MOV	A,L
	ADD	H
	MOV	L,A
	MOV	A,C
	ADD	H
	ADD	A
	MOV	C,A
	MOV	A,B
	ADD	A
	MOV	B,A
	INX	D
	JMP	HF1
HF2:	ADD	L
	ADI	8
	POP	D
	MOV	L,A
	MVI	H,0
	DAD	D
	MOV	A,M
	XRI	KEY
	POP	H
	POP	B
	RET
;
; decode next word of the group into W, carry = secret word flag
NEXTW:	MVI	C,1
	LDA	FST
	ORA	A
	JNZ	NW2
	LXI	D,OFFP
	CALL	HUFFT		; letters shared with previous word
	MOV	C,A
	LXI	D,OFFD
	CALL	HUFFT		; how far the next letter moved on
	MOV	B,A
	LXI	H,W
	MOV	A,L
	ADD	C
	MOV	L,A
	MOV	A,M
	ADD	B
	MOV	M,A
	INR	C
NW2:	XRA	A
	STA	FST
NW3:	MOV	A,C
	CPI	5
	JNC	GETBIT
	LXI	D,OFFL
	CALL	HUFFT		; a fresh letter
	LXI	H,W
	MOV	B,A
	MOV	A,L
	ADD	C
	MOV	L,A
	MOV	M,B
	INR	C
	JMP	NW3
;
; CHECK: HL -> guess. returns HL = 1 if in list
CHECK:	CALL	INIT
	SHLD	GP
	MOV	A,M
	ANI	0DFH
	SUI	'A'
	JC	NO
	CPI	26
	JNC	NO
	CALL	STARTG
CK1:	LHLD	CNT
	MOV	A,H
	ORA	L
	JZ	NO
	DCX	H
	SHLD	CNT
	CALL	NEXTW
CKA:	LHLD	GP
	LXI	D,W
	MVI	B,4
CK2:	INX	H
	INX	D
	MOV	A,M
	ANI	0DFH
	MOV	C,A
	LDAX	D
	CMP	C
	JZ	CK3
	JNC	NO		; list is sorted: passed the guess, give up
	JMP	CK1
CK3:	DCR	B
	JNZ	CK2
	LXI	H,1
	RET
NO:	LXI	H,0
	RET
;
; PICK: HL = R (1..N). unpacks the R'th secret word to W
PICK:	CALL	INIT
	SHLD	RV
	MVI	B,0
PK1:	MOV	A,B
	CALL	GRPENT
	LXI	D,4
	DAD	D
	CALL	LD16		; HL = secret words in group
	XCHG
	LHLD	RV
	MOV	A,L
	SUB	E
	MOV	L,A
	MOV	A,H
	SBB	D
	MOV	H,A		; HL = R - count
	JC	PKF
	ORA	L
	JZ	PKF
	SHLD	RV
	INR	B
	MOV	A,B
	CPI	26
	JC	PK1
	JMP	NO
PKF:	MOV	A,B
	CALL	STARTG
PK2:	LHLD	CNT
	MOV	A,H
	ORA	L
	JZ	NO
	DCX	H
	SHLD	CNT
	CALL	NEXTW
	JNC	PK2
	LHLD	RV
	DCX	H
	SHLD	RV
	MOV	A,H
	ORA	L
	JNZ	PK2
	LXI	H,1
	RET
;
; MARK: HL -> guess (5 letters)
MARK:	PUSH	H
	LXI	D,8
	DAD	D
	SHLD	OUTP
	POP	H
	LXI	D,GL
	MVI	B,5
MK0:	MOV	A,M		; guess -> GL (upper case)
	ANI	0DFH
	STAX	D
	INX	H
	INX	D
	DCR	B
	JNZ	MK0
	LXI	H,SEC
	MVI	B,5
MK1:	MOV	A,M		; @(1..5) -> SL
	STAX	D
	INX	D
	DCX	H
	DCX	H
	DCR	B
	JNZ	MK1
	XRA	A
	MVI	B,11
MK2:	STAX	D		; clear MK, US, GRN
	INX	D
	DCR	B
	JNZ	MK2
; greens
	MVI	C,0
MG1:	LXI	H,GL
	CALL	IDXC
	MOV	A,M
	LXI	D,5
	DAD	D
	CMP	M
	JNZ	MG2
	DAD	D
	MVI	M,2
	DAD	D
	MVI	M,1
	LXI	H,GRN
	INR	M
MG2:	CALL	NEXTC
	JC	MG1
; yellows
	MVI	C,0
MY1:	LXI	H,MK
	CALL	IDXC
	MOV	A,M
	ORA	A
	JNZ	MY4
	LXI	H,GL
	CALL	IDXC
	MOV	E,M		; E = guess letter
	MVI	B,0
MY2:	LXI	H,US
	MOV	A,B
	CALL	ADDL
	MOV	A,M
	ORA	A
	JNZ	MY3
	LXI	H,SL
	MOV	A,B
	CALL	ADDL
	MOV	A,M
	CMP	E
	JNZ	MY3
	LXI	H,US
	MOV	A,B
	CALL	ADDL
	MVI	M,1
	LXI	H,MK
	CALL	IDXC
	MVI	M,1
	JMP	MY4
MY3:	INR	B
	MOV	A,B
	CPI	5
	JC	MY2
MY4:	CALL	NEXTC
	JC	MY1
; letter status: @(21+K) = max(@(21+K), mark+1)
	MVI	C,0
MKB:	LXI	H,MK
	CALL	IDXC
	MOV	B,M
	INR	B
	LXI	H,GL
	CALL	IDXC
	MOV	A,M
	SUI	'A'
	CPI	26
	JNC	MKB2		; not a letter
	ADD	A
	MOV	E,A
	MVI	A,LOW(KEYS)
	SUB	E
	MOV	L,A
	MVI	H,HIGH(KEYS)
	MOV	A,M
	CMP	B
	JNC	MKB2
	MOV	M,B
MKB2:	CALL	NEXTC
	JC	MKB
; build the display line
	LHLD	OUTP
	XCHG
	MVI	C,0
MT1:	LXI	H,GL
	CALL	IDXC
	MOV	B,M
	LXI	H,MK
	CALL	IDXC
	MOV	A,M
	CALL	TILE
	CALL	NEXTC
	JC	MT1
	MVI	A,' '
	CALL	PUT
	CALL	PUT
	CALL	PUT
	MVI	C,0
MA1:	MVI	A,LOW(KEYS)
	SUB	C
	SUB	C
	MOV	L,A
	MVI	H,HIGH(KEYS)
	MOV	L,M		; L = status
	MOV	A,C
	ADI	'A'
	MOV	B,A
	MOV	A,L
	ORA	A
	JZ	MA2
	DCR	A
	JZ	MA3
	CALL	KEYC
	JMP	MA4
MA2:	MOV	A,B
	CALL	PUT
	JMP	MA4
MA3:	MVI	A,'.'
	CALL	PUT
MA4:	INR	C
	MOV	A,C
	CPI	26
	JC	MA1
	XRA	A
	STAX	D
	LDA	GRN
	MOV	L,A
	MVI	H,0
	RET
;
IDXC:	MOV	A,C
ADDL:	ADD	L
	MOV	L,A
	RET
NEXTC:	INR	C
	MOV	A,C
	CPI	5
	RET
PUT:	STAX	D
	INX	D
	RET
;
; TILE: B = letter, A = mark. Keeps C.
TILE:	MOV	H,A
	LDA	CVAR
	ORA	A
	MOV	A,H
	JZ	TT
	CALL	SETCOL
	MVI	A,' '
	CALL	PUT
	MOV	A,B
	CALL	PUT
	MVI	A,' '
	CALL	PUT
	JMP	RESET
TT:	CPI	2
	JZ	TT2
	CPI	1
	JZ	TT1
	MVI	A,' '
	CALL	PUT
	MOV	A,B
	ORI	20H
	CALL	PUT
	MVI	A,' '
	JMP	PUT
TT2:	MVI	A,'['
	CALL	PUT
	MOV	A,B
	CALL	PUT
	MVI	A,']'
	JMP	PUT
TT1:	MVI	A,'('
	CALL	PUT
	MOV	A,B
	CALL	PUT
	MVI	A,')'
	JMP	PUT
;
; KEYC: B = letter, A = mark (1 or 2)
KEYC:	MOV	H,A
	LDA	CVAR
	ORA	A
	MOV	A,H
	JZ	KT
	CALL	SETCOL
	MOV	A,B
	CALL	PUT
	JMP	RESET
KT:	MOV	A,B
	ORI	20H
	JMP	PUT
;
; SETCOL: A = mark -> ESC[30;4Xm  (X = 2 green, 3 yellow, 7 grey)
SETCOL:	MVI	H,'7'
	ORA	A
	JZ	SC1
	MVI	H,'3'
	DCR	A
	JZ	SC1
	MVI	H,'2'
SC1:	MOV	A,H
	PUSH	PSW
	LXI	H,STR1
	CALL	PSTR
	POP	PSW
	CALL	PUT
	MVI	A,'m'
	JMP	PUT
RESET:	LXI	H,STR2
PSTR:	MOV	A,M
	ORA	A
	RZ
	STAX	D
	INX	D
	INX	H
	JMP	PSTR
STR1:	DB	1BH,'[30;4',0
STR2:	DB	1BH,'[0m',0
	END
