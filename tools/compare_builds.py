"""Did a COMPILER change do only what it was meant to? Compare two builds of the same source.

    python3 tools/compare_builds.py <decompiled-old>/src <decompiled-new>/src

Build the same game's patch with each compiler, install each into a copy of the game, decompile
both (`tools/sci-tools-fork/build.sh`), and point this at the two `src` trees. It reports every
file whose source differs and whether the difference is EXACTLY the removal of boolean
coercions -- `(and .. 1)` / `(or .. 0)` -- plus, for each one removed, whether its value was
READ (behavioural) or only tested for truth (inert).

⭐ WHY THIS EXISTS. `measure_emitted_bytes` freezes the SOURCE the patcher writes and cannot
see one opcode of what the compiler makes of it -- which is how a value-position `and` came to
yield a boolean, sent `1` where LB2's script 0 passes a CUE TARGET, and silenced every
conversation in the game after its first line (2026-08-21).

⛔ AND IT EXISTS BECAUSE STATIC REASONING KEPT LYING. Three censuses of "which sites move" gave
three different confident answers -- 244, then 1, then 5 -- and only a diff of the real bytes
settled it. Two of the wrong answers came from instruments that AGREED WITH EACH OTHER because
they shared an assumption. Read the bytes.

Two traps this file already fell into, both of which made a CORRECT build look wrong:
  * the coercion is a trailing literal on an n-ary form: `(and A B 1)` as much as `(and A 1)`.
    Matching only the two-operand shape reported nine untouched KQ6 files as unexplained.
  * a trailing literal can be the GAME'S OWN. KQ6 really writes `(or (and ..) 1)` at
    rm880.sc:1330. Stripping one side only deletes it there and not in the other tree. Both
    sides are stripped, and the COUNTS are reported so the removal is still visible.
"""
import sys, os, glob
sys.path.insert(0, "/home/hayati/coding/sierra_softlock/src")
from sexpr import read_all

TRUTH_ONLY = {"if", "while", "not", "and", "or", "cond", "switch", "until"}

def strip(form, parent=None, idx=0, found=None):
    """Return `form` with every `(and X 1)` / `(or X 0)` coercion replaced by X."""
    if not isinstance(form, list) or not form:
        return form
    h = str(form[0])
    # the coercion is a TRAILING literal on an n-ary and/or: `(and A 1)` and `(and A B 1)`
    # are both it. Stripping only the 2-operand form is what made this report "differs by more
    # than coercion removal" on nine KQ6 files that were nothing of the kind.
    if h in ("and", "or") and len(form) >= 3 and isinstance(form[-1], int) and form[-1] in (0, 1):
        ph = str(parent[0]) if isinstance(parent, list) and parent else "<top>"
        found.append((ph, ph in TRUTH_ONLY))
        inner = form[:-1]                      # drop the coercion literal
        if len(inner) == 2:                    # `(and X)` is just X
            return strip(inner[1], parent, idx, found)
        return [strip(x, form, i, found) for i, x in enumerate(inner)]
    return [strip(s, form, i, found) for i, s in enumerate(form)]

old_dir, new_dir = sys.argv[1], sys.argv[2]
tot_ok = tot_bad = 0
read_val = []
for p in sorted(glob.glob(os.path.join(old_dir, "*.sc"))):
    b = os.path.basename(p)
    q = os.path.join(new_dir, b)
    if not os.path.exists(q):
        continue
    a, c = open(p, errors="replace").read(), open(q, errors="replace").read()
    if a == c:
        continue
    try:
        fa, fc = read_all(a), read_all(c)
    except Exception as e:
        print("  [!] %s unparsable: %s" % (b, e)); tot_bad += 1; continue
    # ⛔ STRIP BOTH SIDES. Stripping only the old one also removes literals that are in
    # SIERRA'S OWN SOURCE -- KQ6's rm880 really does write `(or (and ..) 1)` at rm880.sc:1330 --
    # and the old side then failed to match a new side that had correctly kept it.
    found, found_new = [], []
    sa = [strip(f, None, 0, found) for f in fa]
    sc = [strip(f, None, 0, found_new) for f in fc]
    if sa == sc:
        kinds = {}
        removed = len(found) - len(found_new)
        for ph, truth in found[:max(0, removed)] if removed > 0 else []:
            kinds["truth-only" if truth else "VALUE READ (%s)" % ph] = \
                kinds.get("truth-only" if truth else "VALUE READ (%s)" % ph, 0) + 1
        print("  ✔ %-16s equal modulo coercion: old %d, new %d -> %d removed  %s"
              % (b, len(found), len(found_new), removed, kinds))
        read_val += [f for f in found[:max(0, removed)] if not f[1]] if removed > 0 else []
        tot_ok += 1
    else:
        print("  ⛔ %-16s differs by MORE than coercion removal" % b)
        tot_bad += 1
if tot_ok == 0 and tot_bad == 0:
    # ⛔ NOT A PASS. No differing file was read at all -- either the decompiles are missing or
    # the two trees are identical, and those are very different facts. Say which.
    n_old = len(glob.glob(os.path.join(old_dir, "*.sc")))
    n_new = len(glob.glob(os.path.join(new_dir, "*.sc")))
    print("\n⛔ compared NOTHING: %d source(s) in %s, %d in %s" % (n_old, old_dir, n_new, new_dir))
    sys.exit(2)
print("\n%d file(s) explained purely by coercion removal, %d NOT explained" % (tot_ok, tot_bad))
print("coercions whose value was actually READ (behavioural): %d" % len(read_val))
sys.exit(1 if tot_bad else 0)
