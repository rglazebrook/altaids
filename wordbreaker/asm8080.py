"""Tiny two-pass 8080/8085 assembler (enough for WORDBREAKER's decoder).
Syntax follows A85: LABEL: OP args ; comment, NAME EQU expr, ORG, DB, DW.
Numbers: 123, 0FFH, 101B, 'A'. Expressions are evaluated with Python
operators (+ - * / & | << >> and HIGH()/LOW())."""
import re

REG = {'B': 0, 'C': 1, 'D': 2, 'E': 3, 'H': 4, 'L': 5, 'M': 6, 'A': 7}
RP = {'B': 0, 'D': 1, 'H': 2, 'SP': 3}
RPPSW = {'B': 0, 'D': 1, 'H': 2, 'PSW': 3}
IMPLIED = {'NOP': 0x00, 'RLC': 0x07, 'RRC': 0x0F, 'RAL': 0x17, 'RAR': 0x1F, 'DAA': 0x27, 'CMA': 0x2F,
           'STC': 0x37, 'CMC': 0x3F, 'HLT': 0x76, 'RET': 0xC9, 'XCHG': 0xEB, 'XTHL': 0xE3, 'SPHL': 0xF9,
           'PCHL': 0xE9, 'DI': 0xF3, 'EI': 0xFB, 'RIM': 0x20, 'SIM': 0x30,
           'RNZ': 0xC0, 'RZ': 0xC8, 'RNC': 0xD0, 'RC': 0xD8, 'RPO': 0xE0, 'RPE': 0xE8, 'RP': 0xF0, 'RM': 0xF8}
ADDR16 = {'JMP': 0xC3, 'JNZ': 0xC2, 'JZ': 0xCA, 'JNC': 0xD2, 'JC': 0xDA, 'JPO': 0xE2, 'JPE': 0xEA,
          'JP': 0xF2, 'JM': 0xFA, 'CALL': 0xCD, 'CNZ': 0xC4, 'CZ': 0xCC, 'CNC': 0xD4, 'CC': 0xDC,
          'CPO': 0xE4, 'CPE': 0xEC, 'CP': 0xF4, 'CM': 0xFC, 'LHLD': 0x2A, 'SHLD': 0x22, 'LDA': 0x3A,
          'STA': 0x32}
IMM8 = {'ADI': 0xC6, 'ACI': 0xCE, 'SUI': 0xD6, 'SBI': 0xDE, 'ANI': 0xE6, 'XRI': 0xEE, 'ORI': 0xF6,
        'CPI': 0xFE, 'IN': 0xDB, 'OUT': 0xD3}
ALU = {'ADD': 0x80, 'ADC': 0x88, 'SUB': 0x90, 'SBB': 0x98, 'ANA': 0xA0, 'XRA': 0xA8, 'ORA': 0xB0, 'CMP': 0xB8}


def num(tok):
    t = tok.upper()
    if re.fullmatch(r'[0-9][0-9A-F]*H', t):
        return str(int(t[:-1], 16))
    if re.fullmatch(r'[01]+B', t):
        return str(int(t[:-1], 2))
    return tok


