"""Rebuild a missing `vocab.997` for a game that shipped without selector NAMES.

    python3 tools/reconstruct_selector_vocab.py <nameless.ir.json> <named.ir.json> <out.VOC>

WHY THIS EXISTS. Selector names are a development artifact -- the interpreter dispatches on
NUMBERS and never reads the strings -- so Sierra shipped releases without vocab 997 at all.
ScummVM names LB2 FLOPPY as one, beside several demos (`guest_additions.cpp`, and a
`// HACK for LB2 floppy` in `static_selectors.cpp`). This analyzer cannot work on such a game:
every anchor it has IS a selector name -- `restart:`/`restore:` is death, `newRoom:` is movement,
`has:`/`put:`/`owner` is the item store -- so a nameless IR fails at the first derivation with
"could not derive a death signal", which reads like a fact about the GAME and is not.

⛔ THE TABLE CANNOT BE BORROWED WHOLE FROM ANOTHER BUILD. Numbers are assigned at build time, so
they drift between releases of the SAME GAME: LB2's `doVerb` is 285 on CD and 300 on floppy,
`newRoom` 387 vs 399. Dropping the CD's table on the floppy renames `doVerb` to `stopUpd` and
`newRoom` to `east` -- confidently wrong, which is worse than unnamed. (ScummVM hit the same
trap from the other side: the French PointSoft release of Torin's Passage carries a table that
disagrees with the US one.) Measured live: feeding the floppy's reconstructed table to the LB2
DEMO breaks the decompiler outright, because the demo is a third numbering again.

HOW IT IS DERIVED. Two builds of one game share object names and object shapes, so an object
present in both, with the same method count, has its methods in the same order -- and the same
for its property list. Each aligned pair is one VOTE of "their number means this name". Across
~2,300 objects that is thousands of votes per common selector, and a name is taken only on a
strong majority. Nothing is invented: a selector with no evidence stays `BAD SELECTOR`, exactly
as unused slots do in a real table.

⭐ AND THE ENGINE RANGE IS NOT VOTED ON. Selectors 0-108 are the interpreter's own and are
pinned from ScummVM's static table (`static_selectors.cpp`), which is authoritative there --
`restart` 101, `restore` 76, `doit` 57 -- along with its SCI1.1 remaps and the 4096+
pseudo-selectors. Voting could only corrupt them.

VALIDATION, and it is not optional. The tool prints the method-name histogram beside the named
build's. A correct table reproduces its SHAPE: for LB2 floppy vs CD, doVerb 458/463,
changeState 435/440, init 389/422, newRoom 34/34 -- the small deficits being the 34 scripts the
floppy does not have. A WRONG table shows zeros in that column. Then run the pipeline: LB2
floppy came out at 78 rooms / 95 registers against the CD's 78 / 95.

USING THE RESULT: drop it in the game directory as `997.VOC`. SCI reads a loose `<number>.<ext>`
patch file in preference to the mapped resource, which is the same mechanism Sierra's own
shipped `.SCR` patches use. Verified by generating a `997.VOC` from a game's OWN table and
re-decompiling: the IR comes back identical apart from the game-name field.
"""
import collections
import json
import os
import re
import struct
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STATIC = os.path.join(_ROOT, "tools", "scummvm-ref", "engines", "sci", "engine",
                       "static_selectors.cpp")
BAD = "BAD SELECTOR"
MIN_VOTES, MIN_SHARE = 3, 0.8


def engine_table():
    """Selectors 0-108 plus the SCI1.1 remaps, from ScummVM's own static tables."""
    src = open(_STATIC).read()

    def arr(name):
        m = re.search(r"static const char \* const %s\[\] = \{(.*?)\};" % name, src, re.S)
        if not m:
            raise SystemExit("cannot read %s from %s" % (name, _STATIC))
        return re.findall(r'"([^"]*)"', re.sub(r"//[^\n]*", "", m.group(1)))

    names = arr("sci0Selectors") + arr("sci1Selectors") + arr("sci11Selectors")
    remap = {int(slot): nm for lo, hi, nm, slot in re.findall(
        r'\{\s*(SCI_VERSION_[\w]+),\s*(SCI_VERSION_[\w]+),\s*"([^"]+)",\s*(\d+)\s*\}', src)
        if "1_1" in lo or "1_1" in hi or "2_1" in hi}
    return names, remap


def _selectors(node, out=None):
    """Every `Selector` node in a function body, in source order: `[(name, number), ...]`.

    A send is `{"t": "Selector", "name": ..., "value": <number>}`; two builds of one method emit
    them in the same order, so the lists zip when they are the same length."""
    if out is None:
        out = []
    if isinstance(node, dict):
        if node.get("t") == "Selector":
            out.append((node.get("name"), node.get("value")))
        for v in node.values():
            _selectors(v, out)
    elif isinstance(node, list):
        for v in node:
            _selectors(v, out)
    return out


