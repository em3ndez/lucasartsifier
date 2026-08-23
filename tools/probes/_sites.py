"""Derive the guard-site table from the EMITTED patch source.

The test plans are hand-written and they drift: `KQ5-LITE-TESTPLAN.md` had LB1 and LB2's items
swapped (bit $0040 is the Lamb and $2000 is the Fish, not the other way round), which a suite
that transcribed the plan would have faithfully reproduced as a pass. So the suite reads the
patched source instead -- the same artifact the game was built from.

    python3 tools/probes/_sites.py <patch_project>/src
"""
import os
import re

BIT = re.compile(r"\|= (global40[34]) (\$[0-9a-fA-F]{4})")
INST = re.compile(r"^\((?:instance|class)\s+(\w+)\s+of\s+(\w+)", re.M)
# The head is spelled across lines in some files, so this cannot be a single-line pattern.
SWITCH = re.compile(r"\(switch\s*\(\s*global9\s+indexOf:\s*\(global69\s+curInvIcon:\)\s*\)", re.S)


def _span(text, i):
    """(start, end) of the balanced form beginning at text[i] == '('. `{...}` is a SCI string."""
    depth = 0
    j = i
    while j < len(text):
        c = text[j]
        if c == "{":
            k = text.find("}", j)
            j = (k if k > 0 else j) + 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i, j + 1
        j += 1
    return i, len(text)


def _arms(text, start, end):
    """The depth-1 numbered arms of a switch: [(label, start, end)]."""
    out, depth, i = [], 0, start
    while i < end:
        c = text[i]
        if c == "{":
            k = text.find("}", i)
            i = (k if k > 0 else i) + 1
            continue
        if c == "(":
            depth += 1
            if depth == 2:
                a, b = _span(text, i)
                m = re.match(r"\(\s*(\d+)\s", text[a:b])
                if m:
                    out.append((int(m.group(1)), a, b))
                i, depth = b, depth - 1
                continue
        elif c == ")":
            depth -= 1
        i += 1
    return out


def sites(src_dir):
    """[{file, word, mask, item, owner}] -- one row per (bit, owner) the patch actually emits.

    `item` is None for the guards that are not inventory offers (the positional and edge ones);
    those need a different kind of probe and are reported so they cannot be silently skipped.
    """
    rows, seen = [], set()
    for name in sorted(os.listdir(src_dir)):
        if not name.endswith(".sc"):
            continue
        text = open(os.path.join(src_dir, name), errors="replace").read()
        if "global403 $" not in text and "global404 $" not in text:
            continue
        heads = [(m.start(), m.group(1)) for m in INST.finditer(text)]
        switches = []
        for m in SWITCH.finditer(text):
            s, e = _span(text, m.start())
            switches.append((s, e, _arms(text, s, e)))
        for m in BIT.finditer(text):
            off = m.start()
            owner = next((n for p, n in reversed(heads) if p < off), "?")
            item = None
            for s, e, aa in switches:
                if s < off < e:
                    for lab, a, b in aa:
                        if a < off < b:
                            item = lab
            key = (name, m.group(1), m.group(2), item, owner)
            if key in seen:
                continue
            seen.add(key)
            rows.append({"file": name[:-3], "word": int(m.group(1)[6:]),
                         "mask": int(m.group(2)[1:], 16), "item": item, "owner": owner})
    return rows


if __name__ == "__main__":
    import sys
    rs = sites(sys.argv[1])
    offers = [r for r in rs if r["item"] is not None]
    print("%d emitted sites; %d are inventory offers" % (len(rs), len(offers)))
    for r in sorted(rs, key=lambda r: (r["word"], r["mask"])):
        print("  %-11s g%d $%04x  item=%-5s %s"
              % (r["file"], r["word"], r["mask"], r["item"], r["owner"]))
