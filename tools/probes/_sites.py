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


ADD = re.compile(r"\(=\s*global9\s+self\)\s*add:|\(global9\s+add:", re.S)


def items(src_dir):
    """index -> inventory instance name, read from the `(global9 add: ...)` KQInv builds.

    Every item number in an emitted guard is `(global9 indexOf: (global69 curInvIcon:))`, i.e. a
    position in THIS list -- so reading the list is the only way to get names that agree with the
    numbers by construction. A hand-typed table drifts, and `KQ5-LITE-TESTPLAN.md` already proved
    it can: it had two items' bits swapped.
    """
    for name in sorted(os.listdir(src_dir)):
        if not name.endswith(".sc"):
            continue
        text = open(os.path.join(src_dir, name), errors="replace").read()
        m = ADD.search(text)
        if not m:
            continue
        # `((= global9 self) add: ...)` -- the receiver is itself a form, so the arg list ends at
        # the close of the form OUTSIDE it, not of the receiver.
        outer = text.rindex("(", 0, m.start()) if text[m.start():m.start() + 2] == "(=" \
            else m.start()
        _, end = _span(text, outer)
        args, i = [], m.end()
        while i < end:
            ch = text[i]
            if ch == "{":
                k = text.find("}", i)
                i = (k if k > 0 else i) + 1
                continue
            if ch == "(":                       # `(Pie cursor: pieCursor yourself:)`
                a, b = _span(text, i)
                w = re.match(r"\(\s*(\w+)", text[a:b])
                if w:
                    args.append(w.group(1))
                i = b
                continue
            if ch == ")":
                break
            w = re.match(r"[A-Za-z_]\w*", text[i:])
            if w:
                args.append(w.group(0))         # a bare name, e.g. `Ok`
                i += w.end()
                continue
            i += 1
        if args:
            return dict(enumerate(args))
    raise RuntimeError("no `global9 add:` inventory list under %s" % src_dir)


SCRIPTNO = re.compile(r"\(script#\s*(\d+)\)")
PRINT = re.compile(r"proc255_0 \{([^}]*)\}")
WARN_HEAD = "(if (== global402 1) (proc255_0 {"
WARN = re.compile(r"\(if \(== global402 1\)\s*\(proc255_0 \{([^}]*)\}\)")
SETSCRIPT = re.compile(r"setScript:\s*(\w+)")


def _enclosing(text, off, want=("(== global402 2)", "(== global402 1)")):
    """The smallest form around text[off] that contains the WHOLE mode test.

    Climbing out to it is what makes a site's sentences derivable. The two emitted shapes put
    the `|=` in different places -- `wrap_forbidden_case` puts it in the else of the mode test
    itself, LA6's retraction puts it in a SECOND `(if (not <allow>) ...)` beside the first -- so
    neither "the form the write is in" nor a fixed nesting depth finds both strings. What both
    have in common is that the enclosing form eventually contains the mode test in full.
    """
    stack, opens = [], []
    i = 0
    while i < len(text) and i <= off:
        ch = text[i]
        if ch == "{":
            k = text.find("}", i)
            i = (k if k > 0 else i) + 1
            continue
        if ch == "(":
            opens.append(i)
        elif ch == ")":
            if opens:
                stack.append((opens.pop(), i + 1))
        i += 1
    for start in reversed(opens):                # innermost enclosing form outward
        _, end = _span(text, start)
        chunk = text[start:end]
        if all(w in chunk for w in want):
            return start, end
    return None


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
        sc = SCRIPTNO.search(text)
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
            # The guard's OWN sentences, read out of the arm rather than transcribed from a
            # test plan -- a plan already had two items' bits swapped. Two facts pin them:
            #   * the REFUSAL is the `proc255_0` string immediately before the bit write. Both
            #     emitted shapes put them side by side (`(proc255_0 {...}) (|= globalN $m)`).
            #   * the WARNING is the string in `(if (== global402 1) (proc255_0 {...}))`, the
            #     lite-mode announcement, which is a distinct spelling and cannot be confused
            #     with the refusal.
            # The search is capped to the smallest form holding BOTH, so a neighbouring guard in
            # the same method cannot lend its sentences to this one.
            span = _enclosing(text, off,
                              want=(WARN_HEAD, "|= %s %s" % (m.group(1), m.group(2))))
            refuse = warn = refuse_via = None
            if span:
                chunk = text[span[0]:span[1]]
                w = WARN.search(chunk)
                warn = w.group(1).strip() if w else None
                # ⛔ The warning's own string must not be mistaken for the refusal. Several
                # guards -- every positional one -- have no refusal string of their own at all,
                # and without this exclusion each of them reported the warning as its refusal,
                # i.e. a row would have looked for the ALLOW sentence on the DENY path.
                wspan = (span[0] + w.start(), span[0] + w.end()) if w else (-1, -1)
                before = [x for x in PRINT.finditer(text[span[0]:off])
                          if not (wspan[0] <= span[0] + x.start() < wspan[1])]
                refuse = before[-1].group(1).strip() if before else None
                if refuse is None:
                    # The refusal can be a whole SCRIPT rather than a print: the positional
                    # guards hold the move and hand the room to `sgTurnBack`, whose state 0 is
                    # the sentence. Follow the setScript: to it.
                    sg = SETSCRIPT.search(chunk)
                    if sg:
                        body = re.search(r"\(instance %s of Script.*?\n\)" % sg.group(1),
                                         text, re.S)
                        if body:
                            pm = PRINT.search(body.group(0))
                            refuse = pm.group(1).strip() if pm else None
                            if refuse:
                                refuse_via = sg.group(1)
            rows.append({"file": name[:-3], "script": int(sc.group(1)) if sc else None,
                         "word": int(m.group(1)[6:]),
                         "mask": int(m.group(2)[1:], 16), "item": item, "owner": owner,
                         "refuse": refuse, "warn": warn, "refuse_via": refuse_via})
    return rows