def vote(nameless, named):
    """`{selector number: Counter(name)}` from objects that align in both builds."""
    by_num = {s["number"]: s for s in nameless["scripts"]}
    votes = collections.defaultdict(collections.Counter)
    aligned = 0
    for s in named["scripts"]:
        other = by_num.get(s["number"])
        if not other:
            continue
        theirs = {o["name"]: o for o in other["objects"]}
        for o in s["objects"]:
            p = theirs.get(o["name"])
            if not p or not o["name"]:
                continue
            # equal LENGTH is the alignment test: same object, same shape, same order
            if len(p["methods"]) == len(o["methods"]):
                aligned += 1
                for a, b in zip(o["methods"], p["methods"]):
                    votes[b["sel"]].update([a["name"]])
                    # ⭐ AND THE SENDS INSIDE THE BODY. The item store is send-only --
                    # `has:`, `put:`, `get:`, `indexOf:` never appear in a method table or a
                    # property list, so voting on those two alone leaves the analyzer's whole
                    # inventory model unnamed and it finds almost nothing (LB2 floppy: 2
                    # softlocks against the CD's 10, until this was added).
                    sa, sb = _selectors(a["ast"]), _selectors(b["ast"])
                    if len(sa) == len(sb):
                        for x, y in zip(sa, sb):
                            votes[y[1]].update([x[0]])
            if len(p["properties"]) == len(o["properties"]):
                for a, b in zip(o["properties"], p["properties"]):
                    votes[b["sel"]].update([a["name"]])
    return votes, aligned


def build(votes):
    names, remap = engine_table()
    top = max(list(votes) + [len(names) - 1] + list(remap))
    table = [BAD] * (top + 1)
    strong = weak = 0
    for n, c in votes.items():
        nm, k = c.most_common(1)[0]
        if k >= MIN_VOTES and k / sum(c.values()) >= MIN_SHARE:
            table[n] = nm
            strong += 1
        else:
            weak += 1
    for i, nm in enumerate(names):                 # the engine range is never voted on
        if nm:
            table[i] = nm
    for n, nm in remap.items():
        if n <= top:
            table[n] = nm
    return table, strong, weak


def encode(table):
    """Sierra's vocab.997 layout, wrapped as an SCI patch file (0x80|6 = Vocab, no extra header).

    `[0]` count-1 (the table is off by one, as ScummVM notes), then one absolute uint16 offset
    per selector, each pointing at a uint16 length followed by the name. Unused slots share one
    `BAD SELECTOR` string, which is what the originals do."""
    head = 2 + len(table) * 2
    blob, offsets, seen = bytearray(), [], {}

    def put(s):
        if s not in seen:
            seen[s] = head + len(blob)
            blob.extend(struct.pack("<H", len(s)))
            blob.extend(s.encode("latin-1"))
        return seen[s]

    put(BAD)                                        # first string, as in a real table
    for s in table:
        offsets.append(put(s or BAD))
    out = bytearray(struct.pack("<H", len(table) - 1))
    for o in offsets:
        out.extend(struct.pack("<H", o))
    out.extend(blob)
    return bytes([0x86, 0x00]) + bytes(out)


def histogram(ir, table=None):
    c = collections.Counter()
    for s in ir["scripts"]:
        for o in s["objects"]:
            for m in o["methods"]:
                c[m["name"] if table is None
                  else (table[m["sel"]] if m["sel"] < len(table) else BAD)] += 1
    return c


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__.strip().splitlines()[2].strip())
    nameless = json.load(open(sys.argv[1]))
    named = json.load(open(sys.argv[2]))
    if nameless["selectors"]:
        print("note: %s already has %d selector names"
              % (sys.argv[1], len(nameless["selectors"])))
    votes, aligned = vote(nameless, named)
    table, strong, weak = build(votes)
    print("aligned %d objects; %d selectors voted, %d too weak to name" % (aligned, strong, weak))
    print("table: %d slots, %d named" % (len(table), sum(1 for s in table if s != BAD)))

    ref, got = histogram(named), histogram(nameless, table)
    print("\n⭐ VALIDATE THE SHAPE -- a wrong table shows zeros in the right-hand column")
    print("   %-14s %8s %8s" % ("selector", "named", "rebuilt"))
    for k in ("doVerb", "changeState", "init", "doit", "dispose", "cue", "handleEvent",
              "newRoom"):
        print("   %-14s %8d %8d" % (k, ref[k], got[k]))
    left = sum(v for k, v in got.items() if k == BAD)
    print("   %d of %d methods still unnamed" % (left, sum(got.values())))

    open(sys.argv[3], "wb").write(encode(table))
    print("\nwrote %s -- drop it in the game directory as 997.VOC" % sys.argv[3])


if __name__ == "__main__":
    main()
