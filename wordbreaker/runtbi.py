"""Run a .TBI on the real Altaids ROM inside the emulator.
Serial I/O is trapped at INPUTT/OUTT. Output time is charged at 2400 baud
(10 bits per char) so timings reflect the real machine."""
import os, sys
from emu8085 import CPU, load_hex

ROM = os.environ.get('ALTAIDS_ROM', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Software', 'altaids.hex'))
INPUTT, OUTT, BASIC = 0x1613, 0x164D, 0x0185
CLOCK = 2457600
CHAR_CYC = CLOCK * 10 // 2400


class Machine:
    def __init__(self, tbi=None):
        self.cpu = CPU()
        load_hex(self.cpu, ROM)
        self.out = bytearray()
        self.inp = bytearray()
        self.waiting = False
        self.cpu.traps[INPUTT] = self._in
        self.cpu.traps[OUTT] = self._out
        self.cpu.pc = BASIC
        self.run_until_input()
        if tbi:
            self.load(open(tbi, 'rb').read())

    def load(self, img):
        # same as XLOAD: copy to TXTBGN, TXTUNF = after last non-FF byte
        m = self.cpu.mem
        m[0x201A:0x201A + len(img)] = img
        end = 0x201A + len(img) - 1
        while m[end] == 0xFF:
            end -= 1
        m[0x2018] = (end + 1) & 255; m[0x2019] = (end + 1) >> 8

    def _out(self, c):
        self.out.append(c.r[7])
        c.cycles += CHAR_CYC
        c.pc = c.pop()

    def _in(self, c):
        if not self.inp:
            self.waiting = True
            return
        ch = self.inp.pop(0)
        c.r[7] = ch
        c.cycles += CHAR_CYC
        c.pc = c.pop()

    def run_until_input(self, limit=400_000_000):
        self.waiting = False
        start = self.cpu.cycles
        while not self.waiting:
            self.cpu.step()
            if self.cpu.cycles - start > limit:
                raise RuntimeError('timeout')
        return (self.cpu.cycles - start) / CLOCK

    def send(self, s):
        self.inp += s.encode()
        return self.run_until_input()

    def take(self):
        o = self.out.decode('latin-1'); self.out.clear(); return o


# usage: python runtbi.py WORDBREAKER.TBI "RUN\r" "\r" "crane\r"
if __name__ == '__main__':
    m = Machine(sys.argv[1])
    print(m.take())
    for s in sys.argv[2:]:
        t = m.send(s.replace('\\r', '\r'))
        print(m.take().replace('\x1b', '<E>'), f'   [{t:.2f}s]')
