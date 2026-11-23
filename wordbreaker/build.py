"""Build WORDBREAKER.TBI (python build.py, needs only Python 3): BASIC game + 8085 decoder (line 1) + packed word list (line 32767).

Word list format (all inside the last line, after "REM"):
  table area (every byte XOR KEY so no byte is a CR):
    +0   total words (2)   +2 secret words (2)
    +4   26 groups (one per first letter) x [stream offset(2), words(2), secrets(2)]
    OFFL Huffman table for letters  (8 counts for code lengths 1..8, then symbols)
    OFFD Huffman table for "how far the changed letter moved on"
    OFFP Huffman table for "letters shared with the previous word"
  bit stream at STRM, byte stuffed (0DH and 10H become 10H, byte XOR 80H)
    each group starts on a byte boundary; per word:
      first word of group: 4 letters (L table)
      other words: shared count p (P table), delta for letter p (D table),
                   then letters p+1..4 (L table)
      then 1 bit: 1 = can be a secret word
"""
import heapq, re, sys
from collections import Counter
from asm8080 import Asm

TXTBGN = 0x201A
TXTEND = 0x3E00


def limited_lengths(freq, maxlen=8):
    """Package-merge: optimal code lengths no longer than maxlen."""
    syms = sorted(freq)
    if len(syms) == 1:
        return {syms[0]: 1}
    items = sorted((freq[s], (s,)) for s in syms)
    pk = list(items)
    for _ in range(maxlen - 1):
        merged = [(pk[i][0] + pk[i + 1][0], pk[i][1] + pk[i + 1][1]) for i in range(0, len(pk) - 1, 2)]
        pk = sorted(items + merged, key=lambda x: x[0])
    lens = Counter()
    for w, ss in pk[:2 * len(syms) - 2]:
        for s in ss:
            lens[s] += 1
    return dict(lens)


def canonical(freq):
    lens = limited_lengths(freq)
    order = sorted(lens, key=lambda s: (lens[s], s))
    counts = [0] * 8
    for s in order:
        counts[lens[s] - 1] += 1
    codes, code, prev = {}, 0, 0
    for s in order:
        l = lens[s]
        code <<= (l - prev); prev = l
        codes[s] = (code, l)
        code += 1
    return counts, order, codes


class Bits:
    def __init__(self):
        self.bits = []

    def put(self, v, n):
        for i in range(n - 1, -1, -1):
            self.bits.append(v >> i & 1)

    def tobytes(self):
        b = self.bits + [0] * (-len(self.bits) % 8)
        return bytes(int(''.join(map(str, b[i:i + 8])), 2) for i in range(0, len(b), 8))


def stuff(bs):
    out = bytearray()
    for b in bs:
        if b in (0x0D, 0x10):
            out += bytes([0x10, b ^ 0x80])
        else:
            out.append(b)
    return bytes(out)


def encode(words, answers):
    words = sorted(words)
    groups = [[w for w in words if w[0] == chr(97 + g)] for g in range(26)]
    # gather symbol statistics
    fL, fD, fP = Counter(), Counter(), Counter()
    for grp in groups:
        for i, w in enumerate(grp):
            if i == 0:
                start = 1
            else:
                prev = grp[i - 1]; p = 1
                while w[p] == prev[p]:
                    p += 1
                fP[p] += 1; fD[ord(w[p]) - ord(prev[p])] += 1
                start = p + 1
            for j in range(start, 5):
                fL[w[j].upper()] += 1
    cL, oL, kL = canonical(fL)
    cD, oD, kD = canonical(fD)
    cP, oP, kP = canonical(fP)
    stream, gtab = b'', []
    for grp in groups:
        bits = Bits()
        for i, w in enumerate(grp):
            if i == 0:
                start = 1
            else:
                prev = grp[i - 1]; p = 1
                while w[p] == prev[p]:
                    p += 1
                bits.put(*kP[p]); bits.put(*kD[ord(w[p]) - ord(prev[p])])
                start = p + 1
            for j in range(start, 5):
                bits.put(*kL[w[j].upper()])
            bits.put(int(w in answers), 1)
        gtab.append((len(stream), len(grp), sum(w in answers for w in grp)))
        stream += stuff(bits.tobytes())
    tab = bytearray()
    w16 = lambda v: bytes([v & 255, v >> 8])
    tab += w16(len(words)) + w16(len(answers))
    for off, n, a in gtab:
        tab += w16(off) + w16(n) + w16(a)
    offl = len(tab); tab += bytes(cL) + bytes(ord(s) for s in oL)
    offd = len(tab); tab += bytes(cD) + bytes(oD)
    offp = len(tab); tab += bytes(cP) + bytes(oP)
    return tab, stream, dict(OFFL=offl, OFFD=offd, OFFP=offp, STRM=len(tab))


