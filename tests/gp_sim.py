"""
A tiny interpreter for the subset of MicroBlocks GP text syntax used by
"AI Lens Pro.ubl", so the library logic can be tested on a desktop
against a simulated AI Lens Pro. It is a test tool, not a MicroBlocks VM:
integers, strings, booleans, lists and byte arrays, and the primitives
listed in PRIMS below.
"""
import re

_TOKEN = re.compile(r"""
    (?P<str>'(?:[^']|'')*')
  | (?P<num>-?\d+(?![A-Za-z_]))
  | (?P<op>==|!=|<=|>=|<<|>>|\+=|[-+*/%<>&|^=])
  | (?P<punct>[(){}])
  | (?P<word>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<nl>\n)
  | (?P<ws>[ \t]+)
""", re.X)

INFIX = {'+', '-', '*', '/', '%', '==', '!=', '<', '<=', '>', '>=', '&', '|',
         '^', '<<', '>>'}


class Lit:
    def __init__(self, v):
        self.v = v


class Var:
    def __init__(self, name):
        self.name = name


class Call:
    def __init__(self, name, args):
        self.name, self.args = name, args


class Block:
    def __init__(self, stmts):
        self.stmts = stmts


class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class GPError(Exception):
    pass


def tokenize(text):
    out, pos = [], 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise SyntaxError('cannot parse %r' % text[pos:pos + 30])
        k = m.lastgroup
        if k != 'ws':
            out.append((k, m.group(k)))
        pos = m.end()
    return out


