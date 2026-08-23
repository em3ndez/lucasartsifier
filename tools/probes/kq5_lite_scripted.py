# THE KQ5 LITE PLAN, DRIVEN BY SCRIPTED CLICKS -- the whole guard estate, nobody at the keyboard.
#
# For every inventory-offer guard the patch emits: does the FIRST offer refuse and keep the item,
# and does the SECOND warn and spend it? That is the Lite contract, and it is checked as STATE
# (the warn bit, and whether the ego still holds the item) AND as DIALOGUE (the guard's own
# sentence), because either alone can be satisfied by an accident.
#
# ⛔ EVERYTHING HERE IS DERIVED FROM THE EMITTED PATCH SOURCE, never from a test plan.
# `_sites.py` reads the same artifact the game was built from and hands over, per site:
#   * the bit and the file it is written in          -- so no row can be aimed at the wrong guard
#   * the item NUMBER and, from `(global9 add: ...)`, the item's own instance NAME
#   * the object that owns the arm, which is what a click has to land on
#   * the guard's two SENTENCES, read out of the arm
# `docs/KQ5-LITE-TESTPLAN.md` is hand-written and had drifted -- it has the cat's two items'
# bits swapped -- so a suite transcribing it would have reproduced that as a pass.
#
# ⛔ AND THE THREE THINGS THAT MAKE A ROW TRUE RATHER THAN MERELY GREEN:
#
#  1. THE ICON BAR MUST BE DOWN. `IconBar:doit` is a modal loop; while it spins, `Game:doit`
#     never runs, so teleports do not happen and clicks are eaten. The transport's virtual mouse
#     starts in the bar's strip. `_kq5.park_mouse` and every scripted step deal with this.
#  2. THE ROOM MUST BE IDLE. Every market arm sits under `(not (global2 script:))`, and these
#     rooms greet you at length. `_kq5.settle_room` runs the room out before anything is offered;
#     an offer made during a cutscene is dropped in silence and reads as a guard that did not fire.
#  3. THE BOXES MUST ALL BE DISMISSED, AND NO MORE THAN THAT. A guard's message box is
#     `Dialog::doit` polling kGetEvent, so everything after the print is unreached until it goes.
#     `_kq5.drain_boxes` reads `window_list` and presses Return once per box that is OPEN -- the
#     count is measured, never predicted.
#
# Env: KQ5_SRC=<patch_project>/src     where to derive the rows from
#      KQ5_ROWS=bakeShop,rm006         optional: only these files
#      KQ5_BITS=0x0008,0x0100          optional: only these masks
#
#   .venv-x/bin/python tools/sci_console.py --game <COPY> --id kq5 --title Quest \
#       --binary /tmp/scummvm-playtest-build/scummvm --input-script tools/probes/idle.script \
#       --script tools/probes/kq5_lite_scripted.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, goto, here, nsrect, offer_script, settle_room, wait_spent
from _sites import items, requirements, sites

SRC = os.environ.get("KQ5_SRC", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..",
    "build/kq5_patch_guardpicker/patch_project/src"))
MODE_G = 402
FULL, LITE, OFF = 0, 1, 2

# Where each guarded file lives. `rmNNN` is its own number; the town interiors are regions inside
# room 5 (see _kq5.SHOP_REGIONS); script 0's guards ride on the ego and work anywhere.
PLACE = {"Main": None}

def log(*a): print(*a, flush=True)


def _spell(reqs):
    out = []
    for kind, d, want in reqs:
        if kind == "has":
            out.append("%s%s" % ("" if want else "NOT ", NAMES.get(d, d)))
        elif kind == "owner":
            out.append("item %s owned by %s" % (NAMES.get(d[0], d[0]), d[1]))
        elif kind == "counter":
            out.append("%s %s %s" % (d[0], "==" if want else "!=", d[1]))
        elif kind == "flag":
            out.append("%sflag %s" % ("" if want else "NOT ", d))
        else:
            out.append("⚠️%s%s" % ("" if want else "NOT ", d))
    return "; ".join(out) or "(nothing beyond the click)"


def place_of(f):
    if f in PLACE:
        return PLACE[f]
    if f.startswith("rm"):
        return int(f[2:])
    return SCRIPT_OF.get(f)


NAMES = items(SRC)
allrows = sites(SRC)
SCRIPT_OF = {r["file"]: r["script"] for r in allrows}

rows = [r for r in allrows if r["item"] is not None]
only = os.environ.get("KQ5_ROWS")
if only:
    rows = [r for r in rows if r["file"] in set(only.split(","))]
