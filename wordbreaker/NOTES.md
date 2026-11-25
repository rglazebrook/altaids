# WORDBREAKER for the Altaids

This program was vibe coded with Claude Code.

A five-letter word guessing game. You get 6 guesses. Each letter of a guess is
marked green (right letter, right spot), yellow (in the word, wrong spot) or
grey (not in the word). An alphabet strip shows what's left: `.` = ruled out.

**3,350 words fit in 8KB:** 2,000 common words that can be the secret,
plus 1,350 rarer ones that are only accepted as guesses. About 360 bytes stay
free for the game to run in.

## Playing it

1. In Tiny BASIC type `XLOAD`, then in TeraTerm use File > Transfer > XMODEM > Send
   and pick `WORDBREAKER.TBI`.
2. `RUN`, then answer the hard mode question. In hard mode you can't use a letter
   already marked grey (not in the word). Your answer stays set until the next RUN.

The settings are on line 40:

- `C=1` gives ANSI color tiles. `C=0` gives plain text: `[A]` green, `(A)` yellow,
  lowercase grey.
- `V=1` only accepts guesses from the word list. `V=0` accepts any 5 letters.

You can edit lines 40-99 on the Altaids (EDIT 40 etc.) and XSAVE as usual.
**Don't touch line 1 or line 32767.** LIST shows them as just `1 REM` and
`32767 REM`, but they hold binary data.

`WORDBREAKER.BAS` is the readable source with comments. It is **not** loadable on its
own because it doesn't include line 1 or line 32767. `build.py` makes the .TBI from it.

## How the words fit

Plain 5-bit letters take 25 bits per word. This version averages **11.6 bits per word**:

1. **Sort the list and store only what changed.** For each word we store how many
   letters it shares with the previous word, then how far the first changed letter moved on
   (SIGMA to SILEX: 2 shared, G to L is +5), then the rest of its letters.
2. **Huffman-code everything.** E, A, R, S get short codes and Q, J, X, Z get long ones.
   Most words share 2-3 letters with the word before them, so that count usually costs
   1-2 bits.
3. **One bit per word marks a possible secret.** That lets obscure words count as valid
   guesses without ever being the answer.
4. **One group per first letter.** Each group starts on a byte boundary, and a 26-entry table
   gives each group's offset and counts. Checking a guess only unpacks one group
   (0.6 s at worst, for S). Picking a secret also unpacks one group.

## Where things live in memory

- **Line 1** (`1 REM` + 3 zero bytes + about 900 bytes of 8085 code) always starts at
  201AH (TXTBGN), so the code always lands at 2022H, whatever you do to the other lines.
  The code avoids the byte 0DH, because a CR would end the line.
- **Line 32767** is the packed word list. It is the last line, so GOTO and GOSUB never
  have to scan past it. The code finds it from TXTUNF (2018H). The table bytes are XOR'd
  with a key, and the bit stream escapes 0DH and 10H, so no CR can appear in the line.
- The three 0 bytes after `REM` stop LIST, because PRTLN stops printing at a 0 byte.
- The code's scratch space is the BASIC input buffer (3E40H), which isn't in use during a USR call.
- The secret word goes in `@(1)`-`@(5)`, and letter status in `@(21)`-`@(46)`.

USR entry points:

| Call | Does |
|---|---|
| `USR(8226)` | number of secret words |
| `USR(8229,R)` | unpack secret number R to address 15936 |
| `USR(8232,G)` | 1 if the word at address G is in the list |
| `USR(8235)` | total number of words |
| `USR(8238,G)` | mark guess G, update the alphabet, write the display line to G+8 (for PUT$), return the number of greens |
| `USR(8241,G)` | hard mode: the ASCII code of the first letter in G already marked grey, or 0 |

## Changing the word list

Edit `words.txt`: one word per line, most common first. A `*` marks a word that can be
the secret. Then run `python build.py`, which needs only Python 3. If the list gets too
big for memory, it stops and tells you.

`asm8080.py` is a small assembler that build.py uses for `WBDEC.ASM`. A85 assembles that
file the same way, but build.py fills in the table offsets for you.

## Testing without the hardware

`emu8085.py` + `runtbi.py` run the **real Altaids ROM** (`..\Software\altaids.hex`) with
the serial routines intercepted:

    python runtbi.py WORDBREAKER.TBI "RUN\r" "\r" "crane\r"

`verify.py` checks that all 3,350 words are accepted, that 2,000 non-words are rejected,
that every secret unpacks correctly, and that 3,000 random guesses (including repeated
letters) are marked correctly. Timings assume 2,400 baud output, so a turn takes about
1 second, mostly sending the colored tiles.

The word list comes from public domain dictionaries (Webster's 1913 / web2), ranked
by how common each word is today, with a few modern words added (EMAIL, PIZZA, VIDEO...).
Proper names and slurs are left out, and so are most plurals.
