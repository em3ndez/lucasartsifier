"""Find where the COMPILER changed the meaning of what we shipped.

⭐ THE GATE THAT WAS MISSING. `measure_emitted_bytes` freezes the SOURCE the patcher emits and
never looks at what `scicompile` then makes of it. LB2 2026-08-21: our recompiled script 0
turned

    (param1 setHeading: temp0 (and (IsObject temp3) temp3))

into `(and (IsObject temp3) temp3 1)`. In a CONDITION that trailing 1 is nothing -- only
truthiness is read. As a VALUE it is everything: the idiom yields THE OBJECT, the compiled form
yields 1, and `setHeading:`'s third argument is the cue target. The turn completed, the cue never
reached the caller, and every LB2 conversation stopped dead after its first spoken line. Nothing
in the suite could see it: the emitted source was byte-perfect, and the defect was one opcode
downstream.

USE: decompile a game dir that has the patch installed, then

    python3 tools/check_roundtrip.py <round-trip-src-dir> <title> [<title> ...]

Reports every `and`/`or` that gained a trailing literal in a position where its VALUE is read.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from sexpr import read_all, Sym                                          # noqa: E402

# heads whose operands are read for TRUTH only -- a boolean coercion there changes nothing
COND_HEADS = {"if", "while", "not", "and", "or", "cond", "switch", "until", "return"}


def hazards(form, parent=None, idx=0, out=None):
    """`(and .. 1)` / `(or .. 1)` forms whose value is consumed as more than a truth."""
    out = [] if out is None else out
    if isinstance(form, list) and form:
        head = str(form[0])
        if head in ("and", "or") and len(form) > 2 and isinstance(form[-1], int):
            ph = str(parent[0]) if isinstance(parent, list) and parent else ""
            # a bare condition slot: `(if <this> ..)`, `(not <this>)`, nested in and/or ...
            in_cond = ph in COND_HEADS
            if not in_cond:
                out.append((ph or "<top>", idx, form))
        for i, sub in enumerate(form):
            hazards(sub, form, i, out)
    return out


def main(argv):
    src, titles = argv[1], argv[2:]
    total = 0
    for t in titles:
        p = os.path.join(src, t + ".sc")
        if not os.path.exists(p):
            print("  [skip] %s (not decompiled)" % t)
            continue
        try:
            forms = read_all(open(p, errors="replace").read())
        except Exception as e:                         # noqa: BLE001 -- unparsable round-trip
            print("  [!!] %s: %s" % (t, e))
            continue
        hits = []
        for f in forms:
            hazards(f, None, 0, hits)
        total += len(hits)
        if hits:
            print("  ⛔ %s: %d value-position boolean coercion(s)" % (t, len(hits)))
            for ph, i, form in hits[:6]:
                print("       under (%s ..) arg %d: %s" % (ph, i, _short(form)))
    read = [t for t in titles if os.path.exists(os.path.join(src, t + ".sc"))]
    if not read:
        # ⛔ NOT A PASS. A scan that read nothing must not print a zero and exit green -- that is
        # the shape of every vacuous check this repo has had to go back and fix.
        print("\n⛔ read NONE of the %d title(s) under %s -- this measured nothing."
              % (len(titles), src))
        return 2
    print("\n%d hazard(s) across %d title(s) read (of %d asked)"
          % (total, len(read), len(titles)))
    return 1 if total else 0


def _short(form, n=90):
    def w(x):
        return "(" + " ".join(w(y) for y in x) + ")" if isinstance(x, list) else str(x)
    s = w(form)
    return s if len(s) <= n else s[:n] + "..."


if __name__ == "__main__":
    sys.exit(main(sys.argv))
