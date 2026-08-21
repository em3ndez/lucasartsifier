"""⛔ RED: `(and a b)` in a VALUE position must yield `b`, not a boolean.

THE DEFECT, found in play 2026-08-21. LB2's script 0 carries SCI's standard "pass the object
if it is one, else 0" idiom:

    (param1 setHeading: temp0 (and (IsObject temp3) temp3))

`setHeading:`'s third argument is the CUE TARGET. `scicompile` compiles the value-position
`and` to a BOOLEAN, so the cue target became `1`, the turn completed, and the cue never
reached the caller -- every LB2 conversation stopped dead after its first spoken line. In
speech-only mode that is total silence, which is how the user found it.

Nothing in the suite could see it. `measure_emitted_bytes` freezes the SOURCE the patcher
writes and never what the compiler makes of it, and the emitted source was byte-perfect. The
defect was one opcode downstream.

WHY THIS TEST IS AT THE BYTECODE AND NOT AT A GAME. The property belongs to the COMPILER, not
to LB2 -- KQ6's `rm220` carries the same idiom (`myHeadingCode`, dead code there only because
nothing installs it) and `Actor::setHeading` carries it in the class script every game shares.
A test pinned to an LB2 symptom would go green the moment LB2 stopped shipping script 0 while
the compiler stayed broken. So this compiles the smallest source that can express the question
and reads the opcodes.

THE SHAPE, measured on the buggy compiler:

    8f 01   lsp param1        ; (> param1 0)
    35 00   ldi 0
    1e      gt?
    31 06   bnt -> ret        ; false: acc = 0                     CORRECT
    87 02   lap param2        ; acc = param2
    31 02   bnt -> ret        ; false: acc = param2 = 0            CORRECT
    35 01   ldi 1             ; all true: DISCARDS param2          ⛔ THE BUG
    48      ret

`bnt` tests the accumulator and leaves it alone, so on the all-true path the accumulator
ALREADY holds `param2`. The cure is to stop emitting that final load.
"""

import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
SCICOMPILE = os.path.join(_ROOT, "tools", "scicompile", "build", "scicompile")
TEMPLATE = os.path.join(_ROOT, "vendor", "SCICompanion", "SCICompanion", "Files",
                        "TemplateGame", "SCI0")

PASS, FAIL = [], []

# The smallest source that asks the question, plus a control in the position where a boolean
# IS the right answer -- so a "fix" that changed both would be caught.
SOURCE = """;;; Sierra Script 1.0 - (do not remove this comment)
(script# 990)
(include sci.sh)

(public
\tvalueAnd 0
\tcondAnd 1
\tvalueOr 2
)

(procedure (valueAnd param1 param2)
\t(return (and (> param1 0) param2))
)

(procedure (condAnd param1 param2)
\t(if (and (> param1 0) param2)
\t\t(return 42)
\t)
\t(return 0)
)

(procedure (valueOr param1 param2)
\t(return (or (> param1 0) param2))
)
"""

LDI_B, LDI_W, BNT_B, BNT_W, RET = 0x35, 0x34, 0x31, 0x30, 0x48
# operand loads: lap/lsp (param), lal/lsl (local), lat/lst (temp), lag/lsg (global)
LOADS = set(range(0x80, 0xC0))   # lag/lal/lat/lap and their push-to-stack twins


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("" if cond else ("  -- " + detail if detail else ""))))


def _u16(d, o):
    return d[o] | (d[o + 1] << 8)


def _exports(scr):
    """SCI0 script blocks: (type, size) headers; block type 7 is the export table."""
    i = 0
    while i + 4 <= len(scr):
        btype, size = _u16(scr, i), _u16(scr, i + 2)
        if btype == 0 or size < 4:
            break
        if btype == 7:
            n = _u16(scr, i + 4)
            return [_u16(scr, i + 6 + k * 2) for k in range(n)]
        i += size
    return []


# ⛔ A DISASSEMBLER THAT GUESSES IS WORSE THAN NONE. Two earlier cuts of this walker inferred
# the operand width from bit 0 over a made-up opcode range and slid out of alignment -- the
# first read `8f 01` (lsp param1) as a word, the second put `bt` (raw 0x2E/0x2F) in the
# operand-less bucket and mis-walked the `or` case. Both still "found" the bug, by luck, out of
# a stream of invented opcodes. So: the real encoding, and anything outside it is REPORTED.
#
# An SCI opcode byte is `(opnum << 1) | byteflag`; byteflag SET means a one-byte operand. This
# table is by OPNUM and covers only what these three procedures can emit.
_OPERANDS = {                                          # opnum -> number of SIZED operands
    **{n: 0 for n in range(0x00, 0x17)},               # bnot..ule?  (arithmetic, comparison)
    0x17: 1, 0x18: 1, 0x19: 1, 0x1a: 1,                # bt, bnt, jmp, ldi
    0x1b: 0, 0x1c: 1, 0x1d: 0, 0x1e: 0, 0x1f: 1,       # push, pushi, toss, dup, link
    0x24: 0,                                           # ret
}


