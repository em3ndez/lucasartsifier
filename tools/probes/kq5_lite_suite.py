# The KQ5 LITE plan, checked by machine: for each guard site, does the FIRST attempt refuse and
# keep the item, and the SECOND go through and spend it?
#
# ⛔ The rows are DERIVED from the emitted patch source (`_sites.py`), not transcribed from
# `docs/KQ5-LITE-TESTPLAN.md`. The plan is hand-written and it had drifted: its LB1/LB2 rows have
# the cat's two items swapped (bit $0040 is the Lamb, $2000 is the Fish). A suite built from the
# plan would have reproduced that as a pass.
#
#   .venv-x/bin/python tools/sci_console.py --game <COPY> --id kq5 --title Quest \
#       --script tools/probes/kq5_lite_suite.py
#
# Env: KQ5_SRC=<patch_project>/src   (where to derive the rows from)
#      KQ5_ROWS=toyShop,bakeShop     (optional: only these files)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, goto, game_event, nsrect, offer, wait_spent, SHOP_ROOM
from _sites import sites

SRC = os.environ.get("KQ5_SRC", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..",
    "build/kq5_patch_guardpicker/patch_project/src"))
MODE_G = 402

# Where each guarded file lives. `rmNNN` is its own number; the town interiors are regions in
# room 5 (see _kq5.SHOP_REGIONS); script 0's guards are on the ego and work anywhere.
PLACE = {"toyShop": 204, "tailorShop": 203, "shoeShop": 205, "bakeShop": 206, "Main": None}

# Items by number, for readable output only.
NAMES = {2: "Pie", 3: "Golden_Needle", 5: "Fish", 9: "Heart", 11: "Gold_Coin", 19: "Leg_of_Lamb",
         20: "Rope", 23: "Shell", 29: "Sled"}

def log(*a): print(*a, flush=True)

def place_of(f):
    if f in PLACE:
        return PLACE[f]
    if f.startswith("rm"):
        return int(f[2:])
    return None

rows = [r for r in sites(SRC) if r["item"] is not None]
only = os.environ.get("KQ5_ROWS")
if only:
    keep = set(only.split(","))
    rows = [r for r in rows if r["file"] in keep]
# One row per (file, bit): a bit shared by two owners is ONE guard, and the plan's own rule is
# "every guard fires once". Probe it at the first owner and say which others share it.
bybit, order = {}, []
for r in rows:
    k = (r["file"], r["word"], r["mask"])
    if k not in bybit:
        bybit[k] = dict(r, owners=[])
        order.append(k)
    bybit[k]["owners"].append(r["owner"])
rows = [bybit[k] for k in order]
# Cheapest first: group by place so the suite changes rooms as little as it can.
rows.sort(key=lambda r: (place_of(r["file"]) is None, place_of(r["file"]) or 0))

log("== %d guard sites derived from %s ==" % (len(rows), os.path.normpath(SRC)))
for r in rows:
    log("   %-11s g%d $%04x  item %-3s %-14s %s"
        % (r["file"], r["word"], r["mask"], r["item"],
           NAMES.get(r["item"], "?"), "/".join(r["owners"])))

log("\n== boot ==")
boot(c, log=log)
ego = c.gaddr(0)
c.setg(MODE_G, 1)                                  # LITE
c.watch_text()
EV = game_event(c)                                 # a PERMANENT Event -- never a clone
log("using %s as the event, ego %s" % (EV, ego))

here, aim, results = c.room(), None, []
for r in rows:
    tag = "%s g%d $%04x %s" % (r["file"], r["word"], r["mask"], NAMES.get(r["item"], r["item"]))
    log("\n===== %s  [%s] =====" % (tag, "/".join(r["owners"])))
    want_room = place_of(r["file"])
    try:
        if want_room is not None:
            got = goto(c, want_room, log=log)
            expect = SHOP_ROOM if want_room in (203, 204, 205) else want_room
            if got != expect:
                log("  SKIP: wanted room %s, landed in %s" % (expect, got))
                results.append((tag, "skip: room %s" % got)); continue
            here = got
        target = "?" + r["owners"][0]
        nsrect(c, target, log=log)                  # wait for it to be drawn; offer re-reads it
    except Exception as e:                          # noqa: BLE001
        log("  SKIP: %s" % e)
        for l in c.errors():
            log("    game said: %s" % l)
        results.append((tag, "skip: %s" % e)); continue

    c.setg(r["word"], 0)                            # this site owes a fresh refusal
    c.cmd("send %s get %d" % (ego, r["item"]))      # and the item to spend
    ok = True
    for attempt in (1, 2):
        try:
            said, aim, claimed = offer(c, EV, target,
                                       NAMES.get(r["item"], str(r["item"])), log=log)
        except Exception as e:                      # noqa: BLE001
            log("  attempt %d FAILED: %s" % (attempt, e))
            for l in c.errors():
                log("    game said: %s" % l)
            ok = False; break
        bit = bool(c.gint(r["word"]) & r["mask"])
        if attempt == 2:
            wait_spent(c, ego, r["item"], log=log)  # disposal is sometimes deferred into a Script
        has = c.send(ego, "has", r["item"])[0]
        want_has = 1 if attempt == 1 else 0
        good = bit and has == want_has
        note = ("   ⚠ claimed=0 AND the bit did not move: the handler never saw this event "
                "(aim/box?)" if not claimed and not bit else "")
        log("  attempt %d: bit=%s has(%d)=%s (want %d) -> %s%s   said=%r"
            % (attempt, bit, r["item"], has, want_has,
               "OK" if good else "WRONG", note, said))
        ok = ok and good
    results.append((tag, "PASS" if ok else "FAIL"))

log("\n===================== SUMMARY =====================")
for tag, verdict in results:
    log("  %-8s %s" % (verdict.split(":")[0].upper(), tag) if verdict.startswith("skip")
        else "  %-8s %s" % (verdict, tag))
n_pass = sum(1 for _, v in results if v == "PASS")
log("\n  %d/%d rows PASS, %d not reached" % (n_pass, len(rows), len(rows) - len(results)))
