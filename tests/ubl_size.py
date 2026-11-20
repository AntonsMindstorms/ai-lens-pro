"""Estimate the compiled size of every function in the .ubl.

MicroBlocks refuses functions over 1000 bytes: it replaces them with a stub
that reports "Script too large" when it runs. This follows the byte encoding
of the MicroBlocks compiler (ide/MicroBlocksCompiler.gp): 2 bytes per
instruction word, string literals as 4-byte header + padded UTF-8, plus the
decompiler metadata (library name, spec, local names, function name).

    python3 tests/ubl_size.py            # list functions over 700 bytes
    python3 tests/ubl_size.py --all      # list every function
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from gp_sim import Block, Call, Lit, Var, load_ubl  # noqa: E402

UBL = os.path.join(os.path.dirname(__file__), '..', 'microblocks', 'AI Lens Pro.ubl')
LIMIT = 1000

OPCODES = set('''argOrDefault pop ignoreArgs noop waitUntil waitMicros waitMillis
sendBroadcast recvBroadcast getLastBroadcast millisOp microsOp secsOp millisSince
microsSince timer resetTimer + - * / % & | ^ ~ << >> < <= == != >= > not sum
longMult absoluteValue minimum maximum random hexToInt isType sayIt graphIt
boardType newList at atPut size analogPins digitalPins analogReadOp analogWriteOp
digitalReadOp digitalWriteOp digitalSet digitalClear buttonA buttonB setUserLED
spiSend spiRecv'''.split())


def str_bytes(s):
    n = len(s.encode('utf-8'))
    return 4 + 4 * ((n + 4) // 4)


class Sizer:
    def __init__(self, funcs, globals_):
        self.funcs, self.globals = funcs, set(globals_)

    def size(self, name, params, body, lib, spec):
        self.words = 1                  # initLocals
        self.literals = []
        self.locals = []
        self.params = params
        if not params:                  # broadcast entry for argument-less functions
            self.lit(name)
            self.words += 1
        self.cmds(body)
        self.words += 2                 # return false
        self.words += 1                 # codeEnd
        if self.words % 2:              # literals start on a 32-bit boundary
            self.words += 1
        lit_bytes = sum(str_bytes(s) for s in self.literals)
        names = '\t'.join(sorted(self.locals) + list(params))
        meta = len(lib) + len(spec) + len(names) + len(name) + 4
        return 2 * self.words + lit_bytes + meta

    def lit(self, s):
        self.words += 2
        if s not in self.literals:
            self.literals.append(s)

    def var(self, name, declare=False):
        if declare or (name not in self.globals and name not in self.params):
            if name not in self.locals:
                self.locals.append(name)

    def cmds(self, block):
        for st in block.stmts:
            self.cmd(st)

    def cmd(self, st):
        n, a = st.name, st.args
        if n in ('=', 'local', '+='):
            self.var(a[0].v if isinstance(a[0], Lit) else a[0].name, n == 'local')
            self.expr(a[1])
            self.words += 1
        elif n == 'comment':
            pass
        elif n == 'return':
            if a:
                self.expr(a[0])
            else:
                self.words += 1
            self.words += 1
        elif n == 'if':
            parts = [x for x in a if not (isinstance(x, Var) and x.name == 'else')]
            i = 0
            while i < len(parts):
                if isinstance(parts[i], Block):         # final else
                    self.cmds(parts[i])
                    i += 1
                    continue
                self.expr(parts[i])
                self.words += 2                         # jmpFalse (maybe long)
                self.cmds(parts[i + 1])
                if i + 2 < len(parts):
                    self.words += 2                     # longJmp to end
                i += 2
        elif n == 'repeat':
            self.expr(a[0])
            self.words += 2
            self.cmds(a[1])
            self.words += 2
        elif n == 'repeatUntil':           # jmp to the test, test, jmpFalse back
            self.expr(a[0])
            self.words += 4
            self.cmds(a[1])
        elif n == 'waitUntil':
            self.expr(a[0])
            self.words += 1
        elif n == 'forever':
            self.cmds(a[0])
            self.words += 2
        elif n == 'for':
            self.var(a[0].name, True)
            self.expr(a[1])
            self.words += 2 + 2
            self.cmds(a[2])
            self.words += 4
        elif n == 'exitLoop':
            self.words += 2
        else:
            self.call(n, a, True)

    def call(self, n, a, is_cmd):
        for x in a:
            self.expr(x)
        if n in self.funcs:
            self.words += 2 + (1 if is_cmd else 0)
        elif n in OPCODES:
            self.words += 1
        elif n.startswith('[') and ':' in n:
            prim = n[n.index(':') + 1:-1]
            self.lit(prim)
        else:
            raise ValueError('unknown op %r' % n)

    def expr(self, x):
        if isinstance(x, Lit):
            v = x.v
            if isinstance(v, bool) or v is None:
                self.words += 1
            elif isinstance(v, int):
                self.words += 1 if -64 <= v <= 63 else (2 if abs(v) < 4194304 else 3)
            else:
                self.lit(v)
        elif isinstance(x, Var):
            self.var(x.name)
            self.words += 1
        elif isinstance(x, Block):
            self.cmds(x)
        elif isinstance(x, Call):
            if x.name in ('and', 'or'):
                for y in x.args:
                    self.expr(y)
                self.words += 2 * (len(x.args) - 1)
            elif x.name in self.funcs or x.name in OPCODES or x.name.startswith('['):
                self.call(x.name, x.args, False)
            elif not x.args:                # a plain string in parentheses
                self.lit(x.name)
            else:
                raise ValueError('unknown reporter %r' % x.name)


def main():
    funcs, variables = load_ubl(UBL)
    text = open(UBL, encoding='utf-8').read()
    lib = re.search(r"^module '((?:[^']|'')*)'", text, re.M).group(1)
    specs = {}
    for m in re.finditer(r"^\s*spec '(.)' '((?:[^']|'')*)' '((?:[^']|'')*)'(?: '((?:[^']|'')*)')?", text, re.M):
        specs[m.group(2).replace("''", "'")] = '\t'.join(
            [m.group(1), m.group(3).replace("''", "'"), m.group(4) or ''])
    sizer = Sizer(funcs, variables)
    sizes = sorted(((sizer.size(n, p, b, lib, specs.get(n, n)), n)
                    for n, (p, b) in funcs.items()), reverse=True)
    show_all = '--all' in sys.argv
    for size, name in sizes:
        if show_all or size > 700:
            print('%5d  %s%s' % (size, name, '   <-- TOO LARGE' if size > LIMIT else ''))
    too_big = [n for s, n in sizes if s > LIMIT]
    print('largest: %d bytes (%s); limit %d' % (sizes[0][0], sizes[0][1], LIMIT))
    sys.exit(1 if too_big else 0)


if __name__ == '__main__':
    main()