class Asm:
    def __init__(self, src, consts=None):
        self.src = src
        self.consts = dict(consts or {})

    def ev(self, expr, syms, final):
        e = re.sub(r"'(.)'", lambda m: str(ord(m.group(1))), expr)
        e = re.sub(r'\b[0-9][0-9A-Fa-f]*[Hh]\b|\b[01]+[Bb]\b', lambda m: num(m.group(0)), e)
        e = e.replace('$', str(self.pc))
        env = {'HIGH': lambda v: (v >> 8) & 255, 'LOW': lambda v: v & 255}
        env.update(syms)
        try:
            return int(eval(e, {'__builtins__': {}}, env))
        except NameError:
            if final:
                raise
            return 0

    def run(self):
        syms = dict(self.consts)
        for final in (False, True):
            self.pc = 0
            out = {}
            for lineno, raw in enumerate(self.src.splitlines(), 1):
                line = re.sub(r";.*", "", raw) if "'" not in raw else self._strip(raw)
                if not line.strip():
                    continue
                m = re.match(r'^([A-Za-z_][\w]*):?\s+EQU\s+(.*)$', line.strip(), re.I)
                if m:
                    syms[m.group(1).upper()] = self.ev(m.group(2), syms, final)
                    continue
                m = re.match(r'^([A-Za-z_]\w*):(.*)$', line.strip())
                if m:
                    syms[m.group(1).upper()] = self.pc
                    line = m.group(2)
                    if not line.strip():
                        continue
                parts = line.strip().split(None, 1)
                op = parts[0].upper()
                args = [a.strip() for a in self._split(parts[1])] if len(parts) > 1 else []
                try:
                    bs = self.encode(op, args, syms, final)
                except Exception as ex:
                    raise SyntaxError(f'line {lineno}: {raw!r}: {ex}')
                if bs is None:
                    continue
                for b in bs:
                    out[self.pc] = b & 255
                    self.pc += 1
        self.syms = syms
        lo, hi = min(out), max(out)
        return lo, bytes(out.get(a, 0) for a in range(lo, hi + 1))

    @staticmethod
    def _strip(raw):
        res, q = '', False
        for ch in raw:
            if ch == "'":
                q = not q
            if ch == ';' and not q:
                break
            res += ch
        return res

    @staticmethod
    def _split(s):
        res, cur, q = [], '', False
        for ch in s:
            if ch == "'":
                q = not q
            if ch == ',' and not q:
                res.append(cur); cur = ''
            else:
                cur += ch
        res.append(cur)
        return res

    def encode(self, op, a, syms, final):
        ev = lambda x: self.ev(x, syms, final)
        if op == 'ORG':
            self.pc = ev(a[0]); return None
        if op == 'END':
            return None
        if op == 'DB':
            bs = []
            for x in a:
                if len(x) > 3 and x[0] == "'" and x[-1] == "'":
                    bs += [ord(c) for c in x[1:-1]]
                else:
                    bs.append(ev(x))
            return bs
        if op == 'DW':
            bs = []
            for x in a:
                v = ev(x); bs += [v & 255, (v >> 8) & 255]
            return bs
        if op == 'DS':
            return [0] * ev(a[0])
        if op in IMPLIED:
            return [IMPLIED[op]]
        if op in ADDR16:
            v = ev(a[0]); return [ADDR16[op], v & 255, (v >> 8) & 255]
        if op in IMM8:
            return [IMM8[op], ev(a[0])]
        if op in ALU:
            return [ALU[op] | REG[a[0].upper()]]
        if op == 'MOV':
            d, s = REG[a[0].upper()], REG[a[1].upper()]
            assert not (d == 6 and s == 6)
            return [0x40 | d << 3 | s]
        if op == 'MVI':
            return [0x06 | REG[a[0].upper()] << 3, ev(a[1])]
        if op == 'INR':
            return [0x04 | REG[a[0].upper()] << 3]
        if op == 'DCR':
            return [0x05 | REG[a[0].upper()] << 3]
        if op == 'LXI':
            v = ev(a[1]); return [0x01 | RP[a[0].upper()] << 4, v & 255, (v >> 8) & 255]
        if op == 'DAD':
            return [0x09 | RP[a[0].upper()] << 4]
        if op == 'INX':
            return [0x03 | RP[a[0].upper()] << 4]
        if op == 'DCX':
            return [0x0B | RP[a[0].upper()] << 4]
        if op == 'PUSH':
            return [0xC5 | RPPSW[a[0].upper()] << 4]
        if op == 'POP':
            return [0xC1 | RPPSW[a[0].upper()] << 4]
        if op == 'LDAX':
            return [{'B': 0x0A, 'D': 0x1A}[a[0].upper()]]
        if op == 'STAX':
            return [{'B': 0x02, 'D': 0x12}[a[0].upper()]]
        if op == 'RST':
            return [0xC7 | ev(a[0]) << 3]
        raise ValueError('unknown op ' + op)
