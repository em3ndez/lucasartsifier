# THE KQ5 LITE PLAN, DRIVEN BY SCRIPTED CLICKS -- the whole offer estate, nobody at the keyboard.
#
# For every inventory-offer guard the patch emits: does the FIRST offer refuse and keep the item,
# and does the SECOND warn and let it through? That is the Lite contract, and it is checked as
# STATE (the warn bit, whether the ego still holds the item, whether the world moved) AND as
# DIALOGUE (the guard's own sentences), because either alone can be satisfied by an accident.
#
# ⛔ EVERYTHING IS DERIVED FROM THE EMITTED PATCH SOURCE, never from a test plan. `_sites.py`
# reads the same artifact the game was built from and hands over, per site:
#   * the bit, the file, and WHICH METHOD the write sits in -- `handleEvent` is an offer,
#     `doit` is a positional guard that no click can reach and that needs a different probe
#   * the item NUMBER, and from `(global9 add: ...)` the item's own instance NAME
#   * the object a click has to land on -- which is not always the arm's owner: rm032's sled is
#     used ON GRAHAM, and the site says so with `(proc255_5 global0 param1)`
#   * the guard's two SENTENCES
#   * every PRECONDITION, with polarity: the arm's own enclosing conds, plus the conds around
#     the target's `init:` (room 6's cat only exists if Graham carries the shoe or the stick)
# `docs/KQ5-LITE-TESTPLAN.md` is hand-written and had drifted -- it has the cat's two items'
# bits swapped -- so a suite transcribing it would have reproduced that as a pass.
#
# ⛔ AND THE FOUR THINGS THAT MAKE A ROW TRUE RATHER THAN MERELY GREEN:
#
#  1. THE ICON BAR MUST BE DOWN. `IconBar:doit` is a modal loop; while it spins, `Game:doit`
#     never runs, so teleports do not happen and clicks are eaten. The transport's virtual mouse
#     starts inside the bar's strip. `_kq5.park_mouse` deals with it, and `here()` -- global 11,
#     not `c.room()`, which is the room merely ASKED for -- is what proves a teleport landed.
#  2. THE ROOM MUST BE IDLE. Every market arm sits under `(not (global2 script:))`, and these
#     rooms greet you at length. `_kq5.settle_room` runs the room out first; an offer made during
#     a cutscene is dropped in silence and reads exactly like a guard that did not fire.
#  3. THE BOXES MUST ALL BE DISMISSED AND NO MORE. A guard's box is `Dialog::doit` polling
#     kGetEvent, so everything after the print is unreached until it goes. `_kq5.drain_boxes`
#     reads `window_list` and presses Return once per box that IS open -- measured, not predicted.
#  4. ROWS MUST NOT CONTAMINATE EACH OTHER. Buying the pie closes the door on the bakery's other
#     two rows; feeding the cat is remembered in a room local. So item ownership is restored to
#     the boot snapshot and the room is re-entered before every row.
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
from _kq5 import (boot, goto, here, nsrect, offer_script, resolve, settle_room,
                  wait_spent)
from _sites import items, presence, requirements, sites

SRC = os.environ.get("KQ5_SRC", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..",
    "build/kq5_patch_guardpicker/patch_project/src"))
MODE_G = 402
FULL, LITE, OFF = 0, 1, 2
# KQ5 keeps its flags in a bit array based at global 129. `localproc_0` in the emitted Main.sc is
#     (= temp2 (/ flag 16)) (= temp3 (<< $0001 (mod flag 16))) ... [global129 temp2]
# so flag N is bit N%16 of global (129 + N/16), and a flag is readable and writable with `vv g`.
FLAG_BASE = 129

# Script 0's guards ride on the ego and work anywhere; everything else lives in its own script,
# and `_kq5.goto` knows which of those numbers are Regions inside room 5 rather than rooms.
PLACE = {"Main": None}