if __name__ == "__main__":
    import sys
    names = items(sys.argv[1])
    rs = sites(sys.argv[1])
    offers = [r for r in rs if r["item"] is not None]
    print("%d emitted sites; %d are inventory offers" % (len(rs), len(offers)))
    for r in sorted(rs, key=lambda r: (r["word"], r["mask"])):
        print("  %-11s s%-4s g%d $%04x  item=%-3s %-14s %-10s"
              % (r["file"], r["script"], r["word"], r["mask"], r["item"],
                 names.get(r["item"], "-"), r["owner"]))
        print("      refuse=%r%s\n      warn  =%r"
              % (r["refuse"], " (via %s)" % r["refuse_via"] if r["refuse_via"] else "",
                 r["warn"]))


# ---------------------------------------------------------------------------------------------
# What a site's enclosing code demands before the guard can be reached at all.
#
# ⛔ This exists because "click the item on the NPC" is not a row. The bakery's arm sits under a
# message test, an idle-room test AND `(== ((global9 at: 2) owner:) 206)`; the hermit wants two
# other items in hand; the toy shop's ORIGINAL action branches on an item the guard does not.
# Each of those makes a perfectly good offer do nothing, and all of them look identical from
# outside -- and identical to a guard that did not fire.
#
# ⛔ AND POLARITY IS THE WHOLE PROBLEM. The same `(global0 has: 29)` must be TRUE at one site and
# must NOT be forced at another, because at the second it only selects between two spellings of
# the ORIGINAL action -- forcing it there would stop the allow path spending the item, and the
# row would report a broken guard. So the branch the write actually sits in is computed, not
# guessed: for every enclosing `(if ...)`, whether the offset falls before or after that form's
# own `else`.

ELSE = re.compile(r"(?<![A-Za-z0-9_])else(?![A-Za-z0-9_])")
HAS = re.compile(r"^\(global0 has: (\d+)\)$")
OWNER = re.compile(r"^\(== \(\(global9 at: (\d+)\) owner:\) (\w+)\)$")
COUNTER = re.compile(r"^\(== \(\+\+ (global\d+)\) (\d+)\)$")
FLAG = re.compile(r"^\(proc0_12 (\d+)\)$")

# Tests a scripted offer satisfies BY CONSTRUCTION, so they are not preconditions a row has to
# arrange. Reporting them as unhandled buries the two or three that really are.
#   * the event shape -- a real click is type 16384, carries the use icon's message and lands
#     inside the target's nsRect, which is what proc255_5 tests
#   * the mode test itself -- that IS the row's variable
#   * `(global2 script:)` -- settle_room waits the room out before anything is offered
#   * the "is this item one this handler knows" membership test -- arming the item settles it
HARNESS = (re.compile(r"^\(param1 claimed:\)$"),
           re.compile(r"^\((?:==|!=) \(param1 type:\) 16384\)$"),
           re.compile(r"^\(proc255_5 self param1\)$"),
           re.compile(r"^\(== global402 [012]\)$"),
           re.compile(r"^\(and \(== global402 1\) \(& global40[34] \$[0-9a-fA-F]{4}\)\)$"),
           re.compile(r"^\(& global40[34] \$[0-9a-fA-F]{4}\)$"),
           re.compile(r"^\(global2 script:\)$"),
           re.compile(r"^\(proc999_5 \(global9 indexOf: \(global69 curInvIcon:\)\)"),
           re.compile(r"^\(global9 indexOf: \(global69 curInvIcon:\)\)$"))


