"""Minimal 8080/8085 emulator, enough to run the Altaids ROM with the serial
routines trapped (INPUTT/OUTT) so a test script can talk to Tiny BASIC."""

PARITY = [bin(i).count('1') % 2 == 0 for i in range(256)]
# 8080 cycle counts (taken branches use the larger figure where relevant)
CYC = [4, 10, 7, 5, 5, 5, 7, 4, 4, 10, 7, 5, 5, 5, 7, 4,
       4, 10, 7, 5, 5, 5, 7, 4, 4, 10, 7, 5, 5, 5, 7, 4,
       4, 10, 16, 5, 5, 5, 7, 4, 4, 10, 16, 5, 5, 5, 7, 4,
       4, 10, 13, 5, 10, 10, 10, 4, 4, 10, 13, 5, 5, 5, 7, 4] + \
      [5] * 64 + [4] * 64 + \
      [5, 10, 10, 10, 11, 11, 7, 11, 5, 10, 10, 10, 11, 17, 7, 11,
       5, 10, 10, 10, 11, 11, 7, 11, 5, 10, 10, 10, 11, 17, 7, 11,
       5, 10, 10, 18, 11, 11, 7, 11, 5, 5, 10, 4, 11, 17, 7, 11,
       5, 10, 10, 4, 11, 11, 7, 11, 5, 5, 10, 4, 11, 17, 7, 11]
for i in range(0x40, 0x80):
    CYC[i] = 7 if (i & 7) == 6 or (i >> 3 & 7) == 6 else 5
for i in range(0x80, 0xC0):
    CYC[i] = 7 if (i & 7) == 6 else 4
CYC[0x76] = 7