# ⛔ ONE THING IS NOT DERIVABLE FROM AN ARM: whether the target is ON SCREEN AT ALL. Room 6's cat
# is `init:`ed at x -80 and only crosses the picture during the cat-and-mouse chase, and what
# starts that chase is the room's own `doit`, not any cond around the guard:
#
#     ((and (global5 contains: rat) (> (global0 x:) 290) (> (global0 y:) 142))
#       (User canControl: 0) (global0 setMotion: 0) ... (self setScript: catAndMouse))
#
# So a staging step per room, each quoting the line it satisfies. This is not a declared spec --
# nothing here decides a verdict; it only puts the game where a player would be standing when
# they make the offer. A room with no entry gets none, and a row that then fails to land says so.
STAGE = {
    # rm006: walk Graham to the right-hand edge so the chase begins and the cat is on screen.
    "rm006": lambda c, ego: c.cmd("send %s posn 300 150" % ego),
}

def log(*a): print(*a, flush=True)


def _spell(reqs):
    out = []
    for kind, d, want in reqs:
        if kind == "has":
            out.append("%s%s" % ("" if want else "NOT ", NAMES.get(d, d)))
        elif kind == "owner":
            out.append("item %s %s owned by %s"
                       % (NAMES.get(d[0], d[0]), "is" if want else "is NOT", d[1]))
        elif kind == "counter":
            out.append("%s %s %s" % (d[0], "==" if want else "!=", d[1]))
        elif kind == "flag":
            out.append("%sflag %s" % ("" if want else "NOT ", d))
        elif kind == "global":
            out.append("global%d %s %d" % (d[0], "==" if want else "!=", d[1]))
        elif kind == "detail":
            out.append("detail level %s" % d)
        elif kind == "target":
            out.append("the click lands on the %s" % d)
        else:
            out.append("⚠️%s%s" % ("" if want else "NOT ", d))
    return "; ".join(out) or "(nothing beyond the click)"


NAMES = items(SRC)
allrows = sites(SRC)
SCRIPT_OF = {r["file"]: r["script"] for r in allrows}


def place_of(f):
    if f in PLACE:
        return PLACE[f]
    if f.startswith("rm"):
        return int(f[2:])
    return SCRIPT_OF.get(f)


# ⛔ OFFER ROWS ONLY, and the discriminator is the METHOD, not the owner's name. rm032 writes the
# same bit from `doit` (the ego walking to an edge) and from `handleEvent` (the sled used on the
# ego); only the second is something a click can reach. The positional half of the estate is
# reported here so it cannot be silently skipped, and needs a probe of its own.
offers = [r for r in allrows if r["item"] is not None and r["method"] == "handleEvent"]
elsewhere = [r for r in allrows if not (r["item"] is not None and r["method"] == "handleEvent")]

only = os.environ.get("KQ5_ROWS")
if only:
    offers = [r for r in offers if r["file"] in set(only.split(","))]
bits = os.environ.get("KQ5_BITS")
if bits:
    keep = {int(b, 0) for b in bits.split(",")}
    offers = [r for r in offers if r["mask"] in keep]

# ⛔ One row per (file, word, bit). A bit written under two owners is ONE guard -- the toy shop
# writes $0200 from both `toyMaker` and `sled` -- and the contract is "the guard fires once".
# Probe it at the first owner and name the others.
bybit, order = {}, []
for r in offers:
    k = (r["file"], r["word"], r["mask"])
    if k not in bybit:
        bybit[k] = dict(r, owners=[])
        order.append(k)
    bybit[k]["owners"].append(r["owner"])
rows = [bybit[k] for k in order]

for r in rows:
    text = open(os.path.join(SRC, r["file"] + ".sc"), errors="replace").read()
    # Presence first: it is read by the room's `init`, so it has to be true BEFORE the teleport.
    r["reqs"] = presence(text, r["owners"][0]) + requirements(text, r["off"])
    r["target_ego"] = any(k == "target" and d == "ego" for k, d, _ in r["reqs"])
rows.sort(key=lambda r: (place_of(r["file"]) is None, place_of(r["file"]) or 0, r["mask"]))

