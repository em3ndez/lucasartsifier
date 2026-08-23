# LA1a/LA1b/LA1c from KQ5-LITE-TESTPLAN, driven from the SCI console.
#
# The point of these three rows is the per-SITE warn bit: the toymaker refuses the needle, the
# heart and the gold coin at THREE INDEPENDENT sites, so being warned at one must not let the
# next through without its own refusal first. The market is the only place that can be checked
# cheaply, and it is the whole reason the bit is per site rather than per guard.
#
# ⛔ 204 is the toy shop's SCRIPT, not a room. It is a Region layered into room 5 and selected by
# global313 -- `room 204` points the game at a `Rgn` and kills it. `goto` knows this; `_rooms.py`
# lists every other script number with the same trap.
#
#   .venv-x/bin/python tools/sci_console.py --game <COPY> --id kq5 --title Quest \
#       --script tools/probes/kq5_toymaker.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kq5 import boot, goto, game_event, nsrect, offer, wait_spent, SHOP_ROOM

SHOP_SCRIPT, MODE_G, WARN_G = 204, 402, 403
SITES = [("Golden_Needle", 3, 0x0200), ("Heart", 9, 0x1000), ("Gold_Coin", 11, 0x0010)]
if os.environ.get("KQ5_SITES"):                    # e.g. KQ5_SITES=Heart for a quick re-check
    keep = set(os.environ["KQ5_SITES"].split(","))
    SITES = [t for t in SITES if t[0] in keep]
REFUSE = "Better not"
WARNED = "You have been warned!"

def log(*a): print(*a, flush=True)

log("== boot ==")
boot(c, log=log)

ego = c.gaddr(0)
for _, num, _bit in SITES:
    c.cmd("send %s get %d" % (ego, num))
c.setg(MODE_G, 1)                                  # LITE
c.setg(WARN_G, 0)                                  # all three sites owe a fresh refusal
c.watch_text()
log("mode=%d warn=%#06x" % (c.gint(MODE_G), c.gint(WARN_G)))

EVENT = game_event(c)
log("using %s as the event" % EVENT)

got = goto(c, SHOP_SCRIPT, log=log)
if got != SHOP_ROOM:
    c.shot("/tmp/kq5_not_in_shop.png")
    raise SystemExit("expected room %d, landed in %s -- /tmp/kq5_not_in_shop.png"
                     % (SHOP_ROOM, got))

box = nsrect(c, "?toyMaker", log=log)
log("toyMaker box: %s" % box)

ok = True
for item, num, bit in SITES:
    log("\n===== %s (item %d, bit %#06x) =====" % (item, num, bit))
    for attempt in (1, 2):
        said, _aim, claimed = offer(c, EVENT, "?toyMaker", item)
        set_bit = bool(c.gint(WARN_G) & bit)
        # attempt 1 refuses: bit set, item KEPT. attempt 2 warns and lets it go: item spent --
        # but the toymaker's disposal is DEFERRED into getSled's changeState, so the second
        # attempt has to be polled, not sampled.
        want_has, want_msg = (1, REFUSE) if attempt == 1 else (0, WARNED)
        if attempt == 2:
            wait_spent(c, ego, num, log=log)
        has = c.send(ego, "has", num)[0]
        good = set_bit and has == want_has
        log("  attempt %d: bit=%s has(%d)=%s (want %d) -> %s"
            % (attempt, set_bit, num, has, want_has, "OK" if good else "WRONG"))
        log("    text channel (informational): %r ; looking for %r" % (said, want_msg))
        ok = ok and good
    # ⭐ The independence check: after finishing this site, the OTHERS must still be unwarned.
    others = [(i, b) for i, _n, b in SITES if i != item]
    log("  warn word now %#06x; other sites: %s"
        % (c.gint(WARN_G), {i: bool(c.gint(WARN_G) & b) for i, b in others}))

log("\n=== LA1a/b/c state contract: %s ===" % ("PASS" if ok else "FAIL"))
log("    final warn word %#06x (all three bits = 0x1210)" % c.gint(WARN_G))