def minify(text):
    """Strip spaces outside strings and abbreviate keywords, like Rob's .min.bas files."""
    out, q = '', None
    i = 0
    abbrev = [('PRINT', 'PR.'), ('GOSUB', 'GOS.'), ('RETURN', 'RET.'), ('NEXT', 'N.')]
    while i < len(text):
        ch = text[i]
        if q:
            out += ch
            if ch == q:
                q = None
            i += 1
            continue
        if ch in '"\'':
            q = ch; out += ch; i += 1; continue
        if ch == ' ':
            i += 1; continue
        for k, a in abbrev:
            if text.startswith(k, i):
                out += a; i += len(k); break
        else:
            out += ch; i += 1
    return out


def basic_lines(path, mini=True):
    lines = []
    for raw in open(path):
        raw = raw.rstrip('\r\n')
        if not raw.strip():
            continue
        m = re.match(r'\s*(\d+)\s?(.*)$', raw)
        n, text = int(m.group(1)), m.group(2)
        if mini:
            if text.startswith('REM'):
                continue
            text = minify(text)
        lines.append((n, text))
    # every GOTO/GOSUB target must survive the REM stripping
    nums = {n for n, _ in lines}
    for n, t in lines:
        for tgt in re.findall(r'(?:GOTO|GOS\.|GOSUB)\s*(\d+)', t):
            assert int(tgt) in nums, f'line {n} jumps to missing line {tgt}'
    return lines


def line_bytes(n, body):
    assert b'\r' not in body, f'CR inside line {n}'
    return bytes([n & 255, n >> 8]) + body + b'\r'


def read_words(path='words.txt'):
    words, secrets = [], set()
    for line in open(path):
        line = line.split('#')[0].split()
        if not line:
            continue
        w = line[0].lower()
        assert len(w) == 5 and w.isalpha() and w.isascii(), f'bad word {w!r}'
        if w in words:
            continue
        words.append(w)
        if '*' in line[1:]:
            secrets.add(w)
    return words, secrets


def build(bas='WORDBREAKER.BAS', out='WORDBREAKER.TBI', wordfile='words.txt', mini=True, verbose=True):
    words, answers = read_words(wordfile)
    tab, stream, offs = encode(words, answers)
    # pick a XOR key that keeps CR out of the table area
    for key in range(1, 256):
        if key != 0x0D and all((b ^ key) != 0x0D for b in tab):
            break
    payload = bytes(b ^ key for b in tab) + stream
    src = open('WBDEC.ASM').read()
    for pad in range(0, 4):
        consts = dict(offs, KEY=key, PLEN=len(payload) + pad)
        org, code = Asm(src, consts).run()
        if 0x0D not in code:
            break
    payload += b'\xff' * pad if pad else b''
    assert org == TXTBGN + 8
    assert 0x0D not in code and 0x0D not in payload
    prog = line_bytes(1, b'REM\0\0\0' + code)   # the 0s stop LIST printing binary
    for n, t in basic_lines(bas, mini):
        prog += line_bytes(n, t.encode('ascii'))
    prog += line_bytes(32767, b'REM\0\0\0' + payload)
    end = TXTBGN + len(prog)
    free = TXTEND - end
    # at run time the guess (G=FREE), its 233 byte display line and the
    # @ array (92 bytes below 3E00H) all need to fit above the program
    assert free >= 340, f'only {free} bytes free: remove some words from {wordfile}'
    img = prog + b'\xff' * (-len(prog) % 128)
    open(out, 'wb').write(img)
    if verbose:
        print(f'words={len(words)} secrets={len(answers)} tables={len(tab)} stream={len(stream)} '
              f'bits/word={8 * len(stream) / len(words):.2f} code={len(code)} program={len(prog)} '
              f'free={free} key={key:02X} file={len(img)}')
    return dict(words=words, answers=answers, prog=prog, free=free, img=img)


if __name__ == '__main__':
    build()