log("== %d offer guards derived from %s ==" % (len(rows), os.path.normpath(SRC)))
for r in rows:
    log("   %-11s g%d $%04x  %-14s -> %-18s place %-4s"
        % (r["file"], r["word"], r["mask"], NAMES.get(r["item"], "?"),
           "/".join(r["owners"]), place_of(r["file"])))
    log("        needs: %s" % _spell(r["reqs"]))
log("\n   ⚠️ %d emitted sites are NOT offers and this suite does not cover them -- they are"
    % len(elsewhere))
log("      positional/edge guards that fire on where the ego IS, and need their own probe:")
for r in sorted(elsewhere, key=lambda r: (r["word"], r["mask"])):
    log("        %-11s g%d $%04x  %-9s in %s" % (r["file"], r["word"], r["mask"],
                                                 r["owner"], r["method"]))


# ---- state the rows need arranged ------------------------------------------------------------
_REG = __import__("re").compile(r"Value returned:\s*([0-9a-f]{4}:[0-9a-f]{4})",
                                __import__("re").I)


def _owner(c, name):
    """An item's `owner` as the FULL ssss:oooo the game stores.

    ⛔ NOT `c.send(...)[0]`, which returns the offset alone. An item in Graham's hand is owned by
    the EGO -- an object address -- and writing back only its offset stores a plain integer where
    a reg_t belongs. That is a silent corruption of the ownership store, which is precisely what
    every row here reads and writes."""
    m = _REG.search(c.cmd("send ?%s owner" % name))
    return m.group(1) if m else None


def owners(c):
    """Every inventory item's owner. Index 0 is the Ok button, not an item."""
    out = {}
    for i, name in sorted(NAMES.items()):
        if i == 0:
            continue
        v = _owner(c, name)
        if v is not None:
            out[name] = v
    return out


def restore_owners(c, base, log=print):
    moved = []
    for name, want_owner in base.items():
        if _owner(c, name) != want_owner:
            c.cmd("send ?%s owner %s" % (name, want_owner))
            moved.append(name)
    if moved:
        log("  restored the boot ownership of %s" % ", ".join(moved))
    return moved


def flag(c, n, on):
    """Set or clear KQ5 flag `n`, using `localproc_0`'s own arithmetic (see FLAG_BASE)."""
    g = FLAG_BASE + n // 16
    bit = 1 << (n % 16)
    v = c.gint(g)
    c.setg(g, (v | bit) if on else (v & ~bit & 0xffff))


def apply_reqs(c, ego, reqs, log=print):
    """Make a site's own preconditions true. Returns the ones this cannot arrange."""
    unmet = []
    for kind, d, want in reqs:
        if kind == "has":
            c.cmd("send %s %s %d" % (ego, "get" if want else "put", d))
        elif kind == "owner":
            item, owner = d
            name = NAMES.get(item, item)
            if want:
                if not str(owner).isdigit():
                    unmet.append((kind, d, want))
                    continue
                # `Ego:put` also clears the cursor if the item happens to be on it; the direct
                # write covers the case where the item is owned by neither the ego nor the room.
                c.cmd("send %s put %d %s" % (ego, item, owner))
                c.cmd("send ?%s owner %s" % (name, owner))
            else:
                cur = _owner(c, name)
                if cur is not None and int(cur.split(":")[1], 16) == int(owner):
                    c.cmd("send %s get %d" % (ego, item))     # anywhere but there
        elif kind == "counter":
            # `(if (== (++ globalN) K) <the FIRST time> else <the guard>)`. The increment runs
            # before the comparison, so K-1 makes the test true and K makes it false. The lamb is
            # halved on the first use; its guard is on every use after that.
            g, k = d
            c.setg(int(g[6:]), k - 1 if want else k)
        elif kind == "flag":
            flag(c, d, want)
        elif kind == "global":
            if want:
                c.setg(d[0], d[1])
            else:
                unmet.append((kind, d, want))      # "anything but K" has no single answer
        elif kind == "detail":
            c.cmd("send %s detailLevel %d" % (c.gaddr(1), d))
        elif kind == "target":
            pass                                   # says where to click, not what to arrange
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