bits = os.environ.get("KQ5_BITS")
if bits:
    want = {int(b, 0) for b in bits.split(",")}
    rows = [r for r in rows if r["mask"] in want]

# ⛔ One row per (file, word, bit). A bit written under two owners is ONE guard -- the toy shop
# writes $0200 from both `toyMaker` and `sled` -- and the contract is "the guard fires once".
# Probe it at the first owner and name the others.
bybit, order = {}, []
for r in rows:
    k = (r["file"], r["word"], r["mask"])
    if k not in bybit:
        bybit[k] = dict(r, owners=[])
        order.append(k)
    bybit[k]["owners"].append(r["owner"])
rows = [bybit[k] for k in order]

# What each site's own enclosing code demands before its guard can be reached. Derived with
# polarity from the emitted arm -- see `_sites.requirements`. ⛔ Not a hand-written setup table:
# the same `(global0 has: 29)` must be forced at no site and left alone at the toy shop, where
# it only picks between two spellings of the ORIGINAL action, and forcing it there would stop
# the allow path spending the item and report a working guard as broken.
BITRE = __import__("re").compile(r"\|= (global40[34]) (\$[0-9a-fA-F]{4})")
for r in rows:
    text = open(os.path.join(SRC, r["file"] + ".sc"), errors="replace").read()
    r["reqs"] = []
    for m in BITRE.finditer(text):
        if int(m.group(1)[6:]) == r["word"] and int(m.group(2)[1:], 16) == r["mask"]:
            r["reqs"] = requirements(text, m.start())
            break
# Visit each place once: room changes are the expensive part, and re-entering replays a welcome.
rows.sort(key=lambda r: (place_of(r["file"]) is None, place_of(r["file"]) or 0, r["mask"]))

log("== %d offer guards derived from %s ==" % (len(rows), os.path.normpath(SRC)))
for r in rows:
    log("   %-11s g%d $%04x  %-14s -> %-20s  place %-4s  needs: %s"
        % (r["file"], r["word"], r["mask"], NAMES.get(r["item"], "?"),
           "/".join(r["owners"]), place_of(r["file"]), _spell(r["reqs"])))

# ⛔ ROWS CONTAMINATE EACH OTHER THROUGH THE WORLD, not just through the room. The bakery's arm
# sits under `(== ((global9 at: 2) owner:) 206)`, so the row that BUYS the pie closes the door on
# the two rows after it -- and the game says so in as many words ("Graham already has a pie and
# is not interested in any other baked goods"), which is the only reason that was legible. The
# toy shop has the same shape with the sled. So each row starts from the ownership the game
# itself set up at boot, restored item by item, rather than from whatever the previous row left.
def owners(c):
    out = {}
    for i, name in sorted(NAMES.items()):
        if i == 0:
            continue                              # index 0 is the Ok button, not an item
        v, _ = c.send("?" + name, "owner")
        if v is not None:
            out[name] = v
    return out


def restore_owners(c, base, log=print):
    moved = []
    for name, want_owner in base.items():
        v, _ = c.send("?" + name, "owner")
        if v is not None and v != want_owner:
            c.cmd("send ?%s owner %d" % (name, want_owner))
            moved.append(name)
    if moved:
        log("  restored the boot ownership of %s" % ", ".join(moved))
    return moved


def apply_reqs(c, ego, reqs, log=print):
    """Make the site's own enclosing tests true. Returns the ones this cannot arrange."""
    unmet = []
    for kind, d, want in reqs:
        if kind == "has":
            c.cmd("send %s %s %d" % (ego, "get" if want else "put", d))
        elif kind == "owner":
            item, owner = d
            if not want or not str(owner).isdigit():
                unmet.append((kind, d, want))
                continue
            # `Ego:put` also clears the cursor if the item is on it; the direct write covers the
            # case where the item is owned by neither the ego nor the room.
            c.cmd("send %s put %d %s" % (ego, item, owner))
            c.cmd("send ?%s owner %s" % (NAMES.get(item, item), owner))
        elif kind == "counter":
            # `(if (== (++ globalN) K) <the FIRST time> else <the guard>)`. The increment runs
            # before the comparison, so leaving the counter at K-1 makes the test TRUE and at K
            # makes it FALSE. The lamb's guard is on every use AFTER the one that halves it.
            g, k = d
            c.setg(int(g[6:]), k - 1 if want else k)
        else:
            unmet.append((kind, d, want))
    if unmet:
        log("  ⚠️ preconditions this suite does not arrange: %s" % _spell(unmet))
    return unmet


