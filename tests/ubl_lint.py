"""
Static checks for a MicroBlocks .ubl library (GP text syntax).

Usage: python3 tests/ubl_lint.py "microblocks/AI Lens Pro.ubl"

Checks: balanced brackets and quotes, spec <-> function consistency,
argument counts of custom block calls, known primitives/operators and
use of undeclared variables. It is not a full GP parser, but it catches
the typical mistakes in hand-written libraries.
"""
import re
import sys

KNOWN_COMMANDS = {
    'if', 'else', 'local', 'for', 'repeat', 'repeatUntil', 'waitUntil',
    'waitMillis', 'return', 'comment', 'atPut', 'sayIt', 'forever',
}
KNOWN_REPORTERS = {
    'at', 'size', 'minimum', 'maximum', 'not', 'and', 'or', 'isType',
    'millisOp', 'argOrDefault', 'newList', 'booleanConstant', 'hexToInt',
    'absoluteValue', 'random', 'callCustomReporter',
}
INFIX = {'+', '-', '*', '/', '%', '==', '!=', '<', '<=', '>', '>=', '&', '|',
         '^', '<<', '>>'}
PRIMITIVES = {
    '[sensors:i2cRead]', '[sensors:i2cWrite]', '[sensors:i2cSetPins]',
    '[sensors:i2cSetClockSpeed]', '[sensors:i2cExists]',
    '[data:makeList]', '[data:addLast]', '[data:join]', '[data:convertType]',
    '[data:newByteArray]', '[data:asByteArray]', '[data:copyFromTo]',
    '[data:find]', '[data:split]', '[data:unicodeAt]', '[data:unicodeString]',
}
LITERALS = {'true', 'false', 'nil'}

TOKEN = re.compile(r"""
    (?P<str>'(?:[^']|'')*')
  | (?P<num>-?\d+)
  | (?P<op>==|!=|<=|>=|<<|>>|\+=|[-+*/%<>&|^=])
  | (?P<punct>[(){}])
  | (?P<word>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<nl>\n)
  | (?P<ws>[ \t]+)
""", re.X)


def tokenize(text):
    toks, pos, line = [], 0, 1
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m:
            raise SyntaxError('line %d: cannot parse %r' % (line, text[pos:pos + 20]))
        kind = m.lastgroup
        val = m.group(kind)
        if kind == 'nl':
            toks.append(('nl', '\n', line))
            line += 1
        elif kind != 'ws':
            toks.append((kind, val, line))
            line += val.count('\n') if kind == 'str' else 0
        pos = m.end()
    return toks


def unquote(s):
    return s[1:-1].replace("''", "'")