class CPU:
    def __init__(self):
        self.mem = bytearray(65536)
        self.r = [0] * 8  # B C D E H L (M) A
        self.sp = 0
        self.pc = 0
        self.fs = self.fz = self.fac = self.fp = self.fc = 0
        self.cycles = 0
        self.traps = {}
        self.ie = 0

    # flags
    def getf(self):
        return (self.fs << 7) | (self.fz << 6) | (self.fac << 4) | (self.fp << 2) | 2 | self.fc

    def setf(self, v):
        self.fs = v >> 7 & 1; self.fz = v >> 6 & 1; self.fac = v >> 4 & 1
        self.fp = v >> 2 & 1; self.fc = v & 1

    def szp(self, v):
        self.fs = v >> 7; self.fz = int(v == 0); self.fp = int(PARITY[v])

    def hl(self):
        return self.r[4] << 8 | self.r[5]

    def getr(self, i):
        return self.mem[self.hl()] if i == 6 else self.r[i]

    def setr(self, i, v):
        if i == 6:
            self.mem[self.hl()] = v
        else:
            self.r[i] = v

    def rp(self, i):
        if i == 3:
            return self.sp
        return self.r[2 * i] << 8 | self.r[2 * i + 1]

    def setrp(self, i, v):
        v &= 0xFFFF
        if i == 3:
            self.sp = v
        else:
            self.r[2 * i] = v >> 8; self.r[2 * i + 1] = v & 255

    def rd16(self, a):
        return self.mem[a & 0xFFFF] | self.mem[(a + 1) & 0xFFFF] << 8

    def wr16(self, a, v):
        self.mem[a & 0xFFFF] = v & 255; self.mem[(a + 1) & 0xFFFF] = v >> 8 & 255

    def push(self, v):
        self.sp = (self.sp - 2) & 0xFFFF; self.wr16(self.sp, v)

    def pop(self):
        v = self.rd16(self.sp); self.sp = (self.sp + 2) & 0xFFFF; return v

    def imm8(self):
        v = self.mem[self.pc]; self.pc = (self.pc + 1) & 0xFFFF; return v

    def imm16(self):
        v = self.rd16(self.pc); self.pc = (self.pc + 2) & 0xFFFF; return v

    def cond(self, c):
        return [not self.fz, self.fz, not self.fc, self.fc, not self.fp, self.fp, not self.fs, self.fs][c]

    def alu(self, op, v):
        a = self.r[7]
        if op in (0, 1):  # ADD ADC
            c = self.fc if op == 1 else 0
            res = a + v + c
            self.fac = int(((a & 15) + (v & 15) + c) > 15)
            self.fc = int(res > 255); res &= 255; self.szp(res); self.r[7] = res
        elif op in (2, 3, 7):  # SUB SBB CMP
            c = self.fc if op == 3 else 0
            res = a - v - c
            self.fac = int(((a & 15) - (v & 15) - c) >= 0)
            self.fc = int(res < 0); res &= 255; self.szp(res)
            if op != 7:
                self.r[7] = res
        elif op == 4:
            res = a & v; self.fac = int(((a | v) & 8) != 0); self.fc = 0; self.szp(res); self.r[7] = res
        elif op == 5:
            res = a ^ v; self.fac = 0; self.fc = 0; self.szp(res); self.r[7] = res
        elif op == 6:
            res = a | v; self.fac = 0; self.fc = 0; self.szp(res); self.r[7] = res

    def step(self):
        pc = self.pc
        if pc in self.traps:
            self.traps[pc](self)
            return
        op = self.mem[pc]
        self.pc = (pc + 1) & 0xFFFF
        self.cycles += CYC[op]
        if 0x40 <= op < 0x80:
            if op == 0x76:
                raise RuntimeError('HLT at %04X' % pc)
            self.setr(op >> 3 & 7, self.getr(op & 7)); return
        if 0x80 <= op < 0xC0:
            self.alu(op >> 3 & 7, self.getr(op & 7)); return
        hi = op >> 6
        if hi == 0:
            lo = op & 7; rr = op >> 3 & 7
            if lo == 0:
                if op == 0x20:  # RIM
                    self.r[7] = 0x80 | (8 if self.ie else 0)  # SID idle high
                elif op == 0x30:
                    pass  # SIM
                return
            if lo == 1:
                if op & 8:
                    v = self.hl() + self.rp(rr >> 1); self.fc = int(v > 0xFFFF); self.setrp(2, v)
                else:
                    self.setrp(rr >> 1, self.imm16())
                return
            if lo == 2:
                if op == 0x02: self.mem[self.rp(0)] = self.r[7]
                elif op == 0x12: self.mem[self.rp(1)] = self.r[7]
                elif op == 0x0A: self.r[7] = self.mem[self.rp(0)]
                elif op == 0x1A: self.r[7] = self.mem[self.rp(1)]
                elif op == 0x22: self.wr16(self.imm16(), self.hl())
                elif op == 0x2A: self.setrp(2, self.rd16(self.imm16()))
                elif op == 0x32: self.mem[self.imm16()] = self.r[7]
                elif op == 0x3A: self.r[7] = self.mem[self.imm16()]
                return
            if lo == 3:
                self.setrp(rr >> 1, self.rp(rr >> 1) + (-1 if op & 8 else 1)); return
            if lo == 4:
                v = (self.getr(rr) + 1) & 255; self.fac = int((v & 15) == 0); self.szp(v); self.setr(rr, v); return
            if lo == 5:
                v = (self.getr(rr) - 1) & 255; self.fac = int((v & 15) != 15); self.szp(v); self.setr(rr, v); return
            if lo == 6:
                self.setr(rr, self.imm8()); return
            a = self.r[7]
            if op == 0x07: self.fc = a >> 7; self.r[7] = ((a << 1) | self.fc) & 255
            elif op == 0x0F: self.fc = a & 1; self.r[7] = (a >> 1) | (self.fc << 7)
            elif op == 0x17: c = self.fc; self.fc = a >> 7; self.r[7] = ((a << 1) | c) & 255
            elif op == 0x1F: c = self.fc; self.fc = a & 1; self.r[7] = (a >> 1) | (c << 7)
            elif op == 0x27:
                corr = 0; c = self.fc
                if (a & 15) > 9 or self.fac: corr = 6
                if a > 0x99 or self.fc: corr |= 0x60; c = 1
                self.alu(0, corr); self.fc = c
            elif op == 0x2F: self.r[7] = a ^ 255
            elif op == 0x37: self.fc = 1
            elif op == 0x3F: self.fc ^= 1
            return
        # hi == 3
        lo = op & 7; cc = op >> 3 & 7
        if lo == 0:
            if self.cond(cc): self.pc = self.pop(); self.cycles += 6
            return
        if lo == 1:
            if op & 8:
                if op == 0xC9: self.pc = self.pop()
                elif op == 0xE9: self.pc = self.hl()
                elif op == 0xF9: self.sp = self.hl()
            else:
                v = self.pop(); i = cc >> 1
                if i == 3: self.r[7] = v >> 8; self.setf(v & 255)
                else: self.setrp(i, v)
            return
        if lo == 2:
            a = self.imm16()
            if self.cond(cc): self.pc = a
            return
        if lo == 3:
            if op == 0xC3: self.pc = self.imm16()
            elif op == 0xD3: self.imm8()
            elif op == 0xDB: self.imm8(); self.r[7] = 0xFF
            elif op == 0xE3:
                v = self.rd16(self.sp); self.wr16(self.sp, self.hl()); self.setrp(2, v)
            elif op == 0xEB:
                self.r[2], self.r[4] = self.r[4], self.r[2]; self.r[3], self.r[5] = self.r[5], self.r[3]
            elif op == 0xF3: self.ie = 0
            elif op == 0xFB: self.ie = 1
            return
        if lo == 4:
            a = self.imm16()
            if self.cond(cc): self.push(self.pc); self.pc = a; self.cycles += 6
            return
        if lo == 5:
            if op & 8:
                a = self.imm16(); self.push(self.pc); self.pc = a
            else:
                i = cc >> 1
                self.push((self.r[7] << 8 | self.getf()) if i == 3 else self.rp(i))
            return
        if lo == 6:
            self.alu(cc, self.imm8()); return
        self.push(self.pc); self.pc = cc * 8


def load_hex(cpu, path):
    for line in open(path):
        line = line.strip()
        if not line.startswith(':'):
            continue
        b = bytes.fromhex(line[1:])
        n, addr, typ = b[0], b[1] << 8 | b[2], b[3]
        if typ == 0:
            cpu.mem[addr:addr + n] = b[4:4 + n]