def dead(c, e=None):
    """Has the game process gone? Then no later row means anything."""
    return (c.proc is not None and c.proc.poll() is not None) or "Broken pipe" in str(e or "")


def world(c):
    """Enough of the world to tell "the guard let it through" from "nothing happened"."""
    return (here(c), c.send(c.gaddr(2), "script")[0], c.send(ego, "script")[0])


for r in rows:
    item = NAMES.get(r["item"], str(r["item"]))
    tag = "%s g%d $%04x %s" % (r["file"], r["word"], r["mask"], item)
    log("\n===== %s  [%s] =====" % (tag, "/".join(r["owners"])))
    want_place = place_of(r["file"])
    try:
        restore_owners(c, BASE_OWNERS, log=log)
        # ⛔ BEFORE the teleport: half of these are read by the room's own `init` (whether the cat
        # is on screen at all), and arranging them afterwards is too late.
        apply_reqs(c, ego, r["reqs"], log=log)
        c.cmd("send %s get %d" % (ego, r["item"]))
        if want_place is not None:
            goto(c, want_place, force=True, log=log)   # re-enter so the room's LOCALS re-init
        else:
            settle_room(c, log=log)
        apply_reqs(c, ego, r["reqs"], log=lambda *a: None)   # again: entering may have moved it
        c.cmd("send %s get %d" % (ego, r["item"]))
        if r["file"] in STAGE:
            log("  staging %s so the target is on screen (see STAGE)" % r["file"])
            STAGE[r["file"]](c, ego)
            c.resume(4)
        # ⛔ Try every owner of the bit, not just the first. They are alternative places the
        # same offer can be made -- room 6 writes $2000 from both `cat` and `catStrip`, and the
        # cat is only on screen during the chase while catStrip covers the whole picture -- so
        # "the first owner is not clickable" is not the same as "this guard cannot be reached".
        target, why = None, []
        for owner in ([r["owners"][0]] if r["target_ego"] else r["owners"]):
            try:
                cand = ego if r["target_ego"] else resolve(c, owner, r["script"], log=log)
                nsrect(c, cand, log=log)    # make it exist and be drawn before anything is aimed
                target = cand
                break
            except Exception as e:          # noqa: BLE001
                why.append("%s: %s" % (owner, e))
        if target is None:
            raise RuntimeError("; ".join(why))
    except Exception as e:                  # noqa: BLE001
        log("  SKIP: %s" % e)
        for l in c.errors():
            log("    game said: %s" % l)
        if dead(c, e):
            # ⛔ A dead ScummVM is not a row result. When room 46 killed the game, every later
            # row raised "Broken pipe" and was filed as SKIP -- which reads as ten guards that
            # could not be probed, rather than one game that fell over. Room 46 does it every
            # time: `timers::eachElementDo` signature mismatch, shortly after a teleport in.
            log("  ⛔⛔ SCUMMVM IS GONE. Nothing after this can be measured; the run stops.")
            results.append((tag, "GAME DIED", str(e)))
            break
        if "never entered room" in str(e):
            # ⛔ A room that will not accept a teleport does not just fail its own row -- every
            # row after it inherits the wedge and reports the same thing, which reads as a dozen
            # broken guards. Say so once, with evidence, and stop.
            c.shot("/tmp/kq5_wedged.png")
            log("  ⛔⛔ THE GAME IS WEDGED IN ROOM %s. windows=%s  global84=%s"
                % (here(c), c.windows(), c.gint(84)))
            log("      screenshot /tmp/kq5_wedged.png. Everything after this would report the")
            log("      same failure for the same reason, so the run stops here.")
            results.append((tag, "WEDGED", "stuck in room %s" % here(c)))
            break
        results.append((tag, "SKIP", str(e)))
        continue

    c.setg(MODE_G, LITE)
    c.setg(r["word"], 0)                    # this site owes a fresh refusal
    before = world(c)

    try:
        said, at, aim = offer_script(c, target, item, "%x_d" % r["mask"], log=log)
    except Exception as e:                  # noqa: BLE001
        log("  DENY attempt failed: %s" % e)
        results.append((tag, "GAME DIED" if dead(c, e) else "SKIP", str(e)))
        if dead(c, e):
            break
        continue
    d_bit = bool(c.gint(r["word"]) & r["mask"])
    d_has = c.send(ego, "has", r["item"])[0]
    d_text = bool(r["refuse"]) and any(r["refuse"] in s for s in said)
    log("  DENY : boxes=%d bit=%s has=%s text=%s  said=%s"
        % (aim["boxes"], d_bit, d_has, d_text, said))
    if not d_bit and not d_text:
        # ⛔ SEPARATE THE TWO FAILURES. An offer that never reached the handler looks exactly
        # like a guard that did not fire, and calling the first the second is how a working
        # guard gets reported broken.
        log("  ⛔ THE OFFER DID NOT LAND -- no guard sentence and no bit, so this says NOTHING")
        log("     about the guard. %d box(es), i.e. the click %s"
            % (aim["boxes"], "reached SOME handler" if aim["boxes"] else "reached nothing"))
        results.append((tag, "NOT REACHED", "boxes=%d said=%s" % (aim["boxes"], said)))
        continue

    try:
        said, at, aim = offer_script(c, target, item, "%x_a" % r["mask"], log=log)
    except Exception as e:                  # noqa: BLE001
        log("  ALLOW attempt failed: %s" % e)
        results.append((tag, "GAME DIED" if dead(c, e) else "SKIP", str(e)))
        if dead(c, e):
            break
        continue
    # ⛔ Disposal is not always inline: the shops take payment inside a Script's changeState, so
    # `has:` sampled once right after the click passes for the inline sites and fails for the
    # deferred ones -- at the same site, in the same run.
    wait_spent(c, ego, r["item"], log=lambda *a: None)
    a_has = c.send(ego, "has", r["item"])[0]
    a_text = bool(r["warn"]) and any(r["warn"] in s for s in said)
    a_refused = bool(r["refuse"]) and any(r["refuse"] in s for s in said)
    after = world(c)
    # ⛔ NOT EVERY ALLOW PATH SPENDS THE ITEM. rm032's is `(global0 setScript: useSled)` -- the
    # sled is used, not handed over, and Graham leaves the room on it. So what the allow path has
    # to show is that the ORIGINAL ACTION RAN: the item went, or the world moved.
    moved = after != before
    log("  ALLOW: boxes=%d has=%s warned=%s refused-again=%s world %s->%s"
        % (aim["boxes"], a_has, a_text, a_refused, before, after))

    ok = (d_bit and d_has == 1 and d_text
          and a_text and not a_refused and (a_has == 0 or moved))
    results.append((tag, "PASS" if ok else "FAIL",
                    "deny(bit=%s kept=%s said=%s) allow(spent=%s moved=%s said=%s)"
                    % (d_bit, d_has == 1, d_text, a_has == 0, moved, a_text)))

log("\n===================== SUMMARY =====================")
for t, verdict, note in results:
    log("  %-12s %-38s %s" % (verdict, t, note))
n = len(rows)
counts = {v: sum(1 for _, x, _ in results if x == v) for v in
          ("PASS", "FAIL", "NOT REACHED", "SKIP", "WEDGED", "GAME DIED")}
log("\n  %d/%d PASS   %d FAIL   %d NOT REACHED   %d SKIP   %d WEDGED   %d GAME DIED"
    % (counts["PASS"], n, counts["FAIL"], counts["NOT REACHED"], counts["SKIP"],
       counts["WEDGED"], counts["GAME DIED"]))
log("  ⛔ %d row(s) never ran at all -- NOT a pass and NOT a fail." % (n - len(results)))
log("  ⚠️ and %d emitted sites are positional guards this suite does not cover at all."
    % len(elsewhere))