def main(path):
    text = open(path, encoding='utf-8').read()
    errors = []
    toks = tokenize(text)

    # ---- header: variables, choices, specs
    header, _, body = text.partition('\nto ')
    body = 'to ' + body
    globals_ = set()
    choices = set()
    specs = {}
    statements, cur = [], []
    for k, v, _ in tokenize(header):
        if k == 'nl':
            if cur:
                statements.append(cur)
            cur = []
        else:
            cur.append(v)
    statements.append(cur)
    for t in statements:
        if not t:
            continue
        if t[0] == 'variables':
            globals_.update(unquote(x) if x.startswith("'") else x for x in t[1:])
        elif t[0] == 'choices':
            choices.add(t[1])
        elif t[0] == 'spec':
            name, label = unquote(t[2]), unquote(t[3])
            types = unquote(t[4]).split() if len(t) > 4 else []
            slots = label.split().count('_')
            if slots != len(types):
                errors.append('spec %r: %d slots but %d types' % (name, slots, len(types)))
            for ty in types:
                if '.' in ty and ty.split('.', 1)[1] not in choices and not ty.endswith('Menu'):
                    errors.append('spec %r: unknown menu %r' % (name, ty))
            optional = len(label.split(':')[0].split()) and label.split(':', 1)[0].count('_')
            specs[name] = (slots, optional, t[1])

    # ---- functions
    funcs = {}
    for m in re.finditer(r"^to ('(?:[^']|'')*'|\S+)((?: \w+)*) \{", body, re.M):
        name = unquote(m.group(1)) if m.group(1).startswith("'") else m.group(1)
        funcs[name] = m.group(2).split()
    for name, (slots, _, _) in specs.items():
        if name.startswith('['):
            continue
        if name not in funcs:
            errors.append('spec without function: %r' % name)
        elif len(funcs[name]) != slots:
            errors.append('%r: spec has %d slots, function has %d params'
                          % (name, slots, len(funcs[name])))
    for name in funcs:
        if name not in specs:
            errors.append('function without spec: %r' % name)

    # ---- bracket balance
    depth = {'(': 0, '{': 0}
    for kind, val, line in toks:
        if val in '({' and kind == 'punct':
            depth[val] += 1
        elif val in ')}' and kind == 'punct':
            depth['(' if val == ')' else '{'] -= 1
            if min(depth.values()) < 0:
                errors.append('line %d: unbalanced %s' % (line, val))
                depth = {'(': 0, '{': 0}
    if any(depth.values()):
        errors.append('unbalanced brackets at end of file: %r' % depth)

    # ---- per function: calls, arg counts, variables
    btoks = tokenize(body)
    line_offset = header.count('\n') + 1
    i = 0
    while i < len(btoks):
        kind, val, line = btoks[i]
        if not (kind == 'word' and val == 'to' and (i == 0 or btoks[i - 1][0] == 'nl')):
            i += 1
            continue
        fname = unquote(btoks[i + 1][1]) if btoks[i + 1][0] == 'str' else btoks[i + 1][1]
        params = funcs.get(fname, [])
        known_vars = set(params) | globals_ | LITERALS
        # collect function body tokens
        j = i + 1
        while btoks[j][1] != '{':
            j += 1
        start, d = j, 0
        while True:
            if btoks[j][1] == '{' and btoks[j][0] == 'punct':
                d += 1
            elif btoks[j][1] == '}' and btoks[j][0] == 'punct':
                d -= 1
                if d == 0:
                    break
            j += 1
        ftoks = btoks[start + 1:j]
        i = j + 1

        def where(ln):
            return '%s (line %d)' % (fname, ln + line_offset - 1)

        # locals and loop variables
        for k, (tk, tv, tl) in enumerate(ftoks):
            if tv == 'local' and ftoks[k + 1][0] == 'str':
                known_vars.add(unquote(ftoks[k + 1][1]))
            if tv == 'for' and ftoks[k + 1][0] == 'word':
                known_vars.add(ftoks[k + 1][1])

        # walk expressions
        for k, (tk, tv, tl) in enumerate(ftoks):
            prev = ftoks[k - 1] if k else ('nl', '\n', 0)
            stmt_start = prev[0] == 'nl' or prev[1] in ('{', '}')
            in_paren = prev[1] == '(' and prev[0] == 'punct'
            if tk == 'str' and (stmt_start or in_paren):
                callee = unquote(tv)
                if callee.startswith('['):
                    if callee not in PRIMITIVES:
                        errors.append('%s: unknown primitive %s' % (where(tl), callee))
                elif callee in funcs:
                    # count arguments until end of expression / line
                    n, d2, m = 0, 0, k + 1
                    while m < len(ftoks):
                        t2k, t2v, _ = ftoks[m]
                        if d2 == 0 and (t2k == 'nl' or (t2k == 'punct' and t2v in ')}')):
                            break
                        if t2k == 'punct' and t2v in '({':
                            if d2 == 0:
                                n += 1
                            d2 += 1
                        elif t2k == 'punct' and t2v in ')}':
                            d2 -= 1
                        elif d2 == 0:
                            n += 1
                        m += 1
                    want = len(funcs[callee])
                    if n != want and not (specs.get(callee, (0, 0))[1] <= n <= want):
                        errors.append('%s: %r called with %d args, expects %d'
                                      % (where(tl), callee, n, want))
                elif stmt_start or in_paren:
                    if in_paren and k + 1 < len(ftoks) and ftoks[k + 1][1] == ')':
                        continue  # a string in parentheses is just a value
                    errors.append('%s: call to unknown block %r' % (where(tl), callee))
            elif tk == 'word':
                nxt = ftoks[k + 1] if k + 1 < len(ftoks) else ('nl', '', 0)
                if stmt_start:
                    if tv in KNOWN_COMMANDS or tv in funcs:
                        continue
                    if nxt[1] in ('=', '+='):
                        if tv not in known_vars:
                            errors.append('%s: assignment to undeclared %r' % (where(tl), tv))
                        continue
                    errors.append('%s: unknown command %r' % (where(tl), tv))
                elif in_paren and nxt[0] != 'op':
                    if tv not in KNOWN_REPORTERS and tv not in known_vars:
                        errors.append('%s: unknown reporter %r' % (where(tl), tv))
                elif prev[1] == 'for':
                    continue
                elif tv not in known_vars and tv not in KNOWN_COMMANDS:
                    errors.append('%s: undeclared variable %r' % (where(tl), tv))
            elif tk == 'op' and tv not in INFIX and tv not in ('=', '+='):
                errors.append('%s: unknown operator %r' % (where(tl), tv))

    print('%s: %d functions, %d specs' % (path, len(funcs), len(specs)))
    for e in errors:
        print('ERROR', e)
    print('OK' if not errors else '%d problems' % len(errors))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'microblocks/AI Lens Pro.ubl'))