def _opsize(op):
    """Operand BYTES for `op`, or None if this walker does not know it."""
    if op >= 0x80:                                     # the variable-access block
        return 1 if (op & 1) else 2
    n = _OPERANDS.get(op >> 1)
    if n is None:
        return None
    return n * (1 if (op & 1) else 2)


def _walk(scr, start):
    """[(offset, opcode, arg)] from `start` to the first `ret`, or None on an unknown opcode."""
    out, i = [], start
    while i < len(scr):
        op = scr[i]
        n = _opsize(op)
        if n is None:
            return None
        arg = scr[i + 1] if n == 1 else (_u16(scr, i + 1) if n == 2 else None)
        out.append((i, op, arg))
        i += 1 + n
        if op == RET:
            break
    return out


def _compile(tmp):
    """Compile SOURCE in a scratch copy of the template game; return the script bytes."""
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(TEMPLATE, tmp)
    src = os.path.join(tmp, "src", "andtest.sc")
    open(src, "w").write(SOURCE)
    out = os.path.join(tmp, "out.bin")
    p = subprocess.run([SCICOMPILE, tmp, src, out], capture_output=True, text=True, timeout=600)
    if not os.path.exists(out):
        return None, (p.stdout + p.stderr)[-800:]
    return open(out, "rb").read(), ""


def run():
    print("\n-- `(and a b)` as a VALUE must yield b (scicompile) --")
    if not os.path.exists(SCICOMPILE) or not os.path.isdir(TEMPLATE):
        # ⛔ NOT A PASS. Say so and fail: a compiler test that silently skips is how a broken
        # compiler ships.
        check("the compiler and its template game are present",
              False, "need %s and %s -- build with: cmake -S tools/scicompile -B "
                     "tools/scicompile/build && cmake --build tools/scicompile/build -j"
                     % (SCICOMPILE, TEMPLATE))
        return not FAIL

    scr, err = _compile("/tmp/sc_value_and")
    check("the minimal script compiles", scr is not None, err)
    if scr is None:
        return not FAIL
    exports = _exports(scr)
    check("its three procedures are exported (so the walk below reads real code)",
          len(exports) >= 3, "exports=%r" % (exports,))
    if len(exports) < 3:
        return not FAIL

    for name, idx, value_position in (("valueAnd", 0, True), ("condAnd", 1, False),
                                      ("valueOr", 2, True)):
        ops = _walk(scr, exports[idx])
        check("%s: opcodes were read (no unknown opcode -- the walk is aligned)" % name,
              ops is not None and len(ops) >= 3, repr(ops))
        if ops is None:
            continue
        # the LAST operand load in the procedure -- after it, a value-position `and`/`or` must
        # reach `ret` through branches only, because the accumulator already holds the answer
        loads = [k for k, (_o, op, _a) in enumerate(ops) if op in LOADS]
        if not loads:
            check("%s: an operand load was found" % name, False, repr(ops))
            continue
        after = ops[loads[-1] + 1:]
        clobber = [(hex(o), hex(op), a) for (o, op, a) in after if op in (LDI_B, LDI_W)]
        if value_position:
            check("%s: the last operand survives to the return (no `ldi` after it)" % name,
                  not clobber,
                  "a value-position and/or must yield its last operand; found %r after the "
                  "final operand load. Full walk: %r"
                  % (clobber, [(hex(o), hex(op), a) for (o, op, a) in ops]))
        else:
            # the control: in a condition the compiler already branches straight to the arms,
            # and this must keep saying so -- otherwise the check above proves nothing
            check("%s (control): a truth-position and still compiles to branches" % name,
                  any(op in (BNT_B, BNT_W) for (_o, op, _a) in ops),
                  repr([(hex(o), hex(op), a) for (o, op, a) in ops]))
    return not FAIL


if __name__ == "__main__":
    ok = run()
    print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
    sys.exit(0 if ok else 1)