log("\n== boot ==")
boot(c, log=log, teleport=True)
ego = c.gaddr(0)
c.watch_text()
BASE_OWNERS = owners(c)
log("  item ownership snapshot: %d items" % len(BASE_OWNERS))

results = []


def attempt(r, target, item, tag):
    """One offer. Returns (said, boxes, bit_set, still_has)."""
    said, at, aim = offer_script(c, target, item, tag, log=log)
    if tag.endswith("a"):
        # ⛔ Disposal is not always inline: the shops take payment inside a Script's changeState,
        # so `has:` sampled once right after the click passes for the inline sites and fails for
        # the deferred ones -- at the same site, in the same run. Poll instead.
        wait_spent(c, ego, r["item"], log=lambda *a: None)
    return (said, aim["boxes"], bool(c.gint(r["word"]) & r["mask"]),
            c.send(ego, "has", r["item"])[0])


for r in rows:
    item = NAMES.get(r["item"], str(r["item"]))
    tag = "%s g%d $%04x %s" % (r["file"], r["word"], r["mask"], item)
    log("\n===== %s  [%s] =====" % (tag, "/".join(r["owners"])))
    want = place_of(r["file"])
    try:
        restore_owners(c, BASE_OWNERS, log=log)
        if want is not None:
            goto(c, want, force=True, log=log)     # re-enter so the room's LOCALS are fresh too
        else:
            settle_room(c, log=log)
        target = ego if want is None and r["owners"][0] == "ego" else "?" + r["owners"][0]
        nsrect(c, target, log=log)          # make it exist and be drawn before anything is aimed
    except Exception as e:                  # noqa: BLE001
        log("  SKIP: %s" % e)
        for l in c.errors():
            log("    game said: %s" % l)
        results.append((tag, "SKIP", str(e)))
        continue

    log("  needs: %s" % _spell(r["reqs"]))
    apply_reqs(c, ego, r["reqs"], log=log)
    c.cmd("send %s get %d" % (ego, r["item"]))     # and the item the row spends
    c.setg(MODE_G, LITE)
    c.setg(r["word"], 0)                           # this site owes a fresh refusal

    try:
        d_said, d_boxes, d_bit, d_has = attempt(r, target, item, "%x_d" % r["mask"])
    except Exception as e:                  # noqa: BLE001
        log("  DENY attempt failed: %s" % e)
        results.append((tag, "SKIP", str(e)))
        continue
    d_text = r["refuse"] and any(r["refuse"] in s for s in d_said)
    log("  DENY : boxes=%d bit=%s has=%s  text=%s  said=%s"
        % (d_boxes, d_bit, d_has, d_text, d_said))
    if not d_bit and not d_text:
        # ⛔ SEPARATE THE TWO FAILURES. An offer that never reached the handler looks exactly
        # like a guard that did not fire, and calling the first the second is how a working
        # guard gets reported broken.
        log("  ⛔ THE OFFER DID NOT LAND -- no guard sentence and no bit. This says NOTHING")
        log("     about the guard. boxes=%d, so the click %s"
            % (d_boxes, "reached SOME handler" if d_boxes else "reached nothing at all"))
        results.append((tag, "NOT REACHED", "boxes=%d said=%s" % (d_boxes, d_said)))
        continue

    try:
        a_said, a_boxes, a_bit, a_has = attempt(r, target, item, "%x_a" % r["mask"])
    except Exception as e:                  # noqa: BLE001
        log("  ALLOW attempt failed: %s" % e)
        results.append((tag, "SKIP", str(e)))
        continue
    a_text = r["warn"] and any(r["warn"] in s for s in a_said)
    log("  ALLOW: boxes=%d bit=%s has=%s  text=%s  said=%s"
        % (a_boxes, a_bit, a_has, a_text, a_said))

    ok = d_bit and d_has == 1 and d_text and a_has == 0 and a_text
    results.append((tag, "PASS" if ok else "FAIL",
                    "deny(bit=%s has=%s text=%s) allow(has=%s text=%s)"
                    % (d_bit, d_has, d_text, a_has, a_text)))

log("\n===================== SUMMARY =====================")
for tag, verdict, note in results:
    log("  %-12s %-38s %s" % (verdict, tag, note))
n = len(rows)
log("\n  %d/%d PASS   %d FAIL   %d NOT REACHED   %d SKIP   (%d rows not reached at all)"
    % (sum(1 for _, v, _ in results if v == "PASS"), n,
       sum(1 for _, v, _ in results if v == "FAIL"),
       sum(1 for _, v, _ in results if v == "NOT REACHED"),
       sum(1 for _, v, _ in results if v == "SKIP"), n - len(results)))
