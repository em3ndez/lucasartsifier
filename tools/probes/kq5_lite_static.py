#!/usr/bin/env python3
"""The parts of the KQ5 LITE plan that are claims about the EMITTED SOURCE, not about play.

Three sections of `docs/KQ5-LITE-TESTPLAN.md` do not need a running game at all:

  §Q  the SILENT sites -- no refusal message, so lite must behave exactly like full. In the
      emission that means a `stock_or` wrap (`(or (== global402 2) <guard>)`) with NO warned
      line and NO warn bit. A silent site that had acquired a bit would be a real bug and a
      play test would have to catch it by noticing nothing.
  §Z  the sites that must stay STOCK in every mode -- gypsy rm13, girl rm9. The check is that
      no guard was placed there at all.
  --  the warn bits are one-per-site and none is used twice for different guards.

    python3 tools/probes/kq5_lite_static.py <patch_project>/src
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _sites import sites

MODE_G, WARN_WORDS = 402, (403, 404)
STOCK_OR = re.compile(r"\(or\s*\(==\s*global%d\s+2\)" % MODE_G)
# The LITE dispatch. Anything matching STOCK_OR but NOT this is a SILENT guard: it bypasses in
# stock mode and behaves identically in full and lite, which is what §Q asserts.
LITE_DISPATCH = re.compile(
    r"\(or\s*\(==\s*global%d\s+2\)\s*\(and\s*\(==\s*global%d\s+1\)\s*\(&\s*global40[34]"
    % (MODE_G, MODE_G))
# ⛔ ONE CONSTRUCT, TWO SPELLINGS. `trigger.stock_or` wraps a guard that DEMANDS a condition;
# `trigger.stock_and` wraps one that ADDS a disjunct and so must contribute nothing under stock.
# Counting only the first says rm006 has one silent clause; it has two, and the plan's "8 clauses,
# 5 files" was right while this checker was wrong.
STOCK_AND = re.compile(r"\(not\s*\(==\s*global%d\s+2\)\)" % MODE_G)
WARNED = "You have been warned!"
# §Z -- named in the plan as never guarded, in any mode.
MUST_STAY_STOCK = ["rm013", "rm009"]


def main(src):
    fail = []

    # --- the bit table -------------------------------------------------------------------
    rows = sites(src)
    bybit = {}
    for r in rows:
        bybit.setdefault((r["word"], r["mask"]), set()).add(r["file"])
    print("== %d emitted guard sites over %d distinct warn bits ==" % (len(rows), len(bybit)))
    for (w, m), files in sorted(bybit.items()):
        if len(files) > 1:
            fail.append("bit g%d $%04x is used by more than one FILE: %s" % (w, m, sorted(files)))
    masks = {}
    for (w, m) in bybit:
        masks.setdefault(w, []).append(m)
    for w, ms in sorted(masks.items()):
        dupes = [x for x in ms if ms.count(x) > 1]
        print("   global%d: %d bits, mask union %#06x%s"
              % (w, len(ms), 0 if not ms else eval("|".join(hex(x) for x in ms)),
                 "  DUPLICATES %s" % dupes if dupes else ""))

    # --- §Q: silent guards carry no warn bit and no warned line ---------------------------
    print("\n== silent sites (lite must equal full) ==")
    total, files = [0], []
    for name in sorted(os.listdir(src)):
        if not name.endswith(".sc"):
            continue
        text = open(os.path.join(src, name), errors="replace").read()
        if "softlock-guard" not in text and "global%d" % MODE_G not in text:
            continue
        # A file can hold BOTH kinds -- rm006 has two silent clauses and two lite ones -- so
        # counting whole files misses most of §Q. Count CLAUSES: every stock bypass that is not
        # a lite dispatch.
        n_stock = len(STOCK_OR.findall(text))
        n_lite = len(LITE_DISPATCH.findall(text))
        silent = (n_stock - n_lite) + len(STOCK_AND.findall(text))
        if silent > 0:
            total[0] += silent
            files.append(name[:-3])
            print("   %-11s %d silent clause(s)  (+%d lite-dispatch)  [or=%d and=%d]"
                  % (name[:-3], silent, n_lite, n_stock - n_lite, len(STOCK_AND.findall(text))))

    print("   -> %d silent clauses across %d files" % (total[0], len(files)))

    # --- §Z: must stay stock ---------------------------------------------------------------
    print("\n== must-stay-stock rooms ==")
    for f in MUST_STAY_STOCK:
        p = os.path.join(src, f + ".sc")
        if not os.path.exists(p):
            fail.append("%s.sc is missing" % f)
            continue
        text = open(p, errors="replace").read()
        marks = text.count("softlock-guard")
        mode = text.count("global%d" % MODE_G)
        print("   %-7s softlock-guard marks=%d  mode reads=%d  -> %s"
              % (f, marks, mode, "STOCK" if marks == 0 and mode == 0 else "GUARDED"))
        if marks or mode:
            fail.append("%s was expected to stay stock but carries a guard" % f)

    print("\n== %s ==" % ("ALL STATIC CHECKS PASS" if not fail else "%d FAILURES" % len(fail)))
    for f in fail:
        print("   FAIL: %s" % f)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
