import random, time
from build import build
from runtbi import Machine, CLOCK
info = build(verbose=True)
words = sorted(info['words']); answers = sorted(info['answers'])
m = Machine('WORDBREAKER.TBI'); c = m.cpu
def call(addr, hl):
    c.sp = 0x3F80; c.push(0xFFFF); c.r[4] = hl >> 8; c.r[5] = hl & 255; c.pc = addr; st = c.cycles
    while c.pc != 0xFFFF: c.step()
    return c.hl(), (c.cycles - st) / CLOCK
assert call(8226, 0)[0] == len(answers) and call(8235, 0)[0] == len(words)
G = c.rd16(0x2018)
random.seed(1)
worst = 0
# every word must be accepted
t0=time.time()
for w in words:
    c.mem[G:G+6] = w.upper().encode() + b'\0'
    v, t = call(8232, G); worst = max(worst, t)
    assert v == 1, w
print('all words accepted, worst check %.2fs' % worst, time.time()-t0)
# random non-words rejected
ws = set(words); n = 0
while n < 2000:
    w = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(5))
    if random.random() < .5:  # near misses
        b = random.choice(words); i = random.randrange(5); w = b[:i] + random.choice('abcdefghijklmnopqrstuvwxyz') + b[i+1:]
    if w in ws: continue
    c.mem[G:G+6] = w.encode() + b'\0'
    assert call(8232, G)[0] == 0, w
    n += 1
print('2000 non-words rejected')
# PICK: every secret
worst = 0
for r in range(1, len(answers) + 1):
    v, t = call(8229, r); worst = max(worst, t)
    got = bytes(c.mem[0x3E40:0x3E45]).decode().lower()
    assert v == 1 and got == answers[r - 1], (r, got, answers[r-1])
print('all secrets unpack correctly, worst pick %.2fs' % worst)
# MARK vs reference scoring
def ref(sec, g):
    mk = [0]*5; used = [0]*5
    for i in range(5):
        if g[i] == sec[i]: mk[i] = 2; used[i] = 1
    for i in range(5):
        if mk[i] == 0:
            for j in range(5):
                if not used[j] and sec[j] == g[i]: mk[i] = 1; used[j] = 1; break
    return mk
c.mem[0x3E06] = 0  # C=0 text mode, easy to parse
for trial in range(3000):
    sec = random.choice(answers).upper()
    g = random.choice(words).upper() if trial % 3 else ''.join(random.choice(sec + 'EAS') for _ in range(5))
    for i in range(5):
        a = 0x3E00 - 2 * (i + 1); c.mem[a] = ord(sec[i]); c.mem[a+1] = 0
    for k in range(26):
        a = 0x3E00 - 2 * (21 + k); c.mem[a] = 0; c.mem[a+1] = 0
    c.mem[G:G+6] = g.lower().encode() + b'\0'
    v, t = call(8238, G)
    out = bytes(c.mem[G+8:G+8+200]).split(b'\0')[0].decode()
    mk = ref(sec, g)
    exp = ''.join('[%s]' % ch if x == 2 else '(%s)' % ch if x == 1 else ' %s ' % ch.lower() for ch, x in zip(g, mk))
    assert out.startswith(exp + '   '), (sec, g, out, exp)
    assert v == mk.count(2)
    st = {}
    for ch, x in zip(g, mk): st[ch] = max(st.get(ch, 0), x + 1)
    alpha = ''.join(chr(65+k) if st.get(chr(65+k), 0) == 0 else '.' if st[chr(65+k)] == 1 else chr(97+k) for k in range(26))
    assert out[len(exp)+3:] == alpha, (sec, g, out, alpha)
print('3000 random markings match the reference rules (incl. repeated letters)')