def _args(text, start, end):
    """The depth-1 sub-forms and bare tokens of the form spanning [start, end)."""
    out, i = [], start + 1
    while i < end - 1:
        ch = text[i]
        if ch == "{":
            k = text.find("}", i)
            i = (k if k > 0 else i) + 1
            continue
        if ch == "(":
            a, b = _span(text, i)
            out.append((a, b))
            i = b
            continue
        m = re.match(r"[^\s()]+", text[i:])
        if m:
            out.append((i, i + m.end()))
            i += m.end()
            continue
        i += 1
    return out


def _top_else(text, start, end):
    """Offsets of this form's own `else` tokens -- depth 1 inside it, not a nested if's."""
    out, depth, i = [], 0, start
    while i < end:
        ch = text[i]
        if ch == "{":
            k = text.find("}", i)
            i = (k if k > 0 else i) + 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 1 and ELSE.match(text, i):
            out.append(i)
        i += 1
    return out


def _needs(text, span, want, out):
    """Reduce a test to atoms we can act on, recording anything we cannot."""
    e = " ".join(text[span[0]:span[1]].split())
    # ⛔ Check this BEFORE decomposing. The mode test is spelled `(and (== global402 1)
    # (& globalN $bit))` and taking it apart first turns the row's own variable into an
    # "unhandled precondition" on every single row, which buries the two that really are.
    if any(h.match(e) for h in HARNESS):
        return
    if e.startswith("(not "):
        inner = _args(text, span[0], span[1])
        if len(inner) == 2:
            return _needs(text, inner[1], not want, out)
    if e.startswith("(and ") or e.startswith("(or "):
        conj = e.startswith("(and ")
        parts = _args(text, span[0], span[1])[1:]
        if conj == want:
            # (and ...) that must hold, or (or ...) that must not: every part is pinned.
            for p in parts:
                _needs(text, p, want, out)
            return
        # (or ...) that must hold: any ONE part does. Take the first we can actually satisfy,
        # and say so -- an `or` silently reduced to its first disjunct is how a probe ends up
        # setting up a state the site never asked for.
        for p in parts:
            trial = []
            _needs(text, p, want, trial)
            if trial and all(k != "?" for k, _, _ in trial):
                out.extend(trial)
                return
        out.append(("?", e, want))
        return
    m = HAS.match(e)
    if m:
        out.append(("has", int(m.group(1)), want))
        return
    m = OWNER.match(e)
    if m:
        out.append(("owner", (int(m.group(1)), m.group(2)), want))
        return
    m = COUNTER.match(e)
    if m:
        # `(if (== (++ global316) 1) <the FIRST time> else <the guard>)`: the lamb is cut in
        # half on the first use and the guard is on every use after it. Wanted false means the
        # counter has already been through once.
        out.append(("counter", (m.group(1), int(m.group(2))), want))
        return
    m = FLAG.match(e)
    if m:
        out.append(("flag", int(m.group(1)), want))
        return
    out.append(("?", e, want))


def requirements(text, off):
    """[(kind, detail, wanted)] for the write at `off`, outermost enclosing test first.

    kind is "has" (detail = item number), "owner" (detail = (item, owner)) or "?" (detail = the
    test verbatim, for anything this does not know how to satisfy -- reported, never dropped).
    """
    opens, i = [], 0
    while i <= off and i < len(text):
        ch = text[i]
        if ch == "{":
            k = text.find("}", i)
            i = (k if k > 0 else i) + 1
            continue
        if ch == "(":
            opens.append(i)
        elif ch == ")" and opens:
            opens.pop()
        i += 1
    out = []
    for start in opens:
        _, end = _span(text, start)
        head = text[start:start + 8]
        kids = _args(text, start, end)
        if head.startswith("(if ") or head.startswith("(if\n"):
            if len(kids) < 2:
                continue
            test = kids[1]
            elses = _top_else(text, start, end)
            in_then = not any(off > e for e in elses)
            _needs(text, test, in_then, out)
        elif head.startswith("(cond"):
            for a, b in kids[1:]:
                if a < off < b:                      # the clause the write is in
                    clause = _args(text, a, b)
                    if clause:
                        _needs(text, clause[0], True, out)
                    break
    # Keep the first opinion about each atom: the outermost enclosing test wins, and a later
    # duplicate cannot quietly flip it.
    seen, uniq = set(), []
    for k, d, w in out:
        key = (k, str(d))
        if key in seen:
            continue
        seen.add(key)
        uniq.append((k, d, w))
    return uniq