class Parser:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self, o=0):
        return self.t[self.i + o] if self.i + o < len(self.t) else ('eof', '')

    def take(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def skip_nl(self):
        while self.peek()[0] == 'nl':
            self.i += 1

    def block(self):
        assert self.take()[1] == '{'
        stmts = []
        while True:
            self.skip_nl()
            if self.peek()[1] == '}':
                self.take()
                return Block(stmts)
            stmts.append(self.statement())

    def atom(self):
        k, v = self.peek()
        if k == 'punct' and v == '(':
            return self.paren()
        if k == 'punct' and v == '{':
            return self.block()
        self.take()
        if k == 'str':
            return Lit(v[1:-1].replace("''", "'"))
        if k == 'num':
            return Lit(int(v))
        if k == 'word':
            if v in ('true', 'false'):
                return Lit(v == 'true')
            if v == 'nil':
                return Lit(None)
            return Var(v)
        if k == 'op' and v == '-':  # unlikely
            return Lit('-')
        raise SyntaxError('unexpected %r' % v)

    def paren(self):
        assert self.take()[1] == '('
        items = []
        while self.peek()[1] != ')':
            if self.peek()[0] == 'op':
                items.append(('op', self.take()[1]))
            else:
                items.append(self.atom())
        self.take()
        if len(items) == 3 and isinstance(items[1], tuple):
            return Call(items[1][1], [items[0], items[2]])
        if isinstance(items[0], tuple):  # prefix operator, e.g. (- x)
            return Call(items[0][1], items[1:])
        head = items[0]
        if isinstance(head, Lit) and len(items) == 1:
            # ('name') calls a reporter without arguments; unknown names stay strings
            return Call(head.v, []) if isinstance(head.v, str) else head
        if isinstance(head, Lit):
            return Call(head.v, items[1:])
        if isinstance(head, Var):
            return Call(head.name, items[1:])
        raise SyntaxError('bad expression')

    def statement(self):
        k, v = self.peek()
        if k == 'word' and self.peek(1)[1] in ('=', '+='):
            self.take()
            op = self.take()[1]
            return Call('=' if op == '=' else '+=', [Lit(v), self.atom()])
        self.take()
        name = v[1:-1].replace("''", "'") if k == 'str' else v
        args = []
        while self.peek()[0] not in ('nl', 'eof') and self.peek()[1] != '}':
            args.append(self.atom())
        return Call(name, args)


def load_ubl(path):
    text = open(path, encoding='utf-8').read()
    funcs = {}
    for m in re.finditer(r"^to ('(?:[^']|'')*'|\S+)((?: \w+)*) \{", text, re.M):
        name = m.group(1)
        if name.startswith("'"):
            name = name[1:-1].replace("''", "'")
        start = m.end() - 1
        p = Parser(tokenize(text[start:]))
        funcs[name] = (m.group(2).split(), p.block())
    variables = re.search(r'^variables (.*)$', text, re.M).group(1).split()
    return funcs, variables


class Interp:
    def __init__(self, path, i2c):
        self.funcs, names = load_ubl(path)
        self.globals = {n: 0 for n in names}
        self.i2c = i2c
        self.clock = 0
        self.said = []
        self.steps = 0

    # -------------------------------------------------------------- running
    def call(self, name, *args):
        return self.invoke(name, list(args))

    def invoke(self, name, args):
        params, body = self.funcs[name]
        frame = {'__args': args}
        for i, p in enumerate(params):
            frame[p] = args[i] if i < len(args) else 0
        try:
            self.run(body, frame)
        except ReturnSignal as r:
            return r.value
        return None

    def run(self, block, frame):
        for st in block.stmts:
            self.exec(st, frame)

    def lookup(self, name, frame):
        if name in frame:
            return frame[name]
        if name in self.globals:
            return self.globals[name]
        raise GPError('unknown variable ' + name)

    def assign(self, name, value, frame):
        if name in frame:
            frame[name] = value
        elif name in self.globals:
            self.globals[name] = value
        else:
            raise GPError('assignment to unknown variable ' + name)

    def tick(self):
        self.steps += 1
        if self.steps > 2000000:
            raise GPError('too many steps (infinite loop?)')
        self.clock += 0  # time only advances in waitMillis / i2c

    def exec(self, st, frame):
        self.tick()
        n, a = st.name, st.args
        ev = lambda x: self.eval(x, frame)  # noqa: E731
        if n == '=':
            self.assign(a[0].v, ev(a[1]), frame)
        elif n == '+=':
            self.assign(a[0].v, self.lookup(a[0].v, frame) + ev(a[1]), frame)
        elif n == 'local':
            frame[a[0].v] = ev(a[1])
        elif n == 'comment':
            pass
        elif n == 'if':
            k = 0
            while k < len(a):
                if isinstance(a[k], Var) and a[k].name == 'else':
                    self.run(a[k + 1], frame)
                    return
                if k + 1 < len(a):
                    if self.truth(ev(a[k])):
                        self.run(a[k + 1], frame)
                        return
                    k += 2
                else:  # else block
                    self.run(a[k], frame)
                    return
        elif n == 'else':
            raise GPError('stray else')
        elif n == 'for':
            var, coll, body = a[0].name, ev(a[1]), a[2]
            items = range(1, coll + 1) if isinstance(coll, int) else list(coll)
            for it in items:
                frame[var] = it
                self.run(body, frame)
        elif n == 'repeat':
            for _ in range(ev(a[0])):
                self.run(a[1], frame)
        elif n == 'repeatUntil':
            while not self.truth(ev(a[0])):
                self.tick()
                self.run(a[1], frame)
        elif n == 'waitUntil':
            while not self.truth(ev(a[0])):
                self.tick()
                self.clock += 1
        elif n == 'waitMillis':
            self.clock += ev(a[0])
        elif n == 'return':
            raise ReturnSignal(ev(a[0]) if a else None)
        elif n == 'sayIt':
            self.said.append(ev(a[0]))
        elif n == 'atPut':
            i, coll, v = ev(a[0]), ev(a[1]), ev(a[2])
            if not 1 <= i <= len(coll):
                raise GPError('atPut index %r out of range' % i)
            coll[i - 1] = v
        else:
            self.eval(st, frame)

    @staticmethod
    def truth(v):
        if not isinstance(v, bool):
            raise GPError('condition is not a boolean: %r' % (v,))
        return v

    def eval(self, x, frame):
        if isinstance(x, Lit):
            return x.v
        if isinstance(x, Var):
            return self.lookup(x.name, frame)
        if isinstance(x, Block):
            return x
        n = x.name
        # Evaluate every operand (no short-circuit), so the library must not
        # depend on short-circuit evaluation to stay safe.
        if n == 'and':
            return all([self.truth(self.eval(e, frame)) for e in x.args])
        if n == 'or':
            return any([self.truth(self.eval(e, frame)) for e in x.args])
        args = [self.eval(e, frame) for e in x.args]
        if n in INFIX:
            return self.infix(n, args)
        if n == 'argOrDefault':
            given = frame['__args']
            return given[args[0] - 1] if args[0] <= len(given) else args[1]
        if n in self.funcs:
            return self.invoke(n, args)
        f = getattr(self, 'p_' + re.sub(r'\W', '_', n), None)
        if f is None:
            if not args and not n.startswith('['):
                return n  # a plain string in parentheses
            raise GPError('unknown block ' + n)
        return f(*args)

    @staticmethod
    def infix(op, a):
        x, y = a
        if op in ('==', '!='):
            same = (type(x) is type(y) or (isinstance(x, int) and isinstance(y, int)
                    and not isinstance(x, bool) and not isinstance(y, bool))) and x == y
            return same if op == '==' else not same
        for v in (x, y):
            if not isinstance(v, int) or isinstance(v, bool):
                raise GPError('%s needs numbers, got %r' % (op, (x, y)))
        if op == '+':
            return x + y
        if op == '-':
            return x - y
        if op == '*':
            return x * y
        if op == '/':
            return int(x / y)
        if op == '%':
            return x % y
        if op == '<':
            return x < y
        if op == '<=':
            return x <= y
        if op == '>':
            return x > y
        if op == '>=':
            return x >= y
        if op == '&':
            return x & y
        if op == '|':
            return x | y
        if op == '^':
            return x ^ y
        if op == '<<':
            return x << y
        if op == '>>':
            return x >> y

    # ---------------------------------------------------------- primitives
    def p_at(self, i, coll):
        if isinstance(i, bool) or not isinstance(i, int) or not 1 <= i <= len(coll):
            raise GPError('at: index %r out of range (size %d)' % (i, len(coll)))
        v = coll[i - 1]
        return v

    def p_size(self, coll):
        if isinstance(coll, (int, bool)):
            raise GPError('size of a number')
        return len(coll)

    def p_minimum(self, *a):
        return min(a)

    def p_maximum(self, *a):
        return max(a)

    def p_not(self, v):
        return not self.truth(v)

    def p_millisOp(self):
        self.clock += 1
        return self.clock

    def p_newList(self, n, v=0):
        return [v] * n

    def p_isType(self, v, t):
        return {'number': isinstance(v, int) and not isinstance(v, bool),
                'string': isinstance(v, str), 'list': isinstance(v, list),
                'byte array': isinstance(v, bytearray),
                'boolean': isinstance(v, bool)}[t]

    def p__data_makeList_(self, *a):
        return list(a)

    def p__data_addLast_(self, item, coll):
        coll.append(item)

    def p__data_join_(self, *a):
        if isinstance(a[0], bytearray):
            out = bytearray()
            for x in a:
                out += x.encode() if isinstance(x, str) else x
            return out
        if isinstance(a[0], list):
            return [i for x in a for i in x]
        return ''.join(str(int(x)) if isinstance(x, bool) else str(x) for x in a)

    def p__data_convertType_(self, v, t):
        if t == 'string':
            return bytes(v).decode('utf-8') if isinstance(v, bytearray) else str(v)
        if t == 'byte array':
            return bytearray(v.encode('utf-8')) if isinstance(v, str) else bytearray(v)
        raise GPError('convertType ' + t)

    def p__data_newByteArray_(self, n):
        return bytearray(n)

    def p__data_asByteArray_(self, v):
        return bytearray(v)

    def p__data_copyFromTo_(self, v, a, b=None):
        b = len(v) if b is None else min(b, len(v))
        return v[a - 1:b]

    def p__data_split_(self, s, delim, convert_numbers=False):
        parts = s.split(delim)
        if convert_numbers:
            parts = [int(x) if x.lstrip('-').isdigit() else x for x in parts]
        return parts

    def p__data_find_(self, x, coll):
        for i, v in enumerate(coll):
            if type(v) is type(x) and v == x:
                return i + 1
        return -1

    def p__data_unicodeAt_(self, i, s):
        return ord(s[i - 1])

    def p__data_unicodeString_(self, c):
        return chr(c)

    def p__sensors_i2cSetPins_(self, sda, scl):
        self.pins = (sda, scl)

    def p__sensors_i2cSetClockSpeed_(self, hz):
        self.freq = hz

    def p__sensors_i2cWrite_(self, addr, data, stop=True):
        try:
            self.i2c.writeto(addr, bytes(data))
        except OSError:
            pass
        self.clock += 1

    def p__sensors_i2cRead_(self, addr, buf):
        n = min(len(buf), 32)
        try:
            data = self.i2c.readfrom(addr, n)
        except OSError:
            data = bytes([255] * n)
        for i in range(n):
            buf[i] = data[i]
        self.clock += 1
        return n
